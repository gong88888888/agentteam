"""Deterministic red lines that a model judge may never override."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class HardBlock:
    code: str
    message: str
    action: str            # "reject" | "need_evidence"
    evidence_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _check_result(packet: dict[str, Any]) -> list[HardBlock]:
    blocks: list[HardBlock] = []
    for check in packet.get("deterministic_checks", []):
        if check.get("result") != "pass":
            blocks.append(HardBlock(
                "deterministic_failure",
                f"确定性检查 {check.get('kind')} 失败",
                "reject", check.get("evidence_id", "")))
        if not str(check.get("signed_by", "")).startswith(("tool:", "judge:")):
            blocks.append(HardBlock(
                "unsigned_evidence",
                f"证据 {check.get('evidence_id')} 未由工具/裁判签名",
                "reject", check.get("evidence_id", "")))
    return blocks


def evaluate(packet: dict[str, Any], *, max_packet_bytes: int = 200_000) -> list[HardBlock]:
    blocks = _check_result(packet)
    missing = packet.get("missing_evidence", [])
    if missing:
        blocks.append(HardBlock(
            "missing_evidence",
            f"缺少必需证据：{', '.join(missing)}",
            "need_evidence"))
    diff = packet.get("diff", {})
    if int(diff.get("out_of_scope_writes", 0)) > 0:
        blocks.append(HardBlock(
            "out_of_scope_write",
            f"存在 {diff['out_of_scope_writes']} 处越界写",
            "reject"))
    for check in packet.get("deterministic_checks", []):
        payload = check.get("payload", {}) if isinstance(check.get("payload"), dict) else {}
        if check.get("kind") == "sast" and int(payload.get("high", 0)) > 0:
            blocks.append(HardBlock(
                "high_severity_sast", "存在高危安全漏洞", "reject",
                check.get("evidence_id", "")))
    if packet.get("decision_type") == "release":
        kinds = {c.get("kind") for c in packet.get("deterministic_checks", [])}
        if "rollback_plan" not in kinds:
            blocks.append(HardBlock(
                "release_without_rollback", "发布缺少回滚方案证据", "reject"))
        for check in packet.get("deterministic_checks", []):
            if check.get("kind") == "rollback_plan":
                payload = check.get("payload", {}) or {}
                if not payload.get("feature_flag", False):
                    blocks.append(HardBlock(
                        "release_without_feature_flag",
                        "发布缺少特性开关", "reject",
                        check.get("evidence_id", "")))
    if packet.get("content_isolation", {}).get("instruction_like_blocks", 0) > 0:
        blocks.append(HardBlock(
            "untrusted_instructions",
            "决策包包含指令性文本，必须隔离后重新提交，不得自动批准",
            "reject"))
    if len(str(packet).encode("utf-8")) > max_packet_bytes:
        blocks.append(HardBlock(
            "packet_too_large", f"决策包超过 {max_packet_bytes} 字节", "reject"))
    return blocks


def blocks_approval(blocks: list[HardBlock]) -> bool:
    return any(b.action in ("reject", "need_evidence") for b in blocks)
