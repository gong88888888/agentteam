#!/usr/bin/env python3
"""Deterministic failure-injection acceptance suite.

Each case injects one known defect condition and checks that the system refuses
to report success. This is evidence about fail-closed behavior, not a model
capability benchmark.

  python eval/failure_injection.py
  python eval/failure_injection.py --json eval/out/failure-injection.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.acceptance_web import run_web_acceptance
from orchestrator.actions import ActionStore
from orchestrator.evidence.resolver import EvidenceResolutionError, EvidenceResolver
from orchestrator.evidence.store import EvidenceStore
from orchestrator.execution import ToolBudget, ToolRegistry, run_tool_loop
from orchestrator.findings import FindingStore
from orchestrator.game_check import integration_report
from orchestrator.iterations import IterationManifest, ManifestItem
from orchestrator.models.base import ChatResult, ConfigurationError
from orchestrator.models.router import ModelRouter
from orchestrator.persistence import Database, TaskConflict, TaskStore
from orchestrator.process import definition_of_done
from orchestrator.product_review import (ROLE_MAP, ProductReviewRunner,
                                         _normalize)
from orchestrator.qa import IndependentVerifier, VerificationError
from orchestrator.requirements_ledger import SourceDisposition
from orchestrator.role_gates import evaluate_role
from orchestrator.sandbox import Sandbox
from orchestrator.sources import parse_markdown
from orchestrator.tool_evidence import collect

DOC = "# 产品\n## 目标\n单人通关。\n## 验收\n存档可恢复。\n"


def envelope(role: str, summary: str) -> dict:
    return {"task_id": "t", "role": role, "status": "done", "artifacts": [],
            "claims": [{"claim": summary, "counts_as_evidence": False}],
            "evidence_refs": [], "open_questions": [], "summary": summary}


class Case:
    def __init__(self, case_id: str, expected: str) -> None:
        self.id = case_id
        self.expected = expected
        self.started = time.time()

    def result(self, ok: bool, actual: str) -> dict:
        return {"id": self.id, "expected": self.expected, "actual": actual,
                "ok": bool(ok), "elapsed_ms": int((time.time() - self.started) * 1000)}


def case_invalid_source(tmp: Path) -> dict:
    c = Case("FI-01-invalid-source", "reject")
    doc = parse_markdown(DOC)
    ledger = __import__("orchestrator.requirements_ledger", fromlist=["RequirementLedger"]) \
        .RequirementLedger(doc_id="D", requirements=[], dispositions=[])
    from orchestrator.requirements_ledger import RequirementCandidate
    ledger.requirements.append(RequirementCandidate(
        "REQ-1", "单人通关", ["SU-DOES-NOT-EXIST"], "functional", "可通关"))
    errors = ledger.validate(u.unit_id for u in doc.units)
    return c.result("unknown_source" in {e["code"] for e in errors},
                    "unknown_source")


def case_coverage_pollution(tmp: Path) -> dict:
    c = Case("FI-02-coverage-pollution", "coverage==0")
    doc = tmp / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    runner = ProductReviewRunner(doc=doc, out_dir=tmp / "review", offline=True,
                                 roles=["product-lead"])

    def empty(role, messages, *, response_format=None):
        refs = [s["id"] for s in runner.sections]
        obj = {"task_id": "t", "role": role, "status": "done",
               "source_sections": refs, "findings": [],
               "coverage": {"total_sections": len(refs),
                            "covered_sections": len(refs), "percent": 100},
               "files": [], "summary": "目标 成功指标 非目标 决策 " + " ".join(refs),
               "open_questions": []}
        return ChatResult(content=json.dumps(obj, ensure_ascii=False),
                          backend="fake", model="fake")

    runner.router.execution = empty
    result = runner.run()
    return c.result(result["coverage"] == 0 and result["status"] == "fail",
                   f"coverage={result['coverage']}, status={result['status']}")


def case_blocked_review(tmp: Path) -> dict:
    c = Case("FI-03-blocked-review", "fail")
    doc = tmp / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    runner = ProductReviewRunner(doc=doc, out_dir=tmp / "review", offline=True)
    runner.prepare()
    rel = "docs/product-review/01-document-map.md"
    (runner.out_dir / rel).write_text("来源 主张 歧义 覆盖 SRC-001", encoding="utf-8")
    gate = runner.gate(ROLE_MAP["doc-analyst"],
                       {"status": "blocked", "summary": "来源 覆盖 SRC-001"},
                       [{"path": rel}], 1.0)
    return c.result(gate["status"] == "fail", gate["status"])


def case_stale_gate(tmp: Path) -> dict:
    c = Case("FI-04-stale-gate", "fail")
    doc = tmp / "doc.md"
    doc.write_text(DOC, encoding="utf-8")
    out = tmp / "review"
    first = ProductReviewRunner(doc=doc, out_dir=out, offline=True).run()
    doc.write_text("# 改版\n## 新要求\n旧验收作废。\n", encoding="utf-8")
    second = ProductReviewRunner(doc=doc, out_dir=out, offline=True,
                                 roles=["product-lead"])

    def fail(*args, **kwargs):
        raise RuntimeError("injected failure")

    second.router.execution = fail
    result = second.run()
    return c.result(first["status"] == "pass" and result["status"] == "fail"
                    and result["gates"]["doc-analyst"] == "stale",
                    f"old={first['status']}, new={result['status']}")


def case_empty_artifact(tmp: Path) -> dict:
    c = Case("FI-05-empty-artifact", "fail")
    (tmp / "docs" / "product").mkdir(parents=True)
    (tmp / "docs" / "product" / "product-baseline.md").write_text("", encoding="utf-8")
    gate = evaluate_role("product",
                         envelope("product", "验收标准和非目标已经列出，可以继续。"),
                         project_dir=tmp, files=[])
    return c.result(gate.status == "fail", gate.status)


def case_runner_summary(tmp: Path) -> dict:
    c = Case("FI-06-runner-summary", "fail")
    (tmp / "docs" / "product").mkdir(parents=True)
    (tmp / "docs" / "product" / "product-baseline.md").write_text(
        "# 产品\n\n运行器补写内容，不是模型专业产物，需要重新生成。\n",
        encoding="utf-8")
    gate = evaluate_role(
        "product", envelope("product", "验收标准和非目标已经列出，可以继续。"),
        project_dir=tmp,
        files=[{"path": "docs/product/product-baseline.md",
                "source": "runner-summary"}])
    return c.result(gate.status == "fail", gate.status)


def case_web_invalid_entry(tmp: Path) -> dict:
    c = Case("FI-07-web-invalid-entry", "fail")
    (tmp / "src" / "backend").mkdir(parents=True)
    (tmp / "src" / "backend" / "app.py").write_text("not python !!!\n", encoding="utf-8")
    (tmp / "acceptance.web-plan.json").write_text(json.dumps({
        "entry": "src/backend/app.py",
        "start_argv": ["{python}", "src/backend/app.py", "--port", "{port}"],
        "health": {"path": "/health"}, "flow": [], "startup_timeout_s": 1,
    }), encoding="utf-8")
    result = run_web_acceptance(tmp)
    return c.result(result["status"] == "fail", result["status"])


def case_web_flow_failure(tmp: Path) -> dict:
    c = Case("FI-08-web-flow-failure", "fail")
    shutil.copytree(ROOT / "templates" / "minimal-api", tmp / "svc")
    target = tmp / "svc"
    plan = json.loads((target / "acceptance.web-plan.json").read_text(encoding="utf-8"))
    plan["flow"] = [{"name": "missing", "path": "/api/v1/exports/csv?month=1999-01",
                     "expect_contains": "does-not-exist"}]
    (target / "acceptance.web-plan.json").write_text(json.dumps(plan),
                                                     encoding="utf-8")
    result = run_web_acceptance(target)
    return c.result(result["status"] == "fail", result["status"])


def case_game_unregistered(tmp: Path) -> dict:
    c = Case("FI-09-game-unregistered-module", "fail")
    target = tmp / "game"
    shutil.copytree(ROOT / "templates" / "web-2d-game", target)
    (target / "game" / "js" / "gameplay" / "extra.js").write_text(
        "export function unused() { return 1; }\n", encoding="utf-8")
    report = integration_report(target, Sandbox(target / "game", timeout_s=60))
    return c.result(not report["ok"], f"unreachable={len(report['unreachable'])}")


def case_unknown_backend(tmp: Path) -> dict:
    c = Case("FI-10-unknown-backend", "ConfigurationError")
    try:
        ModelRouter({"models": {"routing": {"backend": {"primary": "deapseek"}}}},
                    offline=False)
        return c.result(False, "no error")
    except ConfigurationError:
        return c.result(True, "ConfigurationError")


def case_forged_evidence(tmp: Path) -> dict:
    c = Case("FI-11-forged-evidence", "need_evidence")
    (tmp / "src" / "backend").mkdir(parents=True)
    (tmp / "src" / "backend" / "app.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8")
    gate = evaluate_role("backend",
                         envelope("backend", "实现接口并通过编译与测试"),
                         project_dir=tmp,
                         files=[{"path": "src/backend/app.py", "source": "role"}],
                         tool_result={"subject_hash": "s", "evidence": [
                             {"kind": "compile", "result": "pass",
                              "evidence_id": "FAKE1"},
                             {"kind": "unit", "result": "pass",
                              "evidence_id": "FAKE2"}]})
    return c.result(gate.status == "need_evidence", gate.status)


def case_expired_evidence(tmp: Path) -> dict:
    c = Case("FI-12-expired-evidence", "reject")
    ledger = tmp / "evidence" / "ledger.jsonl"
    store = EvidenceStore(ledger, b"fi-key")
    rec = store.add(kind="unit", subject_hash="s", tool="unittest",
                    tool_version="3", result="pass", signed_by="tool:unittest",
                    baseline_fp="project", ttl_s=1, now=1)
    try:
        EvidenceResolver(ledger, b"fi-key", now=1000).resolve(
            rec["evidence_id"], kind="unit", subject_hash="s")
        return c.result(False, "accepted expired evidence")
    except EvidenceResolutionError as exc:
        return c.result(exc.code == "expired_or_revoked", exc.code)


def case_zero_tests(tmp: Path) -> dict:
    c = Case("FI-13-zero-tests", "missing unit")
    (tmp / "src" / "backend").mkdir(parents=True)
    (tmp / "src" / "backend" / "app.py").write_text(
        "def ok():\n    return True\n", encoding="utf-8")
    result = collect(tmp, profile="basic")
    return c.result("unit" in [m["kind"] for m in result["missing"]],
                    str([m["kind"] for m in result["missing"]]))


def case_dod_missing_roles(tmp: Path) -> dict:
    c = Case("FI-14-dod-missing-role", "fail")
    (tmp / "docs" / "product").mkdir(parents=True)
    (tmp / "docs" / "product" / "product-baseline.md").write_text(
        "# 产品\n\n用户、范围、验收标准与非目标均已定义。\n", encoding="utf-8")
    manifest = IterationManifest(
        project_id="p", iteration_id="it", project_type="web",
        profile="basic", delivery_kind="documentation", requires_entry=False,
        required_tasks=[ManifestItem("T-P", "product", "product"),
                        ManifestItem("T-B", "backend", "implementation")],
        required_acceptance=[], required_docs=["docs/product/product-baseline.md"])
    state = {"product": {"role": "product", "status": "done", "run_id": "it",
                         "gate": {"status": "pass", "run_id": "it"}}}
    result = definition_of_done(tmp, "web", state, manifest=manifest)
    return c.result(result["status"] == "fail", result["status"])


def case_stale_iteration_gate(tmp: Path) -> dict:
    c = Case("FI-15-stale-iteration-gate", "fail")
    (tmp / "docs" / "product").mkdir(parents=True)
    (tmp / "docs" / "product" / "product-baseline.md").write_text(
        "# 产品\n\n用户、范围、验收标准与非目标均已定义。\n", encoding="utf-8")
    manifest = IterationManifest(
        project_id="p", iteration_id="it-2", project_type="web",
        profile="basic", delivery_kind="documentation", requires_entry=False,
        required_tasks=[ManifestItem("T-P", "product", "product")],
        required_acceptance=[], required_docs=["docs/product/product-baseline.md"])
    state = {"product": {"role": "product", "status": "done", "run_id": "it-1",
                         "gate": {"status": "pass", "run_id": "it-1"}}}
    result = definition_of_done(tmp, "web", state, manifest=manifest)
    return c.result(result["status"] == "fail", result["status"])


def case_duplicate_feedback(tmp: Path) -> dict:
    c = Case("FI-16-duplicate-feedback", "one finding")
    db = Database(tmp / "db.sqlite")
    db.migrate()
    store = FindingStore(db)
    a = store.create(project_id="p", symptom="存档恢复后金币丢失",
                     category="implementation")
    b = store.create(project_id="p", symptom="存档恢复后金币丢失",
                     category="implementation")
    return c.result(a["finding_id"] == b["finding_id"]
                    and len(store.list(project_id="p")) == 1,
                    f"{len(store.list(project_id='p'))} findings")


def case_vague_action(tmp: Path) -> dict:
    c = Case("FI-17-vague-action", "candidate")
    db = Database(tmp / "db.sqlite")
    db.migrate()
    action = ActionStore(db).submit(project_id="p", root_cause="需求遗漏",
                                    owner_role="product", target_iteration="it",
                                    deliverable="以后注意", verification="注意完整性")
    return c.result(not action["queued"] and action["status"] == "candidate",
                    action["status"])


def case_lease_expiry(tmp: Path) -> dict:
    c = Case("FI-18-stale-worker", "TaskConflict")
    db = Database(tmp / "db.sqlite")
    db.migrate()
    store = TaskStore(db)
    store.ensure_project("p", "web")
    store.ensure_iteration("it", "p")
    store.create_task(task_id="T", project_id="p", iteration_id="it",
                      role="backend")
    old = store.claim("T", "old", lease_s=1, now=10)
    store.recover_expired(now=20)
    new = store.claim("T", "new", lease_s=60, now=21)
    try:
        store.complete("T", "old", expected_version=old["attempt_version"], now=22)
        return c.result(False, "old accepted")
    except TaskConflict:
        store.complete("T", "new", expected_version=new["attempt_version"], now=23)
        return c.result(True, "old rejected, new accepted")


def case_budget_exhaustion(tmp: Path) -> dict:
    c = Case("FI-19-tool-budget", "blocked")
    (tmp / "src").mkdir()
    (tmp / "src" / "a.py").write_text("x=1\n", encoding="utf-8")

    def chat(messages, tools):
        return ChatResult(content="", backend="fake", model="fake",
                          finish_reason="tool_calls",
                          tool_calls=[{"id": "c", "type": "function",
                                       "function": {"name": "read_file",
                                                    "arguments": "{\"path\":\"src/a.py\"}"}}])

    registry = ToolRegistry(tmp, write_scope=("src/",))
    result = run_tool_loop(chat, [{"role": "user", "content": "x"}],
                           registry=registry, budget=ToolBudget(max_calls=2))
    return c.result(result.status == "blocked", result.status)


def case_self_verification(tmp: Path) -> dict:
    c = Case("FI-20-self-verification", "reject")
    db = Database(tmp / "db.sqlite")
    db.migrate()
    try:
        IndependentVerifier(db).verify(project_id="p", acceptance_id="AC",
                                       subject_hash="s", status="pass",
                                       verified_by="backend:dev")
        return c.result(False, "accepted")
    except VerificationError as exc:
        return c.result(exc.code == "self_verification", exc.code)


CASES = [case_invalid_source, case_coverage_pollution, case_blocked_review,
         case_stale_gate, case_empty_artifact, case_runner_summary,
         case_web_invalid_entry, case_web_flow_failure, case_game_unregistered,
         case_unknown_backend, case_forged_evidence, case_expired_evidence,
         case_zero_tests, case_dod_missing_roles, case_stale_iteration_gate,
         case_duplicate_feedback, case_vague_action, case_lease_expiry,
         case_budget_exhaustion, case_self_verification]


def run() -> dict:
    rows = []
    for fn in CASES:
        with tempfile.TemporaryDirectory(prefix="agentteam-fi-") as td:
            try:
                rows.append(fn(Path(td)))
            except Exception as exc:
                rows.append({"id": fn.__name__, "expected": "handled",
                             "actual": f"exception: {exc}", "ok": False})
    passed = sum(1 for row in rows if row["ok"])
    return {"suite": "failure-injection", "schema_version": "1.0",
            "total": len(rows), "passed": passed,
            "failed": len(rows) - passed,
            "cases": rows,
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--json", default="eval/out/failure-injection.json")
    args = p.parse_args(argv)
    report = run()
    target = Path(args.json)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps({"suite": report["suite"], "total": report["total"],
                      "passed": report["passed"], "failed": report["failed"],
                      "failed_cases": [c["id"] for c in report["cases"]
                                       if not c["ok"]],
                      "output": str(target)}, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
