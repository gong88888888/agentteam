"""Round 2 acceptance: verified evidence, artifact provenance, empty outputs."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.evidence.resolver import (  # noqa: E402
    EvidenceResolutionError, EvidenceResolver)
from orchestrator.evidence.store import EvidenceStore  # noqa: E402
from orchestrator.role_gates import evaluate_role  # noqa: E402

KEY = b"round2-key"


def envelope(role: str, summary: str) -> dict:
    return {"task_id": "t", "role": role, "status": "done", "artifacts": [],
            "claims": [{"claim": summary, "counts_as_evidence": False}],
            "evidence_refs": [], "open_questions": [], "summary": summary}


class ResolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "evidence" / "tool-ledger.jsonl"
        self.store = EvidenceStore(self.ledger, KEY)
        self.rec = self.store.add(
            kind="unit", subject_hash="subject-a", tool="unittest",
            tool_version="3.13", result="pass", signed_by="tool:unittest",
            baseline_fp="project", ttl_s=3600)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_resolves_current_subject(self) -> None:
        resolver = EvidenceResolver(self.ledger, KEY)
        verified = resolver.resolve(self.rec["evidence_id"], kind="unit",
                                    subject_hash="subject-a")
        self.assertEqual(verified.result, "pass")
        self.assertEqual(verified.kind, "unit")

    def test_missing_id_is_rejected(self) -> None:
        resolver = EvidenceResolver(self.ledger, KEY)
        with self.assertRaises(EvidenceResolutionError) as ctx:
            resolver.resolve("EV-999999", kind="unit")
        self.assertEqual(ctx.exception.code, "not_found")

    def test_wrong_subject_is_rejected(self) -> None:
        resolver = EvidenceResolver(self.ledger, KEY)
        with self.assertRaises(EvidenceResolutionError) as ctx:
            resolver.resolve(self.rec["evidence_id"], kind="unit",
                             subject_hash="subject-b")
        self.assertEqual(ctx.exception.code, "subject_mismatch")

    def test_wrong_kind_is_rejected(self) -> None:
        resolver = EvidenceResolver(self.ledger, KEY)
        with self.assertRaises(EvidenceResolutionError) as ctx:
            resolver.resolve(self.rec["evidence_id"], kind="sast")
        self.assertEqual(ctx.exception.code, "kind_mismatch")

    def test_expired_evidence_is_rejected(self) -> None:
        expired = self.store.add(
            kind="unit", subject_hash="subject-a", tool="unittest",
            tool_version="3.13", result="pass", signed_by="tool:unittest",
            baseline_fp="project", ttl_s=1, now=1)
        resolver = EvidenceResolver(self.ledger, KEY, now=10_000)
        with self.assertRaises(EvidenceResolutionError) as ctx:
            resolver.resolve(expired["evidence_id"], kind="unit",
                             subject_hash="subject-a")
        self.assertEqual(ctx.exception.code, "expired_or_revoked")

    def test_revoked_evidence_is_rejected(self) -> None:
        self.store.invalidate_subject("subject-a", "code changed")
        resolver = EvidenceResolver(self.ledger, KEY)
        with self.assertRaises(EvidenceResolutionError) as ctx:
            resolver.resolve(self.rec["evidence_id"], kind="unit",
                             subject_hash="subject-a")
        self.assertEqual(ctx.exception.code, "expired_or_revoked")

    def test_tampered_ledger_is_not_trusted(self) -> None:
        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        rec = json.loads(lines[0])
        rec["payload"]["exit_code"] = 1
        self.ledger.write_text(json.dumps(rec, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        resolver = EvidenceResolver(self.ledger, KEY)
        with self.assertRaises(EvidenceResolutionError) as ctx:
            resolver.resolve(rec["evidence_id"], kind="unit")
        self.assertEqual(ctx.exception.code, "ledger_integrity")


class GateTrustTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "src" / "backend").mkdir(parents=True)
        (self.project / "src" / "backend" / "app.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8")
        self.files = [{"path": "src/backend/app.py", "sha256": "x",
                       "source": "role", "promoted": True}]
        self.ledger = self.project / "evidence" / "tool-ledger.jsonl"
        self.store = EvidenceStore(self.ledger, KEY)
        self.evidence = [
            self.store.add(kind="compile", subject_hash="subject-a", tool="python",
                           tool_version="3.13", result="pass", signed_by="tool:python",
                           baseline_fp="project"),
            self.store.add(kind="unit", subject_hash="subject-a", tool="unittest",
                           tool_version="3.13", result="pass", signed_by="tool:unittest",
                           baseline_fp="project"),
        ]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _tool(self, subject: str = "subject-a", ids: list[str] | None = None) -> dict:
        return {"subject_hash": subject, "profile": "basic", "missing": [],
                "evidence": [
                    {"kind": r["kind"], "result": "pass",
                     "evidence_id": (ids or [e["evidence_id"] for e in self.evidence])[i]}
                    for i, r in enumerate(self.evidence)]}

    def test_forged_pass_dictionary_is_not_accepted(self) -> None:
        tool = {"subject_hash": "unverified-subject", "evidence": [
            {"kind": "compile", "result": "pass", "evidence_id": "FAKE1"},
            {"kind": "unit", "result": "pass", "evidence_id": "FAKE2"}]}
        gate = evaluate_role("backend", envelope("backend", "实现接口并通过编译与测试"),
                             project_dir=self.project, files=self.files,
                             tool_result=tool, decision_store=None)
        self.assertEqual(gate.status, "need_evidence", gate.to_dict())
        self.assertEqual(gate.trust, "unverified")
        self.assertIn("evidence_trusted",
                      [c.name for c in gate.checks if not c.ok])

    def test_verified_evidence_passes(self) -> None:
        gate = evaluate_role("backend", envelope("backend", "实现接口并通过编译与测试"),
                             project_dir=self.project, files=self.files,
                             tool_result=self._tool(), decision_store=None,
                             evidence_resolver=EvidenceResolver(self.ledger, KEY))
        self.assertEqual(gate.status, "pass", gate.to_dict())
        self.assertEqual(gate.trust, "verified")

    def test_evidence_for_other_subject_fails(self) -> None:
        gate = evaluate_role("backend", envelope("backend", "实现接口并通过编译与测试"),
                             project_dir=self.project, files=self.files,
                             tool_result=self._tool(subject="subject-b"),
                             decision_store=None,
                             evidence_resolver=EvidenceResolver(self.ledger, KEY))
        self.assertEqual(gate.status, "fail", gate.to_dict())
        self.assertTrue(any(e["code"] == "subject_mismatch"
                            for e in gate.evidence_errors))

    def test_legacy_unverified_is_explicit_only(self) -> None:
        gate = evaluate_role("backend", envelope("backend", "实现接口并通过编译与测试"),
                             project_dir=self.project, files=self.files,
                             tool_result=self._tool(), decision_store=None,
                             allow_legacy_unverified=True)
        self.assertEqual(gate.status, "pass", gate.to_dict())
        self.assertEqual(gate.trust, "legacy_unverified")
        self.assertTrue(gate.legacy)


class ArtifactProvenanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "docs" / "product").mkdir(parents=True)
        self.doc = self.project / "docs" / "product" / "product-baseline.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_empty_product_document_fails(self) -> None:
        self.doc.write_text("", encoding="utf-8")
        gate = evaluate_role(
            "product",
            envelope("product", "验收标准和非目标已经列出，当前可以继续后续流程。"),
            project_dir=self.project, files=[], decision_store=None)
        self.assertEqual(gate.status, "fail", gate.to_dict())
        self.assertIn("artifact", [c.name for c in gate.checks if not c.ok])

    def test_runner_summary_cannot_satisfy_delivery(self) -> None:
        self.doc.write_text(
            "# 产品基准\n\n内容不算正式交付，只是运行器补写。\n"
            "验收标准和非目标仍需模型产物与独立验证。\n", encoding="utf-8")
        gate = evaluate_role(
            "product",
            envelope("product", "验收标准和非目标已经列出，当前可以继续后续流程。"),
            project_dir=self.project, files=[],
            tool_result=None, decision_store=None)
        # Disk fallback is usable for legacy calls...
        self.assertEqual(gate.status, "pass", gate.to_dict())
        gate = evaluate_role(
            "product",
            envelope("product", "验收标准和非目标已经列出，当前可以继续后续流程。"),
            project_dir=self.project,
            files=[{"path": "docs/product/product-baseline.md",
                    "source": "runner-summary"}],
            decision_store=None)
        # ...but a declared runner-summary must not.
        self.assertEqual(gate.status, "fail", gate.to_dict())
        failed = {c.name for c in gate.checks if not c.ok}
        self.assertIn("artifact_provenance", failed)


if __name__ == "__main__":
    unittest.main()
