"""Knowledge authority levels and lifecycle.

Retrieved experience is advice, not an approved requirement. Candidate entries
never override contracts/requirements; promotion needs review evidence and a
revoked entry is no longer returned to active tasks.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from ..persistence.db import Database, row_dict

AUTHORITIES = ("contract", "decision", "requirement", "experience", "candidate")
STATUSES = ("candidate", "reviewed", "active", "deprecated", "revoked")
HIGH_AUTHORITY = ("contract", "decision", "requirement")


class KnowledgeAuthority:
    def __init__(self, db: Database) -> None:
        self.db = db
        db.migrate()

    def add(self, *, project_id: str, title: str, body: str,
            authority: str = "candidate", conditions: str = "",
            source_refs: list[str] | None = None,
            approve: bool = False, now: float | None = None) -> dict[str, Any]:
        if authority not in AUTHORITIES:
            raise ValueError(f"未知权威等级：{authority}")
        now = time.time() if now is None else now
        entry_id = f"KB-{uuid.uuid4().hex[:10]}"
        status = "active" if approve and authority in HIGH_AUTHORITY else "candidate"
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO knowledge_entries(entry_id,project_id,title,body,"
                "authority,conditions,status,source_refs,verified_by,created_at,"
                "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (entry_id, project_id, title, body, authority, conditions, status,
                 json.dumps(source_refs or [], ensure_ascii=False), "", now, now))
            row = con.execute("SELECT * FROM knowledge_entries WHERE entry_id=?",
                              (entry_id,)).fetchone()
        return self._decode(row) or {}

    def get(self, entry_id: str) -> dict[str, Any] | None:
        with self.db.read() as con:
            return self._decode(con.execute(
                "SELECT * FROM knowledge_entries WHERE entry_id=?",
                (entry_id,)).fetchone())

    def review(self, entry_id: str, *, reviewer: str, evidence_ref: str,
               now: float | None = None) -> dict[str, Any]:
        if not reviewer or not evidence_ref:
            raise ValueError("复核需要 reviewer 和 evidence_ref")
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            row = con.execute("SELECT * FROM knowledge_entries WHERE entry_id=?",
                              (entry_id,)).fetchone()
            if row is None:
                raise KeyError(f"知识条目不存在：{entry_id}")
            if row["status"] not in ("candidate", "reviewed"):
                raise ValueError(f"条目状态 {row['status']} 不能复核")
            con.execute("UPDATE knowledge_entries SET status='reviewed', "
                        "verified_by=?, updated_at=? WHERE entry_id=?",
                        (f"{reviewer}:{evidence_ref}", now, entry_id))
            fresh = con.execute("SELECT * FROM knowledge_entries WHERE entry_id=?",
                                (entry_id,)).fetchone()
        return self._decode(fresh) or {}

    def activate(self, entry_id: str, *, actor: str,
                 now: float | None = None) -> dict[str, Any]:
        if not actor:
            raise ValueError("晋升需要明确 actor")
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            row = con.execute("SELECT * FROM knowledge_entries WHERE entry_id=?",
                              (entry_id,)).fetchone()
            if row is None:
                raise KeyError(f"知识条目不存在：{entry_id}")
            if row["status"] != "reviewed":
                raise ValueError("只有 reviewed 条目可以晋升为 active")
            con.execute("UPDATE knowledge_entries SET status='active', updated_at=? "
                        "WHERE entry_id=?", (now, entry_id))
            fresh = con.execute("SELECT * FROM knowledge_entries WHERE entry_id=?",
                                (entry_id,)).fetchone()
        return self._decode(fresh) or {}

    def revoke(self, entry_id: str, *, reason: str,
               now: float | None = None) -> dict[str, Any]:
        if not reason:
            raise ValueError("撤销知识必须说明理由")
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            con.execute("UPDATE knowledge_entries SET status='revoked', "
                        "conditions=conditions || ? , updated_at=? WHERE entry_id=?",
                        (f"\nrevoked: {reason}", now, entry_id))
            fresh = con.execute("SELECT * FROM knowledge_entries WHERE entry_id=?",
                                (entry_id,)).fetchone()
        return self._decode(fresh) or {}

    def search(self, query: str, *, project_id: str | None = None,
               allow_candidate: bool = False,
               authorities: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        tokens = [t for t in (query or "").lower().split() if t]
        allowed_status = ("active", "reviewed", "candidate") if allow_candidate else ("active",)
        sql = "SELECT * FROM knowledge_entries WHERE status IN (" + \
              ",".join("?" for _ in allowed_status) + ")"
        params: list[Any] = list(allowed_status)
        if project_id:
            sql += " AND project_id=?"
            params.append(project_id)
        if authorities:
            sql += " AND authority IN (" + ",".join("?" for _ in authorities) + ")"
            params.extend(authorities)
        with self.db.read() as con:
            rows = [self._decode(r) or {} for r in con.execute(sql, params)]
        hits = []
        for row in rows:
            haystack = f"{row['title']} {row['body']} {row['conditions']}".lower()
            score = sum(1 for token in tokens if token in haystack)
            if tokens and score == 0:
                continue
            row["score"] = score
            hits.append(row)
        hits.sort(key=lambda item: (item["authority"] in HIGH_AUTHORITY,
                                    item.get("score", 0)), reverse=True)
        return hits

    @staticmethod
    def _decode(row) -> dict[str, Any] | None:
        data = row_dict(row)
        if data is None:
            return None
        try:
            data["source_refs"] = json.loads(data.pop("source_refs"))
        except json.JSONDecodeError:
            data["source_refs"] = []
        return data
