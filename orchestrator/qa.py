"""Independent QA verification.

An implementer cannot verify its own change. A ``pass`` requires current
verified evidence bound to the same subject; missing execution is ``not_run``,
not success. Findings are only closable with a passing verification.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from .evidence.resolver import EvidenceResolutionError, EvidenceResolver
from .persistence.db import Database, row_dict

STATUSES = ("pass", "fail", "blocked", "not_run", "waived")
IMPLEMENTATION_ACTORS = ("backend", "frontend", "dev", "implementer", "developer")


class VerificationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class IndependentVerifier:
    def __init__(self, db: Database) -> None:
        self.db = db
        db.migrate()

    def verify(self, *, project_id: str, acceptance_id: str,
               subject_hash: str, status: str, verified_by: str,
               evidence_ids: list[str] | None = None,
               resolver: EvidenceResolver | None = None,
               environment: str = "", steps: str = "", expected: str = "",
               actual: str = "", now: float | None = None) -> dict[str, Any]:
        if status not in STATUSES:
            raise VerificationError("invalid_status", f"未知验证状态：{status}")
        actor = str(verified_by).split(":")[0].strip().lower()
        if actor in IMPLEMENTATION_ACTORS:
            raise VerificationError(
                "self_verification",
                "实现者不能关闭或通过自己的缺陷；需要独立 QA/验证者")
        if not subject_hash:
            raise VerificationError("missing_subject", "验证必须绑定当前对象指纹")
        verified: list[str] = []
        if status == "pass":
            if not evidence_ids:
                raise VerificationError("unverified_pass",
                                        "pass 必须引用当前对象的证据")
            if resolver is None:
                raise VerificationError("unverified_pass",
                                        "pass 必须通过 EvidenceResolver 复核账本")
            for evidence_id in evidence_ids:
                try:
                    rec = resolver.resolve(evidence_id, subject_hash=subject_hash)
                except EvidenceResolutionError as exc:
                    raise VerificationError(
                        f"evidence_{exc.code}", str(exc)) from exc
                if rec.result != "pass":
                    raise VerificationError(
                        "evidence_failed", f"{evidence_id} 记录结果为 {rec.result}")
                verified.append(rec.evidence_id)
        now = time.time() if now is None else now
        verification_id = f"VER-{uuid.uuid4().hex[:12]}"
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO verifications(verification_id,project_id,acceptance_id,"
                "subject_hash,status,evidence_json,environment,steps,expected,actual,"
                "verified_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (verification_id, project_id, acceptance_id, subject_hash, status,
                 json.dumps(verified, ensure_ascii=False), environment, steps,
                 expected, actual, verified_by, now))
            row = con.execute("SELECT * FROM verifications WHERE verification_id=?",
                              (verification_id,)).fetchone()
        return self._decode(row) or {}

    @staticmethod
    def _decode(row) -> dict[str, Any] | None:
        data = row_dict(row)
        if data is None:
            return None
        try:
            data["evidence"] = json.loads(data.pop("evidence_json"))
        except json.JSONDecodeError:
            data["evidence"] = []
        return data

    def get(self, verification_id: str) -> dict[str, Any] | None:
        with self.db.read() as con:
            row = con.execute("SELECT * FROM verifications WHERE verification_id=?",
                              (verification_id,)).fetchone()
        return self._decode(row)

    def for_subject(self, subject_hash: str) -> list[dict[str, Any]]:
        with self.db.read() as con:
            rows = con.execute(
                "SELECT * FROM verifications WHERE subject_hash=? "
                "ORDER BY created_at DESC", (subject_hash,)).fetchall()
        return [self._decode(r) or {} for r in rows]

    def can_close_finding(self, finding: dict[str, Any],
                          verification_id: str) -> tuple[bool, str]:
        verification = self.get(verification_id)
        if not verification:
            return False, "验证记录不存在"
        if verification["status"] != "pass":
            return False, f"验证状态为 {verification['status']}"
        finding_subject = str(finding.get("subject_hash", finding.get("task_id", "")))
        if finding_subject and verification["subject_hash"] != finding_subject:
            return False, "验证对象与 finding 当前对象不一致"
        actor = str(verification["verified_by"]).split(":")[0].lower()
        if actor in IMPLEMENTATION_ACTORS:
            return False, "实现者不能关闭 finding"
        return True, ""
