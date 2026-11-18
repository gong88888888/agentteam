"""Round 5 acceptance: game extension registration and reachability."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.game_check import (  # noqa: E402
    entry_reachable, increment_modules, integration_report,
    load_extension_manifest)
from orchestrator.project_runner import ProjectRunner  # noqa: E402
from orchestrator.sandbox import Sandbox  # noqa: E402

MODULE = """\
export const extension = {
  id: "inventory-filter",
  version: 1,
  actions: ["filterItems"],
  smoke: { action: "filterItems", args: [["a", "b"], "a"], expectType: "object" },
};

export function filterItems(items, query) {
  return items.filter((item) => String(item).includes(query));
}
"""


class ExtensionIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "game-project"
        shutil.copytree(ROOT / "templates" / "web-2d-game", self.project)
        self.game = self.project / "game"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _report(self) -> dict:
        return integration_report(self.project, Sandbox(self.game, timeout_s=60))

    def test_unregistered_generated_module_fails(self) -> None:
        module = self.game / "js" / "gameplay" / "inventory_filter.js"
        module.write_text("export function filterItems() { return []; }\n",
                          encoding="utf-8")
        self.assertIn("game/js/gameplay/inventory_filter.js",
                      increment_modules(self.project))
        report = self._report()
        self.assertFalse(report["ok"], report)
        self.assertIn("game/js/gameplay/inventory_filter.js",
                      report["unreachable"])

    def test_registered_module_is_loaded_invoked_and_asserted(self) -> None:
        module = self.game / "js" / "gameplay" / "inventory_filter.js"
        module.write_text(MODULE, encoding="utf-8")
        manifest = self.game / "js" / "extensions" / "manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": "1.0",
            "extensions": [{"id": "inventory-filter",
                            "module": "js/gameplay/inventory_filter.js",
                            "actions": ["filterItems"]}],
        }), encoding="utf-8")
        report = self._report()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["harness"]["loaded"], 1)
        self.assertEqual(report["harness"]["invoked"], 1)
        self.assertEqual(report["harness"]["asserted"], 1)

    def test_manifest_module_missing_fails(self) -> None:
        manifest = self.game / "js" / "extensions" / "manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": "1.0",
            "extensions": [{"id": "ghost",
                            "module": "js/gameplay/ghost.js"}],
        }), encoding="utf-8")
        entries, errors = load_extension_manifest(self.project)
        self.assertEqual(entries, [])
        self.assertTrue(any("模块不存在" in e for e in errors), errors)
        report = self._report()
        self.assertFalse(report["ok"], report)

    def test_baseline_template_has_no_increments(self) -> None:
        self.assertEqual(increment_modules(self.project), [])
        report = self._report()
        self.assertTrue(report["ok"], report)
        self.assertTrue(report.get("harness") is None)

    def test_entry_reachability_tracks_static_imports(self) -> None:
        (self.game / "js" / "ui").mkdir(parents=True, exist_ok=True)
        (self.game / "js" / "ui" / "helper.js").write_text(
            "export const x = 1;\n", encoding="utf-8")
        main = self.game / "js" / "main.js"
        main.write_text('import { x } from "./ui/helper.js";\n' + main.read_text(
            encoding="utf-8"), encoding="utf-8")
        reachable = entry_reachable(self.project)
        self.assertIn("game/js/ui/helper.js", reachable)

    def test_runner_writes_manifest_for_stub_modules(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# 游戏\n玩家、房间、存档、Boss、装备。\n", encoding="utf-8")
            project = base / "run"
            runner = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["backend", "frontend"], template="web-2d-game",
                project_type="game", gates=True, tool_profile="basic",
                decision_db=base / "decisions.db")
            runner.run()
            manifest = json.loads((project / "game" / "js" / "extensions"
                                   / "manifest.json").read_text(encoding="utf-8"))
            ids = {e["id"] for e in manifest["extensions"]}
            self.assertEqual(ids, {"stub-systems", "stub-hud"}, manifest)


class MetadataTest(unittest.TestCase):
    def test_parse_metadata(self) -> None:
        meta = ProjectRunner.parse_extension_metadata(MODULE)
        self.assertEqual(meta["id"], "inventory-filter")
        self.assertEqual(meta["actions"], ["filterItems"])
        self.assertEqual(meta["smoke"]["action"], "filterItems")
        self.assertEqual(meta["smoke"]["expectType"], "object")

    def test_missing_metadata(self) -> None:
        self.assertIsNone(ProjectRunner.parse_extension_metadata(
            "export function f() { return 1; }\n"))


if __name__ == "__main__":
    unittest.main()
