"""Round 6 acceptance: tasks/attempts/leases, outbox, artifacts, tool loop."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.execution import (ToolBudget, ToolRegistry,  # noqa: E402
                                    ToolLoopResult, run_tool_loop)
from orchestrator.models.base import ChatResult  # noqa: E402
from orchestrator.persistence import (Database, EventOutbox,  # noqa: E402
                                      TaskConflict, TaskStore)
from orchestrator.project_runner import ProjectRunner  # noqa: E402


class TaskLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "state" / "tasks.db")
        self.db.migrate()
        self.store = TaskStore(self.db)
        self.store.ensure_project("p", "web")
        self.store.ensure_iteration("it-1", "p")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _task(self, task_id: str = "T-1") -> dict:
        return self.store.create_task(
            task_id=task_id, project_id="p", iteration_id="it-1",
            role="backend", stage="implementation")

    def test_claim_complete_happy_path(self) -> None:
        self._task()
        handle = self.store.claim("T-1", "worker-a", lease_s=60, now=100)
        self.assertEqual(handle["status"], "running")
        self.assertEqual(handle["attempt_version"], 1)
        done = self.store.complete("T-1", "worker-a", expected_version=1, now=101)
        self.assertEqual(done["status"], "completed")
        attempts = self.store.attempts("T-1")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["status"], "completed")

    def test_second_worker_cannot_claim_running_task(self) -> None:
        self._task()
        self.store.claim("T-1", "worker-a", lease_s=60, now=100)
        with self.assertRaises(TaskConflict) as ctx:
            self.store.claim("T-1", "worker-b", lease_s=60, now=101)
        self.assertEqual(ctx.exception.code, "not_ready")

    def test_expired_worker_cannot_complete(self) -> None:
        self._task()
        old = self.store.claim("T-1", "worker-a", lease_s=1, now=100)
        recovered = self.store.recover_expired(now=200)
        self.assertEqual(recovered[0]["task_id"], "T-1")
        self.assertEqual(self.store.get("T-1")["status"], "recovering")
        new = self.store.claim("T-1", "worker-b", lease_s=60, now=201)
        self.assertEqual(new["lease_owner"], "worker-b")
        with self.assertRaises(TaskConflict) as ctx:
            self.store.complete("T-1", "worker-a",
                                expected_version=old["attempt_version"], now=202)
        self.assertIn(ctx.exception.code, ("not_running", "not_owner",
                                           "version_conflict"))
        self.store.complete("T-1", "worker-b",
                            expected_version=new["attempt_version"], now=203)
        attempts = self.store.attempts("T-1")
        self.assertEqual([a["status"] for a in attempts], ["orphaned", "completed"])

    def test_version_conflict_is_rejected(self) -> None:
        self._task()
        self.store.claim("T-1", "worker-a", lease_s=60, now=100)
        with self.assertRaises(TaskConflict) as ctx:
            self.store.complete("T-1", "worker-a", expected_version=99, now=101)
        self.assertEqual(ctx.exception.code, "version_conflict")

    def test_heartbeat_keeps_lease_alive(self) -> None:
        self._task()
        self.store.claim("T-1", "worker-a", lease_s=1, now=100)
        self.store.heartbeat("T-1", "worker-a", lease_s=60, now=101)
        self.assertEqual(self.store.recover_expired(now=150), [])
        self.assertEqual(self.store.get("T-1")["status"], "running")

    def test_requeue_after_recovery(self) -> None:
        self._task()
        self.store.claim("T-1", "worker-a", lease_s=1, now=100)
        self.store.recover_expired(now=102)
        task = self.store.requeue("T-1", "retry after orphan", now=103)
        self.assertEqual(task["status"], "ready")


class OutboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "state" / "tasks.db")
        self.db.migrate()
        self.store = TaskStore(self.db)
        self.store.ensure_project("p", "web")
        self.store.ensure_iteration("it-1", "p")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_dispatch_is_idempotent(self) -> None:
        self.store.create_task(task_id="T-1", project_id="p",
                               iteration_id="it-1", role="backend")
        self.store.claim("T-1", "w", lease_s=60)
        self.store.complete("T-1", "w", expected_version=1)
        seen: list[str] = []

        def handler(event: dict) -> None:
            seen.append(event["event_type"])

        first = self.store.outbox.dispatch("consumer-1", handler)
        second = self.store.outbox.dispatch("consumer-1", handler)
        self.assertGreaterEqual(first["delivered"], 2)
        self.assertEqual(second["delivered"], 0)
        self.assertEqual(seen.count("task.completed"), 1)

    def test_handler_failure_keeps_event_pending(self) -> None:
        with self.db.transaction() as con:
            EventOutbox.emit(con, project_id="p", aggregate_id="x",
                             aggregate_version=1, event_type="feedback.created",
                             payload={"text": "bug"})
        result = self.store.outbox.dispatch(
            "consumer", lambda event: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertEqual(result["failed"], 1)
        self.assertEqual(self.store.outbox.counts()["pending"], 1)

    def test_artifact_registry(self) -> None:
        rec = self.store.record_artifact(path="src/a.py", content_hash="abc",
                                         project_id="p", task_id="T-1",
                                         attempt_id="A1")
        self.assertTrue(rec["artifact_id"].startswith("ART-"))
        self.assertEqual(self.store.counts()["artifacts"], 1)


class RunnerPersistenceTest(unittest.TestCase):
    def test_project_run_writes_tasks_attempts_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# REQ\n月度 CSV 导出，验收 P95<2s。\n", encoding="utf-8")
            project = base / "proj"
            runner = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["product", "backend"], template="minimal-api",
                tool_profile="basic", gates=True, sandbox=True,
                decision_db=base / "decisions.db")
            result = runner.run()
            self.assertIn(result["status"], ("completed", "partial", "failed"))
            db = Database(project / "state" / "agentteam.db")
            self.assertGreaterEqual(db.schema_version(), 1)
            store = TaskStore(db)
            tasks = store.list(iteration_id=runner.run_id)
            self.assertEqual(len(tasks), 2, tasks)
            self.assertTrue(all(t["status"] == "completed" for t in tasks), tasks)
            for task in tasks:
                self.assertEqual(len(store.attempts(task["task_id"])), 1)
            self.assertGreaterEqual(store.counts()["artifacts"], 2)
            project_meta = json.loads((project / "project.json").read_text(
                encoding="utf-8"))
            self.assertEqual(project_meta["persistence"]["completed"], 2)


class ToolLoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "service.py").write_text(
            "def add(a, b):\n    return a - b\n", encoding="utf-8")
        self.registry = ToolRegistry(
            self.root, write_scope=("src/",),
            check_runner=self._check)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _check(self, check_id: str, scope: str) -> dict:
        text = (self.root / "src" / "service.py").read_text(encoding="utf-8")
        ok = "return a + b" in text
        return {"check_id": check_id, "status": "pass" if ok else "fail",
                "evidence_id": "EV-TEST" if ok else "",
                "reason": "" if ok else "expected add to add"}

    @staticmethod
    def _tool_turn(name: str, args: dict, call_id: str = "c") -> ChatResult:
        return ChatResult(
            content="", backend="fake", model="fake", finish_reason="tool_calls",
            tool_calls=[{"id": call_id, "type": "function",
                         "function": {"name": name,
                                      "arguments": json.dumps(args)}}])

    @staticmethod
    def _text(text: str) -> ChatResult:
        return ChatResult(content=text, backend="fake", model="fake")

    def test_read_patch_check_submit(self) -> None:
        script = [
            self._tool_turn("read_file", {"path": "src/service.py"}, "c1"),
            self._tool_turn("run_check", {"check_id": "unit"}, "c2"),
            self._tool_turn("apply_patch", {
                "path": "src/service.py",
                "expected_hash": "",  # filled below by two-step script
                "old": "return a - b", "new": "return a + b"}, "c3"),
            self._tool_turn("run_check", {"check_id": "unit"}, "c4"),
            self._tool_turn("submit_result", {
                "status": "ready_for_verification",
                "summary": "修复 add 并复验"}, "c5"),
        ]
        # The first read returns the real hash; feed it into the patch turn.
        current_hash = __import__("hashlib").sha256(
            (self.root / "src" / "service.py").read_bytes()).hexdigest()
        script[2] = self._tool_turn("apply_patch", {
            "path": "src/service.py", "expected_hash": current_hash,
            "old": "return a - b", "new": "return a + b"}, "c3")

        def chat(messages, tools):
            return script.pop(0)

        result = run_tool_loop(chat, [{"role": "user", "content": "fix"}],
                               registry=self.registry, budget=ToolBudget(max_calls=10))
        self.assertEqual(result.status, "ready_for_verification", result.to_dict())
        self.assertEqual(len(result.trace), 5)
        self.assertTrue(result.trace[3]["success"], result.trace)
        self.assertIn("return a + b",
                      (self.root / "src" / "service.py").read_text(encoding="utf-8"))

    def test_model_text_without_submit_is_not_completion(self) -> None:
        def chat(messages, tools):
            return self._text("我已经完成了，全部测试通过。")

        result = run_tool_loop(chat, [{"role": "user", "content": "x"}],
                               registry=self.registry)
        self.assertEqual(result.status, "needs_submission")

    def test_budget_exhaustion_blocks(self) -> None:
        def chat(messages, tools):
            return self._tool_turn("read_file", {"path": "src/service.py"})

        result = run_tool_loop(chat, [{"role": "user", "content": "x"}],
                               registry=self.registry,
                               budget=ToolBudget(max_calls=2))
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.budget_exceeded, "max_tool_calls")

    def test_unknown_tool_and_path_traversal_are_observations(self) -> None:
        script = [
            self._tool_turn("delete_everything", {}, "c1"),
            self._tool_turn("read_file", {"path": "../outside.txt"}, "c2"),
            self._tool_turn("submit_result", {"status": "blocked",
                                              "summary": "工具边界拒绝"}, "c3"),
        ]
        result = run_tool_loop(lambda m, t: script.pop(0),
                               [{"role": "user", "content": "x"}],
                               registry=self.registry)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.trace[0]["error_type"], "unknown_tool")
        self.assertEqual(result.trace[1]["error_type"], "invalid_path")

    def test_hash_mismatch_and_write_scope(self) -> None:
        bad_hash = self.registry.execute("apply_patch", {
            "path": "src/service.py", "expected_hash": "deadbeef",
            "old": "x", "new": "y"})
        self.assertEqual(bad_hash["error_type"], "hash_mismatch")
        outside = self.registry.execute("apply_patch", {
            "path": "docs/a.md", "expected_hash": "",
            "old": "x", "new": "y"})
        self.assertEqual(outside["error_type"], "write_scope")


if __name__ == "__main__":
    unittest.main()
