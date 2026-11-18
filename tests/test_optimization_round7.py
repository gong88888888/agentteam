"""Round 7 acceptance: findings, QA, iteration control, actions, impact, KB."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.actions import ActionStore  # noqa: E402
from orchestrator.evidence.resolver import EvidenceResolver  # noqa: E402
from orchestrator.evidence.store import EvidenceStore  # noqa: E402
from orchestrator.findings import FindingStore  # noqa: E402
from orchestrator.impact import TypedImpactGraph  # noqa: E402
from orchestrator.iterations import (IterationController,  # noqa: E402
                                     IterationManifest, ManifestItem)
from orchestrator.knowledge.authority import KnowledgeAuthority  # noqa: E402
from orchestrator.persistence import Database, TaskStore  # noqa: E402
from orchestrator.qa import IndependentVerifier, VerificationError  # noqa: E402

KEY = b"round7-key"


class BaseDB(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Database(self.root / "state" / "agentteam.db")
        self.db.migrate()
        self.store = TaskStore(self.db)
        self.store.ensure_project("p", "game")
        self.store.ensure_iteration("it-1", "p", budget={"max_tasks": 4})

    def tearDown(self) -> None:
        self.tmp.cleanup()


class FindingTest(BaseDB):
    def test_duplicate_feedback_does_not_create_competing_task(self) -> None:
        store = FindingStore(self.db)
        first = store.create(project_id="p", symptom="存档恢复后金币丢失",
                             category="implementation")
        second = store.create(project_id="p", symptom="存档恢复后金币丢失",
                              category="implementation")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["finding_id"], second["finding_id"])
        self.assertEqual(len(store.list(project_id="p")), 1)

    def test_requirement_gap_routes_to_product_not_backend(self) -> None:
        store = FindingStore(self.db)
        finding = store.create(project_id="p", symptom="需求漏掉普通成员权限",
                               category="requirement_gap")
        triaged = store.triage(finding["finding_id"], category="requirement_gap",
                               root_cause="表格限制未被提取")
        self.assertEqual(triaged["owner_role"], "product")
        task = store.create_repair_task(finding["finding_id"],
                                        task_store=self.store,
                                        iteration_id="it-1")
        self.assertEqual(task["role"], "product")
        self.assertEqual(store.get(finding["finding_id"])["status"], "in_progress")

    def test_close_requires_verification_or_explicit_reason(self) -> None:
        store = FindingStore(self.db)
        finding = store.create(project_id="p", symptom="UI 恢复状态缺失",
                               category="design_gap")
        with self.assertRaises(ValueError):
            store.close(finding["finding_id"])
        closed = store.close(finding["finding_id"],
                             verification_ref="VER-123", reason="QA 复验通过")
        self.assertEqual(closed["status"], "closed")

    def test_same_symptom_different_category_is_distinct(self) -> None:
        store = FindingStore(self.db)
        a = store.create(project_id="p", symptom="导出失败",
                         category="implementation")
        b = store.create(project_id="p", symptom="导出失败",
                         category="environment")
        self.assertNotEqual(a["finding_id"], b["finding_id"])


class QATest(BaseDB):
    def _resolver(self) -> tuple[EvidenceResolver, EvidenceStore, str]:
        ledger = self.root / "evidence" / "tool-ledger.jsonl"
        store = EvidenceStore(ledger, KEY)
        rec = store.add(kind="game_flow", subject_hash="subject-1",
                        tool="node", tool_version="25", result="pass",
                        signed_by="tool:node", baseline_fp="project")
        return EvidenceResolver(ledger, KEY), store, rec["evidence_id"]

    def test_implementer_cannot_verify_own_change(self) -> None:
        verifier = IndependentVerifier(self.db)
        with self.assertRaises(VerificationError) as ctx:
            verifier.verify(project_id="p", acceptance_id="AC-1",
                            subject_hash="subject-1", status="pass",
                            verified_by="backend:dev")
        self.assertEqual(ctx.exception.code, "self_verification")

    def test_pass_requires_verified_current_evidence(self) -> None:
        verifier = IndependentVerifier(self.db)
        with self.assertRaises(VerificationError) as ctx:
            verifier.verify(project_id="p", acceptance_id="AC-1",
                            subject_hash="subject-1", status="pass",
                            verified_by="qa:alice")
        self.assertEqual(ctx.exception.code, "unverified_pass")
        resolver, _, evidence_id = self._resolver()
        with self.assertRaises(VerificationError):
            verifier.verify(project_id="p", acceptance_id="AC-1",
                            subject_hash="subject-2", status="pass",
                            verified_by="qa:alice", evidence_ids=[evidence_id],
                            resolver=resolver)
        record = verifier.verify(project_id="p", acceptance_id="AC-1",
                                 subject_hash="subject-1", status="pass",
                                 verified_by="qa:alice",
                                 evidence_ids=[evidence_id], resolver=resolver,
                                 environment="test", steps="run flow",
                                 expected="export rows", actual="rows")
        self.assertEqual(record["status"], "pass")
        self.assertEqual(record["evidence"], [evidence_id])

    def test_not_run_is_not_pass(self) -> None:
        verifier = IndependentVerifier(self.db)
        record = verifier.verify(project_id="p", acceptance_id="AC-2",
                                 subject_hash="subject-2", status="not_run",
                                 verified_by="qa:alice")
        self.assertEqual(record["status"], "not_run")
        finding = {"finding_id": "F-1", "subject_hash": "subject-2"}
        ok, reason = verifier.can_close_finding(finding, record["verification_id"])
        self.assertFalse(ok)
        self.assertIn("not_run", reason)


class ControllerTest(BaseDB):
    def _controller(self) -> IterationController:
        return IterationController(self.db, self.store, project_id="p",
                                   iteration_id="it-1")

    def test_pause_survives_and_resume_requires_actor(self) -> None:
        manifest = IterationManifest(
            project_id="p", iteration_id="it-1", project_type="game",
            profile="basic", delivery_kind="game-slice", requires_entry=True,
            required_tasks=[ManifestItem("T-BACKEND", "backend",
                                         "implementation")])
        controller = self._controller()
        controller.compile_plan(manifest)
        controller.pause("用户暂停")
        self.assertTrue(controller.is_paused())
        self.assertEqual(controller.project_state(), "paused")
        self.assertEqual(controller.next_ready(), [])
        with self.assertRaises(ValueError):
            controller.resume(actor="")
        controller.resume(actor="user:owner")
        self.assertFalse(controller.is_paused())
        self.assertEqual(len(controller.next_ready()), 1)

    def test_budget_stops_dispatch(self) -> None:
        with self.db.transaction() as con:
            con.execute("UPDATE iterations SET budget_json=? WHERE iteration_id=?",
                        ('{"max_tasks": 1}', "it-1"))
        self.store.create_task(task_id="T-1", project_id="p",
                               iteration_id="it-1", role="backend")
        controller = self._controller()
        self.assertEqual(controller.budget_exhausted(), "max_tasks")
        self.assertEqual(controller.next_ready(), [])

    def test_verification_backlog_stops_new_implementation(self) -> None:
        self.store.create_task(task_id="T-1", project_id="p",
                               iteration_id="it-1", role="backend",
                               status="awaiting_verification")
        self.store.create_task(task_id="T-2", project_id="p",
                               iteration_id="it-1", role="frontend",
                               status="awaiting_verification")
        controller = self._controller()
        ok, reason = controller.can_dispatch("implementation",
                                             verification_limit=2)
        self.assertFalse(ok)
        self.assertEqual(reason, "verification_backlog")


class ActionTest(BaseDB):
    def test_vague_advice_stays_candidate(self) -> None:
        store = ActionStore(self.db)
        action = store.submit(project_id="p", root_cause="需求遗漏",
                              owner_role="product", target_iteration="it-2",
                              deliverable="以后注意", verification="注意完整性")
        self.assertFalse(action["queued"])
        self.assertEqual(action["status"], "candidate")
        self.assertEqual(action["task_id"], "")

    def test_concrete_action_creates_task_and_verifies(self) -> None:
        store = ActionStore(self.db)
        action = store.submit(
            project_id="p", root_cause="表格否定条件被漏读",
            owner_role="product", target_iteration="it-2",
            deliverable="新增表格否定条件来源处置样本",
            verification="新协议能发现该条款且旧反例不再通过",
            task_store=self.store, iteration_id="it-1")
        self.assertTrue(action["queued"])
        self.assertTrue(action["task_id"])
        with self.assertRaises(ValueError):
            store.verify(action["action_id"], passed=True,
                         evidence_ref="run-1", task_store=self.store)
        handle = self.store.claim(action["task_id"], "worker", lease_s=60)
        self.store.complete(action["task_id"], "worker",
                            expected_version=handle["attempt_version"])
        verified = store.verify(action["action_id"], passed=True,
                                evidence_ref="run-1", task_store=self.store)
        self.assertEqual(verified["status"], "verified")

    def test_overdue_action_is_reported(self) -> None:
        store = ActionStore(self.db)
        store.submit(project_id="p", root_cause="x", owner_role="qa",
                     target_iteration="it-1",
                     deliverable="新增遗漏反例回归", verification="反例通过")
        self.assertEqual(len(store.overdue("it-2")), 1)


class KnowledgeAuthorityTest(BaseDB):
    def test_candidate_is_not_returned_by_default(self) -> None:
        kb = KnowledgeAuthority(self.db)
        kb.add(project_id="p", title="存档必须双备份", body="主备写入并校验",
               authority="experience")
        self.assertEqual(kb.search("存档"), [])
        entry = kb.add(project_id="p", title="存档必须双备份",
                       body="主备写入并校验", authority="experience")
        kb.review(entry["entry_id"], reviewer="qa:alice",
                  evidence_ref="run-1")
        kb.activate(entry["entry_id"], actor="user:owner")
        hits = kb.search("存档")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["authority"], "experience")

    def test_revoked_entry_is_not_retrieved(self) -> None:
        kb = KnowledgeAuthority(self.db)
        entry = kb.add(project_id="p", title="必须使用全局 store",
                       body="所有前端状态放全局", authority="requirement",
                       approve=True)
        self.assertEqual(len(kb.search("全局")), 1)
        kb.revoke(entry["entry_id"], reason="与当前架构冲突")
        self.assertEqual(kb.search("全局"), [])

    def test_contract_outranks_experience(self) -> None:
        kb = KnowledgeAuthority(self.db)
        kb.add(project_id="p", title="契约：存档版本 3", body="冻结接口",
               authority="contract", approve=True)
        experience = kb.add(project_id="p", title="经验：存档版本 2",
                            body="旧经验", authority="experience")
        kb.review(experience["entry_id"], reviewer="qa", evidence_ref="run")
        kb.activate(experience["entry_id"], actor="owner")
        hits = kb.search("存档")
        self.assertEqual(hits[0]["authority"], "contract")


class ImpactGraphTest(unittest.TestCase):
    def _graph(self) -> TypedImpactGraph:
        graph = TypedImpactGraph()
        graph.add_node("REQ-SAVE", "requirement")
        graph.add_node("SCN-SAVE", "scenario")
        graph.add_node("UI-SAVE", "design")
        graph.add_node("API-SAVE", "contract")
        graph.add_node("CODE-SAVE", "code")
        graph.add_node("TEST-SAVE", "test")
        graph.add_node("DOC-OTHER", "document")
        graph.add_edge("SCN-SAVE", "REQ-SAVE", "scenario_satisfies_requirement")
        graph.add_edge("UI-SAVE", "SCN-SAVE", "design_realizes_scenario")
        graph.add_edge("API-SAVE", "UI-SAVE", "depends_on")
        graph.add_edge("CODE-SAVE", "API-SAVE", "code_implements_contract")
        graph.add_edge("TEST-SAVE", "CODE-SAVE", "test_checks_acceptance")
        return graph

    def test_change_reaches_design_code_and_test(self) -> None:
        result = self._graph().affected(["REQ-SAVE"])
        self.assertEqual(set(result["nodes"]),
                         {"REQ-SAVE", "SCN-SAVE", "UI-SAVE", "API-SAVE",
                          "CODE-SAVE", "TEST-SAVE"})
        self.assertNotIn("DOC-OTHER", result["nodes"])

    def test_unknown_relation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._graph().add_edge("a", "b", "vibes")

    def test_unknown_node_is_reported(self) -> None:
        graph = self._graph()
        graph.add_edge("UNKNOWN", "REQ-SAVE", "depends_on")
        result = graph.invalidate(["UNKNOWN"])
        self.assertIn("UNKNOWN", result["unknown"])
        self.assertTrue(result["limitations"])


if __name__ == "__main__":
    unittest.main()
