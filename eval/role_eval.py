#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W4 role golden-set evaluation.

  python eval/role_eval.py --offline
  python eval/role_eval.py --real --roles product,review --limit 2
  python eval/role_eval.py --offline --prompt-dir prompts/candidates/strict-json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.config import load_config, load_schema  # noqa: E402
from orchestrator.judge.backend import parse_json_object  # noqa: E402
from orchestrator.models.router import ModelRouter  # noqa: E402
from orchestrator.prompts import load_prompt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def load_cases(roles: list[str] | None = None,
               limit: int | None = None) -> list[dict[str, Any]]:
    cases = yaml.safe_load((HERE / "golden" / "role_cases.yaml").read_text(encoding="utf-8"))
    if roles:
        cases = [c for c in cases if c["role"] in roles]
    if limit:
        cases = cases[:limit]
    return cases


def run_cases(*, offline: bool, prompt_dir: str | None = None,
              roles: list[str] | None = None, limit: int | None = None,
              config: str | None = None) -> dict[str, Any]:
    cfg = load_config(config)
    router = ModelRouter(cfg, offline=offline)
    cases = load_cases(roles, limit)
    schema = load_schema("agent-output.schema.json")
    rows = []
    for case in cases:
        prompt = load_prompt(case["role"], prompt_dir)
        messages = [{"role": "system", "content": prompt.text},
                    {"role": "user", "content": case["task"]}]
        started = time.perf_counter()
        obj = None
        result = None
        last_exc: Exception | None = None
        for _attempt in range(2):
            try:
                result = router.execution(case["role"], messages, response_format="json")
                obj = parse_json_object(result.content)
                jsonschema.validate(obj, schema)
                break
            except Exception as exc:
                last_exc = exc
                obj = None
                messages += [
                    {"role": "assistant", "content": result.content if result else ""},
                    {"role": "user", "content": f"不符合 schema：{exc}。只输出合法 JSON envelope。"},
                ]
        if obj is None:
            rows.append({"id": case["id"], "role": case["role"],
                         "schema": False, "required": False, "keywords": False,
                         "error": str(last_exc), "prompt": prompt.metadata(),
                         "latency_ms": int((time.perf_counter() - started) * 1000),
                         "tokens": 0})
            continue
        required = [k for k in ("status", "role", "claims", "artifacts", "summary")
                    if k not in obj]
        text = json.dumps(obj, ensure_ascii=False).lower()
        found = [k for k in case.get("keywords", []) if k.lower() in text]
        need = int(case.get("min_keywords", 1))
        keyword_ok = len(found) >= need
        rows.append({
            "id": case["id"], "role": case["role"],
            "schema": True, "required": not required and bool(obj.get("claims"))
            and obj.get("role") == case["role"],
            "keywords": keyword_ok, "found": found,
            "missing_keywords": [k for k in case.get("keywords", []) if k not in found],
            "prompt": prompt.metadata(),
            "model": result.model if result else "",
            "backend": result.backend if result else "",
            "latency_ms": result.latency_ms if result else 0,
            "tokens": (result.prompt_tokens + result.completion_tokens) if result else 0,
        })
    total = len(cases)
    by_role: dict[str, dict[str, int]] = {}
    for r in rows:
        stats = by_role.setdefault(r["role"], {"total": 0, "schema": 0,
                                               "required": 0, "keywords": 0})
        stats["total"] += 1
        stats["schema"] += int(r["schema"])
        stats["required"] += int(r["required"])
        stats["keywords"] += int(r["keywords"])
    return {
        "mode": "offline" if offline else "real",
        "prompt_dir": str(prompt_dir or "prompts/roles"),
        "total": total,
        "schema_pass": sum(int(r["schema"]) for r in rows),
        "required_pass": sum(int(r["required"]) for r in rows),
        "keyword_pass": sum(int(r["keywords"]) for r in rows),
        "errors": sum(1 for r in rows if r.get("error")),
        "latency_ms": sum(int(r.get("latency_ms", 0)) for r in rows),
        "tokens": sum(int(r.get("tokens", 0)) for r in rows),
        "by_role": by_role,
        "rows": rows,
        "models": router.summary(),
    }


def write_report(metrics: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    lines = [
        "# Role Golden Set", "",
        f"- mode: **{metrics['mode']}** · prompt: `{metrics['prompt_dir']}`",
        f"- total: {metrics['total']} · schema {metrics['schema_pass']} · "
        f"required {metrics['required_pass']} · keywords {metrics['keyword_pass']} · "
        f"errors {metrics['errors']}",
        f"- latency {metrics['latency_ms']}ms · tokens {metrics['tokens']}",
        "", "| 角色 | 用例 | schema | required | keywords |",
        "|---|---|---|---|---|",
    ]
    for role, s in sorted(metrics["by_role"].items()):
        lines.append(f"| {role} | {s['total']} | {s['schema']} | "
                     f"{s['required']} | {s['keywords']} |")
    lines += ["", "## Rows", ""]
    for r in metrics["rows"]:
        lines.append(f"- {r['id']} ({r['role']}): schema={r['schema']} "
                     f"required={r['required']} keywords={r['keywords']}"
                     + (f" missing={r.get('missing_keywords')}" if r.get("missing_keywords") else "")
                     + (f" error={r.get('error')}" if r.get("error") else ""))
    path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="W4 role golden-set evaluation")
    p.add_argument("--offline", action="store_true", default=True)
    p.add_argument("--real", action="store_true")
    p.add_argument("--prompt-dir", default=None)
    p.add_argument("--roles", default=None, help="comma-separated roles")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", default=None)
    args = p.parse_args(argv)
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    metrics = run_cases(offline=not args.real, prompt_dir=args.prompt_dir,
                        roles=roles, limit=args.limit, config=args.config)
    write_report(metrics, OUT / "role-eval.json")
    print(json.dumps({k: metrics[k] for k in (
        "mode", "total", "schema_pass", "required_pass", "keyword_pass",
        "errors", "latency_ms", "tokens", "models")}, ensure_ascii=False, indent=2))
    print(f"report -> {OUT / 'role-eval.md'}")
    if metrics["mode"] == "offline":
        return 0 if (metrics["schema_pass"] == metrics["total"]
                     and metrics["required_pass"] == metrics["total"]
                     and metrics["keyword_pass"] == metrics["total"]) else 1
    return 0 if (metrics["schema_pass"] / max(1, metrics["total"]) >= 0.9
                 and metrics["required_pass"] / max(1, metrics["total"]) >= 0.9
                 and metrics["keyword_pass"] / max(1, metrics["total"]) >= 0.7) else 1


if __name__ == "__main__":
    raise SystemExit(main())
