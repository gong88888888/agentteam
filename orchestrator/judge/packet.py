"""Decision packet construction, sanitization and schema validation."""
from __future__ import annotations

import json
import re
import time
from typing import Any
from uuid import uuid4

import jsonschema

from ..config import load_schema
from ..evidence.signing import sha256_hex

PACKET_SCHEMA = load_schema("decision-packet.schema.json")

INSTRUCTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+(rules|instructions)", re.I),
    re.compile(r"(忽略|无视)(以上|之前|所有)?(规则|指令|要求)"),
    re.compile(r"(请|必须|直接)(批准|通过|放行)"),
    re.compile(r"(approve|accept)\s+(this|the)\s+(packet|change|pr)", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"override\s+(the\s+)?(rubric|rules)", re.I),
]


def sanitize_text(text: str) -> tuple[str, int]:
    count = 0
    out = text
    for pat in INSTRUCTION_PATTERNS:
        out, n = pat.subn("[BLOCKED_INSTRUCTION]", out)
        count += n
    return out, count


def packet_hash(packet: dict[str, Any]) -> str:
    tmp = dict(packet)
    tmp.pop("packet_hash", None)
    return sha256_hex(tmp)


def build_packet(*, gate_id: str, decision_type: str, scope: dict[str, Any],
                 baseline_versions: dict[str, str], baseline_fp: str,
                 subject_hash: str, inputs: list[dict[str, Any]],
                 checks: list[dict[str, Any]], missing_evidence: list[str],
                 acceptance: list[str] | None = None,
                 diff: dict[str, Any] | None = None,
                 risk: dict[str, Any] | None = None,
                 claims: list[dict[str, Any]] | None = None,
                 policy_refs: list[str] | None = None,
                 budget: dict[str, Any] | None = None,
                 options: list[dict[str, Any]] | None = None,
                 max_packet_bytes: int = 200_000) -> dict[str, Any]:
    """Build the only input a judge sees. Code/docs are represented by hashes."""
    sanitized_claims: list[dict[str, Any]] = []
    injection_count = 0
    for claim in claims or []:
        text, n = sanitize_text(str(claim.get("claim", "")))
        injection_count += n
        sanitized_claims.append({
            "claim": text,
            "signed_by": str(claim.get("signed_by", "agent")),
            "counts_as_evidence": False,
        })
    packet = {
        "packet_id": f"pkt-{gate_id}-{uuid4().hex[:8]}",
        "gate_id": gate_id,
        "decision_type": decision_type,
        "scope": scope,
        "baseline_versions": baseline_versions,
        "baseline_fp": baseline_fp,
        "subject_hash": subject_hash,
        "inputs": inputs,
        "deterministic_checks": checks,
        "missing_evidence": missing_evidence,
        "acceptance": acceptance or [],
        "diff": diff or {"out_of_scope_writes": 0},
        "risk": risk or {"level": scope.get("risk", "medium"), "factors": []},
        "worker_claims": sanitized_claims,
        "policy_refs": policy_refs or ["constitution#3.2"],
        "budget": budget or {},
        "content_isolation": {"sanitized": True,
                              "instruction_like_blocks": injection_count},
    }
    if options:
        packet["options"] = options
    packet["packet_hash"] = packet_hash(packet)
    validate_packet(packet, max_packet_bytes=max_packet_bytes)
    return packet


def validate_packet(packet: dict[str, Any], *, max_packet_bytes: int = 200_000) -> None:
    jsonschema.validate(packet, PACKET_SCHEMA)
    if len(json.dumps(packet, ensure_ascii=False).encode("utf-8")) > max_packet_bytes:
        raise ValueError(f"决策包超过 {max_packet_bytes} 字节")


def load_packet(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        packet = json.load(f)
    if "packet_hash" not in packet:
        packet["packet_hash"] = packet_hash(packet)
    validate_packet(packet)
    return packet


def make_evidence(kind: str, *, result: str = "pass", subject: str = "subject-1",
                  payload: dict[str, Any] | None = None,
                  evidence_id: str | None = None,
                  signed_by: str | None = None) -> dict[str, Any]:
    """Convenience builder for tests and the simulator bridge."""
    return {
        "evidence_id": evidence_id or f"EV-{uuid4().hex[:8]}",
        "kind": kind,
        "result": result,
        "tool": kind.split(":")[0],
        "tool_version": "test@1",
        "signed_by": signed_by or f"tool:{kind.split(':')[0]}",
        "payload": payload or {},
    }
