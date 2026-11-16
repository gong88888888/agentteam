#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W4 prompt regression: baseline vs candidate prompts on the role golden set.

  python eval/prompt_regression.py --offline
  python eval/prompt_regression.py --real --roles product,review --limit 4
  python eval/prompt_regression.py --offline \
      --baseline prompts/roles --candidate prompts/candidates/strict-json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.role_eval import run_cases  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def _rates(m: dict[str, Any]) -> dict[str, float]:
    total = max(1, m["total"])
    return {
        "schema": round(m["schema_pass"] / total, 3),
        "required": round(m["required_pass"] / total, 3),
        "keyword": round(m["keyword_pass"] / total, 3),
        "latency_ms": m["latency_ms"],
        "tokens": m["tokens"],
    }


def run_regression(*, offline: bool, baseline: str, candidate: str,
                   roles: list[str] | None, limit: int | None,
                   config: str | None = None) -> dict[str, Any]:
    b = run_cases(offline=offline, prompt_dir=baseline, roles=roles,
                  limit=limit, config=config)
    c = run_cases(offline=offline, prompt_dir=candidate, roles=roles,
                  limit=limit, config=config)
    br, cr = _rates(b), _rates(c)
    regressed = (cr["schema"] < br["schema"] - 0.02
                 or cr["required"] < br["required"] - 0.02
                 or cr["keyword"] < br["keyword"] - 0.05)
    improved = (cr["schema"] > br["schema"] + 0.02
                or cr["required"] > br["required"] + 0.02
                or cr["keyword"] > br["keyword"] + 0.05)
    hashes = {}
    for r in b["rows"]:
        hashes.setdefault(r["role"], {})["baseline"] = r.get("prompt", {}).get("hash")
    for r in c["rows"]:
        hashes.setdefault(r["role"], {})["candidate"] = r.get("prompt", {}).get("hash")
    result = {
        "mode": "offline" if offline else "real",
        "baseline": baseline,
        "candidate": candidate,
        "baseline_metrics": br,
        "candidate_metrics": cr,
        "delta": {k: round(cr[k] - br[k], 3) for k in ("schema", "required",
                                                        "keyword")},
        "regressed": regressed,
        "improved": improved,
        "prompt_hashes": hashes,
        "baseline_raw": {k: b[k] for k in ("total", "schema_pass", "required_pass",
                                           "keyword_pass", "errors")},
        "candidate_raw": {k: c[k] for k in ("total", "schema_pass", "required_pass",
                                            "keyword_pass", "errors")},
        "models": c.get("models", {}),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "prompt-regression.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Prompt Regression", "",
        f"- mode: **{result['mode']}**",
        f"- baseline: `{baseline}` · candidate: `{candidate}`",
        f"- cases: {b['total']}",
        "",
        "| 指标 | baseline | candidate | delta |",
        "|---|---|---|---|",
        *(f"| {k} | {br[k]} | {cr[k]} | {result['delta'][k]:+} |"
          for k in ("schema", "required", "keyword")),
        "",
        f"- regressed: **{regressed}** · improved: **{improved}**",
        f"- latency: {br['latency_ms']} → {cr['latency_ms']} ms；"
        f"tokens: {br['tokens']} → {cr['tokens']}",
        "", "## 角色提示词哈希", "",
        "| 角色 | baseline | candidate |",
        "|---|---|---|",
        *[f"| {role} | {h.get('baseline')} | {h.get('candidate')} |"
          for role, h in sorted(hashes.items())],
        "",
        "> offline 模式使用 role-aware stub，提示词不会改变输出，因此 delta 为 0；"
        "真实模型回归请加 `--real`（建议先限定 `--roles` 与 `--limit` 控制成本）。",
    ]
    (OUT / "prompt-regression.md").write_text("\n".join(lines) + "\n",
                                               encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="W4 prompt regression")
    p.add_argument("--offline", action="store_true", default=True)
    p.add_argument("--real", action="store_true")
    p.add_argument("--baseline", default="prompts/roles")
    p.add_argument("--candidate", default="prompts/candidates/strict-json")
    p.add_argument("--roles", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", default=None)
    args = p.parse_args(argv)
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    result = run_regression(offline=not args.real,
                            baseline=args.baseline, candidate=args.candidate,
                            roles=roles, limit=args.limit, config=args.config)
    print(json.dumps({k: result[k] for k in (
        "mode", "baseline", "candidate", "baseline_metrics",
        "candidate_metrics", "delta", "regressed", "improved")},
        ensure_ascii=False, indent=2))
    print(f"report -> {OUT / 'prompt-regression.md'}")
    return 1 if result["regressed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
