from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.product_review import ProductReviewRunner, extract_source_sections


DOC = """# 产品基准
## 目标
单人完整通关，本地双人增强。
## 核心流程
主菜单 -> 战斗 -> 商店 -> 篝火 -> Boss -> 结算 -> 存档。
## 非目标
不做交易行和云存档。
## 验收
可启动、可通关、可回滚、存档成功率可测。
## 升级
新增功能必须兼容旧存档并提供回滚。
"""


class ProductReviewTest(unittest.TestCase):
    def test_sections_have_stable_ids(self) -> None:
        sections = extract_source_sections(DOC)
        self.assertEqual([s["id"] for s in sections],
                         ["SRC-001", "SRC-002", "SRC-003", "SRC-004", "SRC-005", "SRC-006"])

    def test_offline_team_produces_reference_plan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            doc = base / "product.md"
            doc.write_text(DOC, encoding="utf-8")
            out = base / "review"
            runner = ProductReviewRunner(doc=doc, out_dir=out, offline=True)
            result = runner.run()
            self.assertEqual(result["status"], "pass", result)
            self.assertEqual(len(result["gates"]), 11)
            self.assertTrue((out / "REFERENCE-PLAN.md").is_file())
            self.assertTrue((out / "docs" / "product-review" / "08-rehearsal.md").is_file())
            gates = json.loads((out / "state" / "gates.json").read_text(encoding="utf-8"))
            self.assertEqual(gates["status"], "pass")
            self.assertGreaterEqual(gates["coverage_percent"], 80)


if __name__ == "__main__":
    unittest.main()
