"""Deterministic offline model placeholder used by tests and CI."""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .. import hard_blocks
from .base import ChatResult, ModelTimeout


class StubBackend:
    """Rule-based stand-in for local/remote models.

    Modes:
      good        - produce schema-valid JSON from the packet's deterministic facts
      timeout     - raise ModelTimeout
      schema_error- return invalid JSON
      rubber_stamp- approve everything (used to test canary misses)
    """
    name = "stub"

    def __init__(self, mode: str = "good") -> None:
        self.mode = mode

    def available(self) -> bool:
        return True

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None,
             response_format: str | None = None, temperature: float = 0.0,
             seed: int = 0, timeout_s: int | None = None) -> ChatResult:
        started = time.time()
        if self.mode == "timeout":
            raise ModelTimeout("stub timeout")
        text = "\n".join(m.get("content", "") for m in messages)
        if '"packet"' in text:
            obj = self._judge(self._extract_packet(text))
        else:
            role = self._role(text)
            obj = {
                "task_id": "stub-task",
                "role": role,
                "status": "done",
                "artifacts": [],
                "claims": [{"claim": "stub output", "counts_as_evidence": False}],
                "evidence_refs": [],
                "open_questions": [],
                "summary": "stub backend output",
            }
        if self.mode == "schema_error":
            content = '{"not": "a verdict"'
        else:
            content = json.dumps(obj, ensure_ascii=False)
        return ChatResult(content=content, backend=self.name, model=model or "stub",
                          model_version="stub@1", latency_ms=int((time.time() - started) * 1000),
                          response_id="stub")

    @staticmethod
    def _role(text: str) -> str:
        m = re.search(r"ROLE:\s*([a-z]+)", text)
        if m and m.group(1) in ("pm", "product", "ui", "arch", "frontend",
                                "backend", "review", "qa", "security",
                                "ops", "kb", "retro"):
            return m.group(1)
        return "product"

    @staticmethod
    def _extract_packet(text: str) -> dict[str, Any]:
        try:
            return json.loads(text).get("packet", {})
        except Exception:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0)).get("packet", {})
                except Exception:
                    pass
        return {}

    def _judge(self, packet: dict[str, Any]) -> dict[str, Any]:
        blocks = hard_blocks.evaluate(packet)
        decision = "approve"
        findings = []
        required = []
        if blocks:
            decisions = [b.action for b in blocks]
            decision = "reject" if "reject" in decisions else "need_evidence"
            findings = [{"severity": "fatal" if b.action == "reject" else "major",
                         "file": "<packet>", "evidence_ids": [b.evidence_id] if b.evidence_id else [],
                         "remediation": b.message} for b in blocks]
            required = [{"kind": m, "subject": packet.get("subject_hash", ""),
                         "command": f"run {m}", "why": "硬约束要求"} for m in packet.get("missing_evidence", [])]
        if packet.get("content_isolation", {}).get("instruction_like_blocks", 0) > 0:
            decision = "reject"
            findings.append({
                "severity": "major",
                "file": "<packet>",
                "evidence_ids": [],
                "remediation": "决策包含指令性文本，按数据隔离并拒绝自动批准",
            })
        if self.mode == "rubber_stamp":
            decision = "approve"
            findings = []
            required = []
        checks = packet.get("deterministic_checks", [])
        criteria = [{"id": c.get("kind", "check"), "score": 2 if c.get("result") == "pass" else 0,
                     "evidence_ids": [c.get("evidence_id", "")] if c.get("evidence_id") else [],
                     "note": c.get("result", "")} for c in checks]
        if not criteria:
            criteria = [{"id": "packet", "score": 2, "evidence_ids": [], "note": "no deterministic checks"}]
        expiry = int(time.time()) + 24 * 3600
        return {
            "verdict_id": f"vd-stub-{int(time.time() * 1000)}",
            "packet_hash": packet.get("packet_hash", ""),
            "decision": decision,
            "confidence": 0.95 if decision != "approve" else 0.92,
            "rubric_version": "stub@1",
            "criteria": criteria,
            "findings": findings,
            "required_evidence": required,
            "conditions": [],
            "expires_at": expiry,
            "input_hash": packet.get("subject_hash", ""),
            "judge": {"backend": "stub", "model": "stub", "version": "stub@1",
                      "prompt_hash": "stub", "temperature": 0, "seed": 0},
            "signature": "stub",
        }
