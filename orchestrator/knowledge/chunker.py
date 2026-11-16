"""Markdown-aware chunking and CJK-friendly FTS tokens."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.M)
CJK = re.compile(r"[㐀-鿿]+")
WORD = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Unigrams + bigrams for CJK, lowercased words for Latin."""
    text = text.lower()
    out: list[str] = []
    for seq in CJK.findall(text):
        out.extend(seq)
        out.extend(seq[i:i + 2] for i in range(len(seq) - 1))
    out.extend(w.lower() for w in WORD.findall(text))
    seen = set()
    clean = []
    for t in out:
        if len(t) >= 1 and t not in seen:
            seen.add(t)
            clean.append(t)
    return clean


@dataclass
class Chunk:
    source_path: str
    title: str
    heading: str
    text: str
    index: int
    source_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        raw = f"{self.source_path}|{self.heading}|{self.index}|{self.text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def embedding_text(self) -> str:
        return f"{self.title}\n{self.heading}\n{self.text}"


def _source_type(path: str) -> str:
    p = path.replace("\\", "/")
    parts = set(p.split("/"))
    for name, kind in (("skills", "skill"), ("rubrics", "rubric"),
                       ("specs", "spec"), ("eval", "eval"),
                       ("dashboard", "dashboard"), ("prompts", "prompt"),
                       ("knowledge", "knowledge")):
        if name in parts:
            return kind
    return "design"


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        return [text] if text.strip() else []
    out, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                out.append(buf)
            if len(p) <= max_chars:
                buf = p
            else:
                step = max(1, max_chars - overlap)
                for i in range(0, len(p), step):
                    out.append(p[i:i + max_chars])
                buf = ""
    if buf:
        out.append(buf)
    return out


def chunk_markdown(text: str, source_path: str, *, max_chars: int = 900,
                   overlap: int = 80) -> list[Chunk]:
    p = Path(source_path)
    title = p.stem
    sections: list[tuple[str, str]] = []
    matches = list(HEADING.finditer(text))
    if not matches:
        sections = [(title, text)]
    else:
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            heading = m.group(2).strip()
            body = text[start:end].strip()
            sections.append((heading, body))
    chunks: list[Chunk] = []
    idx = 0
    for heading, body in sections:
        if not body and len(sections) > 1:
            continue
        for part in _split_long(body, max_chars, overlap):
            if not part.strip():
                continue
            chunks.append(Chunk(
                source_path=source_path.replace("\\", "/"),
                title=title, heading=heading, text=part, index=idx,
                source_type=_source_type(source_path)))
            idx += 1
    return chunks
