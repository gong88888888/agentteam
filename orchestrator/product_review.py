"""Reusable product-review / upgrade-reference team.

This is a separate workflow from the delivery runner: it reads a product
document (current or proposed next version), maps every source section, builds
user/flow/feature/UX/tech/release/rehearsal/red-team artifacts, and assembles a
reference plan for a future release. It intentionally does not write product
code.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .config import data_dir, load_config, load_schema
from .judge.backend import parse_json_object
from .knowledge import HybridRetriever
from .models.router import ModelRouter
from .prompts import load_prompt


@dataclass(frozen=True)
class ProductRole:
    role: str
    title: str
    artifact: str
    instruction: str
    required_terms: tuple[str, ...]


PRODUCT_ROLES: list[ProductRole] = [
    ProductRole("product-lead", "产品负责人", "docs/product-review/00-brief.md",
                "定义目标、成功指标、非目标、决策问题，主持最终参考方案。",
                ("目标", "成功指标", "非目标", "决策")),
    ProductRole("doc-analyst", "产品文档分析师", "docs/product-review/01-document-map.md",
                "建立来源地图、主张、歧义、缺口和覆盖率。",
                ("来源", "主张", "歧义", "覆盖", "SRC-")),
    ProductRole("user-researcher", "用户与场景研究员", "docs/product-review/02-users-journeys.md",
                "拆用户、场景、旅程、痛点、假设与失败恢复。",
                ("用户", "场景", "旅程", "痛点", "假设")),
    ProductRole("flow-architect", "产品流程架构师", "docs/product-review/03-product-flows.md",
                "状态机、事件、转移、空/加载/错误/恢复。",
                ("状态", "事件", "转移", "失败", "恢复")),
    ProductRole("feature-designer", "功能与验收设计师", "docs/product-review/04-feature-spec.md",
                "功能切片、依赖、非目标、验收与边界。",
                ("功能", "切片", "依赖", "非目标", "验收")),
    ProductRole("ux-reviewer", "UX/可访问性评审", "docs/product-review/05-ux-review.md",
                "信息架构、状态、错误、文案与可访问性。",
                ("信息架构", "状态", "错误", "可访问", "文案")),
    ProductRole("tech-feasibility", "技术可行性评审", "docs/product-review/06-tech-feasibility.md",
                "技术栈、依赖、性能、安全、成本与前置验证。",
                ("技术", "依赖", "性能", "安全", "风险")),
    ProductRole("release-strategist", "版本与发布策略师", "docs/product-review/07-upgrade-plan.md",
                "版本、兼容性、迁移、特性开关、灰度、回滚，面向发版升级。",
                ("版本", "兼容", "迁移", "灰度", "回滚", "特性开关")),
    ProductRole("qa-rehearsal", "质量预演师", "docs/product-review/08-rehearsal.md",
                "至少 3 个升级场景、基线、影响、通过标准、回滚时间、Go/No-Go。",
                ("场景", "基线", "指标", "回滚", "Go/No-Go")),
    ProductRole("red-team", "产品红队评审", "docs/product-review/09-red-team.md",
                "矛盾、缺口、不可验收承诺、范围膨胀和升级破坏，带严重度与 SRC。",
                ("矛盾", "风险", "严重", "SRC-")),
    ProductRole("knowledge-curator", "知识沉淀与复用", "docs/product-review/10-playbook.md",
                "把分析转成下一次升级的触发条件、输入、步骤、门禁、模板和常见坑。",
                ("复用", "升级", "触发条件", "门禁", "模板")),
]

ROLE_MAP = {r.role: r for r in PRODUCT_ROLES}
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.M)
SRC_REF = re.compile(r"SRC-\d{3,}")


def extract_source_sections(text: str) -> list[dict[str, Any]]:
    sections = []
    for index, match in enumerate(HEADING.finditer(text), 1):
        sections.append({
            "id": f"SRC-{index:03d}",
            "level": len(match.group(1)),
            "heading": match.group(2).strip(),
            "line": text[:match.start()].count("\n") + 1,
        })
    return sections


def _normalize(obj: dict[str, Any], role: str, total_sections: int) -> dict[str, Any]:
    out = dict(obj)
    aliases = {"completed": "done", "success": "done", "ok": "done",
               "failed": "blocked", "error": "blocked"}
    status = str(out.get("status", "")).lower()
    out["status"] = aliases.get(status, out.get("status", "done"))
    out.setdefault("task_id", f"PR-{role.upper()}-{int(time.time())}")
    out["role"] = role
    out.setdefault("source_sections", [])
    findings = out.get("findings") or []
    severity_alias = {"low": "minor", "medium": "major", "high": "critical",
                      "severe": "critical", "warning": "minor"}
    for finding in findings:
        if isinstance(finding, dict) and finding.get("severity") in severity_alias:
            finding["severity"] = severity_alias[finding["severity"]]
    out["findings"] = findings
    out.setdefault("files", [])
    out.setdefault("summary", "")
    out.setdefault("open_questions", [])
    cov = out.get("coverage") or {}
    covered = len({*out.get("source_sections", []),
                   *SRC_REF.findall(json.dumps(out, ensure_ascii=False))})
    cov.setdefault("total_sections", total_sections)
    cov["covered_sections"] = min(total_sections, int(cov.get("covered_sections", covered)))
    cov.setdefault("percent", round(cov["covered_sections"] / total_sections * 100, 1)
                   if total_sections else 0)
    out["coverage"] = cov
    return out


class ProductReviewRunner:
    def __init__(self, *, doc: str | Path, out_dir: str | Path,
                 cfg: dict[str, Any] | None = None, offline: bool = True,
                 roles: list[str] | None = None, use_kb: bool = False,
                 extra_note: str = "") -> None:
        self.doc_path = Path(doc)
        if not self.doc_path.is_file():
            raise FileNotFoundError(f"产品文档不存在：{self.doc_path}")
        self.out_dir = Path(out_dir).resolve()
        self.cfg = cfg or load_config()
        self.offline = offline
        self.roles = roles or [r.role for r in PRODUCT_ROLES]
        unknown = [r for r in self.roles if r not in ROLE_MAP]
        if unknown:
            raise ValueError(f"未知产品评审角色：{unknown}")
        self.use_kb = use_kb
        self.extra_note = extra_note
        self.router = ModelRouter(self.cfg, offline=offline)
        self.schema = load_schema("product-review-output.schema.json")
        self.source_text = self.doc_path.read_text(encoding="utf-8")
        self.sections = extract_source_sections(self.source_text)
        self.log_path = self.out_dir / "logs" / "events.jsonl"
        self.state_path = self.out_dir / "state" / "roles.json"
        self.gates_path = self.out_dir / "state" / "gates.json"
        self.previous_state: dict[str, Any] = {}
        self.previous_gates: dict[str, dict[str, Any]] = {}

    def log(self, event: str, **payload: Any) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.time(), "clock": time.strftime("%H:%M:%S"),
               "event": event, **payload}
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def prepare(self) -> None:
        for d in ("input", "artifacts", "docs/product-review", "logs", "state"):
            (self.out_dir / d).mkdir(parents=True, exist_ok=True)
        (self.out_dir / "input" / "product-doc.md").write_text(self.source_text, encoding="utf-8")
        (self.out_dir / "state" / "source-map.json").write_text(
            json.dumps({"source": str(self.doc_path), "sections": self.sections},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.out_dir / "input" / "source-map.yaml").write_text(
            yaml.safe_dump({"sections": self.sections}, allow_unicode=True,
                           sort_keys=False), encoding="utf-8")

    def kb_context(self) -> str:
        if not self.use_kb:
            return ""
        db = data_dir(self.cfg) / "knowledge.db"
        if not db.exists():
            return ""
        try:
            hits = HybridRetriever(db, self.cfg).search(self.source_text[:400], top_k=3)
            return "\n".join(f"- {h.get('citation')}: {h.get('text', '')[:220]}"
                             for h in hits if "citation" in h)
        except Exception:
            return ""

    def user_message(self, spec: ProductRole, prior: list[str], kb: str) -> str:
        section_list = "\n".join(
            f"- {s['id']} L{s['line']} {s['heading']}" for s in self.sections)
        return f"""# 产品文档
{self.source_text}

# 来源章节 ID
{section_list or "（文档没有 Markdown 标题；仍请按内容建立 SRC 引用）"}

# 当前角色
{spec.role} · {spec.title}
{spec.instruction}

# 前序产物
{chr(10).join(prior) if prior else "（本角色为第一个角色）"}

# 知识库引用
{kb or "（未启用或无命中）"}

# 调整要求
{self.extra_note or "（无特别调整）"}

# 输出要求
只输出符合 `specs/product-review-output.schema.json` 的 JSON。
必须把完整分析写入 `{spec.artifact}`（files[].path），不能只写摘要。
每个事实尽量引用 `SRC-###`；不确定内容写入 open_questions。
"""

    def system_message(self, spec: ProductRole) -> str:
        p = load_prompt(spec.role, "prompts/product-team")
        return p.text + f"""

## 本次运行约束
- 输出只能是一个 JSON 对象；不要 Markdown 代码块或解释性前后缀。
- files[].path 必须以 `docs/product-review/` 或 `artifacts/{spec.role}/` 开头。
- 必须保留来源引用 SRC-###；不要编造未在输入中出现的事实。
"""

    def write_files(self, role: str, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        written = []
        allowed = ("docs/product-review/", f"artifacts/{role}/")
        for f in files:
            path = str(f.get("path", "")).replace("\\", "/").lstrip("/")
            content = str(f.get("content", ""))
            if not path or ".." in Path(path).parts:
                continue
            if not any(path.startswith(prefix) for prefix in allowed):
                self.log("file.rejected", role=role, path=path, reason="out of scope")
                continue
            target = (self.out_dir / path).resolve()
            if not str(target).startswith(str(self.out_dir) + os.sep):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
            written.append({"path": path, "sha256": sha,
                            "bytes": len(content.encode("utf-8"))})
            self.log("file.written", role=role, path=path, sha256=sha)
        return written

    def gate(self, spec: ProductRole, obj: dict[str, Any],
             files: list[dict[str, Any]], coverage: float) -> dict[str, Any]:
        checks = []
        text = "\n".join([obj.get("summary", "")] + [
            (self.out_dir / f["path"]).read_text(encoding="utf-8", errors="replace")
            for f in files if (self.out_dir / f["path"]).is_file()])
        for term in spec.required_terms:
            checks.append({"name": f"term:{term}", "ok": term.lower() in text.lower(),
                           "detail": "" if term.lower() in text.lower() else "缺少关键内容"})
        checks.append({"name": "files", "ok": bool(files), "detail": f"{len(files)} files"})
        checks.append({"name": "source_refs", "ok": bool(SRC_REF.search(text)),
                       "detail": "必须引用 SRC-###"})
        findings = obj.get("findings") or []
        if spec.role == "red-team":
            checks.append({"name": "red_findings", "ok": len(findings) >= 5,
                           "detail": f"{len(findings)} findings"})
            checks.append({"name": "finding_refs",
                           "ok": all(f.get("source_refs") for f in findings),
                           "detail": "每条 finding 必须引用来源"})
        if spec.role == "qa-rehearsal":
            checks.append({"name": "scenarios", "ok": text.count("场景") >= 3,
                           "detail": "至少 3 个升级场景"})
            checks.append({"name": "go_no_go", "ok": "go/no-go" in text.lower(),
                           "detail": "需要 Go/No-Go 条件"})
        if spec.role == "doc-analyst":
            checks.append({"name": "coverage", "ok": coverage >= 0.6,
                           "detail": f"{coverage:.0%} source coverage"})
        status = "pass" if all(c["ok"] for c in checks) else "fail"
        return {"role": spec.role, "status": status, "checks": checks,
                "coverage": coverage, "files": files}

    def run(self) -> dict[str, Any]:
        self.prepare()
        if self.gates_path.exists():
            try:
                previous = json.loads(self.gates_path.read_text(encoding="utf-8"))
                self.previous_state = previous.get("roles") or {}
                self.previous_gates = {g["role"]: g for g in previous.get("gates", [])
                                       if isinstance(g, dict) and g.get("role")}
            except (OSError, json.JSONDecodeError):
                self.previous_state, self.previous_gates = {}, {}
        kb = self.kb_context()
        state: dict[str, Any] = dict(self.previous_state)
        gates: list[dict[str, Any]] = list(self.previous_gates.values())
        prior: list[str] = []
        self.log("review.started", doc=str(self.doc_path), sections=len(self.sections),
                 roles=self.roles)
        for spec in PRODUCT_ROLES:
            if spec.role not in self.roles:
                continue
            prompt = load_prompt(spec.role, "prompts/product-team")
            messages = [{"role": "system", "content": self.system_message(spec)},
                        {"role": "user", "content": self.user_message(spec, prior, kb)}]
            started = time.perf_counter()
            obj = None
            result = None
            last_exc: Exception | None = None
            for attempt in range(2):
                try:
                    result = self.router.execution(spec.role, messages,
                                                   response_format="json")
                    parsed = parse_json_object(result.content)
                    obj = _normalize(parsed, spec.role, len(self.sections))
                    jsonschema.validate(obj, self.schema)
                    break
                except Exception as exc:
                    last_exc = exc
                    obj = None
                    messages += [
                        {"role": "assistant", "content": result.content if result else ""},
                        {"role": "user", "content":
                         f"输出不符合 schema：{exc}。只输出合法 JSON，并包含 files。"},
                    ]
            role_dir = self.out_dir / "artifacts" / spec.role
            role_dir.mkdir(parents=True, exist_ok=True)
            (role_dir / "prompt.md").write_text(prompt.text, encoding="utf-8")
            (role_dir / "request.md").write_text(
                f"# system\n\n{messages[0]['content']}\n\n# user\n\n{messages[1]['content']}\n",
                encoding="utf-8")
            if obj is None:
                state[spec.role] = {"role": spec.role, "status": "error",
                                    "error": str(last_exc)[:1000]}
                (role_dir / "error.json").write_text(
                    json.dumps(state[spec.role], ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                self.log("review.role_failed", role=spec.role, error=str(last_exc)[:500])
                if self.extra_note:
                    prior.append(f"- {spec.role}: FAILED — {str(last_exc)[:180]}")
                continue
            files = self.write_files(spec.role, obj.get("files") or [])
            (role_dir / "output.json").write_text(
                json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            file_text = "\n".join(
                (self.out_dir / f["path"]).read_text(encoding="utf-8", errors="replace")
                for f in files if (self.out_dir / f["path"]).is_file())
            refs = set(SRC_REF.findall(file_text + "\n" + obj.get("summary", "")))
            coverage = (len({s["id"] for s in self.sections} & refs) / len(self.sections)
                        if self.sections else 1.0)
            obj["coverage"]["percent"] = round(coverage * 100, 1)
            obj["coverage"]["covered_sections"] = round(coverage * len(self.sections))
            gate = self.gate(spec, obj, files, coverage)
            gates.append(gate)
            meta = {
                "role": spec.role, "title": spec.title, "status": obj["status"],
                "prompt": prompt.metadata(), "model": result.model if result else "",
                "backend": result.backend if result else "",
                "latency_ms": result.latency_ms if result else 0,
                "tokens": (result.prompt_tokens + result.completion_tokens) if result else 0,
                "coverage": obj.get("coverage"), "gate": gate["status"],
                "files": files, "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            (role_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            state[spec.role] = meta
            prior.append(f"- {spec.role} [{gate['status']}] {obj.get('summary', '')[:700]}")
            self.log("review.role_finished", role=spec.role, status=obj["status"],
                     gate=gate["status"], coverage=obj.get("coverage"),
                     files=[f["path"] for f in files])
        all_refs = set()
        for f in self.out_dir.rglob("*.md"):
            try:
                all_refs |= set(SRC_REF.findall(f.read_text(encoding="utf-8")))
            except OSError:
                pass
        total = len(self.sections)
        covered = len({s["id"] for s in self.sections} & all_refs)
        overall = round(covered / total * 100, 1) if total else 0.0
        gate_by_role = {g["role"]: g for g in gates}
        gates = [gate_by_role[r.role] for r in PRODUCT_ROLES if r.role in gate_by_role]
        gate_status = ("pass" if len(gates) == len(PRODUCT_ROLES)
                       and all(g["status"] == "pass" for g in gates) else "fail")
        final = {
            "status": gate_status, "source": str(self.doc_path),
            "source_sections": total, "covered_sections": covered,
            "coverage_percent": overall, "roles": state, "gates": gates,
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        (self.out_dir / "state" / "gates.json").write_text(
            json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.state_path).write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.write_reference_plan(final)
        self.write_readme(final)
        self.log("review.finished", status=gate_status, coverage=overall)
        return {"out_dir": str(self.out_dir), "status": gate_status,
                "coverage": overall, "roles": {r: v.get("status") for r, v in state.items()},
                "gates": {g["role"]: g["status"] for g in gates},
                "reference_plan": str(self.out_dir / "REFERENCE-PLAN.md")}

    def write_reference_plan(self, final: dict[str, Any]) -> None:
        lines = [
            "# Product Deep Review & Upgrade Reference Plan", "",
            f"- Source: `{self.doc_path}`",
            f"- Source sections: {final['source_sections']} · "
            f"Coverage: **{final['coverage_percent']}%**",
            f"- Gate: **{final['status']}**",
            f"- Generated: {final['finished_at']}", "",
            "> 这是给下一次发版/升级使用的参考方案，不是自动发布审批。",
            "", "## Role Gates", "",
            "| 角色 | 输出 | 门禁 |", "|---|---|---|",
        ]
        for spec in PRODUCT_ROLES:
            if spec.role not in self.roles:
                continue
            gate = next((g for g in final["gates"] if g["role"] == spec.role), None)
            lines.append(f"| {spec.role} | `{spec.artifact}` | {gate['status'] if gate else 'missing'} |")
        lines += ["", "## Artifacts", ""]
        for spec in PRODUCT_ROLES:
            path = self.out_dir / spec.artifact
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            lines += [f"### {spec.title}", "", text, ""]
        if not (self.out_dir / "docs/product-review/10-playbook.md").exists():
            lines += ["## Upgrade Checklist", "",
                      "- Run this team against the new version's product document before implementation.",
                      "- Compare coverage, contradictions, compatibility, migration and rollback.",
                      "- Re-run with the previous plan as input and require an explicit delta.", ""]
        (self.out_dir / "REFERENCE-PLAN.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")

    def write_readme(self, final: dict[str, Any]) -> None:
        rows = ["| 角色 | 状态 | 门禁 | 覆盖率 | 文件 |", "|---|---|---|---|---|"]
        for spec in PRODUCT_ROLES:
            meta = final["roles"].get(spec.role)
            if not meta:
                continue
            gate = next((g for g in final["gates"] if g["role"] == spec.role), {})
            rows.append(f"| {spec.role} | {meta.get('status')} | {meta.get('gate')} | "
                        f"{meta.get('coverage', {}).get('percent', '—')}% | "
                        f"{', '.join(f['path'] for f in meta.get('files', [])) or '—'} |")
        lines = [
            "# Product Review Team", "",
            f"- Source: `{self.doc_path}`",
            f"- Status: **{final['status']}**",
            f"- Source coverage: **{final['coverage_percent']}%**",
            f"- Reference plan: `REFERENCE-PLAN.md`",
            f"- Gates: `state/gates.json`",
            "", "## Roles", "", *rows, "",
            "> 该团队只产出产品分析、升级方案与预演，不直接修改产品代码。",
            "",
        ]
        (self.out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
