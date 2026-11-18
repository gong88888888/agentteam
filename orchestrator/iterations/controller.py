"""Iteration controller: pause, budget, in-work limits and ready work.

The controller never equates "the current process ended" with "the project is
done". Pause survives restarts; budget exhaustion stops new claims; a large
verification backlog pauses new implementation work while QA catches up.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from ..persistence.db import Database
from ..persistence.events import EventOutbox
from ..persistence.tasks import TaskStore


def _ensure_columns(db: Database) -> None:
    with db.read() as con:
        cols = {r["name"] for r in con.execute("PRAGMA table_info(iterations)")}
        if "paused" not in cols:
            con.execute("ALTER TABLE iterations ADD COLUMN paused INTEGER NOT NULL DEFAULT 0")
            con.commit()


class IterationController:
    def __init__(self, db: Database, store: TaskStore, *,
                 project_id: str, iteration_id: str) -> None:
        self.db = db
        self.store = store
        self.project_id = project_id
        self.iteration_id = iteration_id
        db.migrate()
        _ensure_columns(db)

    def _iteration(self) -> dict[str, Any]:
        with self.db.read() as con:
            row = con.execute("SELECT * FROM iterations WHERE iteration_id=?",
                              (self.iteration_id,)).fetchone()
        if row is None:
            raise KeyError(f"迭代不存在：{self.iteration_id}")
        return dict(row)

    def pause(self, reason: str = "", *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            con.execute("UPDATE iterations SET paused=1, updated_at=? "
                        "WHERE iteration_id=?", (now, self.iteration_id))
            EventOutbox.emit(con, project_id=self.project_id,
                             aggregate_id=self.iteration_id, aggregate_version=2,
                             event_type="iteration.paused",
                             payload={"reason": reason}, now=now)

    def resume(self, *, actor: str, now: float | None = None) -> None:
        if not str(actor).strip():
            raise ValueError("恢复迭代必须有明确的人/策略授权 actor")
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            con.execute("UPDATE iterations SET paused=0, updated_at=? "
                        "WHERE iteration_id=?", (now, self.iteration_id))
            EventOutbox.emit(con, project_id=self.project_id,
                             aggregate_id=self.iteration_id, aggregate_version=3,
                             event_type="iteration.resumed",
                             payload={"actor": actor}, now=now)

    def is_paused(self) -> bool:
        return bool(self._iteration().get("paused", 0))

    def budget(self) -> dict[str, Any]:
        try:
            return json.loads(self._iteration().get("budget_json") or "{}")
        except json.JSONDecodeError:
            return {}

    def tasks(self) -> list[dict[str, Any]]:
        return self.store.list(iteration_id=self.iteration_id)

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in self.tasks():
            counts[str(task["status"])] = counts.get(str(task["status"]), 0) + 1
        return counts

    def budget_exhausted(self) -> str:
        budget = self.budget()
        max_tasks = budget.get("max_tasks")
        if isinstance(max_tasks, int) and len(self.tasks()) >= max_tasks:
            return "max_tasks"
        max_completed = budget.get("max_completed")
        if isinstance(max_completed, int) and \
                self.counts().get("completed", 0) >= max_completed:
            return "max_completed"
        return ""

    def next_ready(self, limit: int = 10) -> list[dict[str, Any]]:
        if self.is_paused() or self.budget_exhausted():
            return []
        return self.store.list(status="ready", iteration_id=self.iteration_id)[:limit]

    def can_dispatch(self, kind: str = "implementation",
                     *, verification_limit: int = 2) -> tuple[bool, str]:
        if self.is_paused():
            return False, "paused"
        exhausted = self.budget_exhausted()
        if exhausted:
            return False, f"budget:{exhausted}"
        counts = self.counts()
        if kind == "implementation" and counts.get("awaiting_verification", 0) >= verification_limit:
            return False, "verification_backlog"
        return True, ""

    def project_state(self) -> str:
        if self.is_paused():
            return "paused"
        counts = self.counts()
        if counts.get("awaiting_decision", 0):
            return "awaiting_decision"
        if counts.get("running", 0) or counts.get("ready", 0):
            return "active"
        return "idle"

    def compile_plan(self, manifest: Any) -> list[dict[str, Any]]:
        spec = manifest.to_dict() if hasattr(manifest, "to_dict") else dict(manifest)
        created = []
        for item in spec.get("required_tasks", []):
            if not item.get("required", True):
                continue
            task_id = f"T-{self.iteration_id}-{item['role']}"
            created.append(self.store.create_task(
                task_id=task_id, project_id=self.project_id,
                iteration_id=self.iteration_id, role=str(item["role"]),
                stage=str(item.get("stage", "")), title=str(item.get("id", "")),
                input_fingerprint=str(item.get("id", ""))))
        return created
