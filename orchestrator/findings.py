"""Findings: triage, root-cause routing, dedupe and repair-task creation.

A repeated symptom is associated with the existing finding instead of creating
competing repair tasks. A finding is only closed with a verification reference
(or an explicit duplicate/rejected reason); implementers cannot close their own
defects.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from typing import Any

from .persistence.db import Database, row_dict
from .persistence.tasks import TaskStore

CATEGORIES = {
    "source_parse": "product",
    "requirement_gap": "product",
    "design_gap": "ui",
    "contract_conflict": "arch",
    "implementation": "backend",
    "integration": "backend",
    "environment": "ops",
    "verification_gap": "qa",
    "process_gap": "retro",
    "unclassified": "",
}
SEVERITIES = ("fatal", "critical", "major", "minor", "info")
STATUSES = ("reported", "triaged", "reproduced", "in_progress",
            "ready_for_retest", "verified", "closed", "cannot_reproduce",
            "duplicate", "deferred", "rejected")
CLOSED = {"closed", "duplicate", "rejected", "deferred"}
STAGE = {
    "product": "product", "ui": "design", "arch": "design",
    "backend": "implementation", "frontend": "implementation",
    "ops": "release", "qa": "quality", "retro": "release",
}
WRITE_SCOPE = {
    "product": "docs/product/", "ui": "docs/design/",
    "arch": "docs/architecture/", "backend": "src/backend/",
    "frontend": "src/frontend/", "ops": "docs/ops/",
    "qa": "tests/", "retro": "docs/retro/",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _ensure_columns(db: Database) -> None:
    with db.read() as con:
        cols = {r["name"] for r in con.execute("PRAGMA table_info(findings)")}
        if "owner_role" not in cols:
            con.execute("ALTER TABLE findings ADD COLUMN owner_role TEXT NOT NULL DEFAULT ''")
            con.commit()


class FindingStore:
    def __init__(self, db: Database) -> None:
        self.db = db
        db.migrate()
        _ensure_columns(db)

    @staticmethod
    def fingerprint(symptom: str, category: str = "unclassified") -> str:
        return hashlib.sha256(f"{category}|{_norm(symptom)}".encode("utf-8")).hexdigest()

    def create(self, *, project_id: str, symptom: str,
               category: str = "unclassified", severity: str = "major",
               evidence: list[dict[str, Any]] | None = None,
               fingerprint: str | None = None,
               now: float | None = None) -> dict[str, Any]:
        if not str(symptom).strip():
            raise ValueError("finding 缺少 symptom")
        if category not in CATEGORIES:
            raise ValueError(f"未知 finding 分类：{category}")
        if severity not in SEVERITIES:
            raise ValueError(f"未知严重度：{severity}")
        now = time.time() if now is None else now
        fp = fingerprint or self.fingerprint(symptom, category)
        with self.db.transaction() as con:
            existing = con.execute(
                "SELECT * FROM findings WHERE project_id=? AND fingerprint=? "
                "AND status NOT IN ('closed','duplicate','rejected','deferred') "
                "ORDER BY created_at DESC LIMIT 1", (project_id, fp)).fetchone()
            if existing is not None:
                return {**row_dict(existing), "created": False}
            finding_id = f"FND-{uuid.uuid4().hex[:12]}"
            con.execute(
                "INSERT INTO findings(finding_id,project_id,fingerprint,category,"
                "severity,status,symptom,root_cause,owner_role,evidence_json,"
                "task_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (finding_id, project_id, fp, category, severity, "reported",
                 str(symptom).strip(), "", CATEGORIES.get(category, ""),
                 json.dumps(evidence or [], ensure_ascii=False), "", now, now))
            row = con.execute("SELECT * FROM findings WHERE finding_id=?",
                              (finding_id,)).fetchone()
        return {**row_dict(row), "created": True}

    def get(self, finding_id: str) -> dict[str, Any] | None:
        with self.db.read() as con:
            row = con.execute("SELECT * FROM findings WHERE finding_id=?",
                              (finding_id,)).fetchone()
        return self._decode(row)

    def list(self, *, project_id: str | None = None,
             status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM findings"
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id=?")
            params.append(project_id)
        if status:
            clauses.append("status=?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at ASC"
        with self.db.read() as con:
            rows = con.execute(sql, params).fetchall()
        return [self._decode(r) or {} for r in rows]

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        data = row_dict(row)
        if data is None:
            return None
        try:
            data["evidence"] = json.loads(data.pop("evidence_json"))
        except json.JSONDecodeError:
            data["evidence"] = []
        return data

    def triage(self, finding_id: str, *, category: str | None = None,
               severity: str | None = None, root_cause: str = "",
               now: float | None = None) -> dict[str, Any]:
        if category is not None and category not in CATEGORIES:
            raise ValueError(f"未知 finding 分类：{category}")
        if severity is not None and severity not in SEVERITIES:
            raise ValueError(f"未知严重度：{severity}")
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            row = con.execute("SELECT * FROM findings WHERE finding_id=?",
                              (finding_id,)).fetchone()
            if row is None:
                raise KeyError(f"finding 不存在：{finding_id}")
            if row["status"] in CLOSED:
                raise ValueError(f"finding 已关闭：{row['status']}")
            category = category or str(row["category"])
            owner = CATEGORIES.get(category, "")
            con.execute(
                "UPDATE findings SET category=?, severity=?, owner_role=?, "
                "root_cause=?, status='triaged', updated_at=? WHERE finding_id=?",
                (category, severity or row["severity"], owner,
                 root_cause or row["root_cause"], now, finding_id))
            fresh = con.execute("SELECT * FROM findings WHERE finding_id=?",
                                (finding_id,)).fetchone()
        data = self._decode(fresh) or {}
        data["suggested_owner"] = owner
        data["suggested_stage"] = STAGE.get(owner, "")
        return data

    def create_repair_task(self, finding_id: str, *, task_store: TaskStore,
                           iteration_id: str, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        finding = self.get(finding_id)
        if not finding:
            raise KeyError(f"finding 不存在：{finding_id}")
        if finding.get("task_id"):
            return task_store.get(str(finding["task_id"])) or {}
        owner = str(finding.get("owner_role") or "")
        if not owner:
            raise ValueError("finding 未分诊，不能创建修复任务")
        task_id = f"T-{iteration_id}-F-{finding_id.split('-')[-1]}"
        task = task_store.create_task(
            task_id=task_id, project_id=str(finding["project_id"]),
            iteration_id=iteration_id, role=owner,
            title=f"修复 {finding_id}: {finding['symptom'][:60]}",
            stage=STAGE.get(owner, "quality"),
            input_fingerprint=str(finding["fingerprint"]),
            write_scope=WRITE_SCOPE.get(owner, ""))
        with self.db.transaction() as con:
            con.execute("UPDATE findings SET task_id=?, status='in_progress', "
                        "updated_at=? WHERE finding_id=?",
                        (task_id, now, finding_id))
        return task

    def close(self, finding_id: str, *, verification_ref: str = "",
              reason: str = "", now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        finding = self.get(finding_id)
        if not finding:
            raise KeyError(f"finding 不存在：{finding_id}")
        if verification_ref:
            status = "closed"
        elif reason.lower().startswith("duplicate"):
            status = "duplicate"
        elif reason.lower().startswith(("reject", "not a bug")):
            status = "rejected"
        else:
            raise ValueError("关闭 finding 需要 verification_ref，或明确的 duplicate/rejected 理由")
        with self.db.transaction() as con:
            con.execute(
                "UPDATE findings SET status=?, root_cause=?, updated_at=? "
                "WHERE finding_id=?",
                (status, (finding.get("root_cause") or "")
                 + (f"\nclose: {reason}" if reason else
                    f"\nverification: {verification_ref}"), now, finding_id))
            fresh = con.execute("SELECT * FROM findings WHERE finding_id=?",
                                (finding_id,)).fetchone()
        return self._decode(fresh) or {}

    def counts(self, project_id: str | None = None) -> dict[str, int]:
        sql = "SELECT status, COUNT(*) n FROM findings"
        params: list[Any] = []
        if project_id:
            sql += " WHERE project_id=?"
            params.append(project_id)
        sql += " GROUP BY status"
        with self.db.read() as con:
            rows = con.execute(sql, params).fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}
