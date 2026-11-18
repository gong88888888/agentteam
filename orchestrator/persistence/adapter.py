"""Project runner adapter over the SQLite task ledger."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .db import Database
from .events import EventOutbox
from .tasks import TaskStore


class ProjectLedger:
    def __init__(self, project_dir: str | Path, *, project_id: str,
                 iteration_id: str, run_id: str, project_type: str,
                 mode: str = "formal") -> None:
        self.project_dir = Path(project_dir).resolve()
        self.project_id = project_id
        self.iteration_id = iteration_id
        self.run_id = run_id
        self.project_type = project_type
        self.mode = mode
        self.db = Database(self.project_dir / "state" / "agentteam.db")
        self.db.migrate()
        self.store = TaskStore(self.db)
        self.store.ensure_project(project_id, project_type)
        self.store.ensure_iteration(iteration_id, project_id, mode=mode,
                                    status="executing")

    def start_role(self, role: str, stage: str = "",
                   input_fingerprint: str = "") -> dict[str, Any]:
        task_id = f"T-{self.iteration_id}-{role}"
        self.store.create_task(
            task_id=task_id, project_id=self.project_id,
            iteration_id=self.iteration_id, role=role,
            title=role, stage=stage, input_fingerprint=input_fingerprint)
        return self.store.claim(task_id, owner=f"runner:{self.run_id}",
                                lease_s=3600, run_id=self.run_id)

    def finish_role(self, handle: dict[str, Any] | None, *,
                    status: str, summary: str, files: list[dict[str, Any]] | None = None,
                    gate: dict[str, Any] | None = None, error: str = "",
                    model: str = "", backend: str = "") -> dict[str, Any] | None:
        if not handle:
            return None
        task_id = str(handle["task_id"])
        owner = str(handle["lease_owner"])
        version = int(handle["attempt_version"])
        attempt_id = str(handle["attempt_id"])
        for f in files or []:
            path = str(f.get("path", ""))
            if f.get("source") != "role" or not f.get("promoted", True):
                continue
            full = self.project_dir / path
            if not full.is_file():
                continue
            digest = hashlib.sha256(full.read_bytes()).hexdigest()
            self.store.record_artifact(
                path=path, content_hash=digest, project_id=self.project_id,
                task_id=task_id, attempt_id=attempt_id, kind="file",
                producer="role")
        gate_status = (gate or {}).get("status", "")
        if status == "done" and gate_status == "pass":
            return self.store.complete(task_id, owner, expected_version=version,
                                       output_ref=str((handle or {}).get("task_id", "")))
        retryable = gate_status == "need_evidence" or status == "error"
        return self.store.fail(
            task_id, owner, expected_version=version,
            failure=error or summary[:500] or f"status={status}, gate={gate_status}",
            retryable=retryable)

    def skip_role(self, role: str, reason: str) -> None:
        task_id = f"T-{self.iteration_id}-{role}"
        self.store.create_task(
            task_id=task_id, project_id=self.project_id,
            iteration_id=self.iteration_id, role=role, title=role)
        self.store.cancel(task_id, reason=reason)

    def finish_iteration(self, status: str, *, dod: dict[str, Any] | None = None,
                         acceptance: dict[str, Any] | None = None) -> None:
        target = "accepted" if status == "completed" else "blocked"
        self.store.set_iteration_status(self.iteration_id, target)
        with self.db.transaction() as con:
            EventOutbox.emit(
                con, project_id=self.project_id, aggregate_id=self.iteration_id,
                aggregate_version=1, event_type="iteration.completed",
                payload={"status": status,
                         "dod": (dod or {}).get("status", ""),
                         "acceptance": (acceptance or {}).get("status", ""),
                         "mode": self.mode}, now=time.time())
        self.export_domain_events()

    def export_domain_events(self) -> int:
        """A small dashboard view consumer; idempotent by event_id."""
        path = self.project_dir / "state" / "domain-events.json"
        existing: list[dict[str, Any]] = []
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8")).get("events", [])
            except (OSError, json.JSONDecodeError):
                existing = []
        seen = {e.get("event_id") for e in existing}
        new_events: list[dict[str, Any]] = []

        def handler(event: dict[str, Any]) -> None:
            if event.get("event_id") not in seen:
                new_events.append(event)
                seen.add(event.get("event_id"))

        self.store.outbox.dispatch("project-view", handler)
        if new_events:
            payload = {"generated_at": time.time(),
                       "events": (existing + new_events)[-500:]}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        return len(new_events)

    def counts(self) -> dict[str, Any]:
        return {**self.store.counts(), "outbox": self.store.outbox.counts(),
                "database": str(self.db.path)}
