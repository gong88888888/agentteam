"""Revalidation plan: impact set + mandatory checks + judge additions (only add)."""
from __future__ import annotations

from typing import Any

from ..evidence.signing import sha256_hex
from .backend import JudgeBackend
from .rubric import Rubric


def plan_hash(base_checks: list[str], mandatory_checks: list[str]) -> str:
    return sha256_hex({"base_checks": sorted(base_checks),
                       "mandatory_checks": sorted(mandatory_checks)})


class RevalidationPlanner:
    def __init__(self, backend: JudgeBackend) -> None:
        self.backend = backend

    def review(self, *, base_checks: list[str], mandatory_checks: list[str],
               packet: dict[str, Any], rubric: Rubric) -> dict[str, Any]:
        base = sorted(set(base_checks) | set(mandatory_checks))
        plan = {
            "base_plan_hash": plan_hash(base, mandatory_checks),
            "base_checks": base,
            "mandatory_checks": sorted(set(mandatory_checks)),
        }
        result = self.backend.revalidate(plan, packet, tier="J3")
        if result.get("removed_checks"):
            raise ValueError(f"复核计划不得删除检查：{result['removed_checks']}")
        if result.get("base_plan_hash") != plan["base_plan_hash"]:
            raise ValueError("复核计划 base_plan_hash 不匹配")
        added = result.get("added_checks", [])
        for item in added:
            if not item.get("id") or not item.get("why"):
                raise ValueError(f"追加检查缺少 id/why：{item}")
        final = sorted(set(base) | {a["id"] for a in added})
        mandatory = set(mandatory_checks)
        if not mandatory <= set(final):
            raise ValueError("复核计划删除了强制项")
        return {
            "base_plan_hash": plan["base_plan_hash"],
            "base_checks": base,
            "mandatory_checks": sorted(mandatory),
            "added_checks": added,
            "removed_checks": [],
            "final_checks": final,
            "judge": result.get("judge", {}),
            "rationale": result.get("rationale", ""),
        }
