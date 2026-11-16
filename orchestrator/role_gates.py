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

from .decisions import DecisionStore

ROLE_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "pm": {"all": ["切片"], "any": ["依赖", "顺序", "门禁"]},
    "product": {"all": ["验收"], "any": ["非目标", "不做", "范围"]},
    "ui": {"all": ["状态"], "any": ["可访问", "对比度", "空", "加载"]},
    "arch": {"all": ["契约"], "any": ["错误", "不变量", "接口"]},
    "review": {"all": [], "any": ["问题", "finding", "风险", "整改"]},
    "qa": {"all": ["用例"], "any": ["异常", "边界", "权限"]},
    "security": {"all": ["威胁"], "any": ["缓解", "风险", "验证"]},
    "ops": {"all": ["回滚"], "any": ["监控", "灰度", "演练"]},
    "kb": {"all": [], "any": ["知识", "复用", "决策", "踩坑"]},
    "retro": {"all": ["根因"], "any": ["行动", "改进", "验证"]},
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
    status: str                      # pass | fail | need_evidence
    checks: list[GateCheck]
    evidence_ids: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    decision_id: str | None = None
    subject_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id, "role": self.role, "status": self.status,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail}
                       for c in self.checks],
            "evidence_ids": self.evidence_ids, "missing": self.missing,
            "decision_id": self.decision_id, "subject_hash": self.subject_hash,
        }


def _text_of(obj: dict[str, Any]) -> str:
    parts = [str(obj.get("summary", ""))]
    parts += [str(c.get("claim", "")) for c in obj.get("claims") or []]
    parts += [str(q) for q in obj.get("open_questions") or []]
    return "\n".join(parts)


def _artifact_present(project: Path, role: str,
                     files: list[dict[str, Any]]) -> tuple[bool, str]:
    expected = ARTIFACT_PATHS.get(role, ())
    if not expected:
        return True, "no required artifact"
    authored = {str(f.get("path", "")).replace("\\", "/") for f in files
                if f.get("source", "role") == "role"}
    for exp in expected:
        if exp.endswith("/"):
            if any(p.startswith(exp) for p in authored) or any(
                    p.startswith(exp) for p in _disk_files(project, exp)):
                return True, exp
        elif exp in authored:
            return True, exp
        elif (project / exp).is_file() and _usable_doc(project / exp):
            return True, exp
    return False, ", ".join(expected)


def _usable_doc(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:5000].lower()
    except OSError:
        return False
    return "todo" not in text and "scaffold" not in text


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


def evaluate_role(role: str, obj: dict[str, Any], *,
                  project_dir: str | Path,
                  files: list[dict[str, Any]],
                  tool_result: dict[str, Any] | None = None,
                  profile: str = "basic",
                  decision_store: DecisionStore | None = None,
                  project_name: str = "",
                  baseline_fp: str = "") -> GateResult:
    project = Path(project_dir)
    gate_id = f"G-{_slug(project_name or project.name)}-{role}"
    checks: list[GateCheck] = []
    missing: list[str] = []
    evidence_ids: list[str] = []

    checks.append(GateCheck("role_matches", obj.get("role") == role,
                            f"{obj.get('role')} != {role}" if obj.get("role") != role else ""))
    checks.append(GateCheck("status_not_blocked", obj.get("status") != "blocked",
                            str(obj.get("status"))))
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

    present, where = _artifact_present(project, role, files)
    checks.append(GateCheck("artifact", present, where))

    if role in CODE_ROLES:
        authored = [f for f in files if f.get("source", "role") == "role"]
        checks.append(GateCheck("files_written", bool(authored),
                                "代码角色没有写出文件"))
        if not tool_result:
            missing.extend(sorted(_required_kinds(profile)))
            missing.append("tool_evidence")
            checks.append(GateCheck("tool_evidence", False, "没有执行工具证据"))
        else:
            required = _required_kinds(profile)
            for kind in sorted(required):
                status, ev = _evidence_status(tool_result.get("evidence", []), kind)
                if ev:
                    evidence_ids.append(ev)
                if status == "missing":
                    missing.append(kind)
                checks.append(GateCheck(f"evidence:{kind}", status == "pass",
                                        "缺少" if status == "missing" else status))
            subject = str(tool_result.get("subject_hash", ""))
            if subject:
                checks.append(GateCheck("evidence_subject", bool(subject), subject))

    failed = [c for c in checks if not c.ok]
    if not failed:
        status = "pass"
    elif missing or any(c.name.startswith("evidence:") and c.detail == "缺少"
                        for c in failed):
        status = "need_evidence"
    else:
        status = "fail"

    result = GateResult(gate_id=gate_id, role=role, status=status,
                        checks=checks, evidence_ids=evidence_ids,
                        missing=missing,
                        subject_hash=str((tool_result or {}).get("subject_hash", "")))
    if status != "pass" and decision_store is not None:
        result.decision_id = _escalate(result, decision_store, obj, project_name, baseline_fp)
    return result


def _required_kinds(profile: str) -> set[str]:
    if profile == "basic":
        return {"compile", "unit"}
    if profile == "standard":
        return {"compile", "unit", "sast", "contract_test"}
    return {"compile", "unit", "sast", "contract_test", "secret_scan"}


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
