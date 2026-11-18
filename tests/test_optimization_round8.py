"""Round 8 acceptance: capability probe, trust labels, failure-injection suite."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator import cli  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.execution import (capability_report,  # noqa: E402
                                    response_is_complete)
from orchestrator.models.base import ChatResult  # noqa: E402
from orchestrator.project_runner import ProjectRunner  # noqa: E402
from orchestrator.trust import project_trust  # noqa: E402


class CapabilityTest(unittest.TestCase):
    def test_offline_report_is_simulation_and_contract_passes(self) -> None:
        report = capability_report(load_config(), offline=True)
        self.assertTrue(report["identity"]["simulation"])
        self.assertEqual(report["offline_contract"]["status"], "pass",
                         report["offline_contract"])
        self.assertEqual(report["real_probe"]["status"], "not_run")
        self.assertIn("execution", report["identity"]["tiers"])

    def test_real_probe_is_skipped_without_explicit_opt_in(self) -> None:
        from orchestrator.execution.capabilities import real_probe
        from orchestrator.models.router import ModelRouter
        cfg = {"models": {"routing": {"product": {"primary": "local"}},
                          "local": {}, "deepseek": {}}}
        report = real_probe(ModelRouter(cfg, offline=False), allow_network=False)
        self.assertEqual(report["status"], "skipped")

    def test_response_completeness_rules(self) -> None:
        self.assertTrue(response_is_complete(
            ChatResult(content="ok", backend="x", model="x")))
        self.assertTrue(response_is_complete(
            ChatResult(content="", backend="x", model="x",
                       tool_calls=[{"id": "c1"}], finish_reason="tool_calls")))
        self.assertFalse(response_is_complete(
            ChatResult(content="partial", backend="x", model="x",
                       finish_reason="length")))
        self.assertFalse(response_is_complete(
            ChatResult(content="", backend="x", model="x")))

    def test_cli_command(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.main(["model-capabilities", "--offline"])
        self.assertEqual(code, 0)
        data = json.loads(buffer.getvalue())
        self.assertEqual(data["offline_contract"]["status"], "pass")


class TrustTest(unittest.TestCase):
    def test_legacy_project_has_no_manifest(self) -> None:
        self.assertEqual(project_trust({"manifest": None}), "legacy_unverified")

    def test_rehearsal_is_not_current(self) -> None:
        project = {"manifest": {"iteration_id": "it"}, "mode": "rehearsal",
                   "dod": {"status": "pass"}, "acceptance": {"status": "pass"}}
        self.assertEqual(project_trust(project), "rehearsal")

    def test_current_verified_requires_dod_and_acceptance(self) -> None:
        project = {"manifest": {"iteration_id": "it"}, "mode": "formal",
                   "dod": {"status": "pass"}, "acceptance": {"status": "pass"}}
        self.assertEqual(project_trust(project), "current_verified")
        project["acceptance"] = {"status": "fail"}
        self.assertEqual(project_trust(project), "incomplete")

    def test_real_run_records_trust_and_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# REQ\n月度 CSV 导出，验收 P95<2s。\n", encoding="utf-8")
            project = base / "proj"
            runner = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["product", "backend"], template="minimal-api",
                tool_profile="basic", gates=True,
                decision_db=base / "decisions.db")
            runner.run()
            meta = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["trust"], "current_verified", meta.get("dod"))
            self.assertTrue(meta["model_calls"])
            self.assertIn("finish_reason", meta["model_calls"][0])
            self.assertEqual(meta["manifest"]["schema_version"], "1.0")

    def test_single_role_rerun_does_not_complete_the_project(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# REQ\n月度 CSV 导出，验收 P95<2s。\n", encoding="utf-8")
            project = base / "proj"
            ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["product", "backend"], template="minimal-api",
                tool_profile="basic", gates=True,
                decision_db=base / "decisions.db").run()
            partial = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["product"], merge_state=True,
                scope_roles=["product", "backend"], partial_run=True,
                template="minimal-api", tool_profile="basic", gates=True,
                decision_db=base / "decisions.db").run()
            self.assertEqual(partial["status"], "partial_rerun", partial)
            self.assertEqual(partial["roles"]["product"], "done")
            meta = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "partial_rerun")
            self.assertEqual(meta["trust"], "incomplete")
            self.assertEqual(len(meta["manifest"]["required_tasks"]), 2)


class FailureSuiteTest(unittest.TestCase):
    def test_all_injection_cases_fail_closed(self) -> None:
        from eval.failure_injection import run
        report = run()
        self.assertEqual(report["failed"], 0,
                         [c for c in report["cases"] if not c["ok"]])
        self.assertEqual(report["total"], 20)


class JudgeGateTest(unittest.TestCase):
    class FakePanel:
        def __init__(self, decision: str, explode: bool = False) -> None:
            self.decision = decision
            self.explode = explode
            self.calls = 0

        def decide(self, packet, rubric):
            self.calls += 1
            if self.explode:
                raise RuntimeError("judge unavailable")
            return type("Result", (), {
                "verdict": {"decision": self.decision},
                "trace": [{"tier": "stub", "decision": self.decision}],
            })()

    def _runner(self, base: Path, *, judge: bool = True,
                template: str = "minimal-api") -> ProjectRunner:
        req = base / "req.md"
        req.write_text("# REQ\n月度 CSV 导出，验收 P95<2s。\n", encoding="utf-8")
        return ProjectRunner(
            requirements=req, project_dir=base / "proj", offline=True,
            roles=["backend"], template=template, tool_profile="basic",
            gates=True, decision_db=base / "decisions.db",
            judge_gate=judge)

    def test_offline_judge_approves_high_risk_role(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runner = self._runner(Path(td))
            result = runner.run()
            self.assertEqual(result["status"], "completed", result)
            state = json.loads((runner.project_dir / "state" / "roles.json")
                               .read_text(encoding="utf-8"))
            self.assertTrue(state["backend"]["judge"]["approved"])
            self.assertEqual(state["backend"]["judge"]["decision"], "approve")

    def test_judge_rejection_blocks_role(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runner = self._runner(Path(td))
            runner.prepare()
            panel = self.FakePanel("reject")
            runner.judge_panel = panel
            result = runner.run()
            self.assertEqual(panel.calls, 1)
            self.assertEqual(result["roles"]["backend"], "blocked", result)
            self.assertNotEqual(result["status"], "completed")
            state = json.loads((runner.project_dir / "state" / "roles.json")
                               .read_text(encoding="utf-8"))
            self.assertFalse(state["backend"]["judge"]["approved"])

    def test_judge_unavailable_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runner = self._runner(Path(td))
            runner.prepare()
            runner.judge_panel = self.FakePanel("approve", explode=True)
            result = runner.run()
            self.assertEqual(result["roles"]["backend"], "blocked")
            state = json.loads((runner.project_dir / "state" / "roles.json")
                               .read_text(encoding="utf-8"))
            self.assertEqual(state["backend"]["judge"]["decision"], "unavailable")

    def test_deterministic_failure_never_reaches_judge(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runner = self._runner(Path(td), template="none")
            runner.prepare()
            panel = self.FakePanel("approve")
            runner.judge_panel = panel
            result = runner.run()
            self.assertEqual(panel.calls, 0)
            self.assertEqual(result["roles"]["backend"], "blocked")


class DomainFeedbackTest(unittest.TestCase):
    def test_gate_failure_creates_routed_finding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# REQ\n月度 CSV 导出。\n", encoding="utf-8")
            project = base / "proj"
            runner = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["backend"], template="none", tool_profile="basic",
                gates=True, decision_db=base / "decisions.db")
            runner.run()
            from orchestrator.findings import FindingStore
            from orchestrator.persistence import Database
            store = FindingStore(Database(project / "state" / "agentteam.db"))
            findings = store.list(project_id="proj")
            self.assertEqual(len(findings), 1, findings)
            self.assertEqual(findings[0]["category"], "verification_gap")
            self.assertEqual(findings[0]["owner_role"], "qa")
            self.assertEqual(findings[0]["status"], "triaged")

    def test_domain_events_are_exported_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# REQ\n月度 CSV 导出。\n", encoding="utf-8")
            project = base / "proj"
            runner = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["product", "backend"], template="minimal-api",
                tool_profile="basic", gates=True,
                decision_db=base / "decisions.db")
            runner.run()
            path = project / "state" / "domain-events.json"
            self.assertTrue(path.is_file())
            data = json.loads(path.read_text(encoding="utf-8"))
            types = {e["event_type"] for e in data["events"]}
            self.assertIn("task.completed", types)
            self.assertIn("iteration.completed", types)
            before = len(data["events"])
            runner.ledger.export_domain_events()
            after = len(json.loads(path.read_text(encoding="utf-8"))["events"])
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
