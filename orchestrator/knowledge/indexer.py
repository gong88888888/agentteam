"""Index project docs into the local knowledge store."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Iterable

from ..config import ROOT
from .chunker import chunk_markdown
from .embed import Embedder
from .store import KnowledgeStore

ROOT_DOCS = [
    "README.md", "agentteam1.md", "agentteam2.md", "agentteam-cluster-v3.md",
    "agentteam-v4-外部模型裁判.md", "agentteam-评审报告-2026-11-16.md",
    "修复建议1.md", "修复实施记录.md", "开发预演报告.md",
]
DIRS = ["specs", "eval", "dashboard", "prompts", "skills", "rubrics", "knowledge"]
SKILL_GLOB = "RAG-Agent-Toolkit/agent-toolkit/skills/*/SKILL.md"


def default_paths(root: Path = ROOT) -> list[Path]:
    paths = [root / p for p in ROOT_DOCS if (root / p).exists()]
    for d in DIRS:
        base = root / d
        if not base.exists():
            continue
        for ext in ("*.md", "*.yaml", "*.yml"):
            paths.extend(base.rglob(ext))
    paths.extend(root.glob(SKILL_GLOB))
    seen, out = set(), []
    for p in paths:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


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


def index_project(store: KnowledgeStore, embedder: Embedder,
                  paths: Iterable[Path] | None = None,
                  root: Path = ROOT) -> dict[str, Any]:
    files = list(paths) if paths is not None else default_paths(root)
    rows = []
    total_chunks = 0
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        chunks = chunk_markdown(text, rel)
        if not chunks:
            continue
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        vectors = embedder.embed([c.embedding_text() for c in chunks])
        result = store.index_document(
            rel, p.stem, _source_type(rel), content_hash, p.stat().st_mtime,
            chunks, vectors, embedder.name, {"ext": p.suffix})
        rows.append(result)
        total_chunks += result.get("chunks", 0)
    store.set_meta("embedding_model", embedder.name)
    store.set_meta("indexed_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    return {"files": len(rows), "chunks": total_chunks,
            "skipped": sum(1 for r in rows if r.get("skipped")),
            "rows": rows, "stats": store.stats(), "embedder": embedder.name}
