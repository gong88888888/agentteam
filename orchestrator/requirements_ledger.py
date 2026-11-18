"""Structured requirement ledger: atomic requirements and source dispositions.

A model may propose candidates, but only this module validates source identity,
required fields and disposition completeness. The Markdown baseline is a view
rendered from these records, not the authoritative store.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .sources import SourceUnit, coverage

KINDS = {"functional", "rule", "data", "permission", "compatibility",
         "performance", "interaction", "operational"}
DISPOSITIONS = {"requirement", "background", "duplicate", "approved_exclusion",
                "conflict", "parse_uncertain", "unreviewed"}
STATUSES = {"candidate", "approved", "rejected", "deferred", "superseded"}


@dataclass
class RequirementCandidate:
    requirement_id: str
    statement: str
    source_refs: list[str]
    kind: str
    expected_result: str = ""
    actor: str = ""
    conditions: str = ""
    priority: str = "normal"
    status: str = "candidate"
    revision: int = 1
    assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    acceptance_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class SourceDisposition:
    unit_id: str
    status: str
    requirement_ids: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class RequirementLedger:
    doc_id: str
    requirements: list[RequirementCandidate] = field(default_factory=list)
    dispositions: list[SourceDisposition] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    schema_version: str = "1.0"
    created_at: float = field(default_factory=time.time)

    def validate(self, unit_ids: Iterable[str]) -> list[dict[str, str]]:
        valid_units = set(unit_ids)
        errors: list[dict[str, str]] = []
        ids: set[str] = set()
        for req in self.requirements:
            if not req.requirement_id:
                errors.append({"code": "missing_id", "detail": "需求缺少 requirement_id"})
            if req.requirement_id in ids:
                errors.append({"code": "duplicate_id",
                               "detail": f"重复需求 ID：{req.requirement_id}"})
            ids.add(req.requirement_id)
            if not req.statement.strip():
                errors.append({"code": "missing_statement",
                               "detail": f"{req.requirement_id} 缺少 statement"})
            if req.kind not in KINDS:
                errors.append({"code": "invalid_kind",
                               "detail": f"{req.requirement_id} kind={req.kind!r}"})
            if not req.expected_result.strip():
                errors.append({"code": "missing_expected_result",
                               "detail": f"{req.requirement_id} 缺少 expected_result"})
            if not req.source_refs:
                errors.append({"code": "missing_source",
                               "detail": f"{req.requirement_id} 没有来源引用"})
            for ref in req.source_refs:
                if ref not in valid_units:
                    errors.append({"code": "unknown_source",
                                   "detail": f"{req.requirement_id} 引用不存在单元 {ref}"})
        seen_units: set[str] = set()
        for disp in self.dispositions:
            if disp.unit_id not in valid_units:
                errors.append({"code": "unknown_unit",
                               "detail": f"处置引用不存在单元 {disp.unit_id}"})
            if disp.unit_id in seen_units:
                errors.append({"code": "duplicate_disposition",
                               "detail": f"单元被重复处置：{disp.unit_id}"})
            seen_units.add(disp.unit_id)
            if disp.status not in DISPOSITIONS:
                errors.append({"code": "invalid_disposition",
                               "detail": f"{disp.unit_id} status={disp.status!r}"})
            for req_id in disp.requirement_ids:
                if req_id not in ids:
                    errors.append({"code": "unknown_requirement",
                                   "detail": f"{disp.unit_id} 指向不存在需求 {req_id}"})
        return errors

    def coverage(self, units: Iterable[SourceUnit]) -> dict[str, Any]:
        disposed = {d.unit_id for d in self.dispositions
                    if d.status != "unreviewed"}
        result = coverage(units, disposed)
        by_status: dict[str, int] = {}
        for disp in self.dispositions:
            by_status[disp.status] = by_status.get(disp.status, 0) + 1
        result["by_status"] = by_status
        result["computed_by"] = "requirements_ledger"
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "doc_id": self.doc_id,
            "created_at": self.created_at,
            "requirements": [r.to_dict() for r in self.requirements],
            "dispositions": [d.to_dict() for d in self.dispositions],
            "open_questions": self.open_questions,
        }

    def render_markdown(self) -> str:
        lines = [f"# 需求账本 · {self.doc_id}", "",
                 f"- 需求数：{len(self.requirements)}",
                 f"- 来源处置数：{len(self.dispositions)}", "",
                 "## 需求", "",
                 "| ID | 类型 | 状态 | 需求 | 预期结果 | 来源 |",
                 "|---|---|---|---|---|---|"]
        for req in self.requirements:
            lines.append(f"| {req.requirement_id} | {req.kind} | {req.status} | "
                         f"{req.statement.replace('|', '/')} | "
                         f"{req.expected_result.replace('|', '/')} | "
                         f"{', '.join(req.source_refs)} |")
        lines += ["", "## 来源处置", "",
                  "| 单元 | 处置 | 需求 | 理由 |", "|---|---|---|---|"]
        for disp in self.dispositions:
            lines.append(f"| {disp.unit_id} | {disp.status} | "
                         f"{', '.join(disp.requirement_ids)} | {disp.reason} |")
        if self.open_questions:
            lines += ["", "## 待决问题", ""]
            lines += [f"- {q}" for q in self.open_questions]
        return "\n".join(lines) + "\n"

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "RequirementLedger":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(doc_id=str(data.get("doc_id", "")),
                   requirements=[RequirementCandidate(**r)
                                 for r in data.get("requirements", [])],
                   dispositions=[SourceDisposition(**d)
                                 for d in data.get("dispositions", [])],
                   open_questions=list(data.get("open_questions") or []),
                   schema_version=str(data.get("schema_version", "1.0")),
                   created_at=float(data.get("created_at", time.time())))


def from_model_output(obj: dict[str, Any], units: Iterable[SourceUnit],
                      doc_id: str,
                      aliases: dict[str, str] | None = None
                      ) -> tuple[RequirementLedger, list[dict[str, str]]]:
    """Validate a model payload.

    ``aliases`` maps display IDs (for example SRC-001) to stable unit IDs, so a
    model that cites the document's visible section numbers is not rejected
    merely because the internal identity differs.
    """
    aliases = aliases or {}
    units = list(units)

    def resolve(ref: str) -> str:
        return aliases.get(ref, ref)

    raw_reqs = obj.get("requirements") or obj.get("atomic_requirements") or []
    requirements = []
    for index, raw in enumerate(raw_reqs, 1):
        if not isinstance(raw, dict):
            continue
        requirements.append(RequirementCandidate(
            requirement_id=str(raw.get("id") or raw.get("requirement_id")
                               or f"REQ-{index:03d}"),
            statement=str(raw.get("statement") or raw.get("text") or ""),
            source_refs=[resolve(str(x)) for x in raw.get("source_refs") or []],
            kind=str(raw.get("kind") or "functional"),
            expected_result=str(raw.get("expected_result")
                                or raw.get("acceptance") or ""),
            actor=str(raw.get("actor") or ""),
            conditions=str(raw.get("conditions") or ""),
            priority=str(raw.get("priority") or "normal"),
            status=str(raw.get("status") or "candidate"),
            assumptions=[str(x) for x in raw.get("assumptions") or []],
            open_questions=[str(x) for x in raw.get("open_questions") or []],
            acceptance_ids=[str(x) for x in raw.get("acceptance_ids") or []],
        ))
    dispositions = []
    for raw in obj.get("source_dispositions") or obj.get("dispositions") or []:
        if not isinstance(raw, dict):
            continue
        dispositions.append(SourceDisposition(
            unit_id=resolve(str(raw.get("unit_id") or raw.get("source_id") or "")),
            status=str(raw.get("status") or "unreviewed"),
            requirement_ids=[str(x) for x in
                             (raw.get("requirement_ids") or raw.get("requirements") or [])],
            reason=str(raw.get("reason") or ""),
        ))
    ledger = RequirementLedger(
        doc_id=doc_id, requirements=requirements, dispositions=dispositions,
        open_questions=[str(x) for x in obj.get("open_questions") or []])
    errors = ledger.validate(u.unit_id for u in units)
    if not dispositions:
        errors.append({"code": "no_dispositions",
                       "detail": "没有任何来源单元处置，不能宣称覆盖完成"})
    return ledger, errors


def file_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
