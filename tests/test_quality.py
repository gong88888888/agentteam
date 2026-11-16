from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.quality import append_history, load_history, role_trend, score_role
from orchestrator.role_gates import GateCheck, GateResult


class QualityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.gate = GateResult("G-DEMO-backend", "backend", "pass",
                               [GateCheck("artifact", True)])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_score_is_bounded_and_explained(self) -> None:
        obj = {"role": "backend", "status": "done",
               "claims": [{"claim": "实现接口"}],
               "open_questions": [],
               "summary": "实现导出接口，包含参数校验与错误码。"}
        q = score_role("backend", obj, files=[{"path": "src/backend/app.py"}],
                       gate=self.gate, tool_result={
                           "profile": "basic",
                           "evidence": [{"kind": "compile", "result": "pass"},
                                        {"kind": "unit", "result": "pass"}]},
                       latency_ms=8000, tokens=1200)
        self.assertGreaterEqual(q["score"], 80)
        self.assertEqual(q["grade"], "A")
        self.assertIn("gate", q["components"])

    def test_history_and_trend(self) -> None:
        q = {"score": 90, "grade": "A", "components": {}, "issues": []}
        meta = {"model": "stub", "backend": "stub", "latency_ms": 1, "tokens": 2,
                "files": []}
        append_history(self.project, role="backend", quality=q, gate=self.gate,
                       obj={"status": "done"}, meta=meta, run_id="r1")
        append_history(self.project, role="backend", quality={**q, "score": 80},
                       gate=self.gate, obj={"status": "done"}, meta=meta, run_id="r2")
        self.assertEqual(len(load_history(self.project, "backend")), 2)
        trend = role_trend(self.project, "backend")
        self.assertEqual(trend["latest"], 80)
        self.assertEqual(trend["average"], 85.0)


if __name__ == "__main__":
    unittest.main()
