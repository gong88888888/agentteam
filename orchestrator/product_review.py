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
from .requirements_ledger import from_model_output as requirements_from_output
from .sources import SourceUnit, diff_units, parse_markdown


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
SRC_REF = re.compile(r"SRC-\d{3,}")
VALID_STATUSES = {"done", "blocked", "need_evidence", "failed", "error",
                  "draft", "unknown", "invalid"}
STATUS_ALIASES = {"completed": "done", "complete": "done", "success": "done",
                  "ok": "done", "finished": "done", "ready": "done",
                  "ready_for_verification": "done"}


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_source_sections(text: str) -> list[dict[str, Any]]:
    parsed = parse_markdown(text, doc_id="PRODUCT")
    headings = [u for u in parsed.units if u.kind == "heading"]
    lines = text.replace("\r\n", "\n").split("\n")
    sections = []
    for index, unit in enumerate(headings, 1):
        next_line = headings[index].line if index < len(headings) else len(lines) + 1
        body = "\n".join(lines[unit.line: next_line - 1])
        sections.append({
            "id": f"SRC-{index:03d}",
            "level": len(unit.path),
            "heading": unit.heading,
            "line": unit.line,
            "stable_id": unit.unit_id,
            "content_hash": unit.content_hash,
            "body_hash": hashlib.sha256(body.strip().encode("utf-8")).hexdigest(),
            "path": list(unit.path),
        })
    return sections


def _normalize(obj: dict[str, Any], role: str, total_sections: int,
               valid_ids: set[str] | None = None) -> dict[str, Any]:
    out = dict(obj)
    raw_status = str(out.get("status", "")).strip().lower()
    if not raw_status:
        # Missing status is not success. The caller may show the draft for
        # diagnosis, but the gate must not treat it as a completed review.
        out["status"] = "unknown"
        out["status_missing"] = True
    elif raw_status in STATUS_ALIASES:
        out["status"] = STATUS_ALIASES[raw_status]
        out["status_raw"] = raw_status
    elif raw_status in VALID_STATUSES:
        out["status"] = raw_status
    else:
        out["status"] = "invalid"
        out["status_raw"] = raw_status
    out.setdefault("task_id", f"PR-{role.upper()}-{int(time.time())}")
    out["role"] = role
    declared = out.get("source_sections") or []
    if not isinstance(declared, list):
        declared = [str(declared)]
    declared = [str(x) for x in declared]
    invalid = sorted({x for x in declared if valid_ids and x not in valid_ids})
    if valid_ids:
        declared = [x for x in declared if x in valid_ids]
    out["source_sections"] = declared
    if invalid:
        out["invalid_source_refs"] = invalid
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
    cov = out.get("coverage") if isinstance(out.get("coverage"), dict) else {}
    covered = len(set(declared))
    cov["total_sections"] = total_sections
    cov["covered_sections"] = min(total_sections, covered)
    if valid_ids:
        cov["covered_sections"] = min(cov["covered_sections"], len(valid_ids))
    cov["percent"] = round(cov["covered_sections"] / total_sections * 100, 1) \
        if total_sections else 0
    cov["computed_by"] = "product_review.normalize"
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
        self.parsed_source = parse_markdown(self.source_text, doc_id="PRODUCT")
        self.sections = extract_source_sections(self.source_text)
        self.section_ids = {s["id"] for s in self.sections}
        self.source_hash = source_hash(self.source_text)
        self.run_id = f"PR-{time.strftime('%Y%m%d-%H%M%S')}-{self.source_hash[:8]}"
        self.log_path = self.out_dir / "logs" / "events.jsonl"
        self.state_path = self.out_dir / "state" / "roles.json"
        self.gates_path = self.out_dir / "state" / "gates.json"
        self.history_path = self.out_dir / "state" / "gate-history.jsonl"
        self.artifact_registry: dict[str, list[dict[str, Any]]] = {}
        self.requirement_errors_by_role: dict[str, list[dict[str, str]]] = {}
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
            json.dumps({"source": str(self.doc_path), "source_hash": self.source_hash,
                        "run_id": self.run_id, "sections": self.sections},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.out_dir / "input" / "source-map.yaml").write_text(
            yaml.safe_dump({"source_hash": self.source_hash,
                            "sections": self.sections}, allow_unicode=True,
                           sort_keys=False), encoding="utf-8")
        units_path = self.out_dir / "state" / "source-units.json"
        old_units: list[SourceUnit] = []
        if units_path.is_file():
            try:
                old = json.loads(units_path.read_text(encoding="utf-8"))
                for raw in old.get("units") or []:
                    path = tuple(raw.get("path") or [])
                    old_units.append(SourceUnit(
                        unit_id=raw["unit_id"], doc_id=raw.get("doc_id", "PRODUCT"),
                        kind=raw.get("kind", "paragraph"),
                        text=raw.get("text", ""), heading=raw.get("heading", ""),
                        path=path, line=int(raw.get("line", 0)),
                        line_end=int(raw.get("line_end", 0)),
                        content_hash=raw.get("content_hash", ""),
                        identity_key=raw.get("identity_key", ""),
                        occurrence=int(raw.get("occurrence", 1))))
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                old_units = []
        current = self.parsed_source.to_dict()
        units_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        if old_units and old_units != self.parsed_source.units:
            diff = diff_units(old_units, self.parsed_source)
            (self.out_dir / "state" / "source-diff.json").write_text(
                json.dumps(diff, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            self.log("source.changed", counts=diff["counts"])

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
            rec = {"path": path, "sha256": sha,
                   "bytes": len(content.encode("utf-8")),
                   "source": "role", "run_id": self.run_id,
                   "source_hash": self.source_hash}
            written.append(rec)
            self.artifact_registry.setdefault(role, []).append(rec)
            self.log("file.written", role=role, path=path, sha256=sha)
        return written

    def gate(self, spec: ProductRole, obj: dict[str, Any],
             files: list[dict[str, Any]], coverage: float) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        file_texts: list[str] = []
        empty_files: list[str] = []
        for f in files:
            path = self.out_dir / f["path"]
            text = path.read_text(encoding="utf-8", errors="replace") \
                if path.is_file() else ""
            file_texts.append(text)
            if len(text.strip()) < 20:
                empty_files.append(str(f.get("path", "")))
        summary = str(obj.get("summary", ""))
        text = "\n".join([summary, *file_texts])
        status = str(obj.get("status", "")).lower()
        checks.append({"name": "status_done", "ok": status == "done",
                       "detail": f"status={obj.get('status')!r}；"
                                 "blocked/failed/缺失状态都不能作为正式通过"})
        checks.append({"name": "files", "ok": bool(files), "detail": f"{len(files)} files"})
        checks.append({"name": "files_nonempty", "ok": bool(files) and not empty_files,
                       "detail": ("空文件：" + ", ".join(empty_files)) if empty_files
                                 else "所有交付文件非空"})
        for term in spec.required_terms:
            checks.append({"name": f"term:{term}", "ok": term.lower() in text.lower(),
                           "detail": "" if term.lower() in text.lower() else "缺少关键内容"})
        refs = set(SRC_REF.findall(text))
        invalid_refs = sorted(refs - self.section_ids)
        checks.append({"name": "source_refs", "ok": bool(refs),
                       "detail": "必须引用 SRC-###"})
        checks.append({"name": "source_refs_valid", "ok": not invalid_refs,
                       "detail": ("不存在的来源号：" + ", ".join(invalid_refs))
                                 if invalid_refs else "所有来源号属于当前文档"})
        findings = obj.get("findings") or []
        if spec.role == "red-team":
            checks.append({"name": "red_findings", "ok": len(findings) >= 5,
                           "detail": f"{len(findings)} findings"})
            finding_refs = [str(r) for f in findings for r in (f.get("source_refs") or [])]
            invalid_finding_refs = sorted(set(finding_refs) - self.section_ids)
            checks.append({"name": "finding_refs",
                           "ok": bool(findings) and all(f.get("source_refs") for f in findings)
                                 and not invalid_finding_refs,
                           "detail": ("无效 finding 来源：" + ", ".join(invalid_finding_refs))
                                     if invalid_finding_refs
                                     else "每条 finding 必须引用当前来源"})
        if spec.role == "qa-rehearsal":
            checks.append({"name": "scenarios", "ok": text.count("场景") >= 3,
                           "detail": "至少 3 个升级场景"})
            checks.append({"name": "go_no_go", "ok": "go/no-go" in text.lower(),
                           "detail": "需要 Go/No-Go 条件"})
        if spec.role == "doc-analyst":
            checks.append({"name": "coverage", "ok": coverage >= 0.6,
                           "detail": f"{coverage:.0%} source coverage"})
        req_errors = self.requirement_errors_by_role.get(spec.role)
        if req_errors is not None:
            checks.append({
                "name": "requirements_valid", "ok": not req_errors,
                "detail": ("; ".join(f"{e['code']}: {e['detail']}"
                                     for e in req_errors[:6]))
                if req_errors else "结构化需求与来源处置通过校验"})
        gate_status = "pass" if all(c["ok"] for c in checks) else "fail"
        attempt_id = f"{self.run_id}-{spec.role}"
        return {"role": spec.role, "status": gate_status, "checks": checks,
                "coverage": coverage, "files": files,
                "run_id": self.run_id, "attempt_id": attempt_id,
                "source_hash": self.source_hash,
                "subject_fingerprint": self.source_hash,
                "legacy": False}

    def run(self) -> dict[str, Any]:
        self.prepare()
        if self.gates_path.exists():
            try:
                previous = json.loads(self.gates_path.read_text(encoding="utf-8"))
                self.previous_state = previous.get("roles") or {}
                self.previous_gates = {g["role"]: g for g in previous.get("gates", [])
                                       if isinstance(g, dict) and g.get("role")}
                # Preserve the whole previous run as history before replacing
                # the current gate set.
                if self.previous_gates:
                    with open(self.history_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "run_id": previous.get("run_id", ""),
                            "source_hash": previous.get("source_hash", ""),
                            "finished_at": previous.get("finished_at", ""),
                            "gates": list(self.previous_gates.values()),
                            "archived_at": time.time(),
                        }, ensure_ascii=False) + "\n")
            except (OSError, json.JSONDecodeError):
                self.previous_state, self.previous_gates = {}, {}
        kb = self.kb_context()
        state: dict[str, Any] = dict(self.previous_state)
        current_gates: dict[str, dict[str, Any]] = {}
        prior: list[str] = []
        self.log("review.started", doc=str(self.doc_path), sections=len(self.sections),
                 roles=self.roles, run_id=self.run_id, source_hash=self.source_hash)
        for spec in PRODUCT_ROLES:
            if spec.role not in self.roles:
                continue
            attempt_id = f"{self.run_id}-{spec.role}"
            prompt = load_prompt(spec.role, "prompts/product-team")
            messages = [{"role": "system", "content": self.system_message(spec)},
                        {"role": "user", "content": self.user_message(spec, prior, kb)}]
            obj = None
            result = None
            last_exc: Exception | None = None
            for attempt in range(2):
                try:
                    result = self.router.execution(spec.role, messages,
                                                   response_format="json")
                    parsed = parse_json_object(result.content)
                    obj = _normalize(parsed, spec.role, len(self.sections),
                                     valid_ids=self.section_ids)
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
                                    "error": str(last_exc)[:1000],
                                    "run_id": self.run_id, "attempt_id": attempt_id,
                                    "source_hash": self.source_hash}
                current_gates[spec.role] = {
                    "role": spec.role, "status": "fail",
                    "checks": [{"name": "role_execution", "ok": False,
                                "detail": f"本次尝试失败：{str(last_exc)[:300]}"}],
                    "coverage": 0.0, "files": [],
                    "run_id": self.run_id, "attempt_id": attempt_id,
                    "source_hash": self.source_hash,
                    "subject_fingerprint": self.source_hash,
                    "legacy": False,
                }
                (role_dir / "error.json").write_text(
                    json.dumps(state[spec.role], ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                self.log("review.role_failed", role=spec.role, error=str(last_exc)[:500],
                         attempt_id=attempt_id)
                if self.extra_note:
                    prior.append(f"- {spec.role}: FAILED — {str(last_exc)[:180]}")
                continue
            files = self.write_files(spec.role, obj.get("files") or [])
            if "requirements" in obj or "source_dispositions" in obj:
                aliases = {s["id"]: s["stable_id"] for s in self.sections}
                ledger, req_errors = requirements_from_output(
                    obj, self.parsed_source.units, "PRODUCT", aliases=aliases)
                self.requirement_errors_by_role[spec.role] = req_errors
                (role_dir / "requirements.ledger.json").write_text(
                    json.dumps(ledger.to_dict(), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                (role_dir / "requirements.ledger.md").write_text(
                    ledger.render_markdown(), encoding="utf-8")
                self.log("requirements.validated", role=spec.role,
                         requirements=len(ledger.requirements),
                         dispositions=len(ledger.dispositions),
                         errors=[e["code"] for e in req_errors])
            (role_dir / "output.json").write_text(
                json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            file_text = "\n".join(
                (self.out_dir / f["path"]).read_text(encoding="utf-8", errors="replace")
                for f in files if (self.out_dir / f["path"]).is_file())
            refs = set(SRC_REF.findall(file_text + "\n" + obj.get("summary", "")))
            coverage = (len(self.section_ids & refs) / len(self.sections)
                        if self.sections else 1.0)
            obj["coverage"]["percent"] = round(coverage * 100, 1)
            obj["coverage"]["covered_sections"] = round(coverage * len(self.sections))
            obj["coverage"]["basis"] = "current_role_artifacts"
            gate = self.gate(spec, obj, files, coverage)
            current_gates[spec.role] = gate
            meta = {
                "role": spec.role, "title": spec.title, "status": obj["status"],
                "prompt": prompt.metadata(), "model": result.model if result else "",
                "backend": result.backend if result else "",
                "latency_ms": result.latency_ms if result else 0,
                "tokens": (result.prompt_tokens + result.completion_tokens) if result else 0,
                "coverage": obj.get("coverage"), "gate": gate["status"],
                "files": files, "run_id": self.run_id, "attempt_id": attempt_id,
                "source_hash": self.source_hash,
                "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            (role_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            state[spec.role] = meta
            prior.append(f"- {spec.role} [{gate['status']}] {obj.get('summary', '')[:700]}")
            self.log("review.role_finished", role=spec.role, status=obj["status"],
                     gate=gate["status"], coverage=obj.get("coverage"),
                     files=[f["path"] for f in files], attempt_id=attempt_id)
        final_gates: list[dict[str, Any]] = []
        reused: list[str] = []
        stale: list[str] = []
        for spec in PRODUCT_ROLES:
            gate = current_gates.get(spec.role)
            if gate is not None:
                final_gates.append({**gate, "current_attempt": True})
                continue
            prev = self.previous_gates.get(spec.role)
            if (prev and prev.get("source_hash") == self.source_hash
                    and prev.get("status") == "pass"):
                final_gates.append({**prev, "current_attempt": False,
                                    "reused_from": prev.get("attempt_id")
                                    or prev.get("run_id") or "previous-run",
                                    "reused": True})
                reused.append(spec.role)
                continue
            if prev is None:
                reason = "本次未运行，且没有历史结果"
            elif prev.get("source_hash") != self.source_hash:
                reason = "来源已变化，旧结果不适用于当前版本"
            else:
                reason = f"历史状态为 {prev.get('status')}，不能复用"
            final_gates.append({
                "role": spec.role, "status": "stale",
                "checks": [{"name": "current_attempt", "ok": False, "detail": reason}],
                "coverage": 0.0, "files": [], "run_id": self.run_id,
                "attempt_id": "", "source_hash": self.source_hash,
                "subject_fingerprint": self.source_hash,
                "stale_reason": reason, "current_attempt": False, "legacy": False,
            })
            stale.append(spec.role)
        all_refs: set[str] = set()
        registered_files = 0
        for gate in final_gates:
            if gate.get("status") != "pass":
                continue
            for f in gate.get("files") or []:
                path = self.out_dir / f.get("path", "")
                if not path.is_file():
                    continue
                registered_files += 1
                all_refs |= set(SRC_REF.findall(
                    path.read_text(encoding="utf-8", errors="replace")))
        total = len(self.sections)
        covered = len(self.section_ids & all_refs)
        overall = round(covered / total * 100, 1) if total else 0.0
        gate_status = ("pass" if len(final_gates) == len(PRODUCT_ROLES)
                       and all(g["status"] == "pass" for g in final_gates)
                       and all(g.get("source_hash") == self.source_hash
                               for g in final_gates) else "fail")
        final = {
            "status": gate_status, "source": str(self.doc_path),
            "run_id": self.run_id, "source_hash": self.source_hash,
            "source_sections": total, "covered_sections": covered,
            "coverage_percent": overall,
            "coverage_detail": {
                "structural_percent": overall,
                "structural_basis": "registered_current_artifacts",
                "semantic_review": "not_run",
                "registered_files": registered_files,
                "reused_roles": reused,
                "stale_roles": stale,
                "note": "结构覆盖只证明来源有去向，不证明语义理解正确。",
            },
            "roles": state, "gates": final_gates,
            "attempts": {g["role"]: g.get("attempt_id", "") for g in final_gates},
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        (self.out_dir / "state" / "gates.json").write_text(
            json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "run_id": self.run_id, "source_hash": self.source_hash,
                "finished_at": final["finished_at"], "status": gate_status,
                "gates": final_gates,
            }, ensure_ascii=False) + "\n")
        (self.state_path).write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.write_reference_plan(final)
        self.write_readme(final)
        self.log("review.finished", status=gate_status, coverage=overall,
                 run_id=self.run_id, reused=reused, stale=stale)
        return {"out_dir": str(self.out_dir), "status": gate_status,
                "coverage": overall, "run_id": self.run_id,
                "source_hash": self.source_hash,
                "roles": {r: v.get("status") for r, v in state.items()},
                "gates": {g["role"]: g["status"] for g in final_gates},
                "coverage_detail": final["coverage_detail"],
                "reference_plan": str(self.out_dir / "REFERENCE-PLAN.md")}

    def write_reference_plan(self, final: dict[str, Any]) -> None:
        detail = final.get("coverage_detail") or {}
        lines = [
            "# Product Deep Review & Upgrade Reference Plan", "",
            f"- Source: `{self.doc_path}`",
            f"- Run: `{final.get('run_id', '')}` · source hash `{final.get('source_hash', '')[:12]}`",
            f"- Source sections: {final['source_sections']} · "
            f"Structural coverage: **{final['coverage_percent']}%** "
            f"(`{detail.get('structural_basis', 'unknown')}`)",
            f"- Semantic review: **{detail.get('semantic_review', 'not_run')}** "
            "(结构覆盖不等于语义正确)",
            f"- Gate: **{final['status']}**",
            f"- Generated: {final['finished_at']}", "",
            "> 这是给下一次发版/升级使用的参考方案，不是自动发布审批。",
            "", "## Role Gates", "",
            "| 角色 | 输出 | 门禁 | 本次尝试 | 复用 |", "|---|---|---|---|---|",
        ]
        for spec in PRODUCT_ROLES:
            if spec.role not in self.roles and not any(
                    g["role"] == spec.role and g.get("status") == "pass"
                    for g in final["gates"]):
                continue
            gate = next((g for g in final["gates"] if g["role"] == spec.role), None)
            lines.append(f"| {spec.role} | `{spec.artifact}` | "
                         f"{gate['status'] if gate else 'missing'} | "
                         f"{'yes' if gate and gate.get('current_attempt') else 'no'} | "
                         f"{gate.get('reused_from', '') if gate else ''} |")
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
