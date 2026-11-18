"""Verified evidence consumption at the gate trust boundary.

Callers may not pass a hand-built ``result=pass`` dictionary and have it treated
as proof. They pass evidence IDs; the resolver looks the record up in the
signed append-only ledger, re-verifies signature/chain/expiry and checks that it
was produced for the current subject and baseline. ``VerifiedEvidence`` can only
be constructed by this module.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .signing import verify_object
from .store import EvidenceStore, LedgerIntegrityError


class EvidenceResolutionError(RuntimeError):
    def __init__(self, code: str, message: str, evidence_id: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.evidence_id = evidence_id

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self),
                "evidence_id": self.evidence_id}


@dataclass(frozen=True)
class VerifiedEvidence:
    evidence_id: str
    kind: str
    result: str
    subject_hash: str
    tool: str
    tool_version: str
    signed_by: str
    baseline_fp: str
    created_at: int
    expires_at: int


class EvidenceResolver:
    def __init__(self, ledger_path: str | Path, key: bytes, *,
                 now: int | None = None) -> None:
        self.path = Path(ledger_path)
        self.key = key
        self._now = now
        self._store_error = ""
        try:
            self.store: EvidenceStore | None = EvidenceStore(self.path, key)
        except LedgerIntegrityError as exc:
            self.store = None
            self._store_error = str(exc)

    @property
    def integrity_error(self) -> str:
        return self._store_error

    def _now_value(self) -> int:
        return int(time.time()) if self._now is None else self._now

    def resolve(self, evidence_id: str, *, kind: str | None = None,
                subject_hash: str | None = None,
                baseline_fp: str | None = None) -> VerifiedEvidence:
        if not evidence_id:
            raise EvidenceResolutionError("missing_id", "没有提供证据 ID")
        if self.store is None:
            raise EvidenceResolutionError(
                "ledger_integrity", f"证据账本不可信：{self._store_error}", evidence_id)
        rec = self.store.get(evidence_id)
        if rec is None:
            raise EvidenceResolutionError(
                "not_found", f"证据 {evidence_id} 不存在于签名账本", evidence_id)
        if not verify_object(rec, self.key):
            raise EvidenceResolutionError(
                "signature_invalid", f"证据 {evidence_id} 签名无效", evidence_id)
        if not self.store.valid(rec, now=self._now_value()):
            raise EvidenceResolutionError(
                "expired_or_revoked",
                f"证据 {evidence_id} 已过期、被撤销或已失效", evidence_id)
        if kind and rec.get("kind") != kind:
            raise EvidenceResolutionError(
                "kind_mismatch",
                f"证据 {evidence_id} 类型为 {rec.get('kind')}，需要 {kind}", evidence_id)
        if subject_hash and rec.get("subject_hash") != subject_hash:
            raise EvidenceResolutionError(
                "subject_mismatch",
                f"证据 {evidence_id} 属于对象 {rec.get('subject_hash')}，"
                f"不是当前对象 {subject_hash}", evidence_id)
        if baseline_fp and rec.get("baseline_fp") not in (baseline_fp, "project", ""):
            raise EvidenceResolutionError(
                "baseline_mismatch",
                f"证据 {evidence_id} 属于基线 {rec.get('baseline_fp')}，"
                f"不是 {baseline_fp}", evidence_id)
        return VerifiedEvidence(
            evidence_id=evidence_id, kind=str(rec.get("kind")),
            result=str(rec.get("result")), subject_hash=str(rec.get("subject_hash")),
            tool=str(rec.get("tool")), tool_version=str(rec.get("tool_version")),
            signed_by=str(rec.get("signed_by")), baseline_fp=str(rec.get("baseline_fp")),
            created_at=int(rec.get("created_at", 0)),
            expires_at=int(rec.get("expires_at", 0)))

    def resolve_kind(self, kind: str, *, subject_hash: str | None = None,
                     baseline_fp: str | None = None) -> VerifiedEvidence:
        if self.store is None:
            raise EvidenceResolutionError(
                "ledger_integrity", f"证据账本不可信：{self._store_error}")
        rows = self.store.query(kind, subject_hash) if subject_hash else []
        if not rows:
            raise EvidenceResolutionError(
                "not_found", f"当前对象没有有效的 {kind} 证据")
        return self.resolve(str(rows[-1]["evidence_id"]), kind=kind,
                            subject_hash=subject_hash, baseline_fp=baseline_fp)

    def resolve_many(self, evidence_ids: Iterable[str], **constraints: Any
                     ) -> list[VerifiedEvidence]:
        return [self.resolve(eid, **constraints) for eid in evidence_ids]
