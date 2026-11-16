"""Second-stage retrieval rerank.

A local bi-encoder rerank: RRF rank, dense similarity, query-term coverage and
heading matches. It is deterministic and needs no hosted rerank API. The score
is exposed per hit for audit; the base RRF score is preserved.
"""
from __future__ import annotations

import math
from typing import Any

from .chunker import tokenize
from .embed import Embedder


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a[:n])) or 1.0
    nb = math.sqrt(sum(x * x for x in b[:n])) or 1.0
    return dot / (na * nb)


def rerank_hits(query: str, candidates: list[dict[str, Any]], embedder: Embedder,
                top_k: int, *, qvec: list[float] | None = None,
                cache: dict[str, list[float]] | None = None,
                weights: tuple[float, float, float, float] = (0.5, 0.2, 0.3, 0.0)
                ) -> list[dict[str, Any]]:
    if not candidates:
        return []
    texts = [f"{c.get('heading', '')}\n{c.get('text', '')}"[:2000] for c in candidates]
    missing = [t for t in texts if not cache or t not in cache]
    if missing:
        vectors = embedder.embed(missing)
        if cache is not None:
            for text, vec in zip(missing, vectors):
                cache[text] = vec
    dense = [cache[t] if cache and t in cache else None for t in texts]
    if qvec is None:
        qvec = embedder.embed([query])[0]
    q_tokens = set(tokenize(query))
    base_max = max((float(c.get("score", 0.0)) for c in candidates), default=1.0) or 1.0
    seen_texts: list[str] = []
    ranked = []
    for cand, text, vec in zip(candidates, texts, dense):
        base = float(cand.get("score", 0.0)) / base_max
        cos = _cosine(qvec, vec or [])
        dense_score = max(0.0, min(1.0, (cos + 1.0) / 2.0))
        if q_tokens:
            toks = set(tokenize(text))
            coverage = len(q_tokens & toks) / len(q_tokens)
        else:
            coverage = 0.0
        heading = str(cand.get("heading", "")).lower()
        heading_hit = 1.0 if any(t in heading for t in q_tokens) else 0.0
        redundancy = 0.0
        for prev in seen_texts[-8:]:
            if text[:160] == prev[:160]:
                redundancy = 0.05
                break
        seen_texts.append(text)
        score = (weights[0] * base + weights[1] * dense_score
                 + weights[2] * coverage + weights[3] * heading_hit - redundancy)
        item = dict(cand)
        item["rerank_score"] = round(score, 6)
        item["dense_score"] = round(dense_score, 6)
        item["coverage"] = round(coverage, 6)
        item["base_score"] = round(base, 6)
        item["score"] = round(score, 6)
        ranked.append(item)
    ranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    hits = ranked[:top_k]
    for h in hits:
        h["citation"] = f"{h['path']}#{h['heading']}"
    return hits
