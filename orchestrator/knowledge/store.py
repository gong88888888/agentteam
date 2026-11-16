"""SQLite FTS5 + dense vector store for local hybrid retrieval."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from .chunker import Chunk, tokenize

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS docs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  source_type TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  mtime REAL NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  heading TEXT NOT NULL,
  text TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  UNIQUE(doc_id, chunk_index)
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED, title, heading, tokens, tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS embeddings (
  chunk_id INTEGER PRIMARY KEY,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def _quote_fts(token: str) -> str:
    return '"' + token.replace('"', '""') + '"'


class KnowledgeStore:
    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def set_meta(self, key: str, value: str) -> None:
        with self._conn() as con:
            con.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, value))

    def get_meta(self, key: str) -> str | None:
        with self._conn() as con:
            row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return row["value"] if row else None

    def index_document(self, path: str, title: str, source_type: str,
                       content_hash: str, mtime: float,
                       chunks: list[Chunk], vectors: list[list[float]],
                       embedder_name: str, metadata: dict[str, Any] | None = None
                       ) -> dict[str, Any]:
        if len(chunks) != len(vectors):
            raise ValueError("chunks 与 vectors 数量不一致")
        with self._conn() as con:
            old = con.execute("SELECT * FROM docs WHERE path=?", (path,)).fetchone()
            old_model = None
            if old:
                row = con.execute(
                    "SELECT e.model FROM embeddings e JOIN chunks c ON c.id=e.chunk_id "
                    "WHERE c.doc_id=? LIMIT 1", (old["id"],)).fetchone()
                old_model = row["model"] if row else None
            if old and old["content_hash"] == content_hash and old_model == embedder_name:
                con.execute(
                    "UPDATE docs SET title=?, source_type=?, mtime=?, metadata=? WHERE id=?",
                    (title, source_type, mtime,
                     json.dumps(metadata or {}, ensure_ascii=False), old["id"]))
                return {"path": path, "skipped": True, "chunks": 0}
            if old:
                ids = [r["id"] for r in con.execute(
                    "SELECT id FROM chunks WHERE doc_id=?", (old["id"],))]
                if ids:
                    marks = ",".join("?" * len(ids))
                    con.execute(f"DELETE FROM chunks_fts WHERE chunk_id IN ({marks})", ids)
                    con.execute(f"DELETE FROM embeddings WHERE chunk_id IN ({marks})", ids)
                    con.execute(f"DELETE FROM chunks WHERE id IN ({marks})", ids)
                con.execute("DELETE FROM docs WHERE id=?", (old["id"],))
            cur = con.execute(
                "INSERT INTO docs(path,title,source_type,content_hash,mtime,metadata) "
                "VALUES(?,?,?,?,?,?)",
                (path, title, source_type, content_hash, mtime,
                 json.dumps(metadata or {}, ensure_ascii=False)))
            doc_id = cur.lastrowid
            for chunk, vec in zip(chunks, vectors):
                cur = con.execute(
                    "INSERT INTO chunks(doc_id,chunk_index,heading,text,text_hash,metadata) "
                    "VALUES(?,?,?,?,?,?)",
                    (doc_id, chunk.index, chunk.heading, chunk.text,
                     chunk.chunk_id, json.dumps(chunk.metadata, ensure_ascii=False)))
                cid = cur.lastrowid
                con.execute(
                    "INSERT INTO chunks_fts(chunk_id,title,heading,tokens) VALUES(?,?,?,?)",
                    (cid, title, chunk.heading,
                     " ".join(tokenize(f"{title} {chunk.heading} {chunk.text}"))))
                con.execute(
                    "INSERT INTO embeddings(chunk_id,model,dim,vector) VALUES(?,?,?,?)",
                    (cid, embedder_name, len(vec), json.dumps(vec)))
            con.execute(
                "INSERT INTO meta(key,value) VALUES('embedding_model',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (embedder_name,))
            return {"path": path, "skipped": False, "chunks": len(chunks)}

    def _filter_sql(self, source_type: str | None,
                    path_prefix: str | None) -> tuple[str, list[Any]]:
        clauses, params = [], []
        if source_type:
            clauses.append("d.source_type = ?")
            params.append(source_type)
        if path_prefix:
            clauses.append("d.path LIKE ?")
            params.append(f"{path_prefix}%")
        return " AND ".join(clauses), params

    def lexical_search(self, query: str, top_k: int = 30,
                       source_type: str | None = None,
                       path_prefix: str | None = None) -> list[dict[str, Any]]:
        toks = tokenize(query)
        if not toks:
            return []
        match = " OR ".join(_quote_fts(t) for t in toks[:64])
        clauses, params = self._filter_sql(source_type, path_prefix)
        extra = f" AND {clauses}" if clauses else ""
        sql = f"""
            SELECT c.id, c.heading, c.text, c.metadata, d.path, d.title,
                   d.source_type, bm25(chunks_fts) AS rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.chunk_id
            JOIN docs d ON d.id = c.doc_id
            WHERE chunks_fts MATCH ?{extra}
            ORDER BY rank ASC
            LIMIT ?
        """
        with self._conn() as con:
            rows = con.execute(sql, [match, *params, top_k]).fetchall()
        return [{"chunk_id": r["id"], "heading": r["heading"], "text": r["text"],
                 "path": r["path"], "title": r["title"],
                 "source_type": r["source_type"], "rank": float(r["rank"])}
                for r in rows]

    def vector_search(self, query_vec: list[float], top_k: int = 30,
                      source_type: str | None = None,
                      path_prefix: str | None = None,
                      model: str | None = None) -> list[dict[str, Any]]:
        clauses, params = self._filter_sql(source_type, path_prefix)
        if model:
            clauses = (clauses + " AND " if clauses else "") + "e.model = ?"
            params.append(model)
        where = f"WHERE {clauses}" if clauses else ""
        sql = f"""
            SELECT e.chunk_id, e.vector, c.heading, c.text, c.metadata,
                   d.path, d.title, d.source_type
            FROM embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            JOIN docs d ON d.id = c.doc_id
            {where}
        """
        scored = []
        with self._conn() as con:
            for r in con.execute(sql, params):
                vec = json.loads(r["vector"])
                dot = sum(a * b for a, b in zip(query_vec, vec))
                nq = sum(a * a for a in query_vec) ** 0.5
                nv = sum(b * b for b in vec) ** 0.5
                score = dot / (nq * nv) if nq and nv else 0.0
                scored.append({"chunk_id": r["chunk_id"], "heading": r["heading"],
                               "text": r["text"], "path": r["path"],
                               "title": r["title"], "source_type": r["source_type"],
                               "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def stats(self) -> dict[str, Any]:
        with self._conn() as con:
            docs = con.execute("SELECT COUNT(*) AS n FROM docs").fetchone()["n"]
            chunks = con.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
            emb = con.execute("SELECT COUNT(*) AS n FROM embeddings").fetchone()["n"]
            types = {r["source_type"]: r["n"] for r in con.execute(
                "SELECT source_type, COUNT(*) AS n FROM docs GROUP BY source_type")}
            model = self.get_meta("embedding_model")
        return {"docs": docs, "chunks": chunks, "embeddings": emb,
                "source_types": types, "embedding_model": model}
