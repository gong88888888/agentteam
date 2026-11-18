"""Structured source units for Markdown documents.

A heading count is not a requirement count. This parser keeps headings,
paragraphs, list items, tables and fenced code as addressable units with a
stable content identity, so edits can be reported as added / removed / changed /
moved instead of silently renumbering an entire document.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
FENCE = re.compile(r"^\s*```")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


@dataclass
class SourceUnit:
    unit_id: str
    doc_id: str
    kind: str                       # heading | paragraph | list | table | code
    text: str
    heading: str
    path: tuple[str, ...]
    line: int
    line_end: int
    content_hash: str
    identity_key: str
    occurrence: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id, "doc_id": self.doc_id, "kind": self.kind,
            "text": self.text, "heading": self.heading, "path": list(self.path),
            "line": self.line, "line_end": self.line_end,
            "content_hash": self.content_hash, "identity_key": self.identity_key,
            "occurrence": self.occurrence,
        }


@dataclass
class ParsedDocument:
    doc_id: str
    content_hash: str
    units: list[SourceUnit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"doc_id": self.doc_id, "content_hash": self.content_hash,
                "unit_count": len(self.units),
                "by_kind": self.counts(),
                "units": [u.to_dict() for u in self.units]}

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for unit in self.units:
            out[unit.kind] = out.get(unit.kind, 0) + 1
        return out


def _emit(units: list[SourceUnit], *, doc_id: str, kind: str, text: str,
          heading: str, path: tuple[str, ...], line: int, line_end: int,
          occurrences: dict[str, int]) -> None:
    normalized = _norm(text)
    if not normalized:
        return
    # Identity deliberately excludes the heading path: moving a paragraph to a
    # different section must not mint a new identity. Duplicate text is
    # disambiguated by occurrence.
    identity_key = kind + "\0" + normalized
    occurrence = occurrences.get(identity_key, 0) + 1
    occurrences[identity_key] = occurrence
    suffix = "" if occurrence == 1 else f"-{occurrence}"
    unit_id = f"SU-{doc_id}-{_sha(identity_key)[:10]}{suffix}"
    units.append(SourceUnit(
        unit_id=unit_id, doc_id=doc_id, kind=kind, text=text.strip(),
        heading=heading, path=path, line=line, line_end=line_end,
        content_hash=_sha(normalized), identity_key=identity_key,
        occurrence=occurrence))


def parse_markdown(text: str, doc_id: str = "DOC") -> ParsedDocument:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    units: list[SourceUnit] = []
    occurrences: dict[str, int] = {}
    stack: list[tuple[int, str]] = []
    current_heading = ""
    current_path: tuple[str, ...] = ()
    i = 0
    while i < len(lines):
        line = lines[i]
        match = HEADING.match(line)
        if match:
            level, heading = len(match.group(1)), match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
            current_heading = heading
            current_path = tuple(h for _, h in stack)
            _emit(units, doc_id=doc_id, kind="heading", text=heading,
                  heading=heading, path=current_path, line=i + 1, line_end=i + 1,
                  occurrences=occurrences)
            i += 1
            continue
        if FENCE.match(line):
            start = i
            block = [line]
            i += 1
            while i < len(lines) and not FENCE.match(lines[i]):
                block.append(lines[i])
                i += 1
            if i < len(lines):
                block.append(lines[i])
                i += 1
            _emit(units, doc_id=doc_id, kind="code", text="\n".join(block),
                  heading=current_heading, path=current_path, line=start + 1,
                  line_end=i, occurrences=occurrences)
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) \
                and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            start = i
            block = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            _emit(units, doc_id=doc_id, kind="table", text="\n".join(block),
                  heading=current_heading, path=current_path, line=start + 1,
                  line_end=i, occurrences=occurrences)
            continue
        if LIST_ITEM.match(line):
            start = i
            block = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not HEADING.match(lines[i]) \
                    and not LIST_ITEM.match(lines[i]):
                block.append(lines[i])
                i += 1
            _emit(units, doc_id=doc_id, kind="list", text="\n".join(block),
                  heading=current_heading, path=current_path, line=start + 1,
                  line_end=i, occurrences=occurrences)
            continue
        if line.strip():
            start = i
            block = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not HEADING.match(lines[i]) \
                    and not LIST_ITEM.match(lines[i]) and not FENCE.match(lines[i]) \
                    and not lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            _emit(units, doc_id=doc_id, kind="paragraph", text="\n".join(block),
                  heading=current_heading, path=current_path, line=start + 1,
                  line_end=i, occurrences=occurrences)
            continue
        i += 1
    return ParsedDocument(doc_id=doc_id, content_hash=_sha(text), units=units)


def _similarity(a: SourceUnit, b: SourceUnit) -> float:
    if a.kind != b.kind or a.heading != b.heading:
        return 0.0
    return difflib.SequenceMatcher(None, _norm(a.text), _norm(b.text)).ratio()


def diff_units(old: ParsedDocument | Iterable[SourceUnit],
               new: ParsedDocument | Iterable[SourceUnit]) -> dict[str, Any]:
    old_units = list(old.units if isinstance(old, ParsedDocument) else old)
    new_units = list(new.units if isinstance(new, ParsedDocument) else new)
    old_left = list(old_units)
    new_left = list(new_units)
    unchanged: list[dict[str, Any]] = []
    moved: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []

    def same_identity(a: SourceUnit, b: SourceUnit) -> bool:
        return a.identity_key == b.identity_key

    # Exact content identity. A different path means the unit moved.
    for new_unit in list(new_left):
        candidates = [o for o in old_left if same_identity(o, new_unit)]
        if not candidates:
            continue
        old_unit = candidates[0]
        record = {"old_id": old_unit.unit_id, "new_id": new_unit.unit_id,
                  "kind": new_unit.kind, "heading": new_unit.heading,
                  "old_line": old_unit.line, "new_line": new_unit.line}
        if old_unit.path != new_unit.path:
            moved.append(record)
        else:
            unchanged.append(record)
        old_left.remove(old_unit)
        new_left.remove(new_unit)

    # Content edited under the same heading/kind.
    for new_unit in list(new_left):
        scored = [(_similarity(o, new_unit), o) for o in old_left]
        scored = [(s, o) for s, o in scored if s >= 0.75]
        if not scored:
            continue
        scored.sort(key=lambda pair: pair[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            best = scored[0][1]
            uncertain.append({"new_id": new_unit.unit_id, "kind": new_unit.kind,
                              "heading": new_unit.heading,
                              "candidates": [o.unit_id for s, o in scored if s == scored[0][0]],
                              "reason": "多个来源单元同等相似"})
        else:
            best = scored[0][1]
            changed.append({"old_id": best.unit_id, "new_id": new_unit.unit_id,
                            "kind": new_unit.kind, "heading": new_unit.heading,
                            "similarity": round(scored[0][0], 3),
                            "old_line": best.line, "new_line": new_unit.line})
        old_left.remove(best)
        new_left.remove(new_unit)

    removed = [{"unit_id": u.unit_id, "kind": u.kind, "heading": u.heading,
                "line": u.line, "text": u.text[:240]} for u in old_left]
    added = [{"unit_id": u.unit_id, "kind": u.kind, "heading": u.heading,
              "line": u.line, "text": u.text[:240]} for u in new_left]
    return {
        "old_hash": old.content_hash if isinstance(old, ParsedDocument) else "",
        "new_hash": new.content_hash if isinstance(new, ParsedDocument) else "",
        "unchanged": unchanged, "moved": moved, "changed": changed,
        "removed": removed, "added": added, "uncertain": uncertain,
        "counts": {"unchanged": len(unchanged), "moved": len(moved),
                   "changed": len(changed), "removed": len(removed),
                   "added": len(added), "uncertain": len(uncertain)},
    }


def coverage(units: Iterable[SourceUnit], disposed_ids: set[str]) -> dict[str, Any]:
    all_units = list(units)
    total = len(all_units)
    disposed = sum(1 for u in all_units if u.unit_id in disposed_ids)
    by_kind: dict[str, dict[str, int]] = {}
    for unit in all_units:
        row = by_kind.setdefault(unit.kind, {"total": 0, "disposed": 0})
        row["total"] += 1
        if unit.unit_id in disposed_ids:
            row["disposed"] += 1
    return {"total": total, "disposed": disposed,
            "percent": round(disposed / total * 100, 1) if total else 0.0,
            "by_kind": by_kind}
