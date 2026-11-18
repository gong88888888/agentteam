"""Bridge a deterministic role gate to the existing J1/J2/J3 panel.

The deterministic gate runs first. A judge never sees a packet that already
failed a hard check, and its verdict can only block, not approve, a failed
gate. Judge unavailability is fail-closed when this layer is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..evidence.signing import sha256_hex
from ..role_gates import GateResult
from .panel import JudgePanel
from .packet import build_packet
from .rubric import rubric_for_gate

APPROVE = {"approve", "approve_with_conditions"}


@dataclass
class RoleJudgeResult:
    decision: str
    verdict: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    @property
    def approved(self) -> bool:
        return self.decision in APPROVE

    def to_dict(self) -> dict[str, Any]:
        return {"decision": self.decision, "approved": self.approved,
                "verdict": self.verdict, "trace": self.trace,
                "error": self.error}


def build_role_packet(*, role: str, obj: dict[str, Any], gate: GateResult,
                      tool_result: dict[str, Any] | None,
                      project_id: str, baseline_fp: str,
                      risk: str = "medium",
                      files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    verified = set(gate.evidence_verified)
    checks = []
    for row in (tool_result or {}).get("evidence", []):
        evidence_id = str(row.get("evidence_id", ""))
        if evidence_id not in verified:
            continue
        checks.append({
            "evidence_id": evidence_id,
            "kind": str(row.get("kind", "unknown")),
            "result": "pass" if row.get("result") == "pass" else "fail",
            "tool": str(row.get("tool", "unknown")),
            "tool_version": str(row.get("tool_version", "")),
            "signed_by": str(row.get("signed_by", "tool:unknown")),
        })
    inputs = [{"path": str(f.get("path", "")),
               "sha256": str(f.get("sha256", "")),
               "signed_by": "tool:fs"}
              for f in (files or []) if isinstance(f, dict)]
    if not inputs:
        inputs = [{"path": "<role-output>", "sha256": sha256_hex(obj)[:32],
                   "signed_by": "tool:fs"}]
    claims = [{"claim": str(c.get("claim", "")), "signed_by": "agent:" + role}
              for c in obj.get("claims") or [] if isinstance(c, dict)]
    return build_packet(
        gate_id=gate.gate_id, decision_type="gate",
        scope={"project": project_id, "slice": role, "risk": risk},
        baseline_versions={"requirement": baseline_fp[:16] or "unknown",
                           "gate": gate.gate_id},
        baseline_fp=baseline_fp or "project",
        subject_hash=gate.subject_hash or sha256_hex(obj)[:32],
        inputs=inputs, checks=checks, missing_evidence=list(gate.missing),
        acceptance=[c.name for c in gate.checks if c.ok],
        diff={"out_of_scope_writes": 0},
        risk={"level": risk, "factors": ["signed_tool_evidence",
                                         "role:" + role]},
        claims=claims)


def review_role(*, role: str, obj: dict[str, Any], gate: GateResult,
                tool_result: dict[str, Any] | None, project_id: str,
                baseline_fp: str, panel: JudgePanel,
                risk: str = "medium",
                files: list[dict[str, Any]] | None = None) -> RoleJudgeResult:
    if gate.status != "pass":
        return RoleJudgeResult(decision="not_run",
                               error="确定性门禁未通过，裁判不得批准")
    try:
        packet = build_role_packet(
            role=role, obj=obj, gate=gate, tool_result=tool_result,
            project_id=project_id, baseline_fp=baseline_fp, risk=risk,
            files=files)
        rubric = rubric_for_gate(gate.gate_id)
        result = panel.decide(packet, rubric)
        verdict = result.verdict or {}
        return RoleJudgeResult(decision=str(verdict.get("decision", "abstain")),
                               verdict=verdict, trace=result.trace)
    except Exception as exc:
        return RoleJudgeResult(decision="unavailable", error=str(exc)[:500])
