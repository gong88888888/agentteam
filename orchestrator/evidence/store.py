"""Append-only evidence ledger with hash chain and HMAC signatures."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .signing import record_hash, sign_object, verify_object


class LedgerIntegrityError(RuntimeError):
    pass


class EvidenceStore:
    def __init__(self, path: str | os.PathLike, key: bytes) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.key = key
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._invalidated_ids: set[str] = set()
        self._invalidated_subjects: set[str] = set()
        self._invalidated_kinds: set[str] = set()
        self._invalidated_baselines: set[str] = set()
        self._last_hash = ""
        self._seq = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LedgerIntegrityError(f"{self.path}:{lineno} 非法 JSON") from exc
                if rec.get("prev_hash") != self._last_hash:
                    raise LedgerIntegrityError(f"{self.path}:{lineno} 哈希链断裂")
                if not verify_object(rec, self.key):
                    raise LedgerIntegrityError(f"{self.path}:{lineno} 签名无效")
                if record_hash(rec) != rec.get("record_hash"):
                    raise LedgerIntegrityError(f"{self.path}:{lineno} record_hash 不匹配")
                self._last_hash = rec["record_hash"]
                self._records.append(rec)
                self._apply(rec)

    def _apply(self, rec: dict[str, Any]) -> None:
        typ = rec.get("type")
        if typ == "evidence":
            self._by_id[rec["evidence_id"]] = rec
            self._seq = max(self._seq, int(rec["evidence_id"].split("-")[-1]))
        elif typ == "invalidation":
            target = rec.get("target", "")
            if target.startswith("id:"):
                self._invalidated_ids.add(target[3:])
            elif target.startswith("subject:"):
                self._invalidated_subjects.add(target[8:])
            elif target.startswith("kind:"):
                self._invalidated_kinds.add(target[5:])
            elif target.startswith("baseline:"):
                self._invalidated_baselines.add(target[9:])

    def _append(self, rec: dict[str, Any]) -> dict[str, Any]:
        rec = dict(rec)
        rec["prev_hash"] = self._last_hash
        rec = sign_object(rec, self.key)
        rec["record_hash"] = record_hash(rec)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._last_hash = rec["record_hash"]
            self._records.append(rec)
            self._apply(rec)
        return rec

    def add(self, *, kind: str, subject_hash: str, tool: str, tool_version: str,
            result: str, payload: dict[str, Any] | None = None,
            signed_by: str, baseline_fp: str, ttl_s: int = 3600,
            now: int | None = None) -> dict[str, Any]:
        if not signed_by.startswith(("tool:", "judge:")):
            raise ValueError("证据必须由 tool:* 或 judge:* 签名")
        if result not in ("pass", "fail"):
            raise ValueError("result 必须是 pass/fail")
        now = int(time.time()) if now is None else now
        with self._lock:
            self._seq += 1
            seq = self._seq
        rec = {
            "type": "evidence",
            "evidence_id": f"EV-{seq:06d}",
            "kind": kind,
            "subject_hash": subject_hash,
            "tool": tool,
            "tool_version": tool_version,
            "result": result,
            "payload": payload or {},
            "signed_by": signed_by,
            "created_at": now,
            "expires_at": now + ttl_s,
            "baseline_fp": baseline_fp,
            "invalidated_by": None,
        }
        return self._append(rec)

    def _is_invalidated(self, rec: dict[str, Any]) -> bool:
        return (rec["evidence_id"] in self._invalidated_ids
                or rec["subject_hash"] in self._invalidated_subjects
                or rec["kind"] in self._invalidated_kinds
                or rec["baseline_fp"] in self._invalidated_baselines)

    def valid(self, rec: dict[str, Any], *, now: int | None = None) -> bool:
        if rec.get("type") != "evidence":
            return False
        if rec.get("invalidated_by"):
            return False
        if self._is_invalidated(rec):
            return False
        now = int(time.time()) if now is None else now
        return int(rec["expires_at"]) > now

    def query(self, kind: str, subject_hash: str, *, now: int | None = None) -> list[dict[str, Any]]:
        now = int(time.time()) if now is None else now
        rows = [r for r in self._by_id.values()
                if r["kind"] == kind and r["subject_hash"] == subject_hash
                and self.valid(r, now=now)]
        rows.sort(key=lambda r: (r["created_at"], r["evidence_id"]))
        return rows

    def latest(self, kind: str, subject_hash: str, *, now: int | None = None) -> dict[str, Any] | None:
        rows = self.query(kind, subject_hash, now=now)
        return rows[-1] if rows else None

    def invalidate_subject(self, subject_hash: str, reason: str,
                           *, now: int | None = None) -> int:
        return self._invalidate(f"subject:{subject_hash}", reason, "subject_hash",
                                subject_hash, now)

    def invalidate_kind(self, kind: str, reason: str, *, now: int | None = None) -> int:
        return self._invalidate(f"kind:{kind}", reason, "kind", kind, now)

    def invalidate_baseline(self, baseline_fp: str, reason: str,
                            *, now: int | None = None) -> int:
        return self._invalidate(f"baseline:{baseline_fp}", reason, "baseline_fp",
                                baseline_fp, now)

    def _invalidate(self, target: str, reason: str, field: str, value: str,
                    now: int | None) -> int:
        now = int(time.time()) if now is None else now
        affected = sum(1 for r in self._by_id.values()
                       if r.get(field) == value and self.valid(r, now=now))
        self._append({
            "type": "invalidation",
            "target": target,
            "field": field,
            "value": value,
            "reason": reason,
            "created_at": now,
        })
        return affected

    def all(self) -> list[dict[str, Any]]:
        return list(self._by_id.values())

    def verify_chain(self) -> bool:
        last = ""
        for rec in self._records:
            if rec.get("prev_hash") != last:
                return False
            if not verify_object(rec, self.key):
                return False
            if record_hash(rec) != rec.get("record_hash"):
                return False
            last = rec["record_hash"]
        return True
