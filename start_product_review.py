#!/usr/bin/env python3
"""Run the reusable product-review / upgrade-reference team.

  python start_product_review.py --doc <product.md> --out reviews/<name> --real
  python start_product_review.py --doc <product.md> --out reviews/<name> --offline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.config import load_config  # noqa: E402
from orchestrator.product_review import ProductReviewRunner  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Product deep review / upgrade reference team")
    p.add_argument("--doc", required=True, help="产品文档（当前版或下一版）")
    p.add_argument("--out", required=True, help="评审输出目录，如 reviews/product-v2")
    p.add_argument("--offline", action="store_true", default=True,
                   help="离线 stub（默认，用于验证流程）")
    p.add_argument("--real", action="store_true",
                   help="真实模型（本地 Qwen，DeepSeek fallback）")
    p.add_argument("--roles", default=None, help="逗号分隔角色子集")
    p.add_argument("--kb", action="store_true", help="注入知识库引用")
    p.add_argument("--note", default="", help="给全团队的调整要求")
    p.add_argument("--force", action="store_true", help="允许写入非空输出目录")
    p.add_argument("--config", default=None)
    args = p.parse_args()

    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()) and not args.force:
        print(json.dumps({"error": f"输出目录非空：{out}；加 --force"}, ensure_ascii=False))
        return 2
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    runner = ProductReviewRunner(
        doc=args.doc, out_dir=out, cfg=load_config(args.config),
        offline=not args.real, roles=roles, use_kb=args.kb,
        extra_note=args.note)
    result = runner.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
