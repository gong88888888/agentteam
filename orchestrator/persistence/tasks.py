"""Tasks, attempts, leases and compare-and-swap completion."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

from .db import Database, row_dict
from .events import EventOutbox

TASK_STATES = {"draft", "ready", "running", "awaiting_verification",
               "needs_revision", "completed", "blocked", "awaiting_decision",
               "failed", "cancelled", "recovering"}


class TaskConflict(RuntimeError):
    def __init__(self, code: str, message: str, task_id: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.task_id = task_id

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self), "task_id": self.task_id}


class TaskStore:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.outbox = EventOutbox(db)

    # ---------- lifecycle ----------
    def ensure_project(self, project_id: str, project_type: str,
                       *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            con.execute(
                "INSERT OR IGNORE INTO projects(project_id,project_type,status,"
                "created_at,updated_at) VALUES(?,?,?,?,?)",
                (project_id, project_type, "active", now, now))

    def ensure_iteration(self, iteration_id: str, project_id: str, *,
                        mode: str = "formal", budget: dict[str, Any] | None = None,
                        status: str = "approved", now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            con.execute(
                "INSERT OR IGNORE INTO iterations(iteration_id,project_id,status,"
                "mode,budget_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (iteration_id, project_id, status, mode,
                 json.dumps(budget or {}, ensure_ascii=False), now, now))

    def create_task(self, *, task_id: str, project_id: str, iteration_id: str,
                    role: str, title: str = "", stage: str = "",
                    input_fingerprint: str = "", write_scope: str = "",
                    status: str = "ready", priority: int = 0,
                    now: float | None = None) -> dict[str, Any]:
        if status not in TASK_STATES:
            raise ValueError(f"未知任务状态：{status}")
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            existing = con.execute("SELECT * FROM tasks WHERE task_id=?",
                                   (task_id,)).fetchone()
            if existing is not None:
                return row_dict(existing) or {}
            con.execute(
                "INSERT INTO tasks(task_id,project_id,iteration_id,role,title,stage,"
                "status,version,lease_owner,lease_expires_at,input_fingerprint,"
                "write_scope,priority,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, project_id, iteration_id, role, title, stage, status,
                 0, None, None, input_fingerprint, write_scope, priority, now, now))
            EventOutbox.emit(con, project_id=project_id, aggregate_id=task_id,
                             aggregate_version=0, event_type="task.created",
                             payload={"role": role, "stage": stage, "status": status},
                             now=now)
            row = con.execute("SELECT * FROM tasks WHERE task_id=?",
                              (task_id,)).fetchone()
        return row_dict(row) or {}

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self.db.read() as con:
            return row_dict(con.execute("SELECT * FROM tasks WHERE task_id=?",
                                        (task_id,)).fetchone())

    def list(self, *, status: str | None = None,
             iteration_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM tasks"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if iteration_id:
            clauses.append("iteration_id=?")
            params.append(iteration_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at ASC"
        with self.db.read() as con:
            return [dict(r) for r in con.execute(sql, params).fetchall()]

    def attempts(self, task_id: str) -> list[dict[str, Any]]:
        with self.db.read() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM attempts WHERE task_id=? ORDER BY started_at",
                (task_id,)).fetchall()]

    # ---------- leases ----------
    def claim(self, task_id: str, owner: str, *, lease_s: float = 60,
              attempt_id: str = "", run_id: str = "",
              now: float | None = None) -> dict[str, Any]:
        if not owner:
            raise ValueError("claim 需要 owner")
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            row = con.execute("SELECT * FROM tasks WHERE task_id=?",
                              (task_id,)).fetchone()
            if row is None:
                raise TaskConflict("not_found", f"任务不存在：{task_id}", task_id)
            status = str(row["status"])
            if status not in ("ready", "recovering"):
                raise TaskConflict(
                    "not_ready", f"{task_id} 状态为 {status}，不能领取", task_id)
            version = int(row["version"])
            attempt_id = attempt_id or f"{task_id}:A{version + 1}"
            updated = con.execute(
                "UPDATE tasks SET status='running', version=?, lease_owner=?, "
                "lease_expires_at=?, updated_at=? "
                "WHERE task_id=? AND version=? AND status=?",
                (version + 1, owner, now + lease_s, now, task_id, version, status))
            if updated.rowcount != 1:
                raise TaskConflict("version_conflict",
                                   f"{task_id} 已被其他执行者领取", task_id)
            con.execute(
                "INSERT INTO attempts(attempt_id,task_id,run_id,status,started_at,"
                "lease_owner,input_fingerprint) VALUES(?,?,?,?,?,?,?)",
                (attempt_id, task_id, run_id or owner, "running", now, owner,
                 str(row["input_fingerprint"] or "")))
            EventOutbox.emit(con, project_id=str(row["project_id"]),
                             aggregate_id=task_id, aggregate_version=version + 1,
                             event_type="task.claimed",
                             payload={"owner": owner, "attempt_id": attempt_id},
                             now=now)
            fresh = con.execute("SELECT * FROM tasks WHERE task_id=?",
                                (task_id,)).fetchone()
        handle = row_dict(fresh) or {}
        handle.update({"attempt_id": attempt_id, "lease_owner": owner,
                       "lease_expires_at": now + lease_s,
                       "attempt_version": version + 1})
        return handle

    def heartbeat(self, task_id: str, owner: str, *, lease_s: float = 60,
                  now: float | None = None) -> float:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            updated = con.execute(
                "UPDATE tasks SET lease_expires_at=?, updated_at=? "
                "WHERE task_id=? AND status='running' AND lease_owner=?",
                (now + lease_s, now, task_id, owner))
            if updated.rowcount != 1:
                raise TaskConflict("lease_invalid",
                                   f"{task_id} 的租约不属于 {owner} 或已结束", task_id)
        return now + lease_s

    def complete(self, task_id: str, owner: str, *, expected_version: int,
                 output_ref: str = "", now: float | None = None) -> dict[str, Any]:
        return self._finish(task_id, owner, expected_version, target="completed",
                            output_ref=output_ref, failure="", now=now,
                            retryable=False)

    def fail(self, task_id: str, owner: str, *, expected_version: int,
             failure: str, retryable: bool = False,
             now: float | None = None) -> dict[str, Any]:
        target = "needs_revision" if retryable else "blocked"
        return self._finish(task_id, owner, expected_version, target=target,
                            output_ref="", failure=failure, now=now,
                            retryable=retryable)

    def _finish(self, task_id: str, owner: str, expected_version: int, *,
                target: str, output_ref: str, failure: str, retryable: bool,
                now: float | None) -> dict[str, Any]:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            row = con.execute("SELECT * FROM tasks WHERE task_id=?",
                              (task_id,)).fetchone()
            if row is None:
                raise TaskConflict("not_found", f"任务不存在：{task_id}", task_id)
            if row["status"] != "running":
                raise TaskConflict("not_running",
                                   f"{task_id} 状态为 {row['status']}", task_id)
            if row["lease_owner"] != owner:
                raise TaskConflict("not_owner",
                                   f"{task_id} 的租约不属于 {owner}", task_id)
            if int(row["version"]) != int(expected_version):
                raise TaskConflict("version_conflict",
                                   f"{task_id} 版本已变化（期望 {expected_version}，"
                                   f"实际 {row['version']}）", task_id)
            if int(row["lease_expires_at"] or 0) <= now:
                raise TaskConflict("lease_expired",
                                   f"{task_id} 租约已过期，结果不能提交", task_id)
            attempt_id = f"{task_id}:A{int(row['version'])}"
            changed = con.execute(
                "UPDATE tasks SET status=?, version=?, lease_owner=NULL, "
                "lease_expires_at=NULL, updated_at=? "
                "WHERE task_id=? AND version=? AND status='running' "
                "AND lease_owner=? AND lease_expires_at>?",
                (target, int(row["version"]) + 1, now, task_id,
                 expected_version, owner, now))
            if changed.rowcount != 1:
                raise TaskConflict("cas_failed",
                                   f"{task_id} 提交竞争失败", task_id)
            con.execute(
                "UPDATE attempts SET status=?, finished_at=?, failure=?, "
                "output_ref=? WHERE attempt_id=?",
                ("completed" if target == "completed" else "failed", now,
                 failure, output_ref, attempt_id))
            EventOutbox.emit(
                con, project_id=str(row["project_id"]), aggregate_id=task_id,
                aggregate_version=int(row["version"]) + 1,
                event_type="task.completed" if target == "completed" else "task.failed",
                payload={"status": target, "attempt_id": attempt_id,
                         "retryable": retryable, "failure": failure[:500],
                         "output_ref": output_ref}, now=now)
            fresh = con.execute("SELECT * FROM tasks WHERE task_id=?",
                                (task_id,)).fetchone()
        return row_dict(fresh) or {}

    def recover_expired(self, *, now: float | None = None,
                        grace_s: float = 0) -> list[dict[str, Any]]:
        now = time.time() if now is None else now
        recovered: list[dict[str, Any]] = []
        with self.db.transaction() as con:
            rows = con.execute(
                "SELECT * FROM tasks WHERE status='running' "
                "AND lease_expires_at IS NOT NULL AND lease_expires_at<=?",
                (now - grace_s,)).fetchall()
            for row in rows:
                task_id = str(row["task_id"])
                version = int(row["version"])
                con.execute(
                    "UPDATE tasks SET status='recovering', version=?, "
                    "lease_owner=NULL, lease_expires_at=NULL, updated_at=? "
                    "WHERE task_id=? AND version=? AND status='running'",
                    (version + 1, now, task_id, version))
                con.execute(
                    "UPDATE attempts SET status='orphaned', finished_at=? "
                    "WHERE attempt_id=?",
                    (now, f"{task_id}:A{version}"))
                EventOutbox.emit(
                    con, project_id=str(row["project_id"]), aggregate_id=task_id,
                    aggregate_version=version + 1, event_type="task.orphaned",
                    payload={"task_id": task_id,
                             "lease_owner": row["lease_owner"]}, now=now)
                recovered.append({"task_id": task_id,
                                  "previous_owner": row["lease_owner"]})
        return recovered

    def requeue(self, task_id: str, reason: str = "",
                *, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            row = con.execute("SELECT * FROM tasks WHERE task_id=?",
                              (task_id,)).fetchone()
            if row is None:
                raise TaskConflict("not_found", f"任务不存在：{task_id}", task_id)
            if row["status"] not in ("recovering", "needs_revision", "blocked"):
                raise TaskConflict("not_requeueable",
                                   f"{task_id} 状态 {row['status']} 不能重新入队",
                                   task_id)
            version = int(row["version"]) + 1
            con.execute(
                "UPDATE tasks SET status='ready', version=?, lease_owner=NULL, "
                "lease_expires_at=NULL, updated_at=? WHERE task_id=?",
                (version, now, task_id))
            EventOutbox.emit(con, project_id=str(row["project_id"]),
                             aggregate_id=task_id, aggregate_version=version,
                             event_type="task.requeued",
                             payload={"reason": reason}, now=now)
            fresh = con.execute("SELECT * FROM tasks WHERE task_id=?",
                                (task_id,)).fetchone()
        return row_dict(fresh) or {}

    def cancel(self, task_id: str, reason: str = "",
               *, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            row = con.execute("SELECT * FROM tasks WHERE task_id=?",
                              (task_id,)).fetchone()
            if row is None:
                raise TaskConflict("not_found", f"任务不存在：{task_id}", task_id)
            if row["status"] in ("completed", "cancelled"):
                return row_dict(row) or {}
            version = int(row["version"]) + 1
            con.execute(
                "UPDATE tasks SET status='cancelled', version=?, lease_owner=NULL, "
                "lease_expires_at=NULL, updated_at=? WHERE task_id=?",
                (version, now, task_id))
            EventOutbox.emit(con, project_id=str(row["project_id"]),
                             aggregate_id=task_id, aggregate_version=version,
                             event_type="task.cancelled",
                             payload={"reason": reason}, now=now)
            fresh = con.execute("SELECT * FROM tasks WHERE task_id=?",
                                (task_id,)).fetchone()
        return row_dict(fresh) or {}

    def set_iteration_status(self, iteration_id: str, status: str,
                             *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            row = con.execute("SELECT project_id FROM iterations WHERE iteration_id=?",
                              (iteration_id,)).fetchone()
            if row is None:
                raise TaskConflict("not_found", f"迭代不存在：{iteration_id}")
            con.execute("UPDATE iterations SET status=?, updated_at=? "
                        "WHERE iteration_id=?", (status, now, iteration_id))
            EventOutbox.emit(con, project_id=str(row["project_id"]),
                             aggregate_id=iteration_id, aggregate_version=1,
                             event_type="iteration.status",
                             payload={"status": status}, now=now)

    # ---------- artifacts ----------
    def record_artifact(self, *, path: str, content_hash: str,
                        project_id: str, task_id: str = "",
                        attempt_id: str = "", kind: str = "file",
                        producer: str = "role", now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        artifact_id = f"ART-{uuid.uuid4().hex[:12]}"
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO artifacts(artifact_id,project_id,task_id,attempt_id,"
                "path,content_hash,kind,producer,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (artifact_id, project_id, task_id, attempt_id, path, content_hash,
                 kind, producer, now))
        return {"artifact_id": artifact_id, "path": path,
                "content_hash": content_hash, "kind": kind, "producer": producer}

    def counts(self) -> dict[str, int]:
        with self.db.read() as con:
            rows = con.execute("SELECT status, COUNT(*) n FROM tasks GROUP BY status").fetchall()
            artifacts = con.execute("SELECT COUNT(*) n FROM artifacts").fetchone()["n"]
        return {**{str(r["status"]): int(r["n"]) for r in rows},
                "artifacts": int(artifacts)}
