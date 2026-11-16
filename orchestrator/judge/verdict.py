"""Verdict normalization, schema validation and signing."""
from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

import jsonschema

from .. import hard_blocks
from ..config import load_schema
from ..evidence.signing import sign_object, verify_object

VERDICT_SCHEMA = load_schema("verdict.schema.json")
ALLOWED_DECISIONS = {"approve", "approve_with_conditions", "need_evidence",
                     "reject", "defer", "abstain"}

SEVERITY_MAP = {
    "critical": "fatal", "fatal": "fatal",
    "high": "major", "major": "major",
    "medium": "minor", "low": "minor", "minor": "minor",
    "info": "suggestion", "suggestion": "suggestion",
}


def repair_raw_verdict(raw: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    """Repair only cosmetic schema deviations from local models.

    Never changes decision, confidence, or evidence identity. Every repair is
    counted in `schema_repairs` for audit.
    """
    out = dict(raw)
    repairs = 0
    criteria = []
    for i, c in enumerate(out.get("criteria") or []):
        if not isinstance(c, dict):
            repairs += 1
            continue
        try:
            score = int(c.get("score", 1))
        except (TypeError, ValueError):
            score = 1
        score = max(0, min(2, score))
        item = {
            "id": str(c.get("id") or f"criterion-{i + 1}"),
            "score": score,
            "evidence_ids": [str(x) for x in (c.get("evidence_ids") or [])
                             if isinstance(x, str)],
            "note": str(c.get("note", "")),
        }
        if set(c) - {"id", "score", "evidence_ids", "note"} or score != c.get("score"):
            repairs += 1
        criteria.append(item)
    out["criteria"] = criteria
    findings = []
    for f in out.get("findings") or []:
        if not isinstance(f, dict):
            repairs += 1
            continue
        raw_sev = str(f.get("severity", "major")).lower()
        sev = SEVERITY_MAP.get(raw_sev, "major")
        item = {
            "severity": sev,
            "file": str(f.get("file", "<packet>")),
            "evidence_ids": [str(x) for x in (f.get("evidence_ids") or [])
                             if isinstance(x, str)],
            "remediation": str(f.get("remediation", "")),
        }
        line = f.get("line")
        if isinstance(line, int) and line >= 1:
            item["line"] = line
        if sev != raw_sev or set(f) - {"severity", "file", "line",
                                       "evidence_ids", "remediation"}:
            repairs += 1
        findings.append(item)
    out["findings"] = findings
    required = []
    for r in out.get("required_evidence") or []:
        if not isinstance(r, dict) or not r.get("kind"):
            repairs += 1
            continue
        item = {
            "kind": str(r["kind"]),
            "subject": str(r.get("subject") or packet.get("subject_hash", "")),
            "command": str(r.get("command") or f"run {r['kind']}"),
            "why": str(r.get("why") or "缺少该证据"),
        }
        if set(r) - {"kind", "subject", "command", "why"}:
            repairs += 1
        required.append(item)
    if out.get("decision") == "need_evidence" and not required             and packet.get("missing_evidence"):
        required = [{"kind": k, "subject": packet.get("subject_hash", ""),
                     "command": f"run {k}", "why": "缺少该证据"}
                    for k in packet["missing_evidence"]]
        repairs += 1
    out["required_evidence"] = required
    if repairs:
        out["schema_repairs"] = int(raw.get("schema_repairs", 0)) + repairs
    return out


class VerdictValidationError(ValueError):
    pass


def normalize_and_sign(raw: dict[str, Any], packet: dict[str, Any], rubric,
                       judge_meta: dict[str, Any], key: bytes,
                       *, ttl_s: int = 24 * 3600, now: int | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise VerdictValidationError("裁决必须是 JSON 对象")
    now = int(time.time()) if now is None else now
    raw = repair_raw_verdict(raw, packet)
    decision = str(raw.get("decision", ""))
    if decision not in ALLOWED_DECISIONS:
        raise VerdictValidationError(f"非法裁决：{decision!r}")
    verdict = {
        "verdict_id": raw.get("verdict_id") or f"vd-{uuid4().hex[:12]}",
        "packet_hash": packet["packet_hash"],
        "decision": decision,
        "confidence": float(raw.get("confidence", 0.0)),
        "rubric_version": f"{rubric.id}@{rubric.version}",
        "criteria": list(raw.get("criteria") or []),
        "findings": list(raw.get("findings") or []),
        "required_evidence": list(raw.get("required_evidence") or []),
        "conditions": list(raw.get("conditions") or []),
        "expires_at": int(raw.get("expires_at") or (now + ttl_s)),
        "input_hash": packet.get("subject_hash", ""),
        "judge": {**judge_meta},
        "signature": "",
    }
    if raw.get("rationale"):
        verdict["rationale"] = str(raw["rationale"])
    if raw.get("schema_repairs"):
        verdict["schema_repairs"] = int(raw["schema_repairs"])
    signed = sign_object(verdict, key)
    validate_verdict(signed, packet, key, rubric=rubric, now=now)
    return signed


def validate_verdict(verdict: dict[str, Any], packet: dict[str, Any], key: bytes,
                     *, rubric=None, now: int | None = None) -> None:
    try:
        jsonschema.validate(verdict, VERDICT_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise VerdictValidationError(f"裁决 schema 不合法：{exc.message}") from exc
    if verdict["packet_hash"] != packet.get("packet_hash"):
        raise VerdictValidationError("裁决 packet_hash 与决策包不一致")
    if not verify_object(verdict, key):
        raise VerdictValidationError("裁决签名无效")
    now = int(time.time()) if now is None else now
    if verdict["expires_at"] <= now:
        raise VerdictValidationError("裁决已过期")
    if verdict["decision"] in ("approve", "approve_with_conditions") \
            and verdict["expires_at"] <= now:
        raise VerdictValidationError("批准类裁决必须带未来有效期")

    blocks = hard_blocks.evaluate(packet)
    evidence_ids = {c.get("evidence_id") for c in packet.get("deterministic_checks", [])}
    for criterion in verdict.get("criteria", []):
        for eid in criterion.get("evidence_ids", []):
            if eid and eid not in evidence_ids:
                raise VerdictValidationError(f"引用了不存在的证据：{eid}")
    for finding in verdict.get("findings", []):
        for eid in finding.get("evidence_ids", []):
            if eid and eid not in evidence_ids:
                raise VerdictValidationError(f"findings 引用了不存在的证据：{eid}")

    if verdict["decision"] == "approve":
        if blocks:
            raise VerdictValidationError(
                "存在硬约束阻断项，裁判不得 approve：" +
                "; ".join(b.code for b in blocks))
        if packet.get("missing_evidence"):
            raise VerdictValidationError("存在缺失证据，裁判不得 approve")
        if any(c.get("result") != "pass" for c in packet.get("deterministic_checks", [])):
            raise VerdictValidationError("存在未通过的确定性检查，裁判不得 approve")
        if verdict["confidence"] < 0.7:
            raise VerdictValidationError("approve 置信度低于 0.7")
        if not any(c.get("evidence_ids") for c in verdict.get("criteria", [])):
            raise VerdictValidationError("approve 必须引用至少一条证据")
    elif verdict["decision"] == "approve_with_conditions":
        if blocks:
            raise VerdictValidationError("存在硬约束阻断项，不得条件批准")
        if not verdict.get("conditions"):
            raise VerdictValidationError("条件批准必须列出条件")
        if packet.get("scope", {}).get("risk") in ("high", "critical"):
            raise VerdictValidationError("高风险事项不允许条件批准")
        if verdict["confidence"] < 0.7:
            raise VerdictValidationError("条件批准置信度低于 0.7")
    elif verdict["decision"] == "reject":
        if not verdict.get("findings"):
            raise VerdictValidationError("reject 必须给出 findings")
    elif verdict["decision"] == "need_evidence":
        if not verdict.get("required_evidence"):
            raise VerdictValidationError("need_evidence 必须列出具体检查")
    elif verdict["decision"] == "abstain":
        pass


def verdict_template(*, packet: dict[str, Any], decision: str,
                     criteria: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Un-signed template used by tests; callers must sign it."""
    return {
        "verdict_id": f"vd-{uuid4().hex[:12]}",
        "packet_hash": packet["packet_hash"],
        "decision": decision,
        "confidence": 0.9,
        "rubric_version": "rubric/test@1",
        "criteria": criteria or [],
        "findings": [],
        "required_evidence": [],
        "conditions": [],
        "expires_at": int(time.time()) + 3600,
        "input_hash": packet.get("subject_hash", ""),
        "judge": {"backend": "test", "model": "test", "version": "test@1",
                  "prompt_hash": "test", "temperature": 0, "seed": 0},
        "signature": "",
    }
