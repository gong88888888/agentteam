"""Round 3 acceptance: manifest-driven DoD, web runtime acceptance, stage blocking."""
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

from orchestrator.acceptance_web import run_web_acceptance  # noqa: E402
from orchestrator.iterations import IterationManifest, ManifestItem  # noqa: E402
from orchestrator.process import definition_of_done  # noqa: E402
from orchestrator.project_runner import ProjectRunner  # noqa: E402


def role_state(run_id: str = "it-1", gate: str = "pass") -> dict:
    return {role: {"role": role, "status": "done", "run_id": run_id,
                   "gate": {"status": gate, "run_id": run_id}}
            for role in ("product", "backend", "qa")}


class ManifestDoDTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs" / "product").mkdir(parents=True)
        (self.root / "docs" / "product" / "product-baseline.md").write_text(
            "# 产品基准\n\n用户、范围、验收标准与非目标均已定义。\n", encoding="utf-8")
        (self.root / "src" / "backend").mkdir(parents=True)
        (self.root / "src" / "backend" / "app.py").write_text(
            "def main():\n    return 0\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_missing_committed_role_fails_even_if_existing_roles_pass(self) -> None:
        manifest = IterationManifest(
            project_id="p", iteration_id="it-1", project_type="web",
            profile="basic", delivery_kind="software", requires_entry=False,
            required_tasks=[ManifestItem("T-PRODUCT", "product", "product"),
                            ManifestItem("T-BACKEND", "backend", "implementation"),
                            ManifestItem("T-QA", "qa", "quality")],
            required_acceptance=[], required_docs=["docs/product/product-baseline.md"])
        state = {"product": role_state()["product"]}
        result = definition_of_done(self.root, "web", state, manifest=manifest)
        self.assertEqual(result["status"], "fail", result)
        failures = {c["name"] for c in result["checks"] if not c["ok"]}
        self.assertIn("required_roles", failures)

    def test_lightweight_documentation_iteration_passes(self) -> None:
        manifest = IterationManifest(
            project_id="p", iteration_id="it-1", project_type="web",
            profile="basic", delivery_kind="documentation", requires_entry=False,
            required_tasks=[ManifestItem("T-PRODUCT", "product", "product")],
            required_acceptance=[], required_docs=["docs/product/product-baseline.md"])
        state = {"product": role_state()["product"]}
        result = definition_of_done(self.root, "web", state, manifest=manifest)
        self.assertEqual(result["status"], "pass", result)

    def test_stale_gate_from_previous_iteration_fails(self) -> None:
        manifest = IterationManifest(
            project_id="p", iteration_id="it-2", project_type="web",
            profile="basic", delivery_kind="documentation", requires_entry=False,
            required_tasks=[ManifestItem("T-PRODUCT", "product", "product")],
            required_acceptance=[], required_docs=["docs/product/product-baseline.md"])
        state = {"product": role_state(run_id="it-1")["product"]}
        result = definition_of_done(self.root, "web", state, manifest=manifest)
        self.assertEqual(result["status"], "fail", result)
        self.assertIn("gate_current",
                      [c["name"] for c in result["checks"] if not c["ok"]])

    def test_web_acceptance_is_required(self) -> None:
        manifest = IterationManifest(
            project_id="p", iteration_id="it-1", project_type="web",
            profile="basic", delivery_kind="software", requires_entry=True,
            entry="src/backend/app.py",
            required_tasks=[ManifestItem("T-PRODUCT", "product", "product")],
            required_acceptance=["web_health", "web_flow"],
            required_docs=["docs/product/product-baseline.md"])
        state = {"product": role_state()["product"]}
        result = definition_of_done(self.root, "web", state, manifest=manifest,
                                    acceptance=None)
        self.assertEqual(result["status"], "fail", result)
        self.assertIn("acceptance",
                      [c["name"] for c in result["checks"] if not c["ok"]])

    def test_no_manifest_is_legacy_incomplete(self) -> None:
        result = definition_of_done(self.root, "web", role_state())
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result.get("legacy_incomplete"))


class WebAcceptanceTest(unittest.TestCase):
    def test_template_service_runs_health_and_business_flow(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "svc"
            shutil.copytree(ROOT / "templates" / "minimal-api", target)
            result = run_web_acceptance(target)
            self.assertEqual(result["status"], "pass", result)
            names = {c["name"] for c in result["checks"]}
            self.assertTrue({"web_start", "web_health"}.issubset(names))
            self.assertTrue(any(n.startswith("web_flow:") for n in names), names)
            self.assertGreaterEqual(len(result["evidence_ids"]), 3)

    def test_invalid_entry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "bad"
            (target / "src" / "backend").mkdir(parents=True)
            (target / "src" / "backend" / "app.py").write_text(
                "this is not valid python !!!\n", encoding="utf-8")
            (target / "acceptance.web-plan.json").write_text(json.dumps({
                "entry": "src/backend/app.py",
                "start_argv": ["{python}", "src/backend/app.py", "--port", "{port}"],
                "health": {"path": "/health"},
                "flow": [], "startup_timeout_s": 1,
            }), encoding="utf-8")
            result = run_web_acceptance(target)
            self.assertEqual(result["status"], "fail", result)
            self.assertFalse(result["checks"][0]["ok"])

    def test_health_passes_but_business_flow_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "flow"
            (target / "src" / "backend").mkdir(parents=True)
            (target / "src" / "backend" / "app.py").write_text(
                "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
                "import json\n"
                "class H(BaseHTTPRequestHandler):\n"
                "    def do_GET(self):\n"
                "        if self.path != '/health':\n"
                "            self.send_response(404)\n"
                "            self.end_headers()\n"
                "            return\n"
                "        body = json.dumps({'status': 'ok'}).encode()\n"
                "        self.send_response(200)\n"
                "        self.send_header('Content-Length', str(len(body)))\n"
                "        self.end_headers()\n"
                "        self.wfile.write(body)\n"
                "    def log_message(self, *a):\n"
                "        return\n"
                "import sys\n"
                "port = int(sys.argv[sys.argv.index('--port') + 1])\n"
                "HTTPServer(('127.0.0.1', port), H).serve_forever()\n",
                encoding="utf-8")
            (target / "acceptance.web-plan.json").write_text(json.dumps({
                "entry": "src/backend/app.py",
                "start_argv": ["{python}", "src/backend/app.py", "--port", "{port}"],
                "health": {"path": "/health", "expect_json": {"status": "ok"}},
                "flow": [{"name": "export", "path": "/missing",
                          "expect_status": 200}],
                "startup_timeout_s": 5,
            }), encoding="utf-8")
            result = run_web_acceptance(target)
            self.assertEqual(result["status"], "fail", result)
            flow = next(c for c in result["checks"]
                        if c["name"].startswith("web_flow:"))
            self.assertFalse(flow["ok"])

    def test_missing_flow_is_need_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "noflow"
            shutil.copytree(ROOT / "templates" / "minimal-api", target)
            plan = json.loads((target / "acceptance.web-plan.json").read_text(
                encoding="utf-8"))
            plan["flow"] = []
            (target / "acceptance.web-plan.json").write_text(
                json.dumps(plan), encoding="utf-8")
            result = run_web_acceptance(target)
            self.assertEqual(result["status"], "need_evidence", result)


class StageBlockingTest(unittest.TestCase):
    def test_formal_mode_skips_downstream_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# REQ\n月度 CSV 导出，验收 P95<2s。\n", encoding="utf-8")
            project = base / "proj"
            runner = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["backend", "ops"], template="none", tool_profile="basic",
                gates=True, decision_db=base / "decisions.db", mode="formal")
            result = runner.run()
            self.assertEqual(result["status"], "failed", result)
            self.assertEqual(result["roles"]["backend"], "blocked")
            self.assertEqual(result["roles"]["ops"], "skipped")
            state = json.loads((project / "state" / "roles.json").read_text(
                encoding="utf-8"))
            self.assertEqual(state["ops"]["status"], "skipped")

    def test_rehearsal_mode_continues_but_never_completes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req = base / "req.md"
            req.write_text("# REQ\n月度 CSV 导出，验收 P95<2s。\n", encoding="utf-8")
            project = base / "proj"
            runner = ProjectRunner(
                requirements=req, project_dir=project, offline=True,
                roles=["product", "backend"], template="minimal-api",
                tool_profile="basic", gates=True,
                decision_db=base / "decisions.db", mode="rehearsal",
                sandbox=True)
            result = runner.run()
            self.assertEqual(result["status"], "rehearsal", result)
            self.assertEqual(result["roles"]["backend"], "done")


if __name__ == "__main__":
    unittest.main()
