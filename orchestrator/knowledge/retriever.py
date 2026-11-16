"""Hybrid retrieval: FTS5 BM25 + dense cosine, fused with RRF and citations."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import load_config
from .embed import Embedder, embedder_from_name
from .rerank import rerank_hits
from .store import KnowledgeStore


class HybridRetriever:
    def __init__(self, db_path: str | Path, cfg: dict | None = None,
                 embedder: Embedder | None = None) -> None:
        self.store = KnowledgeStore(db_path)
        self.cfg = cfg or load_config()
        self.model = self.store.get_meta("embedding_model") or "hash:256"
        self.embedder = embedder or embedder_from_name(self.model, self.cfg)
        self._embed_cache: dict[str, list[float]] = {}

    def search(self, query: str, top_k: int = 8, *,
               source_type: str | None = None,
               path_prefix: str | None = None,
               rrf_k: int = 60, rerank: bool = True,
               candidate_k: int = 30) -> list[dict[str, Any]]:
        lexical = self.store.lexical_search(query, top_k=candidate_k,
                                            source_type=source_type,
                                            path_prefix=path_prefix)
        vector: list[dict[str, Any]] = []
        warnings: list[str] = []
        qvec: list[float] | None = None
        try:
            qvec = self.embedder.embed([query])[0]
            vector = self.store.vector_search(qvec, top_k=candidate_k,
                                              source_type=source_type,
                                              path_prefix=path_prefix,
                                              model=self.model)
        except Exception as exc:  # dense is optional; lexical still works
            warnings.append(f"vector search unavailable: {exc}")
        fused: dict[int, dict[str, Any]] = {}
        for rank, row in enumerate(lexical, 1):
            item = fused.setdefault(row["chunk_id"], {**row, "score": 0.0,
                                                      "lexical_rank": rank,
                                                      "vector_rank": None})
            item["score"] += 1.0 / (rrf_k + rank)
            item["rank"] = row["rank"]
        for rank, row in enumerate(vector, 1):
            item = fused.setdefault(row["chunk_id"], {
                "chunk_id": row["chunk_id"], "heading": row["heading"],
                "text": row["text"], "path": row["path"], "title": row["title"],
                "source_type": row["source_type"], "score": 0.0,
                "lexical_rank": None, "vector_rank": rank,
            })
            item["score"] += 1.0 / (rrf_k + rank)
            item["vector_score"] = row["score"]
        q = query.lower()
        for item in fused.values():
            if q and q in (item.get("heading", "") + item.get("text", "")).lower():
                item["score"] += 0.02
        candidates = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        if rerank:
            hits = rerank_hits(query, candidates, self.embedder, top_k,
                               qvec=qvec, cache=self._embed_cache)
        else:
            hits = candidates[:top_k]
            for h in hits:
                h["citation"] = f"{h['path']}#{h['heading']}"
                h["score"] = round(h["score"], 6)
        if warnings:
            hits = hits or [{"warnings": warnings}]
        return hits

    def stats(self) -> dict[str, Any]:
        return self.store.stats()
