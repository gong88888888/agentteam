"""Structured interaction-state checks for design handoff.

Pages are not enough: a scenario is designable only when loading, empty, ready,
submitting, success, error, timeout, retry, unauthorized, conflict, offline and
expiry states have either a definition or an explicit not-applicable reason,
and every transition points at a real state.
"""
from __future__ import annotations

from typing import Any

BASE_STATES = ("idle", "loading", "empty", "ready", "submitting", "success",
               "error", "timeout", "retrying", "unauthorized", "expired",
               "conflict", "offline", "cancelled")
TERMINAL = {"success", "cancelled", "expired"}


def validate_design(pages: list[dict[str, Any]], *,
                    required_scenarios: list[str] | None = None,
                    required_states: tuple[str, ...] = BASE_STATES) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    page_ids: set[str] = set()
    state_keys: dict[str, set[str]] = {}
    scenario_pages: dict[str, list[str]] = {}
    for page in pages:
        page_id = str(page.get("id") or page.get("page") or page.get("component") or "")
        if not page_id:
            findings.append({"severity": "blocking", "code": "missing_page_id",
                             "detail": "页面/组件缺少 id"})
            continue
        if page_id in page_ids:
            findings.append({"severity": "blocking", "code": "duplicate_page",
                             "detail": f"重复页面/组件：{page_id}"})
        page_ids.add(page_id)
        states = page.get("states") or []
        state_map: dict[str, dict[str, Any]] = {}
        for state in states:
            name = str(state.get("name") or state.get("id") or "").lower()
            if not name:
                findings.append({"severity": "major", "code": "missing_state_name",
                                 "detail": f"{page_id} 有状态缺少 name"})
                continue
            if name in state_map:
                findings.append({"severity": "major", "code": "duplicate_state",
                                 "detail": f"{page_id} 重复状态 {name}"})
            state_map[name] = state
        state_keys[page_id] = set(state_map)
        for name in required_states:
            state = state_map.get(name)
            if state is None:
                findings.append({
                    "severity": "blocking", "code": "missing_state",
                    "detail": f"{page_id} 缺少 {name} 状态；不适用时必须写明理由"})
                continue
            na_reason = str(state.get("not_applicable_reason")
                            or state.get("na_reason") or "").strip()
            if state.get("applicable") is False and not na_reason:
                findings.append({
                    "severity": "major", "code": "na_without_reason",
                    "detail": f"{page_id}.{name} 标记不适用但没有理由"})
        transitions = page.get("transitions") or []
        if not transitions:
            findings.append({"severity": "major", "code": "no_transitions",
                             "detail": f"{page_id} 没有定义任何状态转移"})
        outgoing = {str(t.get("from") or "").lower() for t in transitions}
        for trans in transitions:
            source = str(trans.get("from") or "").lower()
            target = str(trans.get("to") or "").lower()
            event = str(trans.get("event") or "")
            if source not in state_map:
                findings.append({"severity": "blocking", "code": "unknown_from",
                                 "detail": f"{page_id} 转移起点不存在：{source}"})
            if target not in state_map:
                findings.append({"severity": "blocking", "code": "unknown_to",
                                 "detail": f"{page_id} 转移终点不存在：{target}"})
            if not event:
                findings.append({"severity": "major", "code": "missing_event",
                                 "detail": f"{page_id} {source}->{target} 缺少事件"})
        for name in state_map:
            if name in TERMINAL:
                continue
            if name not in outgoing:
                findings.append({
                    "severity": "minor", "code": "no_outgoing",
                    "detail": f"{page_id}.{name} 是非终态但没有出边（确认是否死胡同）"})
        for scenario in page.get("scenarios") or []:
            scenario_pages.setdefault(str(scenario), []).append(page_id)
    covered = 0
    for scenario in required_scenarios or []:
        if scenario not in scenario_pages:
            findings.append({"severity": "blocking", "code": "scenario_not_designed",
                             "detail": f"场景 {scenario} 没有对应设计"})
        else:
            covered += 1
    blocking = [f for f in findings if f["severity"] == "blocking"]
    return {
        "status": "pass" if not blocking else "fail",
        "pages": len(page_ids),
        "states": sum(len(v) for v in state_keys.values()),
        "transitions": sum(len(p.get("transitions") or []) for p in pages),
        "scenario_coverage": {
            "required": len(required_scenarios or []),
            "covered": covered,
            "percent": round(covered / len(required_scenarios) * 100, 1)
            if required_scenarios else 0.0,
        },
        "findings": findings,
        "blocking": len(blocking),
    }


def render_matrix(pages: list[dict[str, Any]]) -> str:
    lines = ["| 页面/组件 | 状态 | 适用 | 操作/反馈 |", "|---|---|---|---|"]
    for page in pages:
        page_id = page.get("id") or page.get("page") or "?"
        for state in page.get("states") or []:
            name = state.get("name") or "?"
            applicable = "否：" + str(state.get("not_applicable_reason") or "")
            if state.get("applicable") is not False:
                applicable = "是"
            action = state.get("feedback") or state.get("actions") or ""
            lines.append(f"| {page_id} | {name} | {applicable} | {action} |")
    return "\n".join(lines) + "\n"
