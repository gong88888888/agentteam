"""Retrospective actions become real tasks, not prose.

An action is only queued when it has an owner, deliverable, verification and a
persisted task ID. "Be more careful next time" stays a candidate suggestion and
is not counted as closed loop.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from .persistence.db import Database, row_dict
from .persistence.tasks import TaskStore

STATUSES = ("candidate", "queued", "in_progress", "completed", "verified",
            "ineffective", "cancelled")
REQUIRED = ("root_cause", "owner_role", "target_iteration", "deliverable",
            "verification")


class ActionStore:
    def __init__(self, db: Database) -> None:
        self.db = db
        db.migrate()

    def submit(self, *, project_id: str, root_cause: str, owner_role: str,
               target_iteration: str, deliverable: str, verification: str,
               trigger: str = "", task_store: TaskStore | None = None,
               iteration_id: str = "", now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        fields = {"root_cause": root_cause, "owner_role": owner_role,
                  "target_iteration": target_iteration,
                  "deliverable": deliverable, "verification": verification}
        missing = [name for name, value in fields.items() if not str(value).strip()]
        action_id = f"ACT-{uuid.uuid4().hex[:10]}"
        status = "candidate"
        task_id = ""
        reason = ""
        if missing:
            reason = "缺少字段：" + ", ".join(missing)
        elif len(str(deliverable).strip()) < 10 or len(str(verification).strip()) < 10:
            reason = "交付或验证过于笼统；需要可观察行为"
        elif task_store is None or not iteration_id:
            reason = "没有可入队的迭代/任务账本"
        else:
            digest = hashlib.sha256(
                f"{project_id}|{root_cause}|{deliverable}".encode("utf-8")
            ).hexdigest()[:8]
            task_id = f"T-{iteration_id}-ACT-{digest}"
            task_store.create_task(
                task_id=task_id, project_id=project_id,
                iteration_id=iteration_id, role=str(owner_role),
                title=str(deliverable)[:100], stage="release",
                input_fingerprint=digest, write_scope="")
            status = "queued"
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO actions(action_id,project_id,root_cause,owner_role,"
                "target_iteration,trigger,deliverable,verification,status,task_id,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (action_id, project_id, root_cause, owner_role, target_iteration,
                 trigger, deliverable, verification, status, task_id, now, now))
            row = con.execute("SELECT * FROM actions WHERE action_id=?",
                              (action_id,)).fetchone()
        data = row_dict(row) or {}
        data["queued"] = status == "queued"
        if reason:
            data["reason"] = reason
        return data

    def get(self, action_id: str) -> dict[str, Any] | None:
        with self.db.read() as con:
            return row_dict(con.execute("SELECT * FROM actions WHERE action_id=?",
                                        (action_id,)).fetchone())

    def list(self, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM actions"
        params: list[Any] = []
        if project_id:
            sql += " WHERE project_id=?"
            params.append(project_id)
        sql += " ORDER BY created_at ASC"
        with self.db.read() as con:
            return [dict(r) for r in con.execute(sql, params).fetchall()]

    def verify(self, action_id: str, *, passed: bool, evidence_ref: str,
               task_store: TaskStore | None = None,
               now: float | None = None) -> dict[str, Any]:
        if not str(evidence_ref).strip():
            raise ValueError("行动验证需要 evidence_ref")
        action = self.get(action_id)
        if not action:
            raise KeyError(f"行动不存在：{action_id}")
        if action.get("task_id") and task_store is not None:
            task = task_store.get(str(action["task_id"]))
            if not task or task.get("status") != "completed":
                raise ValueError("行动任务尚未完成，不能标记验证")
        now = time.time() if now is None else now
        status = "verified" if passed else "ineffective"
        with self.db.transaction() as con:
            con.execute("UPDATE actions SET status=?, updated_at=? "
                        "WHERE action_id=?", (status, now, action_id))
            fresh = con.execute("SELECT * FROM actions WHERE action_id=?",
                                (action_id,)).fetchone()
        data = row_dict(fresh) or {}
        data["evidence_ref"] = evidence_ref
        return data

    def overdue(self, current_iteration: str) -> list[dict[str, Any]]:
        rows = []
        for action in self.list():
            if action["status"] in ("verified", "ineffective", "cancelled"):
                continue
            if action.get("target_iteration") and \
                    action["target_iteration"] != current_iteration:
                rows.append(action)
        return rows

    def counts(self) -> dict[str, int]:
        with self.db.read() as con:
            rows = con.execute("SELECT status, COUNT(*) n FROM actions "
                               "GROUP BY status").fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}
