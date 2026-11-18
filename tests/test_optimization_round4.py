"""Round 4 acceptance: response protocol, source units, requirements, context."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.context import ContextAssembler  # noqa: E402
from orchestrator.design_states import BASE_STATES, validate_design  # noqa: E402
from orchestrator.models.base import (BackendUnavailable, ChatResult,  # noqa: E402
                                      ModelAuthError, ModelRateLimit,
                                      ModelTransientError, ModelTruncated)
from orchestrator.models.deepseek import DeepSeekBackend  # noqa: E402
from orchestrator.models.router import ModelRouter  # noqa: E402
from orchestrator.project_runner import ProjectRunner  # noqa: E402
from orchestrator.requirements_ledger import (  # noqa: E402
    RequirementCandidate, RequirementLedger, SourceDisposition,
    from_model_output)
from orchestrator.sources import diff_units, parse_markdown  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, text: str = "") -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = text
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self) -> dict:
        return self.payload


class ResponseProtocolTest(unittest.TestCase):
    def _backend(self) -> DeepSeekBackend:
        return DeepSeekBackend("https://api.deepseek.com/v1", "key",
                               "deepseek-chat")

    def test_empty_text_with_tool_call_is_usable(self) -> None:
        payload = {
            "id": "resp-tool", "model": "deepseek-chat",
            "choices": [{
                "message": {"content": "", "tool_calls": [
                    {"id": "call-1", "type": "function",
                     "function": {"name": "read_file",
                                  "arguments": "{\"path\":\"a.py\"}"}}]},
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4},
        }
        with patch("orchestrator.models.deepseek.requests.post",
                   return_value=FakeResponse(payload)):
            result = self._backend().chat([{"role": "user", "content": "x"}],
                                          tools=[{"type": "function"}])
        self.assertTrue(result.usable())
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.finish_reason, "tool_calls")

    def test_truncated_response_is_an_error(self) -> None:
        payload = {"choices": [{"message": {"content": ""},
                                "finish_reason": "length"}]}
        with patch("orchestrator.models.deepseek.requests.post",
                   return_value=FakeResponse(payload)):
            with self.assertRaises(ModelTruncated):
                self._backend().chat([{"role": "user", "content": "x"}])

    def test_http_errors_are_classified(self) -> None:
        cases = [(401, ModelAuthError), (429, ModelRateLimit),
                 (500, ModelTransientError)]
        for code, expected in cases:
            with self.subTest(code=code):
                with patch("orchestrator.models.deepseek.requests.post",
                           return_value=FakeResponse({}, status_code=code,
                                                     text="provider error")):
                    with self.assertRaises(expected):
                        self._backend().chat([{"role": "user", "content": "x"}])

    def test_router_rejects_truncation_from_any_backend(self) -> None:
        class FakeBackend:
            name = "fake"

            def available(self) -> bool:
                return True

            def chat(self, messages, **kwargs):
                return ChatResult(content="", backend="fake", model="fake",
                                  finish_reason="length")

        router = ModelRouter({"models": {"routing": {"product": {
            "primary": "local"}}}}, offline=False)
        router.local = FakeBackend()
        with self.assertRaises(BackendUnavailable) as ctx:
            router.execution("product", [{"role": "user", "content": "x"}])
        self.assertIn("finish_reason=length", str(ctx.exception))

    def test_router_accepts_tool_only_response(self) -> None:
        class FakeBackend:
            name = "fake"

            def available(self) -> bool:
                return True

            def chat(self, messages, **kwargs):
                return ChatResult(content="", backend="fake", model="fake",
                                  tool_calls=[{"id": "c1"}],
                                  finish_reason="tool_calls")

        router = ModelRouter({"models": {"routing": {"product": {
            "primary": "local"}}}}, offline=False)
        router.local = FakeBackend()
        result = router.execution("product", [{"role": "user", "content": "x"}])
        self.assertTrue(result.usable())


class SourceUnitTest(unittest.TestCase):
    def test_prepending_heading_keeps_stable_id(self) -> None:
        old = parse_markdown("# 目标\n\n单人可通关。\n\n# 验收\n\n可回滚。\n")
        new = parse_markdown("# 新增\n\n# 目标\n\n单人可通关。\n\n# 验收\n\n可回滚。\n")
        old_goal = next(u for u in old.units
                        if u.kind == "heading" and u.heading == "目标")
        new_goal = next(u for u in new.units
                        if u.kind == "heading" and u.heading == "目标")
        self.assertEqual(old_goal.unit_id, new_goal.unit_id)
        diff = diff_units(old, new)
        self.assertEqual(diff["counts"]["added"], 1, diff)

    def test_moved_paragraph_is_reported(self) -> None:
        old = parse_markdown("# A\n\n限制：失败后保留输入。\n\n# B\n\n其他。\n")
        new = parse_markdown("# A\n\n# B\n\n限制：失败后保留输入。\n\n其他。\n")
        diff = diff_units(old, new)
        self.assertGreaterEqual(diff["counts"]["moved"], 1, diff)
        moved = diff["moved"][0]
        self.assertEqual(moved["old_id"], moved["new_id"])

    def test_table_negative_condition_is_a_unit(self) -> None:
        doc = parse_markdown(
            "# 功能\n\n| 功能 | 角色 | 限制 |\n|---|---|---|\n"
            "| 导出 | 普通成员 | 不得查看他人记录 |\n")
        tables = [u for u in doc.units if u.kind == "table"]
        self.assertEqual(len(tables), 1)
        self.assertIn("不得查看他人记录", tables[0].text)

    def test_document_without_headings_still_has_units(self) -> None:
        doc = parse_markdown("第一段。\n\n第二段包含末尾限制。\n")
        self.assertTrue(doc.units)
        self.assertTrue(all(u.heading == "" for u in doc.units))


class RequirementLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = parse_markdown(
            "# 存档\n\n支持自动存档。\n\n# 备份\n\n主存档损坏时读取备份。\n")
        self.units = self.doc.units

    def test_valid_requirements_and_dispositions(self) -> None:
        ids = [u.unit_id for u in self.units]
        ledger = RequirementLedger(
            doc_id="PRODUCT",
            requirements=[
                RequirementCandidate("REQ-1", "自动存档", [ids[1]], "functional",
                                     "每 15 秒落盘"),
                RequirementCandidate("REQ-2", "损坏主档读取备份", [ids[3]],
                                     "compatibility", "恢复最近有效备份"),
            ],
            dispositions=[
                SourceDisposition(ids[0], "background", [], "标题"),
                SourceDisposition(ids[1], "requirement", ["REQ-1"]),
                SourceDisposition(ids[2], "background", [], "标题"),
                SourceDisposition(ids[3], "requirement", ["REQ-2"]),
            ])
        self.assertEqual(ledger.validate(ids), [])
        self.assertEqual(ledger.coverage(self.units)["percent"], 100.0)

    def test_unknown_source_is_rejected(self) -> None:
        ledger = RequirementLedger(
            doc_id="PRODUCT",
            requirements=[RequirementCandidate("REQ-1", "自动存档", ["SU-MISSING"],
                                               "functional", "落盘")],
            dispositions=[])
        errors = ledger.validate(u.unit_id for u in self.units)
        self.assertIn("unknown_source", {e["code"] for e in errors})

    def test_model_output_requires_dispositions(self) -> None:
        ledger, errors = from_model_output({
            "requirements": [{"id": "REQ-1", "statement": "自动存档",
                              "source_refs": [self.units[1].unit_id],
                              "kind": "functional", "expected_result": "落盘"}],
        }, self.units, "PRODUCT")
        self.assertIn("no_dispositions", {e["code"] for e in errors})
        self.assertEqual(len(ledger.requirements), 1)

    def test_model_src_alias_maps_to_stable_unit(self) -> None:
        heading = self.doc.units[0]
        ledger, errors = from_model_output({
            "requirements": [{"id": "REQ-1", "statement": "自动存档",
                              "source_refs": ["SRC-001"],
                              "kind": "functional", "expected_result": "落盘"}],
            "source_dispositions": [{"unit_id": "SRC-001",
                                     "status": "requirement",
                                     "requirement_ids": ["REQ-1"]}],
        }, self.units, "PRODUCT", aliases={"SRC-001": heading.unit_id})
        self.assertEqual(errors, [], errors)
        self.assertEqual(ledger.requirements[0].source_refs, [heading.unit_id])

    def test_duplicate_disposition_is_rejected(self) -> None:
        unit = self.units[1].unit_id
        ledger = RequirementLedger(
            doc_id="PRODUCT",
            requirements=[RequirementCandidate("REQ-1", "自动存档", [unit],
                                               "functional", "落盘")],
            dispositions=[SourceDisposition(unit, "requirement", ["REQ-1"]),
                          SourceDisposition(unit, "background")])
        errors = ledger.validate(u.unit_id for u in self.units)
        self.assertIn("duplicate_disposition", {e["code"] for e in errors})


class DesignStateTest(unittest.TestCase):
    def _valid_page(self) -> dict:
        states = [{"name": name} for name in BASE_STATES]
        for state in states:
            if state["name"] == "idle":
                state["actions"] = "显示表单"
        transitions = [
            {"from": "idle", "event": "submit", "to": "submitting"},
            {"from": "submitting", "event": "ok", "to": "success"},
            {"from": "submitting", "event": "error", "to": "error"},
            {"from": "error", "event": "retry", "to": "submitting"},
        ]
        return {"id": "save-dialog", "states": states,
                "transitions": transitions, "scenarios": ["SCN-SAVE-04"]}

    def test_complete_states_pass(self) -> None:
        result = validate_design([self._valid_page()],
                                 required_scenarios=["SCN-SAVE-04"])
        # Minor no-outgoing warnings are allowed; blocking findings are not.
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["scenario_coverage"]["covered"], 1)

    def test_missing_error_state_blocks(self) -> None:
        page = self._valid_page()
        page["states"] = [s for s in page["states"] if s["name"] != "error"]
        result = validate_design([page], required_scenarios=["SCN-SAVE-04"])
        self.assertEqual(result["status"], "fail", result)
        self.assertIn("missing_state",
                      {f["code"] for f in result["findings"]})

    def test_not_applicable_needs_reason(self) -> None:
        page = self._valid_page()
        for state in page["states"]:
            if state["name"] == "offline":
                state["applicable"] = False
        result = validate_design([page])
        self.assertIn("na_without_reason",
                      {f["code"] for f in result["findings"]})
        for state in page["states"]:
            if state["name"] == "offline":
                state["not_applicable_reason"] = "纯本地读写，无网络调用"
        result = validate_design([page])
        self.assertNotIn("na_without_reason",
                         {f["code"] for f in result["findings"]})

    def test_unknown_transition_blocks(self) -> None:
        page = self._valid_page()
        page["transitions"].append({"from": "idle", "event": "x", "to": "ghost"})
        result = validate_design([page])
        self.assertIn("unknown_to", {f["code"] for f in result["findings"]})


class ContextAssemblerTest(unittest.TestCase):
    def test_required_reference_is_injected_in_full(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "docs" / "product" / "product-baseline.md"
            doc.parent.mkdir(parents=True)
            long_text = "# 产品\n\n" + ("前文约束。\n\n" * 200) + "末尾限制：失败后保留输入。\n"
            doc.write_text(long_text, encoding="utf-8")
            assembler = ContextAssembler(root, budget_chars=20000)
            assembler.add_file("docs/product/product-baseline.md",
                               importance="required", required=True)
            pack = assembler.build()
            self.assertIn("末尾限制：失败后保留输入", pack.render())
            self.assertEqual(pack.errors, [])
            manifest = pack.manifest()
            self.assertEqual(manifest["items"][0]["importance"], "required")

    def test_missing_required_reference_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            assembler = ContextAssembler(Path(td), budget_chars=1000)
            assembler.add_file("docs/product/missing.md", required=True)
            pack = assembler.build()
            self.assertTrue(pack.missing)
            self.assertIn("MISSING", pack.render())
            self.assertTrue(pack.errors)

    def test_budget_truncation_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "big.md"
            doc.write_text("x" * 500, encoding="utf-8")
            assembler = ContextAssembler(root, budget_chars=100)
            assembler.add_file("big.md", importance="required", required=True)
            pack = assembler.build()
            self.assertTrue(pack.items[0].truncated)
            self.assertIn("TRUNCATED", pack.render())

    def test_project_runner_builds_context_from_product_document(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# REQ\n实现导出。\n", encoding="utf-8")
            runner = ProjectRunner(requirements=req, project_dir=base / "proj",
                                   offline=True, roles=["product", "backend"],
                                   template="minimal-api")
            runner.prepare()
            doc = runner.project_dir / "docs" / "product" / "product-baseline.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("# 产品\n\n" + ("背景。\n\n" * 100)
                           + "末尾限制：失败后保留输入。\n", encoding="utf-8")
            state = {"product": {"status": "done", "files": [
                {"path": "docs/product/product-baseline.md", "source": "role"}]}}
            pack = runner.build_context("backend", state)
            self.assertIn("末尾限制：失败后保留输入", pack.render())
            self.assertTrue(any(item.importance == "required"
                                for item in pack.items))


if __name__ == "__main__":
    unittest.main()
