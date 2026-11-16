"""J1/J2/J3 panel with disagreement escalation and fail-closed semantics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import hard_blocks
from ..config import signing_key
from ..evidence.verdict_store import VerdictStore
from .backend import (JudgeBackend, JudgeError, JudgeUnavailable,
                      JudgeValidationError)
from .rubric import Rubric
from . import verdict as verdict_mod

APPROVE = {"approve", "approve_with_conditions"}


@dataclass
class PanelResult:
    verdict: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)
    conservative: bool = False
    disagreements: int = 0


class JudgePanel:
    def __init__(self, backend: JudgeBackend, *,
                 store: VerdictStore | None = None,
                 conservative: bool = False) -> None:
        self.backend = backend
        self.store = store
        self.conservative = conservative

    def _tiers(self, packet: dict[str, Any]) -> list[str]:
        risk = packet.get("scope", {}).get("risk", "medium")
        if packet.get("decision_type") == "release":
            return ["J2", "J3"]
        if risk in ("high", "critical") or self.conservative:
            return ["J1", "J2"]
        return ["J1"]

    def _run(self, packet: dict[str, Any], rubric: Rubric, tier: str) -> dict[str, Any]:
        try:
            return self.backend.judge(packet, rubric, tier)
        except JudgeError:
            raise
        except Exception as exc:
            raise JudgeUnavailable(f"{tier} 裁判调用失败：{exc}") from exc

    def _hard_block_verdict(self, packet: dict[str, Any], rubric: Rubric,
                            blocks: list[hard_blocks.HardBlock]) -> dict[str, Any]:
        decision = "reject" if any(b.action == "reject" for b in blocks)             else "need_evidence"
        findings = [{
            "severity": "fatal" if b.action == "reject" else "major",
            "file": "<packet>",
            "evidence_ids": [b.evidence_id] if b.evidence_id else [],
            "remediation": b.message,
        } for b in blocks]
        required = [{
            "kind": k, "subject": packet.get("subject_hash", ""),
            "command": f"run {k}", "why": "硬约束要求补充证据",
        } for k in packet.get("missing_evidence", [])]
        raw = {
            "decision": decision,
            "confidence": 1.0,
            "criteria": [],
            "findings": findings,
            "required_evidence": required,
            "conditions": [],
            "rationale": "机械硬约束在裁判之前拦截",
        }
        meta = {"backend": "gate-engine", "model": "hard-blocks",
                "version": "hard-blocks@1", "prompt_hash": "hard-blocks",
                "temperature": 0, "seed": 0, "response_id": "hard-blocks"}
        return verdict_mod.normalize_and_sign(raw, packet, rubric, meta, signing_key())

    def decide(self, packet: dict[str, Any], rubric: Rubric) -> PanelResult:
        blocks = hard_blocks.evaluate(packet)
        if blocks:
            v = self._hard_block_verdict(packet, rubric, blocks)
            trace = [{"tier": "HARD", "decision": v["decision"],
                      "model": "hard-blocks", "backend": "gate-engine",
                      "confidence": 1.0}]
            return self._finish(v, trace, 0)
        tiers = self._tiers(packet)
        trace: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        for tier in tiers:
            v = self._run(packet, rubric, tier)
            results.append(v)
            trace.append({"tier": tier, "decision": v["decision"],
                          "model": v["judge"].get("model", ""),
                          "backend": v["judge"].get("backend", ""),
                          "confidence": v["confidence"]})
        disagreements = 0
        if len(results) == 1:
            if results[0]["decision"] == "abstain":
                v = self._run(packet, rubric, "J3")
                trace.append({"tier": "J3", "decision": v["decision"],
                              "model": v["judge"].get("model", ""),
                              "backend": v["judge"].get("backend", ""),
                              "confidence": v["confidence"]})
                if v["decision"] == "abstain":
                    raise JudgeUnavailable("J3 仍为 abstain，按失败关闭处理")
                return self._finish(v, trace, disagreements)
            return self._finish(results[0], trace, disagreements)
        # Two judges: agree -> use J1; disagree -> J3.
        a, b = results[0], results[1]
        same_side = (a["decision"] in APPROVE) == (b["decision"] in APPROVE)
        if same_side and a["decision"] == b["decision"]:
            return self._finish(a, trace, disagreements)
        if same_side:
            return self._finish(a, trace, disagreements)
        disagreements += 1
        if "J3" not in tiers:
            v = self._run(packet, rubric, "J3")
            results.append(v)
            trace.append({"tier": "J3", "decision": v["decision"],
                          "model": v["judge"].get("model", ""),
                          "backend": v["judge"].get("backend", ""),
                          "confidence": v["confidence"]})
        if results[-1]["decision"] == "abstain":
            raise JudgeUnavailable("J3 仍为 abstain，按失败关闭处理")
        return self._finish(results[-1], trace, disagreements)

    def _finish(self, verdict: dict[str, Any], trace: list[dict[str, Any]],
                disagreements: int) -> PanelResult:
        if verdict["decision"] == "abstain":
            raise JudgeUnavailable("裁判 abstain，按失败关闭处理")
        if self.store is not None:
            record = dict(verdict)
            record["panel_trace"] = trace
            self.store.put(record)
        return PanelResult(verdict=verdict, trace=trace,
                           conservative=self.conservative,
                           disagreements=disagreements)

    def one(self, packet: dict[str, Any], rubric: Rubric,
            tier: str = "J1") -> dict[str, Any]:
        return self._run(packet, rubric, tier)

    def revalidate(self, plan: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self.backend.revalidate(plan, packet, tier="J3")
        except JudgeError:
            raise
        except Exception as exc:
            raise JudgeUnavailable(f"复核计划裁判失败：{exc}") from exc
        if result.get("removed_checks"):
            raise JudgeValidationError("复核裁判试图删除强制检查，拒绝")
        if result.get("base_plan_hash") != plan.get("base_plan_hash"):
            raise JudgeValidationError("复核裁决的 base_plan_hash 与当前计划不一致")
        return result
