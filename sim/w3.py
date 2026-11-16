#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W3 交付预演：3 切片并行、共享文件冲突、契约变更影响图、serial baseline。

运行：
  python sim/w3.py --mode both
  python sim/w3.py --mode parallel
  python sim/w3.py --mode serial

输出：
  sim/out/w3/parallel/{metrics.json,events.jsonl,timeline.md,auto-report.md,impact.json,w3-report.md}
  sim/out/w3/serial/...
  sim/out/w3/comparison.json / comparison.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dryrun as d  # noqa: E402
from orchestrator.impact import ContractImpactGraph  # noqa: E402

SLICES = ("S1", "S2", "S3")
AC = {"s1": "AC-1", "s2": "AC-2", "s3": "AC-3"}

# Contract regate judge plans (J1 approves; hard blocks still apply).
for sid in SLICES:
    d.JUDGE_PLAN.setdefault(f"H-W3-{sid}", [{
        "tier": "J1", "latency": 4, "verdict": "approve", "reason": "",
    }])


class W3Sim(d.Sim):
    def __init__(self, *, serial: bool = False) -> None:
        super().__init__()
        self.mode = "serial" if serial else "parallel"
        self.serial = serial
        self.out_dir = str(HERE / "out" / "w3" / self.mode)
        self.max_concurrency = 1 if serial else 4
        self.impact_graph = ContractImpactGraph()
        self.contract_changes = 0
        self.contract_impacted_tasks = 0
        self.contract_evidence_invalidated = 0

    # ---------- 业务扩展 ----------
    def produce(self, task: d.Task) -> None:
        tid = task.id
        if tid.startswith("shared_"):
            path = "package.json" if "pkg" in tid else "shared/ui-tokens.css"
            content = {"task": tid, "owner": task.role, "rev": "w3"}
            self.write_artifact(task, path, content, "v1.0")
            self.log("shared_file.written", task=tid, path=path)
            return
        if tid == "contract_change":
            art = self.write_artifact(
                task, "docs/architecture/接口契约.md",
                {"contracts": ["X1", "X2", "X3"], "x1_version": "v1.1",
                 "change": "auth owner-check contract revision"},
                "v1.1")
            self.log("contract.change", contract="X1", old="v1.0", new="v1.1",
                     artifact=art.content_hash)
            self.apply_contract_change()
            return
        if tid.endswith("_contract_fix"):
            sid = tid.split("_")[0]
            art = self.write_artifact(
                task, f"src/backend/{sid}/main.py",
                {"contract": "X1@v1.1", "owner_check": True, "task": tid},
                "v1.1")
            self._code_evidence(sid)
            self._review_evidence(sid)
            self._acceptance_evidence(sid, AC[sid])
            self.log("contract.fix.done", task=tid, slice=sid,
                     artifact=art.content_hash)
            return
        super().produce(task)

    def apply_contract_change(self) -> None:
        self.contract_changes += 1
        self.impact_graph.add_node("contract:X1", "contract", "X1 auth contract")
        impacted_tasks: list[str] = []
        total_invalidated = 0
        for sid in SLICES:
            old_subject = self.source_subject(sid)
            before = self.evidence_invalidated
            self.invalidate_subject(old_subject,
                                    f"契约 X1 v1.1 影响 {sid}，旧证据/裁决失效")
            invalidated = max(0, self.evidence_invalidated - before)
            total_invalidated += invalidated
            fix_id = f"{sid.lower()}_contract_fix"
            regate_id = f"{sid.lower()}_contract_regate"
            if fix_id not in self.tasks:
                self.add_task(d.Task(
                    fix_id, f"{sid} 契约变更返工（X1 v1.1）", "backend",
                    sid, ["contract_change"], 25, priority=1, risk="high"))
            if regate_id not in self.tasks:
                self.add_task(d.Task(
                    regate_id, f"{sid} 契约变更复评门禁", "pm", sid,
                    [fix_id], 10, priority=1, risk="high",
                    gate=sid.lower(), approval=f"H-W3-{sid}"))
            for dep_task in ("integration_qa", "security_scan"):
                t = self.tasks.get(dep_task)
                if t and regate_id not in t.deps:
                    t.deps.append(regate_id)
            # Pending slice QA must wait for the new regate, not the superseded gate.
            for qa_id in (f"{sid.lower()}_qa", f"{sid.lower()}_qa_retest"):
                qa = self.tasks.get(qa_id)
                if qa and qa.state in (d.PENDING, d.READY):
                    old_gate = f"{sid.lower()}_gate"
                    if old_gate in qa.deps:
                        qa.deps.remove(old_gate)
                    if regate_id not in qa.deps:
                        qa.deps.append(regate_id)
            # Any conditional group that referenced the old gate must also accept
            # the new regate (e.g. integration_qa, s2_serial_join).
            for t in self.tasks.values():
                for group in t.deps_any:
                    if regate_id == "s2_contract_regate" and (
                            "s2_gate" in group or "s2_regate" in group)                             and regate_id not in group:
                        group.append(regate_id)
            impacted_tasks.extend([fix_id, regate_id])
            self.impact_graph.add_node(f"slice:{sid}", "slice", sid)
            self.impact_graph.add_node(f"task:{fix_id}", "task", fix_id)
            self.impact_graph.add_node(f"task:{regate_id}", "task", regate_id)
            self.impact_graph.add_node(f"gate:{sid}", "gate", sid)
            self.impact_graph.add_edge("contract:X1", f"slice:{sid}", "impacts")
            self.impact_graph.add_edge(f"slice:{sid}", f"task:{fix_id}", "rework")
            self.impact_graph.add_edge(f"task:{fix_id}", f"task:{regate_id}", "verify")
            self.impact_graph.add_edge(f"task:{regate_id}", f"gate:{sid}", "regate")
            self.log("impact.computed", contract="X1", slice=sid,
                     old_subject=old_subject, invalidated=invalidated,
                     fix=fix_id, regate=regate_id)
        self.contract_impacted_tasks += len(impacted_tasks)
        self.contract_evidence_invalidated += total_invalidated
        self.impact_graph.record_change(
            contract="X1", from_version="v1.0", to_version="v1.1",
            slices=list(SLICES), tasks=impacted_tasks,
            invalidated=total_invalidated)
        self.log("impact.summary", contract="X1", slices=list(SLICES),
                 tasks=impacted_tasks, invalidated=total_invalidated)

    # ---------- 指标 ----------
    def metrics(self) -> dict:
        m = super().metrics()
        m.update({
            "mode": self.mode,
            "serial": self.serial,
            "contract_changes": self.contract_changes,
            "contract_impacted_tasks": self.contract_impacted_tasks,
            "contract_evidence_invalidated": self.contract_evidence_invalidated,
        })
        return m

    def write_outputs(self) -> dict:
        m = super().write_outputs()
        os.makedirs(self.out_dir, exist_ok=True)
        with open(os.path.join(self.out_dir, "impact.json"), "w",
                  encoding="utf-8") as f:
            json.dump(self.impact_graph.to_dict(), f, ensure_ascii=False, indent=2)
        report = [
            f"# W3 预演报告（{self.mode}）", "",
            f"- status：{m['status']}，虚拟工期 {m['elapsed_minutes']} 分钟",
            f"- 任务：成功 {m['tasks_succeeded']} / 失败 {m['tasks_failed']} / "
            f"被取代 {m['tasks_superseded']} / 总计 {m['tasks_total']}",
            f"- 并发：峰值 {m['peak_concurrency']}；平均排队等待 "
            f"{m['avg_queue_wait_min']} 分钟",
            f"- 共享文件：冲突 {m['lock_conflicts']} 次，锁等待 {m['lock_wait_min']} 分钟，"
            f"峰值持锁 {m['peak_locks']}",
            f"- 契约变更：{m['contract_changes']} 次；影响任务 "
            f"{m['contract_impacted_tasks']} 个；失效证据事件 "
            f"{m['contract_evidence_invalidated']} 次",
            f"- 门禁首过：{m['gate_first_pass']}/{m['gates']} = "
            f"{m['gate_first_pass_rate']:.0%}；返工 {m['rework_count']}",
            f"- 裁判：{m['judge_calls']} 次 / {m['judge_wait_min']} 分钟 / "
            f"${m['judge_cost_usd']}",
            f"- 证据：{m['evidence_total']} 条，复用 {m['evidence_reused']}，"
            f"失效 {m['evidence_invalidated']}",
        ]
        with open(os.path.join(self.out_dir, "w3-report.md"), "w",
                  encoding="utf-8") as f:
            f.write("\n".join(report) + "\n")
        return m


def build_w3_scenario(sim: W3Sim) -> None:
    d.build_scenario(sim)

    # Shared-file writers: same lock forces serialization and records conflicts.
    sim.add_task(d.Task("shared_pkg_s1", "更新 package.json（S1）", "backend",
                        "X0", [], 25, priority=1, locks=["package.json"]))
    sim.add_task(d.Task("shared_pkg_s2", "更新 package.json（S2）", "backend",
                        "X0", [], 20, priority=1, locks=["package.json"]))
    sim.add_task(d.Task("shared_pkg_s3", "更新 package.json（S3）", "backend",
                        "X0", [], 15, priority=1, locks=["package.json"]))
    sim.add_task(d.Task("shared_tokens_s1", "更新 shared/ui-tokens.css（S1）",
                        "frontend", "S1", [], 15, priority=1,
                        locks=["shared/ui-tokens.css"]))
    sim.add_task(d.Task("shared_tokens_s3", "更新 shared/ui-tokens.css（S3）",
                        "frontend", "S3", [], 15, priority=1,
                        locks=["shared/ui-tokens.css"]))

    # Contract change after the three code gates; it invalidates all slices.
    sim.add_task(d.Task("contract_change", "X1 契约变更 v1.1（auth）", "arch", "X0",
                        ["s1_gate", "s3_gate"], 15, priority=1, risk="high",
                        deps_any=[["s2_gate", "s2_regate"]]))
    sim.tasks["security_scan"].deps = ["contract_change"]
    sim.tasks["security_scan"].deps_any = [
        ["s1_gate", "s1_contract_regate"],
        ["s3_gate", "s3_contract_regate"],
        ["s2_gate", "s2_regate", "s2_contract_regate"],
    ]
    sim.tasks["integration_qa"].deps.append("contract_change")
    # Contract regates are appended as required deps when the change creates them.

    if sim.serial:
        sim.add_task(d.Task("s1_serial_join", "S1 串行屏障", "pm", "X0",
                            ["s1_qa"], 1, priority=8))
        sim.add_task(d.Task("s2_serial_join", "S2 串行屏障", "pm", "X0",
                            [], 1, priority=8,
                            deps_any=[["s2_qa", "s2_qa_retest"],
                                      ["s2_gate", "s2_regate"]]))
        for tid in ("s2_qa_cases", "s2_be", "s2_fe"):
            sim.tasks[tid].deps.append("s1_serial_join")
        for tid in ("s3_qa_cases", "s3_be"):
            sim.tasks[tid].deps.append("s2_serial_join")


def run_mode(mode: str) -> dict:
    sim = W3Sim(serial=(mode == "serial"))
    build_w3_scenario(sim)
    sim.validate_dag()
    sim.run()
    m = sim.write_outputs()
    print(json.dumps({
        "mode": mode, "status": m["status"],
        "elapsed_minutes": m["elapsed_minutes"],
        "tasks_total": m["tasks_total"],
        "tasks_succeeded": m["tasks_succeeded"],
        "tasks_failed": m["tasks_failed"],
        "tasks_superseded": m["tasks_superseded"],
        "peak_concurrency": m["peak_concurrency"],
        "lock_conflicts": m["lock_conflicts"],
        "lock_wait_min": m["lock_wait_min"],
        "contract_changes": m["contract_changes"],
        "contract_impacted_tasks": m["contract_impacted_tasks"],
        "contract_evidence_invalidated": m["contract_evidence_invalidated"],
        "gate_first_pass_rate": m["gate_first_pass_rate"],
        "rework_count": m["rework_count"],
        "judge_calls": m["judge_calls"],
        "judge_cost_usd": m["judge_cost_usd"],
    }, ensure_ascii=False, indent=2))
    print(f"outputs -> {sim.out_dir}")
    return m


def compare(parallel: dict, serial: dict) -> dict:
    def delta(key: str) -> float:
        p = parallel.get(key, 0) or 0
        s = serial.get(key, 0) or 0
        return round(s - p, 2)

    result = {
        "parallel": {k: parallel.get(k) for k in (
            "elapsed_minutes", "avg_queue_wait_min", "peak_concurrency",
            "lock_conflicts", "lock_wait_min", "contract_changes",
            "contract_impacted_tasks", "contract_evidence_invalidated",
            "gate_first_pass_rate", "rework_count", "tasks_total",
            "tasks_succeeded", "tasks_failed", "tasks_superseded",
            "judge_calls", "judge_cost_usd", "evidence_total",
            "evidence_reused", "status")},
        "serial": {k: serial.get(k) for k in (
            "elapsed_minutes", "avg_queue_wait_min", "peak_concurrency",
            "lock_conflicts", "lock_wait_min", "contract_changes",
            "contract_impacted_tasks", "contract_evidence_invalidated",
            "gate_first_pass_rate", "rework_count", "tasks_total",
            "tasks_succeeded", "tasks_failed", "tasks_superseded",
            "judge_calls", "judge_cost_usd", "evidence_total",
            "evidence_reused", "status")},
        "delta_serial_minus_parallel": {
            k: delta(k) for k in (
                "elapsed_minutes", "avg_queue_wait_min", "lock_conflicts",
                "lock_wait_min", "contract_changes", "contract_impacted_tasks",
                "contract_evidence_invalidated", "gate_first_pass_rate",
                "rework_count", "judge_calls", "judge_cost_usd",
                "tasks_total", "tasks_succeeded", "tasks_failed",
                "tasks_superseded", "evidence_total", "evidence_reused")},
        "speedup_parallel_vs_serial": round(
            (serial.get("elapsed_minutes", 1) or 1)
            / (parallel.get("elapsed_minutes", 1) or 1), 3),
    }
    out = HERE / "out" / "w3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    p, s = result["parallel"], result["serial"]
    lines = [
        "# W3 并行 vs Serial Baseline", "",
        "| 指标 | Parallel (3 slices) | Serial baseline | 差异 |",
        "|---|---|---|---|",
    ]
    for label, key in (
            ("虚拟工期(min)", "elapsed_minutes"),
            ("平均排队等待(min)", "avg_queue_wait_min"),
            ("峰值并发", "peak_concurrency"),
            ("共享文件冲突", "lock_conflicts"),
            ("锁等待(min)", "lock_wait_min"),
            ("契约变更", "contract_changes"),
            ("受影响任务", "contract_impacted_tasks"),
            ("门禁首过率", "gate_first_pass_rate"),
            ("返工", "rework_count"),
            ("任务成功", "tasks_succeeded"),
            ("任务失败", "tasks_failed"),
            ("任务被取代", "tasks_superseded"),
            ("证据总量", "evidence_total"),
            ("证据复用", "evidence_reused"),
            ("裁判调用", "judge_calls"),
            ("裁判成本($)", "judge_cost_usd")):
        lines.append(f"| {label} | {p.get(key)} | {s.get(key)} | "
                     f"{result['delta_serial_minus_parallel'].get(key, '')} |")
    lines += ["", f"**并行加速比（serial/parallel）**："
                  f"{result['speedup_parallel_vs_serial']}x", ""]
    (out / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="W3 parallel/shared-file/contract-impact simulation")
    p.add_argument("--mode", choices=["both", "parallel", "serial"], default="both")
    args = p.parse_args(argv)
    results = {}
    if args.mode in ("both", "parallel"):
        results["parallel"] = run_mode("parallel")
    if args.mode in ("both", "serial"):
        results["serial"] = run_mode("serial")
    if "parallel" in results and "serial" in results:
        cmp = compare(results["parallel"], results["serial"])
        print(json.dumps({"comparison": cmp["speedup_parallel_vs_serial"],
                          "output": str(HERE / "out" / "w3" / "comparison.md")},
                         ensure_ascii=False, indent=2))
    bad = [m for m in results.values() if m.get("status") != "completed"]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
