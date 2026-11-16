#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Role-based project runner: requirements file -> project workspace -> role records."""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from .config import ROOT, data_dir, load_config, load_schema
from .judge.backend import parse_json_object
from .knowledge import HybridRetriever
from .models.router import ModelRouter
from .prompts import load_prompt


@dataclass(frozen=True)
class RoleSpec:
    role: str
    title: str
    scope: tuple[str, ...]
    instruction: str


ROLE_SPECS: list[RoleSpec] = [
    RoleSpec("pm", "项目计划与切片",
             ("docs/plan/", "artifacts/pm/"),
             "输出项目目标、功能切片、依赖顺序、门禁与角色分工；写 docs/plan/project-plan.md。"),
    RoleSpec("product", "产品基准",
             ("docs/product/", "artifacts/product/"),
             "输出产品定位、功能清单、非目标、验收标准、用户场景；写 docs/product/product-baseline.md。"),
    RoleSpec("ui", "UI/UX 设计规范",
             ("docs/design/", "artifacts/ui/"),
             "输出信息架构、交互状态、设计 token、深浅色与可访问性要求；写 docs/design/ui-spec.md。"),
    RoleSpec("arch", "架构与契约",
             ("docs/architecture/", "contracts/", "artifacts/arch/"),
             "输出分层、状态机、接口契约、错误码、不变量；写 docs/architecture/architecture.md 与 contracts/openapi.yaml。"),
    RoleSpec("backend", "后端实现",
             ("src/backend/", "artifacts/backend/"),
             "按契约实现接口、参数校验、错误处理、日志与单测；需要写代码时用 files 写 src/backend/**。"),
    RoleSpec("frontend", "前端实现",
             ("src/frontend/", "artifacts/frontend/"),
             "按设计稿与契约实现页面、加载/空/错误状态、可访问性；需要写代码时用 files 写 src/frontend/**。"),
    RoleSpec("review", "代码评审",
             ("docs/reviews/", "artifacts/review/"),
             "只输出 findings、证据引用与整改方向，不判定门禁通过；写 docs/reviews/review.md。"),
    RoleSpec("qa", "测试计划与用例",
             ("tests/", "docs/qa/", "artifacts/qa/"),
             "覆盖正常/异常/边界/权限场景，给出可执行用例和证据要求；写 tests/test-plan.md。"),
    RoleSpec("security", "安全与合规",
             ("docs/security/", "artifacts/security/"),
             "输出威胁模型、高风险项、缓解措施与验证方式；写 docs/security/threat-model.md。"),
    RoleSpec("ops", "发布与回滚",
             ("docs/ops/", "scripts/", "artifacts/ops/"),
             "输出构建、灰度、监控、回滚与演练方案；写 docs/ops/release-plan.md。"),
    RoleSpec("kb", "知识沉淀",
             ("knowledge/", "artifacts/kb/"),
             "把本次需求的可复用资产、决策、踩坑与失效条件写成知识条目；写 knowledge/project-notes.md。"),
    RoleSpec("retro", "复盘与改进",
             ("docs/retro/", "artifacts/retro/"),
             "输出时间线、偏差、根因、行动项（owner/deadline/verification）；写 docs/retro/retro.md。"),
]

ROLE_MAP = {r.role: r for r in ROLE_SPECS}
CODE_ROLES = {"backend", "frontend"}


class ProjectRunner:
    def __init__(self, *, requirements: str | Path, project_dir: str | Path,
                 cfg: dict[str, Any] | None = None, offline: bool = True,
                 roles: list[str] | None = None, use_kb: bool = False,
                 stop_on_error: bool = False, extra_note: str = "",
                 merge_state: bool = False) -> None:
        self.requirements_path = Path(requirements)
        if not self.requirements_path.exists():
            raise FileNotFoundError(f"需求文件不存在：{self.requirements_path}")
        self.project_dir = Path(project_dir).resolve()
        self.cfg = cfg or load_config()
        self.offline = offline
        self.roles = roles or [r.role for r in ROLE_SPECS]
        unknown = [r for r in self.roles if r not in ROLE_MAP]
        if unknown:
            raise ValueError(f"未知角色：{unknown}")
        self.use_kb = use_kb
        self.stop_on_error = stop_on_error
        self.extra_note = extra_note
        self.merge_state = merge_state
        self.router = ModelRouter(self.cfg, offline=offline)
        self.schema = load_schema("agent-output.schema.json")
        self.log_path = self.project_dir / "logs" / "events.jsonl"
        self.state_path = self.project_dir / "state" / "roles.json"
        self.requirement_text = self.requirements_path.read_text(encoding="utf-8")

    # ---------- workspace ----------
    def prepare(self) -> None:
        for d in ("requirements", "artifacts", "logs", "state", "docs",
                  "src", "tests", "contracts", "knowledge"):
            (self.project_dir / d).mkdir(parents=True, exist_ok=True)
        target = self.project_dir / "requirements" / "input.md"
        if self.requirements_path.resolve() != target.resolve():
            shutil.copyfile(self.requirements_path, target)
        meta_path = self.project_dir / "project.json"
        previous: dict[str, Any] = {}
        if meta_path.exists():
            try:
                previous = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                previous = {}
        project_roles = sorted(set(previous.get("roles") or []) | set(self.roles))
        project = {
            "project_id": self.project_dir.name,
            "created_at": previous.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "requirement": str(target.relative_to(self.project_dir)),
            "offline": self.offline,
            "roles": project_roles,
            "status": "running",
        }
        (self.project_dir / "project.json").write_text(
            json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def log(self, event: str, **payload) -> None:
        rec = {"ts": time.time(), "clock": time.strftime("%H:%M:%S"), "event": event, **payload}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------- context ----------
    def kb_context(self) -> str:
        if not self.use_kb:
            return ""
        db = data_dir(self.cfg) / "knowledge.db"
        if not db.exists():
            self.log("kb.skipped", reason="knowledge.db not found")
            return ""
        try:
            r = HybridRetriever(db, self.cfg)
            query = self.requirement_text[:400]
            hits = r.search(query, top_k=3)
            lines = []
            for h in hits:
                if "citation" in h:
                    lines.append(f"- {h['citation']}: {h['text'][:240].replace(chr(10), ' ')}")
            self.log("kb.context", hits=len(lines))
            return "\n".join(lines)
        except Exception as exc:
            self.log("kb.error", error=str(exc)[:300])
            return ""

    def user_message(self, spec: RoleSpec, prior: list[str], kb: str) -> str:
        scope = ", ".join(spec.scope)
        return f"""# 项目需求
{self.requirement_text}

# 当前角色
{spec.role} · {spec.title}
{spec.instruction}

# 前置产物摘要
{chr(10).join(prior) if prior else "（首个角色，无前置产物）"}

# 知识库引用
{kb or "（未启用或无命中）"}

# 调整要求
{self.extra_note or "（无特别调整）"}

# 输出要求
只输出符合 `specs/agent-output.schema.json` 的 JSON 对象。
如需写文件，增加 `"files":[{{"path":"{scope}...","content":"..."}}]`；
只能写这些前缀：{scope}；不得写项目目录之外；不得写密钥。
"""

    def system_message(self, role: str) -> str:
        p = load_prompt(role)
        return p.text + f"""

## 项目运行器约束
你正在项目目录 `{self.project_dir.name}` 中作为 {role} 工作。
输出只能是 JSON；如需写文件，files[].path 必须落在 `{', '.join(ROLE_MAP[role].scope)}`。
不得写项目目录之外，不得写密钥；不确定时写 open_questions，不要编造证据。
"""

    # ---------- run ----------
    def run(self) -> dict[str, Any]:
        self.prepare()
        kb = self.kb_context()
        existing: dict[str, Any] = {}
        if self.merge_state and self.state_path.exists():
            existing = json.loads(self.state_path.read_text(encoding="utf-8"))
        prior: list[str] = []
        for spec in ROLE_SPECS:
            if spec.role in existing and spec.role not in self.roles:
                summary_path = self.project_dir / "artifacts" / spec.role / "summary.md"
                if summary_path.exists():
                    text = summary_path.read_text(encoding="utf-8")[:900]
                    prior.append(f"- {spec.role}: {text}")
        state: dict[str, Any] = dict(existing)
        statuses: dict[str, str] = {}
        started_all = time.time()
        self.log("project.started", offline=self.offline, roles=self.roles)

        for role in self.roles:
            spec = ROLE_MAP[role]
            prompt = load_prompt(role)
            system_text = self.system_message(role)
            user_text = self.user_message(spec, prior, kb)
            messages = [{"role": "system", "content": system_text},
                        {"role": "user", "content": user_text}]
            role_dir = self.project_dir / "artifacts" / role
            role_dir.mkdir(parents=True, exist_ok=True)
            (role_dir / "request.md").write_text(
                f"# system\n\n{system_text}\n\n# user\n\n{user_text}\n", encoding="utf-8")
            self.log("role.started", role=role,
                     adjustment=self.extra_note or None,
                     prompt=prompt.metadata())
            started = time.perf_counter()
            obj = None
            result = None
            last_exc: Exception | None = None
            for _attempt in range(2):
                try:
                    result = self.router.execution(role, messages, response_format="json")
                    obj = parse_json_object(result.content)
                    jsonschema.validate(obj, self.schema)
                    break
                except Exception as exc:
                    last_exc = exc
                    obj = None
                    messages += [
                        {"role": "assistant", "content": result.content if result else ""},
                        {"role": "user", "content": f"输出不符合 schema：{exc}。只输出合法 JSON。"},
                    ]
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            (role_dir / "prompt.md").write_text(prompt.text, encoding="utf-8")
            if obj is None:
                statuses[role] = "error"
                error = {"role": role, "error": str(last_exc), "at": time.time()}
                (role_dir / "error.json").write_text(
                    json.dumps(error, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self.log("role.failed", role=role, error=str(last_exc)[:500],
                         prompt=prompt.metadata())
                prior.append(f"- {role}: FAILED — {str(last_exc)[:200]}")
                state[role] = {"status": "error", "error": str(last_exc)[:500]}
                if self.stop_on_error:
                    break
                continue
            code_pass = False
            if not self.offline and role in CODE_ROLES and not obj.get("files"):
                code_obj = self.code_files(role, prompt, obj, prior, kb)
                if code_obj and code_obj.get("files"):
                    obj["files"] = code_obj["files"]
                    if code_obj.get("summary"):
                        obj["summary"] = code_obj["summary"]
                    code_pass = True
                else:
                    self.log("code.no_files", role=role)
            files = self.write_files(role, obj.get("files") or [])
            (role_dir / "output.json").write_text(
                json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary = obj.get("summary") or "; ".join(
                c.get("claim", "") for c in obj.get("claims", []))
            (role_dir / "summary.md").write_text(
                self.summary_md(role, spec, obj, files), encoding="utf-8")
            meta = {
                "role": role, "title": spec.title,
                "status": obj.get("status", "done"),
                "prompt": prompt.metadata(),
                "model": result.model if result else "",
                "backend": result.backend if result else "",
                "latency_ms": result.latency_ms if result else elapsed_ms,
                "tokens": (result.prompt_tokens + result.completion_tokens) if result else 0,
                "cost_usd": result.cost_usd if result else 0.0,
                "files": files,
                "code_pass": code_pass,
                "adjustment": self.extra_note or "",
                "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            (role_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            statuses[role] = obj.get("status", "done")
            state[role] = meta
            prior.append(f"- {role}: {summary[:700]}")
            self.log("role.finished", role=role, status=meta["status"],
                     model=meta["model"], backend=meta["backend"],
                     prompt=prompt.metadata(), latency_ms=meta["latency_ms"],
                     files=[f["path"] for f in files])
        elapsed = int(time.time() - started_all)
        errors = [r for r, s in statuses.items() if s == "error"]
        all_errors = [r for r, v in state.items() if v.get("status") == "error"]
        status = "failed" if all_errors and len(all_errors) == len(state) else (
            "partial" if all_errors else "completed")
        self.write_state(state, status, elapsed)
        self.write_readme(state, status)
        self.log("project.finished", status=status, elapsed_s=elapsed, errors=errors)
        return {"project_dir": str(self.project_dir), "status": status,
                "roles": statuses, "errors": errors,
                "elapsed_s": elapsed, "model": self.router.summary()}

    @staticmethod
    def parse_file_blocks(text: str) -> list[dict[str, str]]:
        files = []
        # Tolerate missing END markers and truncated output: split on FILE headers.
        parts = re.split(r"=== FILE:[ ]*(.+?)[ ]*===", text)
        for i in range(1, len(parts), 2):
            path = parts[i].strip()
            content = parts[i + 1].strip()
            content = re.sub(r"=== END FILE ===.*$", "", content, flags=re.S).strip()
            if content.startswith("```"):
                content = content.split(chr(10), 1)[1] if chr(10) in content else ""
                if content.rstrip().endswith("```"):
                    content = content.rstrip()[:-3].rstrip()
            if path and content:
                files.append({"path": path, "content": content})
        return files

    def code_files(self, role: str, prompt, base: dict[str, Any],
                   prior: list[str], kb: str) -> dict[str, Any] | None:
        """Second pass: plain-text file blocks (robust against JSON escaping)."""
        spec = ROLE_MAP[role]
        scope = ", ".join(spec.scope)
        system = prompt.text + f"""

## 本轮例外：代码文件输出（纯文本，不要 JSON）
忽略上面的 JSON 输出要求。只输出文件块，格式严格如下：
=== FILE: {scope}path/to/file ===
<完整文件内容>
=== END FILE ===
最多 2 个文件，优先 1 个最关键且完整的文件；path 必须以下列前缀之一开头：{scope}。
不要输出解释、不要输出 Markdown 代码块，内容直接放在 FILE 标记之间。
"""
        user = f"""# 需求
{self.requirement_text}

# 已确认实现摘要
{json.dumps(base, ensure_ascii=False)[:3500]}

# 前置产物摘要
{chr(10).join(prior[-3:])}

# 知识库引用
{kb or "（无）"}

请输出至少 1 个完整代码文件，使用 FILE 块格式。
"""
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        debug_dir = self.project_dir / "artifacts" / role
        debug_dir.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                result = self.router.execution(role, messages, response_format=None)
                (debug_dir / f"code_pass_attempt{attempt + 1}.txt").write_text(
                    result.content, encoding="utf-8")
                files = self.parse_file_blocks(result.content)
                self.log("code.attempt", role=role, attempt=attempt + 1,
                         files=[f["path"] for f in files], mode="file_blocks")
                if files:
                    return {"files": files,
                            "summary": f"代码文件已生成：{', '.join(f['path'] for f in files)}"}
                messages += [{"role": "assistant", "content": result.content},
                             {"role": "user", "content":
                              "没有识别到 FILE 块。请严格使用 === FILE: path === 与 === END FILE ===。"}]
            except Exception as exc:
                self.log("code.attempt_error", role=role, attempt=attempt + 1,
                         error=str(exc)[:500])
                messages += [{"role": "user", "content": f"调用失败：{exc}"}]
        return None

    def summary_md(self, role: str, spec: RoleSpec, obj: dict[str, Any],
                   files: list[dict[str, Any]]) -> str:
        claims = obj.get("claims") or []
        questions = obj.get("open_questions") or []
        lines = [f"# {role} · {spec.title}", "",
                 f"- 状态：{obj.get('status', 'done')}",
                 f"- 摘要：{obj.get('summary', '')}", "",
                 *([f"- 调整要求：{self.extra_note}", ""] if self.extra_note else []),
                 "## Claims（不参与门禁）", "",
                 *[f"- {c.get('claim', '')}" for c in claims], "",
                 "## 写入文件", "",
                 *([f"- `{f['path']}` · {f['sha256'][:12]}" for f in files] or ["- 无"]), "",
                 "## 未决问题", "",
                 *([f"- {q}" for q in questions] or ["- 无"]), ""]
        return "\n".join(lines)

    # ---------- files ----------
    def write_files(self, role: str, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scope = ROLE_MAP[role].scope
        written: list[dict[str, Any]] = []
        for f in files:
            path = str(f.get("path", "")).replace("\\", "/").lstrip("/")
            content = str(f.get("content", ""))
            if not path or ".." in Path(path).parts:
                self.log("file.rejected", role=role, path=path, reason="path traversal")
                continue
            if not any(path.startswith(prefix) for prefix in scope):
                self.log("file.rejected", role=role, path=path, reason="out of scope")
                continue
            target = (self.project_dir / path).resolve()
            root = str(self.project_dir)
            if not (str(target) == root or str(target).startswith(root + os.sep)):
                self.log("file.rejected", role=role, path=path, reason="outside project")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            import hashlib
            sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
            written.append({"path": path, "sha256": sha, "bytes": len(content.encode("utf-8"))})
            self.log("file.written", role=role, path=path, sha256=sha)
        return written

    # ---------- reports ----------
    def write_state(self, state: dict[str, Any], status: str, elapsed: int) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        (self.state_path).write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
        project = json.loads((self.project_dir / "project.json").read_text(encoding="utf-8"))
        project.update({"status": status, "elapsed_s": elapsed,
                        "model": self.router.summary()})
        (self.project_dir / "project.json").write_text(
            json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_readme(self, state: dict[str, Any], status: str) -> None:
        rows = ["| 角色 | 标题 | 状态 | 模型 | Prompt | 文件 |",
                "|---|---|---|---|---|---|"]
        for spec in ROLE_SPECS:
            role = spec.role
            if role not in state:
                continue
            s = state.get(role, {})
            prompt = s.get("prompt", {})
            files = s.get("files", [])
            rows.append(f"| {role} | {spec.title} | {s.get('status', '—')} | "
                        f"{s.get('model', '—')} | {prompt.get('version', '—')} / "
                        f"{prompt.get('hash', '—')} | {', '.join(f['path'] for f in files) or '—'} |")
        lines = [
            f"# {self.project_dir.name}", "",
            f"- 状态：**{status}**",
            f"- 需求：`requirements/input.md`",
            f"- 角色记录：`artifacts/<role>/{{output.json,summary.md,meta.json,prompt.md}}`",
            f"- 事件账本：`logs/events.jsonl`",
            f"- 状态：`state/roles.json`",
            "", "## 角色执行记录", "", *rows, "",
            "> 这是角色产出记录，不是生产验收；代码/文档仍需门禁、证据与裁判。",
            "",
        ]
        (self.project_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
