"""Transactional event outbox and idempotent consumers."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any, Callable

from .db import Database


class EventOutbox:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def emit(con: sqlite3.Connection, *, project_id: str, aggregate_id: str,
             aggregate_version: int, event_type: str,
             payload: dict[str, Any] | None = None, causation_id: str = "",
             event_id: str | None = None, now: float | None = None) -> str:
        """Insert event and outbox row in the caller's transaction."""
        now = time.time() if now is None else now
        event_id = event_id or f"EVT-{uuid.uuid4().hex[:16]}"
        con.execute(
            "INSERT INTO events(event_id,project_id,aggregate_id,aggregate_version,"
            "event_type,payload_json,causation_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (event_id, project_id, aggregate_id, aggregate_version, event_type,
             json.dumps(payload or {}, ensure_ascii=False), causation_id, now))
        con.execute("INSERT OR IGNORE INTO outbox(event_id) VALUES(?)", (event_id,))
        return event_id

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.read() as con:
            rows = con.execute(
                "SELECT e.* FROM outbox o JOIN events e ON e.event_id=o.event_id "
                "WHERE o.dispatched_at IS NULL ORDER BY o.seq LIMIT ?", (limit,)
            ).fetchall()
        return [self._event(row) for row in rows]

    @staticmethod
    def _event(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["payload"] = json.loads(data.pop("payload_json"))
        except json.JSONDecodeError:
            data["payload"] = {}
        return data

    def is_processed(self, consumer_id: str, event_id: str) -> bool:
        with self.db.read() as con:
            row = con.execute(
                "SELECT 1 FROM consumers WHERE consumer_id=? AND event_id=?",
                (consumer_id, event_id)).fetchone()
        return row is not None

    def mark_processed(self, consumer_id: str, event_id: str,
                       *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self.db.transaction() as con:
            con.execute("INSERT OR IGNORE INTO consumers(consumer_id,event_id,"
                        "processed_at) VALUES(?,?,?)", (consumer_id, event_id, now))
            con.execute("UPDATE outbox SET dispatched_at=? WHERE event_id=?",
                        (now, event_id))

    def dispatch(self, consumer_id: str,
                 handler: Callable[[dict[str, Any]], None],
                 *, limit: int = 100) -> dict[str, int]:
        """Deliver pending events at most once per consumer.

        A handler failure leaves the outbox row pending for retry; the consumer
        row is only written after the handler returns.
        """
        delivered = 0
        skipped = 0
        failed = 0
        for event in self.pending(limit=limit):
            if self.is_processed(consumer_id, event["event_id"]):
                skipped += 1
                self.mark_processed(consumer_id, event["event_id"])
                continue
            try:
                handler(event)
            except Exception:
                failed += 1
                continue
            self.mark_processed(consumer_id, event["event_id"])
            delivered += 1
        return {"delivered": delivered, "skipped": skipped, "failed": failed}

    def counts(self) -> dict[str, int]:
        with self.db.read() as con:
            pending = con.execute(
                "SELECT COUNT(*) n FROM outbox WHERE dispatched_at IS NULL"
            ).fetchone()["n"]
            total = con.execute("SELECT COUNT(*) n FROM outbox").fetchone()["n"]
        return {"pending": int(pending), "total": int(total)}
