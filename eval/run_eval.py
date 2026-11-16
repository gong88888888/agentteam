#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W2 evaluation harness: judge golden set, canary, agent schema, revalidation.

Offline (default for CI):
  python eval/run_eval.py --offline

Real models (local Qwen 3.6; DeepSeek if configured):
  python eval/run_eval.py --real --allow-local-judge --limit 3

Exit code is non-zero on false approves, judge errors, canary miss > 10%,
revalidation violations, or (offline) agent schema failures.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.config import load_config, load_schema  # noqa: E402
from orchestrator.judge.backend import (ModelJudgeBackend,  # noqa: E402
                                        StubJudgeBackend, parse_json_object)
from orchestrator.judge.canary import run_canary  # noqa: E402
from orchestrator.judge.packet import build_packet, make_evidence  # noqa: E402
from orchestrator.judge.panel import JudgePanel  # noqa: E402
from orchestrator.judge.revalidation import RevalidationPlanner  # noqa: E402
from orchestrator.judge.rubric import load_rubric, rubric_for_gate  # noqa: E402
from orchestrator.models.router import ModelRouter  # noqa: E402
from orchestrator.skills import SkillRegistry  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def _load_yaml(name: str) -> list[dict[str, Any]]:
    with open(HERE / "golden" / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _packet_from_case(case: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for i, spec in enumerate(case.get("checks", []), 1):
        checks.append(make_evidence(
            spec["kind"],
            result=spec.get("result", "pass"),
            payload=spec.get("payload", {}),
            evidence_id=f"EV-{i:04d}",
            signed_by=spec.get("signed_by")))
    risk = case.get("risk", "high")
    return build_packet(
        gate_id=case["gate"],
        decision_type=case.get("decision_type", "gate"),
        scope={"project": "eval", "slice": "S2", "risk": risk},
        baseline_versions={"product": "v1.1", "arch": "v1.0"},
        baseline_fp=f"eval-{case['id']}",
        subject_hash=f"subject-{case['id']}",
        inputs=[{"path": "src/backend/s2/main.py",
                 "sha256": f"subject-{case['id']}", "signed_by": "tool:fs"}],
        checks=checks,
        missing_evidence=case.get("missing", []),
        acceptance=["AC-2"],
        diff={"out_of_scope_writes": case.get("out_of_scope", 0)},
        risk={"level": risk, "factors": case.get("factors", ["auth"])},
        claims=[{"claim": c, "signed_by": "agent:backend"}
                for c in case.get("claims", [])],
    )


def _run_judge_cases(panel: JudgePanel, limit: int | None) -> dict[str, Any]:
    cases = _load_yaml("judge_cases.yaml")
    if limit:
        cases = cases[:limit]
    rows = []
    passed = false_approve = false_reject = errors = 0
    for case in cases:
        packet = _packet_from_case(case)
        rubric = rubric_for_gate(case["gate"], case.get("decision_type", "gate"))
        expected = case["expected"]
        started = time.perf_counter()
        try:
            result = panel.decide(packet, rubric)
            actual = result.verdict["decision"]
            ok = actual in expected
            if ok:
                passed += 1
            if actual in ("approve", "approve_with_conditions") and "approve" not in expected \
                    and "approve_with_conditions" not in expected:
                false_approve += 1
            if actual not in ("approve", "approve_with_conditions") \
                    and ("approve" in expected or "approve_with_conditions" in expected):
                false_reject += 1
            rows.append({"id": case["id"], "expected": expected, "actual": actual,
                         "pass": ok, "trace": result.trace,
                         "latency_ms": int((time.perf_counter() - started) * 1000)})
        except Exception as exc:
            errors += 1
            rows.append({"id": case["id"], "expected": expected,
                         "actual": "error", "pass": False,
                         "error": str(exc),
                         "latency_ms": int((time.perf_counter() - started) * 1000)})
    total = len(cases)
    return {
        "total": total, "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0,
        "false_approve": false_approve, "false_reject": false_reject,
        "errors": errors, "rows": rows,
    }


def _agent_prompt(role: str, skills: SkillRegistry) -> str:
    specs = yaml.safe_load((ROOT / "specs" / "agent-specs.yaml").read_text(encoding="utf-8"))
    spec = next((s for s in specs["specs"] if s["id"] == role), None)
    if not spec:
        raise ValueError(f"未知角色：{role}")
    return (
        f"ROLE: {role}\n{spec['role']}\n\n"
        f"工具白名单：{json.dumps(spec['tools'], ensure_ascii=False)}\n"
        f"读写范围：{json.dumps(spec['scope'], ensure_ascii=False)}\n"
        f"禁止事项：{json.dumps(spec['prohibitions'], ensure_ascii=False)}\n"
        f"输出必须符合 specs/agent-output.schema.json，只能输出 JSON。\n"
        f"claims 不参与门禁；证据必须引用 evidence_refs。\n"
        f"artifacts 每项必须包含 path 和 sha256；没有真实产物时使用 []。\n"
        f"输出格式示例：{{\"task_id\":\"T-1\",\"role\":\"{role}\",\"status\":\"done\",\"artifacts\":[],\"claims\":[{{\"claim\":\"...\",\"counts_as_evidence\":false}}],\"evidence_refs\":[],\"open_questions\":[],\"summary\":\"...\"}}\n"
        f"{skills.prompt_context(role)}"
    )


def _run_agent_cases(router: ModelRouter, offline: bool,
                     limit: int | None) -> dict[str, Any]:
    cases = _load_yaml("agent_cases.yaml")
    if limit:
        cases = cases[:limit]
    schema = load_schema("agent-output.schema.json")
    skills = SkillRegistry.load(ROOT / "skills" / "registry.yaml")
    rows = []
    schema_pass = required_pass = errors = 0
    latency = tokens = 0
    for case in cases:
        messages = [{"role": "system", "content": _agent_prompt(case["role"], skills)},
                    {"role": "user", "content": case["task"]}]
        started = time.perf_counter()
        obj = None
        result = None
        last_exc: Exception | None = None
        for _attempt in range(2):
            try:
                result = router.execution(case["role"], messages, response_format="json")
                latency += result.latency_ms
                tokens += result.prompt_tokens + result.completion_tokens
                obj = parse_json_object(result.content)
                jsonschema.validate(obj, schema)
                break
            except Exception as exc:
                last_exc = exc
                obj = None
                messages += [
                    {"role": "assistant", "content": result.content if result else ""},
                    {"role": "user",
                     "content": f"输出不符合 agent-output schema：{exc}。只输出合法 JSON envelope。"},
                ]
        if obj is None:
            errors += 1
            rows.append({"id": case["id"], "role": case["role"],
                         "schema": False, "required": False,
                         "error": str(last_exc),
                         "latency_ms": int((time.perf_counter() - started) * 1000)})
        else:
            schema_pass += 1
            missing = [k for k in case.get("required", []) if k not in obj]
            has_claim = bool(obj.get("claims"))
            if not missing and has_claim and obj.get("role") == case["role"]:
                required_pass += 1
            rows.append({"id": case["id"], "role": case["role"],
                         "schema": True, "required": not missing and has_claim,
                         "missing": missing, "model": result.model if result else "",
                         "backend": result.backend if result else ""})
    total = len(cases)
    return {
        "total": total,
        "schema_pass": schema_pass,
        "schema_rate": round(schema_pass / total, 3) if total else 0,
        "required_pass": required_pass,
        "required_rate": round(required_pass / total, 3) if total else 0,
        "errors": errors,
        "latency_ms": latency,
        "tokens": tokens,
        "rows": rows,
    }


class _FakeRevalidationBackend:
    def __init__(self, case: dict[str, Any]) -> None:
        self.case = case

    def revalidate(self, plan: dict[str, Any], packet: dict[str, Any],
                   tier: str = "J3") -> dict[str, Any]:
        return {
            "decision": "expand_not_reduce",
            "base_plan_hash": ("bad-hash" if self.case.get("mismatch")
                               else plan["base_plan_hash"]),
            "added_checks": self.case.get("added", []),
            "removed_checks": self.case.get("removed", []),
            "rationale": "eval fake",
            "judge": {"backend": "fake", "model": "fake"},
        }


def _run_revalidation_cases() -> dict[str, Any]:
    cases = _load_yaml("revalidation_cases.yaml")
    rubric = load_rubric("revalidation")
    packet = build_packet(
        gate_id="G-CODE-S2", decision_type="gate",
        scope={"project": "eval", "slice": "S2", "risk": "high"},
        baseline_versions={"product": "v1.1"}, baseline_fp="eval-reval",
        subject_hash="subject-reval", inputs=[],
        checks=[make_evidence("unit", evidence_id="EV-0001")],
        missing_evidence=[], acceptance=[],
        diff={"out_of_scope_writes": 0},
        risk={"level": "high", "factors": ["auth", "migration"]},
        claims=[])
    rows = []
    passed = 0
    for case in cases:
        planner = RevalidationPlanner(_FakeRevalidationBackend(case))
        try:
            result = planner.review(
                base_checks=case["base"], mandatory_checks=case["mandatory"],
                packet=packet, rubric=rubric)
            ok = case["expected"] == "pass"
            rows.append({"id": case["id"], "expected": case["expected"],
                         "actual": "pass", "pass": ok,
                         "final_checks": result["final_checks"]})
            passed += 1 if ok else 0
        except Exception as exc:
            ok = case["expected"] == "fail"
            rows.append({"id": case["id"], "expected": case["expected"],
                         "actual": "fail", "pass": ok, "error": str(exc)})
            passed += 1 if ok else 0
    total = len(cases)
    return {"total": total, "passed": passed,
            "pass_rate": round(passed / total, 3) if total else 0, "rows": rows}


def run(*, offline: bool = True, allow_local_judge: bool = False,
        limit: int | None = None, config: str | None = None) -> int:
    cfg = load_config(config)
    router = ModelRouter(cfg, offline=offline)
    backend = (StubJudgeBackend() if offline
               else ModelJudgeBackend(router, allow_local=allow_local_judge))
    panel = JudgePanel(backend)
    judge = _run_judge_cases(panel, limit)
    canary = run_canary(backend, load_rubric("code-gate"),
                        max_cases=limit, panel=panel)
    agents = _run_agent_cases(router, offline, limit)
    revalidation = _run_revalidation_cases()
    metrics = {
        "mode": "offline" if offline else "real",
        "allow_local_judge": allow_local_judge,
        "judge": judge,
        "canary": canary,
        "agents": agents,
        "revalidation": revalidation,
        "models": router.summary(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# W2 Evaluation Report", "",
        f"- mode: **{metrics['mode']}**（allow_local_judge={allow_local_judge}）",
        f"- judge: {judge['passed']}/{judge['total']} passed，"
        f"false approve={judge['false_approve']}，false reject={judge['false_reject']}，"
        f"errors={judge['errors']}",
        f"- canary: {canary['caught']}/{canary['total']} caught，"
        f"miss={canary['miss_rate']:.0%}，conservative={canary['conservative']}",
        f"- agents: schema {agents['schema_pass']}/{agents['total']}，"
        f"required {agents['required_pass']}/{agents['total']}，"
        f"latency={agents['latency_ms']}ms，tokens={agents['tokens']}",
        f"- revalidation: {revalidation['passed']}/{revalidation['total']} passed",
        f"- models: {json.dumps(metrics['models'], ensure_ascii=False)}",
        "", "## Judge rows", "",
        *[f"- {r['id']}: expected={r['expected']} actual={r['actual']} "
          f"pass={r['pass']}" + (f" error={r.get('error')}" if r.get("error") else "")
          for r in judge["rows"]],
        "", "## Agent rows", "",
        *[f"- {r['id']}: schema={r['schema']} required={r['required']}"
          + (f" error={r.get('error')}" if r.get("error") else "")
          for r in agents["rows"]],
        "", "## Revalidation rows", "",
        *[f"- {r['id']}: expected={r['expected']} actual={r['actual']} "
          f"pass={r['pass']}" + (f" error={r.get('error')}" if r.get("error") else "")
          for r in revalidation["rows"]],
        "",
    ]
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "mode": metrics["mode"],
        "judge": {k: judge[k] for k in ("total", "passed", "false_approve",
                                         "false_reject", "errors")},
        "canary": {k: canary[k] for k in ("total", "caught", "miss_rate",
                                           "conservative")},
        "agents": {k: agents[k] for k in ("total", "schema_pass",
                                           "required_pass", "errors")},
        "revalidation": {k: revalidation[k] for k in ("total", "passed")},
        "models": metrics["models"],
        "report": str(OUT / "report.md"),
    }, ensure_ascii=False, indent=2))
    hard_fail = (judge["false_approve"] > 0 or judge["errors"] > 0
                 or revalidation["passed"] < revalidation["total"]
                 or canary["miss_rate"] > 0.10)
    if offline and (agents["schema_pass"] < agents["total"]
                    or agents["required_pass"] < agents["total"]):
        hard_fail = True
    if not offline and agents["schema_rate"] < 0.8:
        hard_fail = True
    return 1 if hard_fail else 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import argparse
    p = argparse.ArgumentParser(description="W2 evaluation")
    p.add_argument("--offline", action="store_true", default=True)
    p.add_argument("--real", action="store_true")
    p.add_argument("--allow-local-judge", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", default=None)
    args = p.parse_args(argv)
    offline = not args.real
    return run(offline=offline, allow_local_judge=args.allow_local_judge,
               limit=args.limit, config=args.config)


if __name__ == "__main__":
    raise SystemExit(main())
