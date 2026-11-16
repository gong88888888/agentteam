#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.1 编排协议自检（不依赖 pytest）。

覆盖：
  - 正常场景收敛、失败任务不混入成功计数；
  - 无故障注入 happy path 不死锁；
  - 门禁顺序：机器检查 → 决策包 → 裁判；
  - 门禁只查工具签名证据，Agent 自述只作 claim；
  - 代码变更后裁决失效、s2_gate 被取代、s2_regate 复评；
  - 重复 ID、DAG 环、重试上限、预算硬停。

运行：python -I sim/selfcheck.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("dryrun", os.path.join(HERE, "dryrun.py"))
assert SPEC and SPEC.loader
d = importlib.util.module_from_spec(SPEC)
sys.modules["dryrun"] = d
SPEC.loader.exec_module(d)


def fresh():
    sim = d.Sim()
    d.build_scenario(sim)
    sim.validate_dag()
    return sim


def test_normal() -> None:
    s = fresh()
    s.run()
    m = s.metrics()
    assert m["status"] == "completed", m["status"]
    assert not m["fatal"] and not m["deadlock"]
    assert m["human_decisions"] == 0 and m["human_wait_min"] == 0
    assert m["tasks_done"] == m["tasks_succeeded"]
    assert (m["tasks_succeeded"] + m["tasks_failed"]
            + m["tasks_superseded"] == m["tasks_total"])
    assert m["tasks_failed"] == 2          # s1_review / s2_qa 的失败尝试
    assert m["tasks_superseded"] == 1      # 旧 s2_gate
    assert s.tasks["s1_review"].state == d.FAILED
    assert s.tasks["s2_qa"].state == d.FAILED
    assert s.tasks["s2_gate"].state == d.SUPERSEDED
    assert s.tasks["s2_regate"].state in d.SUCCESS
    assert s.valid_verdict("s2")
    assert "s2" in s.invalidated_verdicts
    assert s.verdicts_invalidated == 1
    assert m["evidence_invalidated"] >= 1
    assert m["evidence_reused"] == sum(
        1 for e in s.events if e["event"] == "evidence.reused")
    assert all(e.signed_by.startswith(("tool:", "judge:")) for e in s.evidence)
    assert all(x["status"] == "closed" for x in s.defects)
    assert s.gate_first_pass_ids == {"s1", "s3", "gate_close"}
    # 门禁顺序：机器检查必须早于裁判请求
    for task in s.tasks.values():
        if not task.gate and task.id != "gate_close":
            continue
        ci = [i for i, e in enumerate(s.events)
              if e["event"] == "gate.checked" and e.get("task") == task.id]
        ji = [i for i, e in enumerate(s.events)
              if e["event"] == "judge.requested" and e.get("task") == task.id]
        assert ci, task.id
        if ji:
            assert ci[0] < ji[0], f"{task.id} 先裁判后检查"
    # 裁决绑定决策包
    for dec in s.decisions:
        assert d.packet_digest(dec.packet) == dec.packet_hash
    # 证据必须是工具/裁判签名；claim 不进入 evidence
    assert all(ev.signed_by.split(":")[0] in ("tool", "judge") for ev in s.evidence)
    print("  normal OK:", m["elapsed_minutes"], "min,", m["tasks_total"], "tasks")


def test_happy_path() -> None:
    s = fresh()
    s.injected_failure = lambda task: False
    s.run()
    m = s.metrics()
    assert m["status"] == "completed", m["status"]
    assert not m["fatal"] and not m["deadlock"]
    assert m["tasks_failed"] == 0, m["tasks_failed"]
    assert m["tasks_superseded"] == 0
    print("  happy OK:", m["elapsed_minutes"], "min")


def test_duplicate_id() -> None:
    s = fresh()
    try:
        s.add_task(d.Task("p_s1", "dup", "product", "S1", [], 10))
    except d.TaskIdExistsError:
        print("  duplicate-id OK")
        return
    raise AssertionError("重复 ID 未抛错")


def test_dag_cycle() -> None:
    s = fresh()
    s.tasks["p_s1"].deps = ["gate_product"]
    try:
        s.validate_dag()
    except d.DagValidationError:
        print("  dag-cycle OK")
        return
    raise AssertionError("DAG 环未抛错")


def test_retry_cap() -> None:
    s = fresh()
    s.evaluate_gate = lambda task: (False, ["forced deterministic failure"], [], [])
    s.run()
    m = s.metrics()
    assert m["status"] == "failed", m["status"]
    assert m["fatal"] and m["retry_cap_violations"] >= 1
    print("  retry-cap OK:", m["retry_cap_violations"])


def test_budget_stop() -> None:
    old = d.BUDGET_TOKENS
    try:
        d.BUDGET_TOKENS = 1000
        s = fresh()
        s.run()
        m = s.metrics()
        assert m["status"] == "budget_exceeded", m["status"]
        assert m["budget_exceeded"] and m["fatal"]
        print("  budget OK:", m["status"])
    finally:
        d.BUDGET_TOKENS = old


def main() -> None:
    print("v4.1 selfcheck")
    test_normal()
    test_happy_path()
    test_duplicate_id()
    test_dag_cycle()
    test_retry_cap()
    test_budget_stop()
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
