"""Budgeted task context assembly.

The downstream role receives referenced source/requirement/design/contract/code
files, not only a 700-character summary. Every injected item keeps an ID, hash
and truncation flag; a missing required reference is an explicit error rather
than silently absent context.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

IMPORTANCE_ORDER = {"required": 0, "local": 1, "history": 2, "summary": 3}
SECTION_TITLES = {
    "required": "必须遵守的当前契约与约束",
    "local": "完成任务需要的局部材料",
    "history": "相关历史反例",
    "summary": "导航摘要（非权威）",
}


@dataclass
class ContextItem:
    item_id: str
    kind: str
    origin: str
    importance: str
    text: str
    content_hash: str = ""
    truncated: bool = False
    missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "kind": self.kind, "origin": self.origin,
                "importance": self.importance, "content_hash": self.content_hash,
                "truncated": self.truncated, "missing": self.missing,
                "chars": len(self.text)}


@dataclass
class ContextPack:
    items: list[ContextItem] = field(default_factory=list)
    budget_chars: int = 12000
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def used_chars(self) -> int:
        return sum(len(item.text) for item in self.items)

    @property
    def missing(self) -> list[str]:
        return [item.origin for item in self.items if item.missing]

    def render(self) -> str:
        if not self.items:
            return ""
        lines: list[str] = []
        for importance in ("required", "local", "history", "summary"):
            group = [item for item in self.items if item.importance == importance]
            if not group:
                continue
            lines += [f"# {SECTION_TITLES[importance]}", ""]
            for item in group:
                marker = f"{item.item_id} · {item.kind} · `{item.origin}`"
                if item.content_hash:
                    marker += f" · sha256:{item.content_hash[:12]}"
                if item.truncated:
                    marker += " · TRUNCATED（原文未完整注入）"
                if item.missing:
                    marker += " · MISSING"
                lines += [f"## {marker}", "", item.text.strip() or "（空）", ""]
        return "\n".join(lines).rstrip() + "\n"

    def manifest(self) -> dict[str, Any]:
        return {
            "budget_chars": self.budget_chars,
            "used_chars": self.used_chars,
            "items": [item.to_dict() for item in self.items],
            "warnings": self.warnings,
            "errors": self.errors,
            "missing": self.missing,
            "truncated": [item.item_id for item in self.items if item.truncated],
        }


class ContextAssembler:
    def __init__(self, project_dir: str | Path, *, budget_chars: int = 12000) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.budget_chars = int(budget_chars)
        self._items: list[ContextItem] = []
        self._warnings: list[str] = []
        self._errors: list[str] = []

    def add_text(self, item_id: str, text: str, *, kind: str = "reference",
                 origin: str = "", importance: str = "required") -> ContextItem:
        if importance not in IMPORTANCE_ORDER:
            raise ValueError(f"未知上下文重要级别：{importance}")
        item = ContextItem(item_id=item_id, kind=kind, origin=origin or item_id,
                           importance=importance, text=text or "",
                           content_hash=hashlib.sha256(
                               (text or "").encode("utf-8")).hexdigest())
        self._items.append(item)
        return item

    def add_file(self, ref: str, *, kind: str = "artifact",
                 importance: str = "local", max_chars: int | None = None,
                 required: bool = False) -> ContextItem | None:
        rel = str(ref).replace("\\", "/")
        path = (self.project_dir / rel).resolve()
        if not str(path).startswith(str(self.project_dir)) or not path.is_file():
            message = f"上下文引用不存在：{rel}"
            self._errors.append(message)
            self._items.append(ContextItem(
                item_id=f"MISSING-{len(self._items) + 1}", kind=kind,
                origin=rel, importance=importance, text=message,
                missing=True))
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        truncated = False
        if max_chars and len(text) > max_chars:
            text = text[:max_chars] + f"\n…（已截断，原文件 {len(text)} 字符，可读取 `{rel}`）"
            truncated = True
            self._warnings.append(f"{rel} 因预算截断")
        item = ContextItem(
            item_id=f"CTX-{len(self._items) + 1}", kind=kind, origin=rel,
            importance=importance, text=text,
            content_hash=hashlib.sha256(
                path.read_bytes()).hexdigest(), truncated=truncated)
        self._items.append(item)
        if required and truncated:
            self._errors.append(f"必需上下文被截断：{rel}")
        return item

    def add_many(self, refs: Iterable[str], **kwargs: Any) -> list[ContextItem | None]:
        return [self.add_file(ref, **kwargs) for ref in refs]

    def build(self) -> ContextPack:
        ordered = sorted(self._items, key=lambda item: IMPORTANCE_ORDER[item.importance])
        budget = self.budget_chars
        kept: list[ContextItem] = []
        warnings = list(self._warnings)
        errors = list(self._errors)
        for item in ordered:
            if item.missing:
                kept.append(item)
                continue
            if budget <= 0:
                warnings.append(f"{item.item_id} 因总预算被省略")
                continue
            if len(item.text) <= budget:
                kept.append(item)
                budget -= len(item.text)
            else:
                if item.importance in ("required", "local"):
                    head = item.text[:budget]
                    kept.append(ContextItem(
                        item_id=item.item_id, kind=item.kind, origin=item.origin,
                        importance=item.importance,
                        text=head + f"\n…（总预算截断，保留 {budget}/{len(item.text)} 字符）",
                        content_hash=item.content_hash, truncated=True))
                    warnings.append(f"{item.item_id} 因总预算截断")
                    if item.importance == "required":
                        errors.append(f"必需上下文因总预算截断：{item.origin}")
                    budget = 0
                else:
                    warnings.append(f"{item.item_id} 因总预算省略")
        return ContextPack(items=kept, budget_chars=self.budget_chars,
                           warnings=warnings, errors=errors)
