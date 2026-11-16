"""Append-only verdict ledger, bound to packet/subject/baseline hashes."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .signing import record_hash, sign_object, verify_object


class VerdictLedgerError(RuntimeError):
    pass


class VerdictStore:
    def __init__(self, path: str | os.PathLike, key: bytes) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.key = key
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._invalidated_gates: set[str] = set()
        self._last_hash = ""
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("prev_hash") != self._last_hash:
                    raise VerdictLedgerError(f"{self.path}:{lineno} 哈希链断裂")
                if not verify_object(rec, self.key):
                    raise VerdictLedgerError(f"{self.path}:{lineno} 签名无效")
                if record_hash(rec) != rec.get("record_hash"):
                    raise VerdictLedgerError(f"{self.path}:{lineno} record_hash 不匹配")
                self._last_hash = rec["record_hash"]
                self._records.append(rec)
                if rec.get("type") == "verdict":
                    self._by_id[rec["verdict_id"]] = rec
                elif rec.get("type") == "invalidation":
                    gate = rec.get("gate_id")
                    if gate:
                        self._invalidated_gates.add(gate)

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
            if rec.get("type") == "verdict":
                self._by_id[rec["verdict_id"]] = rec
        return rec

    def put(self, verdict: dict[str, Any]) -> dict[str, Any]:
        rec = {"type": "verdict", **verdict}
        return self._append(rec)

    def get(self, verdict_id: str) -> dict[str, Any] | None:
        return self._by_id.get(verdict_id)

    def valid_for(self, *, gate_id: str, packet_hash: str, subject_hash: str,
                  baseline_fp: str, now: int | None = None) -> dict[str, Any] | None:
        now = int(time.time()) if now is None else now
        for rec in reversed(self._records):
            if rec.get("type") != "verdict":
                continue
            if rec.get("gate_id") != gate_id:
                continue
            if gate_id in self._invalidated_gates:
                return None
            if rec.get("packet_hash") != packet_hash:
                continue
            if rec.get("input_hash") != subject_hash:
                continue
            if rec.get("baseline_fp") != baseline_fp:
                continue
            if int(rec.get("expires_at", 0)) <= now:
                continue
            if rec.get("decision") not in ("approve", "approve_with_conditions"):
                continue
            return rec
        return None

    def invalidate_gate(self, gate_id: str, reason: str,
                        *, now: int | None = None) -> None:
        now = int(time.time()) if now is None else now
        self._append({"type": "invalidation", "gate_id": gate_id,
                      "reason": reason, "created_at": now})
        self._invalidated_gates.add(gate_id)

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
