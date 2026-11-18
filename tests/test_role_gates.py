from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.decisions import DecisionStore  # noqa: E402
from orchestrator.evidence.resolver import EvidenceResolver  # noqa: E402
from orchestrator.evidence.store import EvidenceStore  # noqa: E402
from orchestrator.role_gates import evaluate_role  # noqa: E402


def envelope(role: str, summary: str) -> dict:
    return {"task_id": "t", "role": role, "status": "done", "artifacts": [],
            "claims": [{"claim": summary, "counts_as_evidence": False}],
            "evidence_refs": [], "open_questions": [], "summary": summary}


class RoleGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.store = DecisionStore(self.project / "decisions.db")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_product_gate_passes_with_acceptance_and_non_goals(self) -> None:
        (self.project / "docs" / "product").mkdir(parents=True)
        (self.project / "docs" / "product" / "product-baseline.md").write_text(
            "# 产品基准\n\n- 验收标准：P95 < 2s\n- 非目标：不做 Excel 公式\n",
            encoding="utf-8")
        gate = evaluate_role("product",
                             envelope("product", "验收标准 非目标 用户场景"),
                             project_dir=self.project, files=[],
                             decision_store=None)
        self.assertEqual(gate.status, "pass", gate.to_dict())

    def test_failure_escalates_to_inbox(self) -> None:
        gate = evaluate_role("product", envelope("product", "只有一句空泛描述"),
                             project_dir=self.project, files=[],
                             decision_store=self.store, project_name="demo")
        self.assertEqual(gate.status, "fail")
        self.assertTrue(gate.decision_id)
        item = self.store.get(gate.decision_id)
        self.assertIsNotNone(item)
        self.assertEqual(item["status"], "pending")
        self.assertEqual(item["gate_id"], gate.gate_id)

    def test_code_gate_requires_passing_evidence(self) -> None:
        (self.project / "src" / "backend").mkdir(parents=True)
        (self.project / "src" / "backend" / "app.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8")
        files = [{"path": "src/backend/app.py", "sha256": "x", "source": "role",
                  "promoted": True}]
        key = b"round2-test-key"
        ledger = self.project / "evidence" / "tool-ledger.jsonl"
        store = EvidenceStore(ledger, key)
        first = store.add(kind="compile", subject_hash="abc", tool="python",
                          tool_version="3.13", result="pass", signed_by="tool:python",
                          baseline_fp="project")
        second = store.add(kind="unit", subject_hash="abc", tool="unittest",
                           tool_version="3.13", result="pass", signed_by="tool:unittest",
                           baseline_fp="project")
        tool = {"subject_hash": "abc", "profile": "basic", "missing": [],
                "ledger": str(ledger),
                "evidence": [
                    {"kind": "compile", "result": "pass",
                     "evidence_id": first["evidence_id"]},
                    {"kind": "unit", "result": "pass",
                     "evidence_id": second["evidence_id"]}]}
        gate = evaluate_role("backend", envelope("backend", "实现接口并通过编译与测试"),
                             project_dir=self.project, files=files,
                             tool_result=tool, decision_store=None,
                             evidence_resolver=EvidenceResolver(ledger, key))
        self.assertEqual(gate.status, "pass", gate.to_dict())
        self.assertEqual(gate.trust, "verified")
        self.assertEqual(set(gate.evidence_verified),
                         {first["evidence_id"], second["evidence_id"]})

    def test_code_gate_blocks_when_evidence_missing(self) -> None:
        (self.project / "src" / "backend").mkdir(parents=True)
        (self.project / "src" / "backend" / "app.py").write_text("x=1\n", encoding="utf-8")
        files = [{"path": "src/backend/app.py", "sha256": "x", "source": "role"}]
        gate = evaluate_role("backend", envelope("backend", "实现接口并通过编译与测试"),
                             project_dir=self.project, files=files,
                             tool_result=None, decision_store=self.store,
                             project_name="demo")
        self.assertEqual(gate.status, "need_evidence")
        self.assertIn("unit", " ".join(gate.missing) + " tool_evidence")


if __name__ == "__main__":
    unittest.main()
