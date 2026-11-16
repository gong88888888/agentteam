from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.evidence.store import EvidenceStore  # noqa: E402
from orchestrator.tool_evidence import collect  # noqa: E402


class ToolEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["EVIDENCE_SIGNING_KEY"] = "test-key-0123456789"
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "src" / "backend").mkdir(parents=True)
        (self.project / "src" / "backend" / "app.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8")
        (self.project / "tests").mkdir()
        (self.project / "tests" / "test_app.py").write_text(
            "import unittest\n"
            "from src.backend.app import add\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(1, 2), 3)\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()
        os.environ.pop("EVIDENCE_SIGNING_KEY", None)

    def test_basic_profile_passes_and_signs(self) -> None:
        result = collect(self.project, profile="basic")
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["missing"], [])
        kinds = {e["kind"] for e in result["evidence"]}
        self.assertEqual(kinds, {"compile", "unit"})
        store = EvidenceStore(self.project / "evidence" / "tool-ledger.jsonl",
                              b"test-key-0123456789")
        self.assertTrue(store.verify_chain())
        self.assertEqual(len(store.all()), 2)

    def test_missing_tests_is_explicit(self) -> None:
        for p in (self.project / "tests").glob("*"):
            p.unlink()
        result = collect(self.project, profile="basic")
        self.assertIn("unit", [m["kind"] for m in result["missing"]])
        self.assertNotIn("unit", result["passed"])

    def test_failing_test_is_signed_fail(self) -> None:
        (self.project / "tests" / "test_app.py").write_text(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_bad(self):\n"
            "        self.assertEqual(1, 2)\n", encoding="utf-8")
        result = collect(self.project, profile="basic")
        self.assertIn("unit", result["failed"])
        rec = next(e for e in result["evidence"] if e["kind"] == "unit")
        self.assertEqual(rec["result"], "fail")


if __name__ == "__main__":
    unittest.main()
