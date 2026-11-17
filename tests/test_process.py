from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.process import definition_of_done, preflight, stage_plan


class ProcessTest(unittest.TestCase):
    def test_preflight_game_template(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "game"
            shutil.copytree(ROOT / "templates" / "web-2d-game", target)
            result = preflight(target, "game", "web-2d-game")
            self.assertEqual(result["status"], "pass", result)
            self.assertIn("game/js/core.js + main.js",
                          [c["detail"] for c in result["checks"]])

    def test_dod_blocks_missing_docs_or_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "game").mkdir()
            (root / "game" / "index.html").write_text("x", encoding="utf-8")
            state = {"product": {"status": "done", "gate": {"status": "pass"}}}
            result = definition_of_done(root, "game", state,
                                        acceptance={"status": "pass"})
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(c["name"] == "docs" and not c["ok"]
                                for c in result["checks"]))

    def test_stage_plan_has_gates(self) -> None:
        plan = stage_plan("game")
        self.assertEqual(plan[0]["id"], "intake")
        self.assertEqual(plan[3]["gate"], "game_acceptance")


if __name__ == "__main__":
    unittest.main()
