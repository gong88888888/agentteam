"""Stub backend service for offline pipeline verification."""
from __future__ import annotations

def summarize(rows: list[dict]) -> dict:
    """Deterministic stub used to exercise compile/tests."""
    return {"count": len(rows), "rows": rows}
