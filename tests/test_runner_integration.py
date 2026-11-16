from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.project_runner import ProjectRunner  # noqa: E402


class RunnerIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.req = self.base / "req.md"
        self.req.write_text("# REQ\n月度 CSV 导出，验收 P95<2s，非目标 Excel 公式。\n",
                            encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_template_tools_gates_quality_and_sandbox(self) -> None:
        project = self.base / "proj"
        runner = ProjectRunner(
            requirements=self.req, project_dir=project, offline=True,
            roles=["product", "backend", "frontend"], template="minimal-api",
            tool_profile="basic", gates=True, sandbox=True,
            decision_db=self.base / "decisions.db")
        result = runner.run()
        self.assertEqual(result["status"], "completed", result)
        self.assertTrue((project / "src" / "backend" / "service.py").is_file())
        self.assertTrue((project / "src" / "frontend" / "app.js").is_file())
        self.assertTrue((project / "docs" / "product" / "product-baseline.md").is_file())
        ledger = project / "evidence" / "tool-ledger.jsonl"
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        self.assertGreaterEqual(len(rows), 4)
        state = json.loads((project / "state" / "roles.json").read_text(encoding="utf-8"))
        for role in ("product", "backend", "frontend"):
            self.assertEqual(state[role]["gate"]["status"], "pass", role)
            self.assertIsNotNone(state[role]["quality"]["score"])
        history = (project / "quality" / "history.jsonl").read_text(encoding="utf-8")
        self.assertEqual(len(history.strip().splitlines()), 3)

    def test_missing_tests_blocks_and_escalates(self) -> None:
        project = self.base / "failproj"
        runner = ProjectRunner(
            requirements=self.req, project_dir=project, offline=True,
            roles=["backend"], template="none", tool_profile="basic",
            gates=True, sandbox=False, decision_db=self.base / "decisions2.db")
        result = runner.run()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["roles"]["backend"], "blocked")
        state = json.loads((project / "state" / "roles.json").read_text(encoding="utf-8"))
        self.assertEqual(state["backend"]["gate"]["status"], "need_evidence")
        self.assertTrue(state["backend"]["gate"]["decision_id"])


if __name__ == "__main__":
    unittest.main()
