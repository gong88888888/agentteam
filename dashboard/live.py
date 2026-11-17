"""Live project task data for the dashboard.

Reads the project runner's state, event log and signed tool ledger and turns
each role into a task row with timing, model, gate, quality and evidence data.

This module is intentionally dependency-light: the dashboard build and the
HTTP server both import it. It never mutates project files.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROJECTS = ROOT / "projects"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.project_runner import ROLE_SPECS  # noqa: E402

ROLE_ORDER = [r.role for r in ROLE_SPECS]
ROLE_TITLES = {r.role: r.title for r in ROLE_SPECS}
ROLE_STAGE = {
    "pm": ("plan", "计划"),
    "product": ("product", "产品"),
    "ui": ("product", "设计"),
    "arch": ("product", "架构"),
    "backend": ("build", "开发"),
    "frontend": ("build", "开发"),
    "review": ("quality", "质量"),
    "qa": ("quality", "质量"),
    "security": ("quality", "质量"),
    "ops": ("release", "发布"),
    "kb": ("knowledge", "沉淀"),
    "retro": ("knowledge", "沉淀"),
}
STAGES = [
    ("plan", "计划"),
    ("product", "产品/设计/架构"),
    ("build", "开发"),
    ("quality", "质量"),
    ("release", "发布"),
    ("knowledge", "沉淀"),
]
STAGE_ORDER = {sid: i for i, (sid, _) in enumerate(STAGES)}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _read_jsonl(path: Path, limit: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        return []
    return rows[-limit:]


def project_dirs() -> list[Path]:
    if not PROJECTS.exists():
        return []
    return [p for p in PROJECTS.iterdir()
            if p.is_dir() and (p / "project.json").exists()]


def _updated_key(p: Path, project: dict[str, Any]) -> float:
    value = str(project.get("updated_at") or "")
    if value:
        try:
            return time.mktime(time.strptime(value, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            pass
    try:
        return (p / "project.json").stat().st_mtime
    except OSError:
        return 0.0


def project_summary(p: Path) -> dict[str, Any]:
    project = _read_json(p / "project.json", {})
    state = _read_json(p / "state" / "roles.json", {})
    progress = _read_json(p / "state" / "progress.json", {})
    roles = [state[r] for r in ROLE_ORDER if isinstance(state.get(r), dict)]
    statuses = Counter(str(r.get("status", "unknown")) for r in roles)
    gates = project.get("gates") or {}
    if not gates:
        gate_rows = [r.get("gate") or {} for r in roles]
        gates = {
            "pass": sum(1 for g in gate_rows if g.get("status") == "pass"),
            "fail": sum(1 for g in gate_rows if g.get("status") == "fail"),
            "need_evidence": sum(1 for g in gate_rows
                                if g.get("status") == "need_evidence"),
            "off": sum(1 for g in gate_rows if g.get("status") in (None, "off")),
        }
    quality = project.get("quality_avg")
    if quality is None:
        scores = [r.get("quality", {}).get("score") for r in roles
                  if isinstance(r.get("quality"), dict)
                  and r.get("quality", {}).get("score") is not None]
        quality = round(sum(scores) / len(scores), 1) if scores else None
    return {
        "name": p.name,
        "archived": p.name.startswith(("_", ".")),
        "status": progress.get("status") or project.get("status", "unknown"),
        "updated_at": project.get("updated_at", ""),
        "created_at": project.get("created_at", ""),
        "requirement": project.get("requirement", "requirements/input.md"),
        "offline": project.get("offline"),
        "project_type": project.get("project_type", "web"),
        "template": project.get("template", "none"),
        "tool_profile": project.get("tool_profile", "basic"),
        "run_id": project.get("run_id", ""),
        "quality_avg": quality,
        "gates": gates,
        "roles_total": len(roles) or int(project.get("total_roles", 0) or 0),
        "roles_done": statuses.get("done", 0),
        "roles_blocked": statuses.get("blocked", 0),
        "roles_error": statuses.get("error", 0),
        "roles_running": statuses.get("running", 0),
        "current_role": project.get("current_role", "")
        or progress.get("current_role", ""),
        "current_index": project.get("current_index", 0)
        or progress.get("current_index", 0),
        "elapsed_s": project.get("elapsed_s", progress.get("elapsed_s", 0)),
        "acceptance_status": (project.get("acceptance") or {}).get("status", ""),
        "dod_status": (project.get("dod") or {}).get("status", ""),
        "process_metrics": project.get("process_metrics", {}),
        "stages": project.get("stages", []),
        "updated_ts": _updated_key(p, project),
    }


def list_projects(include_archived: bool = True) -> list[dict[str, Any]]:
    items = [project_summary(p) for p in project_dirs()]
    if not include_archived:
        items = [x for x in items if not x["archived"]]
    items.sort(key=lambda x: x.get("updated_ts", 0), reverse=True)
    return items


def _events(p: Path) -> list[dict[str, Any]]:
    return _read_jsonl(p / "logs" / "events.jsonl")


def _role_intervals(events: list[dict[str, Any]]) -> dict[str, tuple[dict, dict | None]]:
    """Pair the latest role.started with its next role.finished/failed."""
    open_by_role: dict[str, dict[str, Any]] = {}
    latest: dict[str, tuple[dict, dict | None]] = {}
    for e in events:
        role = str(e.get("role") or "")
        if not role:
            continue
        event = str(e.get("event") or "")
        if event == "role.started":
            open_by_role[role] = e
        elif event in ("role.finished", "role.failed"):
            start = open_by_role.pop(role, None)
            if start is not None:
                latest[role] = (start, e)
    for role, start in open_by_role.items():
        latest[role] = (start, None)
    return latest


def _evidence_counts(p: Path) -> dict[str, int]:
    rows = _read_jsonl(p / "evidence" / "tool-ledger.jsonl")
    evidence = [r for r in rows if r.get("type") == "evidence"]
    results = Counter(str(r.get("result", "unknown")) for r in evidence)
    return {
        "total": len(evidence),
        "pass": results.get("pass", 0),
        "fail": results.get("fail", 0),
        "other": len(evidence) - results.get("pass", 0) - results.get("fail", 0),
    }


def _task_rows(p: Path, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state = _read_json(p / "state" / "roles.json", {})
    intervals = _role_intervals(events)
    start_ts = [s.get("ts") for s, _ in intervals.values()
                if isinstance(s.get("ts"), (int, float))]
    all_ts = [e.get("ts") for e in events
              if isinstance(e.get("ts"), (int, float))]
    base = min(start_ts) if start_ts else (min(all_ts) if all_ts else time.time())
    last_ts = max(all_ts) if all_ts else base
    rows: list[dict[str, Any]] = []
    for index, role in enumerate(ROLE_ORDER):
        meta = state.get(role) if isinstance(state.get(role), dict) else {}
        start, end = intervals.get(role, (None, None))
        status = str(meta.get("status") or ("running" if start and not end else "pending"))
        if start and not end and status == "pending":
            status = "running"
        s_ts = start.get("ts") if start else None
        e_ts = end.get("ts") if end else (last_ts if start else None)
        if not isinstance(s_ts, (int, float)):
            start_min = float(index * 10)
            end_min = start_min + 10.0
            start_clock = end_clock = ""
        else:
            start_min = max(0.0, (float(s_ts) - float(base)) / 60.0)
            end_ts = float(e_ts) if isinstance(e_ts, (int, float)) else float(s_ts) + 60
            end_min = max(start_min + 0.5, (end_ts - float(base)) / 60.0)
            start_clock = str(start.get("clock") or "")
            end_clock = str(end.get("clock") or "") if end else ""
        gate = meta.get("gate") if isinstance(meta.get("gate"), dict) else {}
        tools = meta.get("tools") if isinstance(meta.get("tools"), dict) else {}
        quality = meta.get("quality") if isinstance(meta.get("quality"), dict) else {}
        files = meta.get("files") if isinstance(meta.get("files"), list) else []
        stage, stage_label = ROLE_STAGE.get(role, ("other", "其他"))
        rows.append({
            "id": role,
            "role": role,
            "title": ROLE_TITLES.get(role, role),
            "stage": stage,
            "stage_label": stage_label,
            "stage_index": STAGE_ORDER.get(stage, 99),
            "status": status,
            "model": meta.get("model", ""),
            "backend": meta.get("backend", ""),
            "start_clock": start_clock,
            "end_clock": end_clock,
            "start_min": round(start_min, 1),
            "end_min": round(end_min, 1),
            "duration_min": round(end_min - start_min, 1),
            "latency_ms": meta.get("latency_ms", 0),
            "tokens": meta.get("tokens", 0),
            "cost_usd": meta.get("cost_usd", 0.0),
            "gate_status": gate.get("status", "off"),
            "gate_id": gate.get("gate_id", ""),
            "decision_id": gate.get("decision_id"),
            "quality_score": quality.get("score"),
            "quality_grade": quality.get("grade"),
            "tool_profile": tools.get("profile", ""),
            "tool_passed": tools.get("passed", []),
            "tool_failed": tools.get("failed", []),
            "tool_missing": tools.get("missing", []),
            "files": [f.get("path", "") for f in files if isinstance(f, dict)],
            "sandbox": meta.get("sandbox", "direct"),
            "adjustment": meta.get("adjustment", ""),
            "prompt": meta.get("prompt", {}),
            "finished_at": meta.get("finished_at", ""),
        })
    return rows


def live_project(p: Path, *, event_limit: int = 400) -> dict[str, Any]:
    summary = project_summary(p)
    events = _events(p)
    tasks = _task_rows(p, events)
    evidence = _evidence_counts(p)
    tokens = sum(int(t.get("tokens") or 0) for t in tasks)
    cost = sum(float(t.get("cost_usd") or 0) for t in tasks)
    gates = Counter(str(t.get("gate_status") or "off") for t in tasks)
    max_end = max((float(t["end_min"]) for t in tasks), default=0.0)
    recent = events[-event_limit:]
    return {
        "project": summary,
        "tasks": tasks,
        "metrics": {
            "roles_total": len(tasks),
            "roles_done": sum(1 for t in tasks if t["status"] == "done"),
            "roles_blocked": sum(1 for t in tasks if t["status"] == "blocked"),
            "roles_error": sum(1 for t in tasks if t["status"] == "error"),
            "roles_running": sum(1 for t in tasks if t["status"] == "running"),
            "gates_pass": gates.get("pass", 0),
            "gates_fail": gates.get("fail", 0),
            "gates_need_evidence": gates.get("need_evidence", 0),
            "gates_off": gates.get("off", 0),
            "tokens": tokens,
            "cost_usd": round(cost, 6),
            "evidence": evidence,
            "timeline_max_min": round(max_end, 1),
            "events_total": len(events),
        },
        "events": recent,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def live_payload(project: str | None = None, *, event_limit: int = 400) -> dict[str, Any]:
    projects = list_projects(include_archived=True)
    chosen = None
    if project:
        for item in projects:
            if item["name"] == project:
                chosen = item
                break
        if chosen is None:
            raise KeyError(f"project not found: {project}")
    else:
        chosen = next((item for item in projects if not item["archived"]),
                      projects[0] if projects else None)
    if chosen is None:
        return {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "projects": [], "project": None}
    p = PROJECTS / chosen["name"]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "projects": projects,
        "project": live_project(p, event_limit=event_limit),
    }
