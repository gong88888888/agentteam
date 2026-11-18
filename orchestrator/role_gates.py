"""Deterministic role gates + decision-inbox escalation.

Gates consume the role envelope and signed tool evidence only. They never read
self-reported claims as proof. Failures are fail-closed and can be escalated to
the decision inbox with a stable decision id.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import signing_key
from .decisions import DecisionStore
from .evidence.resolver import EvidenceResolutionError, EvidenceResolver

ROLE_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "pm": {"all": [], "any": ["切片", "模块", "阶段", "计划", "路线"]},
    "product": {"all": ["验收"], "any": ["非目标", "不做", "范围"]},
    "ui": {"all": [], "any": ["状态", "交互", "流程", "设计规范", "设计 token", "token"]},
    "arch": {"all": [], "any": ["契约", "接口", "状态机", "错误", "不变量", "事件"]},
    "review": {"all": [], "any": ["问题", "finding", "风险", "整改"]},
    "qa": {"all": [], "any": ["用例", "测试", "断言", "不变量", "测试计划", "证据"]},
    "security": {"all": ["威胁"], "any": ["缓解", "风险", "验证"]},
    "ops": {"all": [], "any": ["回滚", "监控", "灰度", "演练", "备份", "发布", "快照"]},
    "kb": {"all": [], "any": ["知识", "复用", "决策", "踩坑"]},
    "retro": {"all": [], "any": ["根因", "偏差", "问题", "风险", "行动", "改进", "建议"]},
}

ARTIFACT_GAME: dict[str, tuple[str, ...]] = {
    "backend": ("game/js/gameplay/",),
    "frontend": ("game/js/ui/", "game/css/"),
    "arch": ("docs/architecture/architecture.md",),
    "ui": ("docs/design/ui-spec.md",),
    "qa": ("game/tests/", "tests/test-plan.md"),
    "ops": ("docs/ops/release-plan.md",),
}

ARTIFACT_PATHS: dict[str, tuple[str, ...]] = {
    "pm": ("docs/plan/project-plan.md",),
    "product": ("docs/product/product-baseline.md",),
    "ui": ("docs/design/ui-spec.md",),
    "arch": ("docs/architecture/architecture.md", "contracts/openapi.yaml"),
    "backend": ("src/backend/",),
    "frontend": ("src/frontend/",),
    "review": ("docs/reviews/review.md",),
    "qa": ("tests/test-plan.md",),
    "security": ("docs/security/threat-model.md",),
    "ops": ("docs/ops/release-plan.md",),
    "kb": ("knowledge/project-notes.md",),
    "retro": ("docs/retro/retro.md",),
}

CODE_ROLES = {"backend", "frontend"}
HIGH_RISK_ROLES = {"backend", "frontend", "security", "ops"}


@dataclass
class GateCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class GateResult:
    gate_id: str
    role: str
    status: str                      # pass | fail | need_evidence | stale
    checks: list[GateCheck]
    evidence_ids: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    decision_id: str | None = None
    subject_hash: str = ""
    evidence_verified: list[str] = field(default_factory=list)
    evidence_errors: list[dict[str, str]] = field(default_factory=list)
    trust: str = "unverified"        # verified | legacy_unverified | unverified
    legacy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id, "role": self.role, "status": self.status,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail}
                       for c in self.checks],
            "evidence_ids": self.evidence_ids, "missing": self.missing,
            "decision_id": self.decision_id, "subject_hash": self.subject_hash,
            "evidence_verified": self.evidence_verified,
            "evidence_errors": self.evidence_errors,
            "trust": self.trust, "legacy": self.legacy,
        }


def _text_of(obj: dict[str, Any]) -> str:
    parts = [str(obj.get("summary", ""))]
    parts += [str(c.get("claim", "")) for c in obj.get("claims") or []]
    parts += [str(q) for q in obj.get("open_questions") or []]
    return "\n".join(parts)


def _artifact_present(project: Path, role: str,
                     files: list[dict[str, Any]],
                     project_type: str = "web",
                     files_root: Path | None = None) -> tuple[bool, str]:
    expected = (ARTIFACT_GAME.get(role, ARTIFACT_PATHS.get(role, ()))
                if project_type == "game" else ARTIFACT_PATHS.get(role, ()))
    if not expected:
        return True, "no required artifact"
    authored_root = files_root or project
    authored = {str(f.get("path", "")).replace("\\", "/") for f in files
                if f.get("source", "role") == "role"}
    summary_paths = {str(f.get("path", "")).replace("\\", "/") for f in files
                     if f.get("source") == "runner-summary"}
    for exp in expected:
        if exp.endswith("/"):
            if any(p.startswith(exp) and _usable_code(authored_root / p) for p in authored):
                return True, exp
            disk = [p for p in _disk_files(project, exp) if p not in summary_paths
                    and _usable_code(project / p)]
            if disk:
                return True, exp
        elif exp in authored:
            if _usable_doc(authored_root / exp):
                return True, exp
        elif exp not in summary_paths and (project / exp).is_file() \
                and _usable_doc(project / exp):
            return True, exp
    return False, ", ".join(expected)


def _usable_doc(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return False
    lowered = text.lower()
    if len(text) < 25 or "todo" in lowered or "scaffold" in lowered:
        return False
    content_lines = [line.strip() for line in text.splitlines()
                     if line.strip() and not line.lstrip().startswith("#")]
    return len(" ".join(content_lines)) >= 25


def _usable_code(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return False
    return len(text) >= 10 and not text.lower().startswith("todo")


def _disk_files(project: Path, prefix: str) -> list[str]:
    base = project / prefix.rstrip("/")
    if not base.exists():
        return []
    return [p.relative_to(project).as_posix() for p in base.rglob("*") if p.is_file()]


def _evidence_status(evidence: list[dict[str, Any]], kind: str) -> tuple[str, str]:
    rows = [e for e in evidence if e.get("kind") == kind]
    if not rows:
        return "missing", "没有该证据"
    last = rows[-1]
    return last.get("result", "fail"), last.get("evidence_id", "")


def _auto_resolver(tool_result: dict[str, Any] | None) -> EvidenceResolver | None:
    ledger = str((tool_result or {}).get("ledger", "") or "")
    if not ledger:
        return None
    try:
        if not Path(ledger).is_file():
            return None
        return EvidenceResolver(ledger, signing_key())
    except Exception:
        return None


def _resolve_tool_evidence(role: str, profile: str,
                           tool_result: dict[str, Any],
                           resolver: EvidenceResolver | None,
                           *, baseline_fp: str,
                           allow_legacy_unverified: bool,
                           checks: list[GateCheck], missing: list[str],
                           evidence_ids: list[str], verified: list[str],
                           errors: list[dict[str, str]]) -> str:
    required = _required_kinds(profile, role)
    rows = tool_result.get("evidence") or []
    subject = str(tool_result.get("subject_hash", "") or "")
    if not subject:
        missing.append("subject_hash")
        checks.append(GateCheck("evidence_subject", False,
                                "没有对象指纹，证据无法绑定当前对象"))
    if resolver is None:
        if allow_legacy_unverified:
            for kind in sorted(required):
                status, ev = _evidence_status(rows, kind)
                if ev:
                    evidence_ids.append(ev)
                if status == "missing":
                    missing.append(kind)
                checks.append(GateCheck(f"evidence:{kind}", status == "pass",
                                        "缺少" if status == "missing" else status))
            checks.append(GateCheck("evidence_trusted", True,
                                    "legacy_unverified：显式兼容模式，未在账本中复核"))
            return "legacy_unverified"
        missing.extend(sorted(required))
        missing.append("evidence_ledger")
        checks.append(GateCheck("evidence_trusted", False,
                                "没有可信 EvidenceResolver / 签名账本；"
                                "原始 result=pass 字典不能作为门禁证据"))
        return "unverified"
    for kind in sorted(required):
        candidates = [e for e in rows if e.get("kind") == kind
                      and e.get("result") == "pass" and e.get("evidence_id")]
        if not candidates:
            failed_rows = [e for e in rows if e.get("kind") == kind]
            if failed_rows:
                checks.append(GateCheck(f"evidence:{kind}", False,
                                        str(failed_rows[-1].get("result", "fail"))))
            else:
                missing.append(kind)
                checks.append(GateCheck(f"evidence:{kind}", False, "缺少"))
            continue
        resolved = None
        last_error: EvidenceResolutionError | None = None
        for row in reversed(candidates):
            try:
                resolved = resolver.resolve(
                    str(row["evidence_id"]), kind=kind,
                    subject_hash=subject or None,
                    baseline_fp=baseline_fp or None)
                break
            except EvidenceResolutionError as exc:
                last_error = exc
                errors.append(exc.to_dict())
        if resolved is not None:
            evidence_ids.append(resolved.evidence_id)
            verified.append(resolved.evidence_id)
            checks.append(GateCheck(f"evidence:{kind}", resolved.result == "pass",
                                    f"verified {resolved.evidence_id}"))
        else:
            code = last_error.code if last_error else "not_found"
            evidence_ids.append(str(candidates[-1]["evidence_id"]))
            if code in ("not_found", "expired_or_revoked", "ledger_integrity"):
                missing.append(kind)
            checks.append(GateCheck(f"evidence:{kind}", False,
                                    f"{code}: {last_error}" if last_error else code))
    if verified:
        checks.append(GateCheck("evidence_trusted", True,
                                f"{len(verified)} 条证据已在签名账本中复核"))
    return "verified"


def evaluate_role(role: str, obj: dict[str, Any], *,
                  project_dir: str | Path,
                  files: list[dict[str, Any]],
                  tool_result: dict[str, Any] | None = None,
                  profile: str = "basic",
                  decision_store: DecisionStore | None = None,
                  project_name: str = "",
                  baseline_fp: str = "",
                  project_type: str = "web",
                  evidence_resolver: EvidenceResolver | None = None,
                  allow_legacy_unverified: bool = False,
                  files_root: str | Path | None = None) -> GateResult:
    project = Path(project_dir)
    file_base = Path(files_root) if files_root else project
    gate_id = f"G-{_slug(project_name or project.name)}-{role}"
    checks: list[GateCheck] = []
    missing: list[str] = []
    evidence_ids: list[str] = []
    verified: list[str] = []
    evidence_errors: list[dict[str, str]] = []
    trust = "not_required"

    checks.append(GateCheck("role_matches", obj.get("role") == role,
                            f"{obj.get('role')} != {role}" if obj.get("role") != role else ""))
    checks.append(GateCheck("status_done", obj.get("status") == "done",
                            f"status={obj.get('status')!r}；非 done 不能作为正式通过"))
    checks.append(GateCheck("summary_present", len(str(obj.get("summary", "")).strip()) >= 12,
                            "summary 过短或缺失"))

    rules = ROLE_KEYWORDS.get(role)
    if rules:
        text = _text_of(obj)
        for kw in rules.get("all", []):
            checks.append(GateCheck(f"keyword:{kw}", kw.lower() in text.lower(),
                                    "缺少必需内容"))
        any_kw = rules.get("any", [])
        if any_kw:
            checks.append(GateCheck("keyword:any", any(k.lower() in text.lower()
                                                       for k in any_kw),
                                    "缺少任一预期内容：" + "/".join(any_kw)))

    present, where = _artifact_present(project, role, files, project_type,
                                        files_root=file_base)
    checks.append(GateCheck("artifact", present, where))
    if files and all(f.get("source") == "runner-summary" for f in files):
        checks.append(GateCheck("artifact_provenance", False,
                                "只有 runner-summary 补写文档，不是模型专业产物"))
    else:
        checks.append(GateCheck("artifact_provenance", True, "产物来源可接受"))
    missing_files = []
    for f in files:
        if f.get("source") != "role":
            continue
        path = file_base / str(f.get("path", ""))
        if not path.is_file() or path.stat().st_size == 0:
            missing_files.append(str(f.get("path", "")))
    checks.append(GateCheck("files_nonempty", not missing_files,
                            ("缺失或空文件：" + ", ".join(missing_files))
                            if missing_files else "作者产物非空"))

    if project_type == "game" and role in ("product", "arch"):
        doc_rel = "docs/product/product-baseline.md" if role == "product" else "docs/architecture/architecture.md"
        doc_path = project / doc_rel
        doc_text = doc_path.read_text(encoding="utf-8", errors="replace") if doc_path.exists() else ""
        required = (["流程", "房间", "职业", "装备", "存档", "验收", "非目标"]
                    if role == "product" else
                    ["模块", "契约", "存档", "测试"])
        missing_terms = [term for term in required if term not in doc_text]
        min_chars = 4000 if role == "product" else 2500
        checks.append(GateCheck("deep_brief", not missing_terms and len(doc_text) >= min_chars,
                                f"缺少章节 {missing_terms}；长度 {len(doc_text)}/{min_chars}"))

    if role in CODE_ROLES:
        authored = [f for f in files if f.get("source", "role") == "role"]
        checks.append(GateCheck("files_written", bool(authored),
                                "代码角色没有写出文件"))
        if project_type == "game":
            checks.append(GateCheck("game_artifact", present,
                                    "游戏角色必须在 game/ 下写出增量模块"))
        elif not tool_result:
            missing.extend(sorted(_required_kinds(profile, role)))
            missing.append("tool_evidence")
            checks.append(GateCheck("tool_evidence", False, "没有执行工具证据"))
            trust = "unverified"
        else:
            resolver = evidence_resolver or _auto_resolver(tool_result)
            trust = _resolve_tool_evidence(
                role, profile, tool_result, resolver,
                baseline_fp=baseline_fp,
                allow_legacy_unverified=allow_legacy_unverified,
                checks=checks, missing=missing, evidence_ids=evidence_ids,
                verified=verified, errors=evidence_errors)

    failed = [c for c in checks if not c.ok]
    hard_evidence_fail = any(
        e.get("code") in ("signature_invalid", "subject_mismatch",
                          "baseline_mismatch", "kind_mismatch")
        for e in evidence_errors)
    if not failed:
        status = "pass"
    elif hard_evidence_fail:
        status = "fail"
    elif missing or any(c.name.startswith("evidence:") and c.detail == "缺少"
                        for c in failed):
        status = "need_evidence"
    else:
        status = "fail"

    result = GateResult(gate_id=gate_id, role=role, status=status,
                        checks=checks, evidence_ids=evidence_ids,
                        missing=missing,
                        subject_hash=str((tool_result or {}).get("subject_hash", "")),
                        evidence_verified=verified,
                        evidence_errors=evidence_errors,
                        trust=trust,
                        legacy=(trust == "legacy_unverified"))
    if status != "pass" and decision_store is not None:
        result.decision_id = _escalate(result, decision_store, obj, project_name, baseline_fp)
    return result


def _required_kinds(profile: str, role: str = "") -> set[str]:
    if profile == "basic":
        return {"unit"} if role == "frontend" else {"compile", "unit"}
    if profile == "standard":
        base = {"unit", "sast", "contract_test"}
        return base if role == "frontend" else base | {"compile"}
    base = {"unit", "sast", "contract_test", "secret_scan"}
    return base if role == "frontend" else base | {"compile"}


def _slug(value: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()
    return s[:32] or "PROJECT"


def _escalate(result: GateResult, store: DecisionStore, obj: dict[str, Any],
              project_name: str, baseline_fp: str) -> str:
    decision_id = f"DEC-{_slug(project_name)}-{_slug(result.role)}"
    risk = "high" if result.role in HIGH_RISK_ROLES else "medium"
    failed = [{"name": c.name, "detail": c.detail} for c in result.checks if not c.ok]
    packet = {
        "gate_id": result.gate_id,
        "scope": {"project": project_name, "role": result.role, "risk": risk},
        "baseline_fp": baseline_fp,
        "subject_hash": result.subject_hash,
        "deterministic_checks": failed,
        "missing_evidence": result.missing,
        "role_summary": str(obj.get("summary", ""))[:1000],
        "evidence_ids": result.evidence_ids,
        "evidence_verified": result.evidence_verified,
        "evidence_errors": result.evidence_errors,
        "evidence_trust": result.trust,
    }
    options = [
        {"id": "A", "summary": "补证据/修正后重跑该角色", "cost": "低",
         "risk": "低", "reversible": True},
        {"id": "B", "summary": "带条件接受并记录豁免（需理由）", "cost": "低",
         "risk": "中", "reversible": True},
        {"id": "C", "summary": "阻塞当前切片，等待上游修复", "cost": "中",
         "risk": "低", "reversible": True},
    ]
    rec = store.create(
        decision_id=decision_id, gate_id=result.gate_id,
        title=f"{project_name} · {result.role} 门禁未通过（{result.status}）",
        scope=packet["scope"], risk=risk, options=options, packet=packet,
        verdicts=[], evidence=[{"evidence_id": e} for e in result.evidence_ids],
        recommendation="按检查项修正后重跑；不要用摘要代替工具证据。",
    )
    return str(rec.get("id", decision_id)) if rec else decision_id
