"""Round 1 acceptance: fail-closed routing, review status, provenance coverage."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.models.base import ChatResult, ConfigurationError  # noqa: E402
from orchestrator.models.router import ModelRouter  # noqa: E402
from orchestrator.product_review import (  # noqa: E402
    ROLE_MAP, ProductReviewRunner, _normalize)


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


class RouterConfigTest(unittest.TestCase):
    def test_unknown_backend_is_configuration_error(self) -> None:
        router = ModelRouter({}, offline=False)
        with self.assertRaises(ConfigurationError):
            router._backend("deapseek")

    def test_invalid_routing_rejected_at_construction(self) -> None:
        cfg = {"models": {"routing": {"backend": {"primary": "deapseek"}}}}
        with self.assertRaises(ConfigurationError):
            ModelRouter(cfg, offline=False)

    def test_stub_rejected_in_real_mode(self) -> None:
        cfg = {"models": {"routing": {"backend": {"primary": "stub"}}}}
        with self.assertRaises(ConfigurationError):
            ModelRouter(cfg, offline=False)

    def test_stub_allowed_only_in_offline_mode(self) -> None:
        cfg = {"models": {"routing": {"backend": {"primary": "stub"}}}}
        router = ModelRouter(cfg, offline=True)
        self.assertEqual(router._backend("stub").name, "stub")
        with self.assertRaises(ConfigurationError):
            ModelRouter({"models": {"routing": {"backend": {"primary": "stub"}}}},
                        offline=False)._backend("stub")

    def test_legal_backends_are_kept(self) -> None:
        cfg = {"models": {"routing": {
            "backend": {"primary": "local", "fallback": "deepseek"},
            "judge_j1": {"primary": "deepseek", "fallback": "local"},
        }}}
        router = ModelRouter(cfg, offline=False)
        self.assertEqual(router.routing["backend"]["primary"], "local")
        self.assertIs(router._backend("deepseek"), router.deepseek)


class ReviewGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.doc = self.base / "product.md"
        self.doc.write_text(DOC, encoding="utf-8")
        self.review = ProductReviewRunner(doc=self.doc, out_dir=self.base / "review",
                                          offline=True)
        self.review.prepare()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_blocked_review_never_passes(self) -> None:
        rel = "docs/product-review/01-document-map.md"
        (self.review.out_dir / rel).write_text(
            "来源 主张 歧义 覆盖 SRC-001 用户 流程", encoding="utf-8")
        gate = self.review.gate(ROLE_MAP["doc-analyst"],
                                {"status": "blocked", "summary": "来源 覆盖 SRC-001"},
                                [{"path": rel}], 1.0)
        self.assertEqual(gate["status"], "fail", gate)
        self.assertIn("status_done", [c["name"] for c in gate["checks"] if not c["ok"]])

    def test_missing_status_is_not_success(self) -> None:
        rel = "docs/product-review/01-document-map.md"
        (self.review.out_dir / rel).write_text(
            "来源 主张 歧义 覆盖 SRC-001 用户 流程", encoding="utf-8")
        obj = _normalize({"role": "doc-analyst", "summary": "来源 主张 歧义 覆盖 SRC-001"},
                         "doc-analyst", len(self.review.sections),
                         valid_ids=self.review.section_ids)
        self.assertEqual(obj["status"], "unknown")
        gate = self.review.gate(ROLE_MAP["doc-analyst"], obj, [{"path": rel}], 1.0)
        self.assertEqual(gate["status"], "fail", gate)

    def test_invalid_source_reference_fails(self) -> None:
        rel = "docs/product-review/01-document-map.md"
        (self.review.out_dir / rel).write_text(
            "来源 主张 歧义 覆盖 SRC-001 SRC-999 用户 流程", encoding="utf-8")
        gate = self.review.gate(ROLE_MAP["doc-analyst"],
                                {"status": "done", "summary": "来源 主张 歧义 覆盖 SRC-999"},
                                [{"path": rel}], 1.0)
        self.assertEqual(gate["status"], "fail", gate)
        failed = {c["name"] for c in gate["checks"] if not c["ok"]}
        self.assertIn("source_refs_valid", failed)

    def test_empty_artifact_fails(self) -> None:
        rel = "docs/product-review/01-document-map.md"
        (self.review.out_dir / rel).write_text("   \n", encoding="utf-8")
        gate = self.review.gate(ROLE_MAP["doc-analyst"],
                                {"status": "done",
                                 "summary": "来源 主张 歧义 覆盖 SRC-001"},
                                [{"path": rel}], 1.0)
        self.assertEqual(gate["status"], "fail", gate)
        self.assertIn("files_nonempty",
                      [c["name"] for c in gate["checks"] if not c["ok"]])


class ReviewRunTest(unittest.TestCase):
    def test_request_text_does_not_contribute_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            doc = base / "product.md"
            doc.write_text(DOC, encoding="utf-8")
            runner = ProductReviewRunner(doc=doc, out_dir=base / "review", offline=True,
                                         roles=["product-lead"])

            def empty_files(role, messages, *, response_format=None):
                refs = [s["id"] for s in runner.sections]
                obj = {
                    "task_id": "t", "role": role, "status": "done",
                    "source_sections": refs, "findings": [],
                    "coverage": {"total_sections": len(refs), "covered_sections": len(refs),
                                 "percent": 100},
                    "files": [],
                    "summary": "目标 成功指标 非目标 决策 " + " ".join(refs),
                    "open_questions": [],
                }
                return ChatResult(content=json.dumps(obj, ensure_ascii=False),
                                  backend="fake", model="fake")

            runner.router.execution = empty_files
            result = runner.run()
            self.assertEqual(result["coverage"], 0.0, result)
            self.assertEqual(result["status"], "fail", result)

    def test_new_failure_supersedes_old_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            doc = base / "product.md"
            doc.write_text(DOC, encoding="utf-8")
            out = base / "review"
            first = ProductReviewRunner(doc=doc, out_dir=out, offline=True).run()
            self.assertEqual(first["status"], "pass", first)

            doc.write_text("# 新版本\n## 不同要求\n旧验收不再适用。\n", encoding="utf-8")
            second = ProductReviewRunner(doc=doc, out_dir=out, offline=True,
                                         roles=["product-lead"])

            def fail(*args, **kwargs):
                raise RuntimeError("injected backend failure")

            second.router.execution = fail
            result = second.run()
            self.assertEqual(result["status"], "fail", result)
            self.assertEqual(result["gates"]["product-lead"], "fail", result)
            self.assertEqual(result["gates"]["doc-analyst"], "stale", result)
            saved = json.loads((out / "state" / "gates.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "fail")
            self.assertTrue((out / "state" / "gate-history.jsonl").is_file())
            history = (out / "state" / "gate-history.jsonl").read_text(
                encoding="utf-8").splitlines()
            self.assertTrue(any('"status": "pass"' in line for line in history))

    def test_unchanged_source_reuses_other_gates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            doc = base / "product.md"
            doc.write_text(DOC, encoding="utf-8")
            out = base / "review"
            first = ProductReviewRunner(doc=doc, out_dir=out, offline=True).run()
            self.assertEqual(first["status"], "pass", first)
            partial = ProductReviewRunner(doc=doc, out_dir=out, offline=True,
                                          roles=["product-lead"]).run()
            self.assertEqual(partial["status"], "pass", partial)
            self.assertEqual(partial["coverage_detail"]["reused_roles"][0],
                             "doc-analyst")
            gates = json.loads((out / "state" / "gates.json").read_text(encoding="utf-8"))
            reused = [g for g in gates["gates"] if g.get("reused")]
            self.assertEqual(len(reused), 10, gates["gates"])


if __name__ == "__main__":
    unittest.main()
