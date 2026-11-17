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

from orchestrator.game_check import detect_project_type, run_game_acceptance
from orchestrator.project_runner import ProjectRunner


GAME_REQ = """# 迷宫冒险家
2D 横版房间制迷宫动作冒险，单人+本地同屏，玩家打怪掉装，Boss 掉落，存档成长。
"""


class GameProfileTest(unittest.TestCase):
    def test_detects_game_requirement(self) -> None:
        self.assertEqual(detect_project_type(GAME_REQ), "game")
        self.assertEqual(detect_project_type("做一个财务报表 API，CSV 导出"), "web")

    def test_template_is_playable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "game-template"
            shutil.copytree(ROOT / "templates" / "web-2d-game", target)
            result = run_game_acceptance(target)
            self.assertEqual(result["status"], "pass", result)
            names = {c["name"] for c in result["checks"]}
            self.assertTrue({"entry", "logic", "smoke", "render"}.issubset(names))

    def test_game_runner_requires_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text(GAME_REQ, encoding="utf-8")
            project = base / "game-project"
            (project / "docs" / "product").mkdir(parents=True, exist_ok=True)
            (project / "docs" / "architecture").mkdir(parents=True, exist_ok=True)
            (project / "docs" / "product" / "product-baseline.md").write_text(
                "# Product\n\n流程、房间、职业、装备、存档、验收、非目标。\n",
                encoding="utf-8")
            (project / "docs" / "architecture" / "architecture.md").write_text(
                "# Arch\n\n模块、契约、存档、测试。\n", encoding="utf-8")
            runner = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["backend", "frontend", "qa"], template="web-2d-game",
                project_type="game", gates=True, tool_profile="basic",
                decision_db=base / "decisions.db")
            result = runner.run()
            self.assertEqual(result["status"], "completed", result)
            accepted = json.loads((project / "acceptance.json").read_text(encoding="utf-8"))
            self.assertEqual(accepted["status"], "pass")
            self.assertTrue((project / "game" / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
