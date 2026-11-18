"""SQLite schema and connection management.

Small, local, transactional authority for iterations, tasks, attempts,
artifacts, findings and the event outbox. JSON files remain compatibility
views for the dashboard; they are not the write authority.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class SchemaVersionError(RuntimeError):
    pass


SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_meta (
  version INTEGER NOT NULL,
  applied_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  project_type TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS iterations (
  iteration_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL,
  mode TEXT NOT NULL DEFAULT 'formal',
  budget_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  role TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  stage TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT,
  lease_expires_at REAL,
  input_fingerprint TEXT NOT NULL DEFAULT '',
  write_scope TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
  attempt_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  model TEXT NOT NULL DEFAULT '',
  backend TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  started_at REAL NOT NULL,
  finished_at REAL,
  failure TEXT NOT NULL DEFAULT '',
  output_ref TEXT NOT NULL DEFAULT '',
  lease_owner TEXT NOT NULL DEFAULT '',
  input_fingerprint TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '',
  attempt_id TEXT NOT NULL DEFAULT '',
  path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'file',
  producer TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  aggregate_version INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  causation_id TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  dispatched_at REAL,
  attempts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS consumers (
  consumer_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  processed_at REAL NOT NULL,
  PRIMARY KEY (consumer_id, event_id)
);

CREATE TABLE IF NOT EXISTS findings (
  finding_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  symptom TEXT NOT NULL,
  root_cause TEXT NOT NULL DEFAULT '',
  owner_role TEXT NOT NULL DEFAULT '',
  evidence_json TEXT NOT NULL DEFAULT '[]',
  task_id TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS verifications (
  verification_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  acceptance_id TEXT NOT NULL,
  subject_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  environment TEXT NOT NULL DEFAULT '',
  steps TEXT NOT NULL DEFAULT '',
  expected TEXT NOT NULL DEFAULT '',
  actual TEXT NOT NULL DEFAULT '',
  verified_by TEXT NOT NULL,
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
  action_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  root_cause TEXT NOT NULL,
  owner_role TEXT NOT NULL,
  target_iteration TEXT NOT NULL DEFAULT '',
  trigger TEXT NOT NULL DEFAULT '',
  deliverable TEXT NOT NULL DEFAULT '',
  verification TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_entries (
  entry_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  authority TEXT NOT NULL,
  conditions TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  source_refs TEXT NOT NULL DEFAULT '[]',
  verified_by TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_fingerprint ON findings(project_id, fingerprint);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox(dispatched_at, seq);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=15000")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        con = self.connect()
        try:
            yield con
        finally:
            con.close()

    def migrate(self, *, now: float | None = None) -> int:
        now = time.time() if now is None else now
        with self.read() as con:
            con.executescript(SCHEMA_SQL)
            row = con.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            if row is None:
                con.execute("INSERT INTO schema_meta(version, applied_at) VALUES(?,?)",
                            (SCHEMA_VERSION, now))
                con.commit()
                return SCHEMA_VERSION
            version = int(row["version"])
            if version > SCHEMA_VERSION:
                raise SchemaVersionError(
                    f"数据库 schema {version} 高于本程序支持的 {SCHEMA_VERSION}；"
                    "只读诊断，不写入")
            if version < SCHEMA_VERSION:
                con.execute("UPDATE schema_meta SET version=?, applied_at=?",
                            (SCHEMA_VERSION, now))
                con.commit()
            return SCHEMA_VERSION

    def schema_version(self) -> int:
        with self.read() as con:
            try:
                row = con.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            except sqlite3.Error:
                return 0
            return int(row["version"]) if row else 0

    def integrity_check(self) -> str:
        with self.read() as con:
            row = con.execute("PRAGMA integrity_check").fetchone()
            return str(row[0]) if row else "unknown"


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None
