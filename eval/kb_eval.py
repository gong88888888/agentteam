#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W4 knowledge retrieval evaluation (offline hash index by default).

  python eval/kb_eval.py
  python eval/kb_eval.py --real   # uses data/knowledge.db (bge-m3)
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.config import load_config  # noqa: E402
from orchestrator.knowledge import (HashingEmbedder, HybridRetriever,  # noqa: E402
                                    KnowledgeStore, index_project)

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

FILES = [
    "README.md",
    "sim/README.md",
    "agentteam-v4-外部模型裁判.md",
    "agentteam2.md",
    "修复实施记录.md",
    "skills/frontend-design/SKILL.md",
    "skills/registry.yaml",
    "RAG-Agent-Toolkit/agent-toolkit/skills/postmortem-to-tests/SKILL.md",
    "rubrics/release-gate.yaml",
    "knowledge/README.md",
]


def run(real: bool = False) -> dict:
    cases = yaml.safe_load((HERE / "golden" / "kb_cases.yaml").read_text(encoding="utf-8"))
    if real:
        cfg = load_config()
        db = Path(cfg.get("runtime", {}).get("data_dir", "data")) / "knowledge.db"
        if not db.exists():
            raise SystemExit("data/knowledge.db 不存在；先运行 kb-index")
        retriever = HybridRetriever(db, cfg)
        tmp = None
    else:
        tmp = tempfile.TemporaryDirectory()
        db = Path(tmp.name) / "kb.db"
        store = KnowledgeStore(db)
        embedder = HashingEmbedder()
        paths = [ROOT / f for f in FILES if (ROOT / f).exists()]
        index_project(store, embedder, paths, ROOT)
        retriever = HybridRetriever(db, embedder=embedder)
    rows = []
    hits = 0
    filter_ok = 0
    filter_total = 0
    for case in cases:
        result = retriever.search(case["query"], top_k=5,
                                  source_type=case.get("source_type"))
        citations = [h.get("citation", "") for h in result]
        ok = any(any(exp in c for c in citations) for exp in case["expected"])
        if case.get("source_type"):
            filter_total += 1
            filter_ok += int(all(f"{case['source_type']}" in (h.get("source_type") or "")
                                 for h in result if "citation" in h))
        hits += int(ok)
        rows.append({"id": case["id"], "query": case["query"],
                     "expected": case["expected"], "citations": citations[:5],
                     "pass": ok})
    total = len(cases)
    metrics = {"mode": "real" if real else "offline",
               "total": total, "hits": hits,
               "recall_at_5": round(hits / total, 3) if total else 0,
               "filter_pass": f"{filter_ok}/{filter_total}",
               "stats": retriever.stats(), "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "kb-eval.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Knowledge Retrieval Evaluation", "",
        f"- mode: **{metrics['mode']}**",
        f"- recall@5: **{metrics['recall_at_5']}** ({hits}/{total})",
        f"- source_type filter: {metrics['filter_pass']}",
        f"- index: {json.dumps(metrics['stats'], ensure_ascii=False)}",
        "", "| 用例 | 结果 | citations |", "|---|---|---|",
        *[f"| {r['id']} | {'✅' if r['pass'] else '❌'} | "
          f"{'<br>'.join(r['citations'][:3])} |" for r in rows],
        "",
    ]
    (OUT / "kb-eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if tmp:
        tmp.cleanup()
    return metrics


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="W4 knowledge retrieval eval")
    p.add_argument("--real", action="store_true")
    args = p.parse_args(argv)
    m = run(real=args.real)
    print(json.dumps({k: m[k] for k in ("mode", "total", "hits",
                                        "recall_at_5", "filter_pass", "stats")},
                     ensure_ascii=False, indent=2))
    print(f"report -> {OUT / 'kb-eval.md'}")
    return 0 if m["hits"] == m["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
