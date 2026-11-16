#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentTeam v4 开发预演 —— 外部模型裁判（deepseekharness）审批版

与 v3 的差异：
  - 去掉人审批；门禁与变更由外部裁判模型裁决
  - 裁判分级 J1/J2/J3；高风险门禁用双裁判 + 强裁判
  - 裁判只能加严，不能放宽确定性检查
  - 证据失效：机械失效 + 外部模型裁定复核计划（只允许追加，不允许削减）
  - 裁判金丝雀、注入检测、超时失败关闭、裁决可复验
  - 保留 v3 的切片 DAG、证据缓存、定向返工与预算

本脚本不调用真实 LLM；裁判决策按脚本化 rubric 桩执行，用于验证审批协议。
运行：python sim/dryrun.py
对照：python sim/_baseline_v3.py（人审批基线，输出到 sim/out/human/）
输出：sim/out/v4/{events.jsonl,timeline.md,metrics.json,auto-report.md}
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "v4")
DAY = 24 * 60
START_OFFSET = 9 * 60  # 虚拟起点 09:00
BASELINE_VERSION = "base-2026.11.16"
TOOL_VERSION = "tool-suite@1"
JUDGE_PROMPT_VERSION = "judge-rubric@v4.2"

# ---------- 状态 ----------
PENDING = "待就绪"
READY = "就绪"
RUNNING = "执行中"
PASSED = "通过"
MERGED = "已合入"
REWORK = "定向整改"
WAITING = "待人决策"
BLOCKED = "阻塞"
FAILED = "失败"
TERMINAL = {PASSED, MERGED, FAILED}

ACTIVE = {PENDING, READY, RUNNING, REWORK, WAITING, BLOCKED}


def now_str(minutes: int) -> str:
    total = minutes + START_OFFSET
    day = total // DAY + 1
    m = total % DAY
    return f"D{day} {m // 60:02d}:{m % 60:02d}"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ---------- 数据模型 ----------
@dataclass
class Task:
    id: str
    title: str
    role: str
    slice_id: str
    deps: list[str]
    duration: int
    priority: int = 5
    risk: str = "medium"
    acceptance: list[str] = field(default_factory=list)
    write_scope: list[str] = field(default_factory=list)
    gate: str | None = None
    approval: str | None = None
    start_after: int = 0
    dynamic: bool = False
    state: str = PENDING
    attempts: int = 0
    ready_at: int | None = None
    started_at: int | None = None
    ended_at: int | None = None
    wait_minutes: int = 0
    tokens: int = 0


@dataclass
class Decision:
    id: str
    task_id: str | None
    requested_at: int
    resolve_at: int
    decision: str
    reason: str
    tier: str = "J1"
    status: str = "pending"
    spawn: tuple | None = None
    confidence: float = 0.0


@dataclass
class Evidence:
    kind: str
    key: str
    result: str
    created_at: int
    expires_at: int
    cached: bool = False


ROLE_TOKENS = {
    "pm": 9000, "product": 14000, "ui": 12000, "arch": 16000,
    "frontend": 22000, "backend": 22000, "review": 12000,
    "qa": 16000, "security": 12000, "ops": 9000, "kb": 8000, "retro": 8000,
    "judge": 2000,
}

JUDGE_TIERS = {
    "J1": {"model": "deepseek-chat", "tokens": 9000, "price_per_m": 0.5},
    "J2": {"model": "secondary-family", "tokens": 12000, "price_per_m": 1.5},
    "J3": {"model": "deepseek-reasoner", "tokens": 18000, "price_per_m": 2.5},
}

# 每个决策的裁判计划；条目按请求次数依次消费。
# spawn = (task_id, title, role, duration, slice_id)
JUDGE_PLAN = {
    "H1": [
        {"tier": "J1", "latency": 5, "verdict": "reject",
         "reason": "3 条验收标准不可量化（可观测性/可测性不足）",
         "spawn": ("p_baseline_fix", "产品基准返工：验收标准量化", "product", 45, "X0")},
        {"tier": "J1", "latency": 4, "verdict": "approve", "reason": ""},
    ],
    "H2": [
        {"tier": "J3", "latency": 10, "verdict": "need_evidence",
         "reason": "J1/J2 分歧：缺少 auth 威胁模型增量；J3 维持从严",
         "spawn": ("threat_model_auth", "补 auth 威胁模型增量", "security", 20, "X0"),
         "panel": ["J1", "J2", "J3"], "disagreement": True},
        {"tier": "J1", "latency": 5, "verdict": "approve", "reason": ""},
    ],
    "H3": [
        {"tier": "J2", "latency": 12, "verdict": "need_evidence",
         "reason": "缺少回滚演练证据；不能以发布方案替代演练",
         "spawn": ("rollback_rehearsal", "回滚演练并留存证据", "ops", 25, "X0")},
        {"tier": "J1", "latency": 5, "verdict": "approve", "reason": ""},
    ],
    "H4": [
        {"tier": "J1", "latency": 3, "verdict": "timeout",
         "reason": "deepseekharness 超时，失败关闭"},
        {"tier": "J3", "latency": 8, "verdict": "approve", "reason": "重试成功"},
    ],
    "H5": [{"tier": "J1", "latency": 4, "verdict": "approve", "reason": ""}],
    "H-S1": [{"tier": "J1", "latency": 3, "verdict": "approve", "reason": ""}],
    "H-S2": [{"tier": "J1", "latency": 3, "verdict": "approve", "reason": ""}],
    "H-S3": [{"tier": "J1", "latency": 3, "verdict": "approve", "reason": ""}],
    "H-CR": [{"tier": "J1", "latency": 4, "verdict": "defer",
              "reason": "范围外变更，不阻塞主线，进入 v1.1 待办"}],
    "H-S2R": [{"tier": "J1", "latency": 5, "verdict": "approve", "reason": ""}],
}


class Sim:
    def __init__(self) -> None:
        self.t = 0
        self.tasks: dict[str, Task] = {}
        self.events: list[dict] = []
        self.decisions: list[Decision] = []
        self.decision_seq: dict[str, int] = {}
        self.artifacts: dict[str, dict] = {}
        self.evidence: list[Evidence] = []
        self.cache: dict[str, Evidence] = {}
        self.defects: list[dict] = []
        self.running: dict[str, int] = {}  # task_id -> finish time
        self.max_concurrency = 4
        self.peak_concurrency = 0
        self.tokens = 0
        self.rework_count = 0
        self.gate_invocations = 0
        self.gate_first_pass = 0
        self.gates_retried: set[str] = set()
        self.acceptance_covered: set[str] = set()
        self.backlog: list[dict] = []
        self.frozen_contracts = {"X1": "x1@v1.0", "X2": "x2@v1.0", "X3": "x3@v1.0"}
        # 裁判与裁决
        self.judge_calls = 0
        self.judge_tokens = 0
        self.judge_cost = 0.0
        self.judge_rejects = 0
        self.judge_need_evidence = 0
        self.judge_timeouts = 0
        self.judge_escalations = 0
        self.judge_disagreements = 0
        self.judge_canary_total = 0
        self.judge_canary_caught = 0
        self.judge_injections_blocked = 0
        self.judge_recheck_added = 0
        self.judge_wait_total = 0
        self.judge_conservative = False
        self.verdicts: dict[str, Evidence] = {}
        self.invalidated_verdicts: set[str] = set()
        self.injection_seen = False
        self.decision_counts: dict[str, int] = {}
        self.fatal = False
        self.budget_exceeded = False
        self.retry_cap_violations = 0
        self.deadlock = False

    # ---------- 基础设施 ----------
    def log(self, event: str, **payload) -> None:
        self.events.append({"t": self.t, "clock": now_str(self.t), "event": event, **payload})

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task
        if not task.deps and task.start_after == 0:
            task.state = READY
            task.ready_at = self.t
        self.log("task.created", task=task.id, slice=task.slice_id, role=task.role,
                 gate=task.gate, decision=task.approval)

    def deps_ok(self, task: Task) -> bool:
        for d in task.deps:
            if d not in self.tasks or self.tasks[d].state not in TERMINAL:
                return False
        return True

    def refresh_ready(self) -> None:
        for task in self.tasks.values():
            if task.state == PENDING and self.t >= task.start_after and self.deps_ok(task):
                task.state = READY
                task.ready_at = self.t

    def add_evidence(self, kind: str, key: str, result: str, ttl: int) -> Evidence:
        ev = Evidence(kind=kind, key=key, result=result, created_at=self.t,
                      expires_at=self.t + ttl)
        self.evidence.append(ev)
        self.log("evidence.created", kind=kind, key=key, result=result, ttl=ttl)
        return ev

    def charge_judge(self, tier: str = "J1", n: int = 1) -> None:
        info = JUDGE_TIERS[tier]
        self.judge_calls += n
        self.judge_tokens += info["tokens"] * n
        self.judge_cost += info["tokens"] * n / 1_000_000 * info["price_per_m"]

    def cached_check(self, kind: str, key: str, ttl: int, result: str) -> Evidence:
        cache_key = f"{kind}|{key}|{BASELINE_VERSION}|{TOOL_VERSION}"
        hit = self.cache.get(cache_key)
        if hit and hit.expires_at > self.t:
            hit.cached = True
            self.log("evidence.reused", kind=kind, key=key)
            return hit
        ev = self.add_evidence(kind, key, result, ttl)
        self.cache[cache_key] = ev
        return ev

    def write_artifact(self, task: Task, path: str, meta: dict, version: str = "v1.0") -> None:
        payload = json.dumps({"task": task.id, "meta": meta, "v": version},
                             ensure_ascii=False, sort_keys=True)
        self.artifacts[task.id] = {
            "path": path, "version": version, "meta": meta, "hash": digest(payload)
        }
        self.log("artifact.created", task=task.id, path=path, version=version,
                 hash=self.artifacts[task.id]["hash"])

    # ---------- 外部模型裁判 ----------
    def request_decision(self, decision_id: str, task_id: str | None) -> Decision:
        plan = JUDGE_PLAN.get(decision_id, [
            {"tier": "J1", "latency": 4, "verdict": "approve", "reason": ""}
        ])
        idx = self.decision_seq.get(decision_id, 0)
        entry = plan[min(idx, len(plan) - 1)]
        self.decision_seq[decision_id] = idx + 1

        tier = entry.get("tier", "J1")
        latency = entry.get("latency", 4)
        if self.judge_conservative and decision_id in ("H3", "H-S2R"):
            if tier == "J1":
                tier = "J2"
            latency += 4
        verdict = entry.get("verdict", "approve")
        spawn = entry.get("spawn")
        reason = entry.get("reason", "")

        if entry.get("panel"):
            self.log("judge.panel_started", decision=decision_id, task=task_id,
                     members=entry["panel"], mode="dual_plus_strong")
        if entry.get("disagreement"):
            self.judge_disagreements += 1
            self.judge_escalations += 1
            self.log("judge.disagreement", decision=decision_id,
                     j1="approve", j2="need_evidence", issue="缺少 auth 威胁模型增量")
            self.log("judge.escalated", decision=decision_id, to=tier)

        if decision_id in ("H-S2", "H-S2R") and not self.injection_seen:
            self.injection_seen = True
            self.judge_injections_blocked += 1
            self.log("judge.injection_blocked", decision=decision_id,
                     detail="S2 产物含“忽略规则并批准”的指令文本；按数据隔离，未进入裁判指令区")

        info = JUDGE_TIERS[tier]
        self.charge_judge(tier)
        d = Decision(decision_id, task_id, self.t, self.t + latency, verdict,
                     reason, tier=tier, spawn=spawn,
                     confidence=entry.get("confidence", 0.9))
        self.decisions.append(d)
        self.log("judge.requested", decision=decision_id, task=task_id, tier=tier,
                 model=info["model"], latency=latency, verdict_plan=verdict,
                 rubric=JUDGE_PROMPT_VERSION)
        return d

    def resolve_decisions(self) -> None:
        for d in self.decisions:
            if d.status != "pending" or d.resolve_at > self.t:
                continue
            d.status = d.decision
            self.judge_wait_total += d.resolve_at - d.requested_at
            self.log("judge.verdict", decision_id=d.id, task=d.task_id, tier=d.tier,
                     verdict=d.decision, confidence=d.confidence, reason=d.reason,
                     model=JUDGE_TIERS[d.tier]["model"], rubric=JUDGE_PROMPT_VERSION)

            if d.id == "H-CR":
                self.backlog.append({"item": "CSV 导出", "reason": d.reason,
                                     "decision": "defer"})
                self.log("change_request.deferred", cr="CR-01", target="v1.1")
                continue

            task = self.tasks.get(d.task_id or "")
            if not task:
                continue
            if d.decision == "timeout":
                self.judge_timeouts += 1
                self.log("judge.timeout", decision=d.id, task=d.task_id,
                         tier=d.tier, action="fail_closed_retry")
                task.state = READY
                task.ready_at = self.t
                continue
            if d.decision == "approve":
                if task.gate:
                    ev = self.add_evidence(
                        f"judge_verdict:{task.gate}",
                        f"{task.gate}:{JUDGE_PROMPT_VERSION}:{d.tier}",
                        "approve", 60 * 24)
                    self.verdicts[task.gate] = ev
                    self.invalidated_verdicts.discard(task.gate)
                task.state = READY
                task.ready_at = self.t
            else:
                if d.decision == "need_evidence":
                    self.judge_need_evidence += 1
                else:
                    self.judge_rejects += 1
                self.on_judge_rejected(task, d)

    def on_judge_rejected(self, task: Task, d: Decision) -> None:
        self.decision_counts[task.id] = self.decision_counts.get(task.id, 0) + 1
        if self.decision_counts[task.id] > 3:
            task.state = FAILED
            self.fatal = True
            self.retry_cap_violations += 1
            self.log("task.terminal_failed", task=task.id,
                     reason="裁判拒绝/补证超过 3 次，终止而非无限重试",
                     decision=d.id)
            return
        self.rework_count += 1
        self.gates_retried.add(task.id)
        task.state = REWORK
        if d.spawn:
            sid, title, role, duration, slice_id = d.spawn
            if sid not in self.tasks:
                self.add_task(Task(sid, title, role, slice_id, [], duration,
                                   priority=1, risk="high"))
            task.deps.append(sid)
        else:
            sid = f"{task.id}_fix"
            if sid not in self.tasks:
                self.add_task(Task(sid, f"{task.id} 整改", "backend",
                                   task.slice_id, [], 25, priority=2))
            task.deps.append(sid)
        task.state = PENDING
        event = ("judge.need_evidence" if d.decision == "need_evidence"
                 else "judge.rejected")
        self.log(event, decision=d.id, task=task.id, reason=d.reason,
                 rework_task=sid, tier=d.tier)

    def decision_granted(self, task: Task) -> bool:
        for d in reversed(self.decisions):
            if d.id == task.approval and d.task_id == task.id:
                return d.status == "approve"
        return False

    def invalidate(self, kind: str, reason: str) -> None:
        affected = 0
        for ev in self.evidence:
            if ev.kind == kind and ev.expires_at > self.t:
                ev.expires_at = self.t
                affected += 1
        for ev in self.cache.values():
            if ev.kind == kind:
                ev.expires_at = self.t
        for gate, ev in self.verdicts.items():
            if ev.kind == kind:
                self.invalidated_verdicts.add(gate)
        self.log("evidence.invalidated", kind=kind, reason=reason,
                 affected=affected)

    # ---------- 门禁检查 ----------
    def check_product(self) -> tuple[bool, list[str]]:
        meta = self.artifacts["p_baseline"]["meta"]
        reasons = []
        if meta["non_goals"] < 3:
            reasons.append("非目标清单不足 3 条")
        if meta["measurable_ratio"] < 0.9:
            reasons.append("量化验收标准比例 < 90%")
        if not meta["acceptance_ids"]:
            reasons.append("缺少验收 ID")
        return (not reasons), reasons

    def check_arch(self) -> tuple[bool, list[str]]:
        meta = self.artifacts["arch_baseline"]["meta"]
        reasons = []
        if meta["invariants"] < 4:
            reasons.append("不变量不足 4 条")
        if set(meta["contracts"]) != {"X1", "X2", "X3"}:
            reasons.append("接口契约不完整")
        if not meta["errors_defined"]:
            reasons.append("错误码未定义")
        return (not reasons), reasons

    def check_code(self, slice_id: str) -> tuple[bool, list[str]]:
        review = self.artifacts.get(f"{slice_id.lower()}_review_retry") or \
                 self.artifacts.get(f"{slice_id.lower()}_review")
        meta = review["meta"]
        reasons = []
        if meta["fatal"] > 0:
            reasons.append("存在致命评审问题")
        if meta["out_of_scope_writes"] > 0:
            reasons.append("写越界")
        if meta["contract"] != self.frozen_contracts.get(meta["contract_id"], "unfrozen"):
            reasons.append("契约漂移")
        return (not reasons), reasons

    def check_acceptance(self) -> tuple[bool, list[str]]:
        reasons = []
        open_serious = [d for d in self.defects if d["status"] == "open"
                        and d["severity"] in ("致命", "严重")]
        if open_serious:
            reasons.append(f"未闭环致命/严重缺陷 {len(open_serious)} 个")
        required = {"AC-1", "AC-2", "AC-3", "AC-X"}
        missing = required - self.acceptance_covered
        if missing:
            reasons.append(f"验收项证据缺失：{sorted(missing)}")
        if "rollback_rehearsal" not in self.artifacts:
            reasons.append("缺少回滚演练证据")
        for g in ("s1", "s2", "s3"):
            if g not in self.verdicts or g in self.invalidated_verdicts:
                reasons.append(f"{g} 门禁裁决缺失或已失效")
        return (not reasons), reasons

    def check_release(self) -> tuple[bool, list[str]]:
        meta = self.artifacts["release_plan"]["meta"]
        reasons = []
        if meta["rollback_steps"] < 3:
            reasons.append("回滚方案不足 3 步")
        if not meta["feature_flag"]:
            reasons.append("缺少特性开关")
        return (not reasons), reasons

    GATE_FN = {
        "product": "check_product", "arch": "check_arch",
        "s1": "check_code", "s2": "check_code", "s3": "check_code",
        "acceptance": "check_acceptance", "release": "check_release",
    }

    def run_gate(self, task: Task) -> None:
        self.gate_invocations += 1
        fn_name = self.GATE_FN[task.gate]
        if task.gate in ("s1", "s2", "s3"):
            ok, reasons = self.check_code(task.gate)
        else:
            ok, reasons = getattr(self, fn_name)()
        self.add_evidence(f"gate:{task.gate}", f"gate:{task.gate}:a{task.attempts}",
                          "pass" if ok else "fail", ttl=60 * 24)
        if ok:
            task.state = PASSED
            if task.attempts == 1:
                self.gate_first_pass += 1
            self.log("gate.passed", task=task.id, gate=task.gate)
        else:
            self.rework_count += 1
            self.gates_retried.add(task.id)
            task.state = REWORK
            self.log("gate.failed", task=task.id, gate=task.gate, reasons=reasons)
            if task.attempts >= 3:
                task.state = FAILED
                self.fatal = True
                self.retry_cap_violations += 1
                self.log("task.terminal_failed", task=task.id,
                         reason="确定性门禁连续失败超过 3 次，终止并等待人工/策略修复")
                return
            # 门禁失败 → 定向返工对应开发任务
            fix = Task(f"{task.gate}_gate_fix", f"{task.gate} 门禁返工", "backend",
                       task.slice_id, [], 30, priority=2)
            self.add_task(fix)
            task.deps.append(fix.id)
            task.state = PENDING
            self.log("rework.targeted", gate=task.gate, rework_task=fix.id)

    # ---------- 业务桩 ----------
    def produce(self, task: Task) -> None:
        tid = task.id
        version = "v1.0"
        if tid in ("p_s1", "p_s2", "p_s3"):
            self.write_artifact(task, f"docs/product/{tid}.md",
                                {"acceptance_ids": [f"AC-{tid[-1]}"]}, version)
            self.acceptance_covered.add(f"AC-{tid[-1]}")
        elif tid == "p_baseline":
            self.write_artifact(task, "docs/product/产品基准.md",
                                {"features": 3, "non_goals": 4,
                                 "acceptance_ids": ["AC-1", "AC-2", "AC-3"],
                                 "measurable_ratio": 0.67}, version)
        elif tid == "p_baseline_fix":
            base = self.artifacts["p_baseline"]
            base["meta"]["measurable_ratio"] = 1.0
            base["version"] = "v1.1"
            self.log("baseline.revised", doc="产品基准", old="v1.0", new="v1.1",
                     change="3 条验收标准改为可量化表述")
            self.write_artifact(task, "docs/product/产品基准.md",
                                {"features": 3, "non_goals": 4,
                                 "acceptance_ids": ["AC-1", "AC-2", "AC-3"],
                                 "measurable_ratio": 1.0}, "v1.1")
        elif tid == "qa_testability":
            self.write_artifact(task, "docs/product/可测性审查.md", {"reviews": 3}, version)
        elif tid == "judge_calibration":
            self.judge_canary_total = 5
            self.judge_canary_caught = 4
            self.charge_judge("J1", 5)
            miss = (self.judge_canary_total - self.judge_canary_caught) / self.judge_canary_total
            self.judge_conservative = miss > 0.10
            self.log("judge.canary_report", total=self.judge_canary_total,
                     caught=self.judge_canary_caught, miss_rate=round(miss, 2),
                     threshold=0.10)
            if self.judge_conservative:
                self.log("judge.calibration_alert", miss_rate=round(miss, 2),
                         action="启用保守模式：高风险门禁强制双裁判 + 额外复核")
                self.log("judge.policy_upgraded", old=JUDGE_PROMPT_VERSION,
                         new="judge-rubric@v4.3", reason="金丝雀漏判超阈值")
            self.write_artifact(task, "reports/judge-calibration.md",
                                {"canary": 5, "caught": 4, "conservative": True}, version)
        elif tid == "threat_model_auth":
            self.write_artifact(task, "docs/architecture/auth-threat-model.md",
                                {"threats": 4, "mitigations": 4, "scope": "X1"}, version)
        elif tid == "rollback_rehearsal":
            self.write_artifact(task, "reports/rollback-rehearsal.md",
                                {"steps": 5, "result": "pass", "rto_min": 12}, version)
        elif tid == "revalidation_judge":
            self.charge_judge("J3")
            self.judge_recheck_added = 2
            self.log("evidence.revalidation_plan", defect="D-101",
                     base_checks=["unit:S2", "lint:S2", "acceptance:AC-2", "sast"],
                     removed=[])
            self.log("judge.revalidation_verdict", decision="expand_not_reduce",
                     added=["X1-auth-contract", "migration-sanity"],
                     rationale="owner 校验触及认证边界与数据迁移，需追加复核")
            self.write_artifact(task, "reports/revalidation-plan.md",
                                {"base": 4, "added": 2, "removed": 0}, version)
            if "auth_contract_recheck" not in self.tasks:
                self.add_task(Task("auth_contract_recheck", "X1 认证契约复核",
                                   "security", "X1", ["revalidation_judge"], 15,
                                   priority=1))
                self.add_task(Task("migration_sanity", "迁移一致性复核", "backend",
                                   "X2", ["revalidation_judge"], 10, priority=1))
        elif tid == "auth_contract_recheck":
            self.write_artifact(task, "reports/auth-contract-recheck.md",
                                {"result": "pass", "contract": "X1@v1.0"}, version)
            self.cached_check("contract_test", "X1@v1.0", 60, "pass")
        elif tid == "migration_sanity":
            self.write_artifact(task, "reports/migration-sanity.md",
                                {"result": "pass", "migrations": 3}, version)
        elif tid == "ui_explore":
            self.write_artifact(task, "workspace/ui/mock-draft.html",
                                {"screens": 3, "status": "draft"}, "v0.1")
        elif tid == "ui_align":
            self.write_artifact(task, "workspace/ui/mock-v1.html",
                                {"screens": 3, "aligned_to": BASELINE_VERSION}, version)
        elif tid == "arch_contracts":
            for cid in ("X1", "X2", "X3"):
                self.log("contract.frozen", contract=cid, version="v1.0")
            self.write_artifact(task, "docs/architecture/接口契约.md",
                                {"contracts": ["X1", "X2", "X3"], "errors_defined": True},
                                version)
        elif tid == "arch_invariants":
            self.write_artifact(task, "docs/architecture/不变量.md",
                                {"invariants": 6}, version)
        elif tid == "arch_security":
            self.write_artifact(task, "docs/architecture/威胁模型.md",
                                {"threats": 7, "high_risk": 1}, version)
        elif tid == "arch_baseline":
            self.write_artifact(task, "docs/architecture/架构基准.md",
                                {"contracts": ["X1", "X2", "X3"],
                                 "errors_defined": True, "invariants": 6}, version)
        elif tid == "sandbox":
            self.write_artifact(task, "workspace/sandbox/mocks.json",
                                {"mocks": 12, "contract_tests": 9}, version)
            self.log("contract_sandbox.ready", mocks=12, contract_tests=9)
        elif tid.endswith("_qa_cases"):
            n = 8 if "s1" in tid else 7
            self.write_artifact(task, f"tests/{tid}.md", {"cases": n}, version)
        elif tid == "s2_fix":
            for d in self.defects:
                if d["id"] == "D-101":
                    d["status"] = "closed"
            self.log("defect.fixed", defect="D-101",
                     detail="服务层统一 owner 校验；权限回归重跑")
            self.invalidate("gate:s2", "门禁后代码变更，确定性凭证失效")
            self.invalidate("judge_verdict:s2", "裁判所依据的代码版本已变化，裁决失效")
            self.invalidate("sast", "扫描后代码变更，定向重扫")
            if "s2_recheck" not in self.tasks:
                self.add_task(Task("s2_recheck", "S2 修复定向复核", "review", "S2",
                                   ["s2_fix"], 15, priority=2))
                self.add_task(Task("security_rescan_s2", "S2 定向安全重扫", "security",
                                   "S2", ["s2_fix"], 15, priority=2))
                self.add_task(Task("revalidation_judge", "外部模型裁定复核计划",
                                   "judge", "S2", ["s2_fix"], 6, priority=1))
            self.write_artifact(task, "src/backend/s2/main.py",
                                {"endpoints": 4, "tests": 7, "owner_check": True},
                                version)
            self.cached_check("lint", f"backend:{tid}:{version}", 240, "pass")
            self.cached_check("unit", f"backend:{tid}:{version}", 240, "pass")
        elif tid.endswith("_be") or tid in ("s1_be_fix",):
            self.write_artifact(task, f"src/backend/{tid[:2]}/main.py",
                                {"endpoints": 4, "tests": 6}, version)
            self.cached_check("lint", f"backend:{tid}:{version}", 240, "pass")
            self.cached_check("typecheck", f"backend:{tid}:{version}", 240, "pass")
        elif tid.endswith("_fe"):
            self.write_artifact(task, f"src/frontend/{tid[:2]}/App.vue",
                                {"pages": 3, "a11y": "pass"}, version)
            self.cached_check("lint", f"frontend:{tid}:{version}", 240, "pass")
        elif tid.endswith("_review") or tid.endswith("_review_retry"):
            self.write_artifact(task, f"reports/{tid}.md",
                                {"fatal": 0, "out_of_scope_writes": 0,
                                 "contract": "x1@v1.0", "contract_id": "X1"}, version)
            self.cached_check("lint", f"frontend:{tid[:2]}_fe:{version}", 240, "pass")
            self.cached_check("unit", f"backend:{tid[:2]}_be:{version}", 240, "pass")
            self.cached_check("contract_test", f"X1@v1.0", 60, "pass")
        elif tid in ("s1_qa", "s2_qa", "s3_qa") or tid.endswith("_qa_retest"):
            sid = tid[:2]
            for ac in {"s1": ["AC-1"], "s2": ["AC-2"], "s3": ["AC-3"]}[sid]:
                self.acceptance_covered.add(ac)
                self.add_evidence(f"acceptance:{ac}", f"{sid}:{ac}", "pass", 480)
            self.write_artifact(task, f"reports/{tid}.md",
                                {"passed": 7, "failed": 0}, version)
        elif tid == "s2_recheck":
            self.write_artifact(task, "reports/s2-recheck.md",
                                {"fatal": 0, "scope": "owner 校验路径"}, version)
        elif tid == "security_rescan_s2":
            self.write_artifact(task, "reports/security-rescan-s2.md",
                                {"high": 0, "scope": "S2 diff"}, version)
            self.cached_check("sast", "repo:all", 0, "pass")
            self.log("evidence.revalidated", kind="sast:all", scope="S2 diff")
        elif tid == "security_scan":
            self.write_artifact(task, "reports/security-scan.md",
                                {"high": 0, "medium": 1}, version)
            self.cached_check("sast", "repo:all", 0, "pass")
            self.cached_check("deps", "requirements.lock", 0, "pass")
        elif tid == "integration_qa":
            self.write_artifact(task, "reports/integration-qa.md",
                                {"e2e": 12, "failed": 0}, version)
            self.add_evidence("acceptance:AC-X", "e2e:cross-slice", "pass", 480)
            self.acceptance_covered.add("AC-X")
        elif tid == "release_plan":
            self.write_artifact(task, "reports/release-plan.md",
                                {"rollback_steps": 5, "feature_flag": True}, version)
        elif tid == "gray_release":
            self.write_artifact(task, "reports/gray.md",
                                {"traffic": "10%", "error_rate": 0.0}, version)
        elif tid == "monitor":
            self.write_artifact(task, "reports/monitor-24h.md",
                                {"error_rate": 0.002, "p95_ms": 180}, version)
            self.log("release.monitored", error_rate=0.002, p95_ms=180)
        elif tid == "full_release":
            self.log("release.completed", version="v1.0.0", traffic="100%")
        elif tid == "kb_archive":
            self.write_artifact(task, "knowledge/项目归档.md",
                                {"assets": 9, "lessons": 4}, version)
            for kid in ("K-001", "K-002", "K-003"):
                self.log("knowledge.promoted", knowledge=kid, state="候选→已复核")
        elif tid == "retro":
            self.write_artifact(task, "reports/retro.md",
                                {"deviations": 2, "actions": 3}, version)
        elif tid == "final_report":
            self.write_artifact(task, "reports/final-delivery.md",
                                {"status": "delivered"}, version)
            self.log("project.delivered", version="v1.0.0")
        elif tid == "cr_export":
            self.write_artifact(task, "docs/product/CR-01.md",
                                {"scope": "CSV导出", "size": "M"}, version)
        else:
            self.write_artifact(task, f"reports/{tid}.md", {"ok": True}, version)

    def post_checks(self, task: Task) -> None:
        if task.id in ("s1_review_retry",):
            self.cached_check("unit", "backend:s1_be_fix", 240, "pass")
            self.cached_check("contract_test", "X1@v1.0", 60, "pass")
        if task.id == "s2_qa_retest":
            self.cached_check("acceptance:s2", "s2:permission-regression", 0, "pass")
            self.cached_check("lint", "frontend:s2_fe:v1.0", 240, "pass")

    # ---------- 故障注入 ----------
    def injected_failure(self, task: Task) -> bool:
        if task.id == "s2_fe" and task.attempts == 1:
            self.log("output.validation_failed", task=task.id,
                     detail="manifest 缺 acceptance_ids；写入拦截，未产生半成品",
                     scope="src/frontend/s2/**")
            self.rework_count += 1
            task.state = REWORK
            task.attempts += 0  # 由 retry 维护
            self.retry_later(task, 15)
            return True
        if task.id == "s1_review" and task.attempts == 1:
            self.log("review.finding", task=task.id, severity="严重",
                     file="src/backend/s1/main.py:88", rule="接口契约 X1 §3.2",
                     detail="新增 token_expires_at 字段，契约未定义")
            self.rework_count += 1
            task.state = FAILED
            fix = Task("s1_be_fix", "契约漂移修复", "backend", "S1",
                       ["s1_review"], 25, priority=2)
            retry = Task("s1_review_retry", "S1 复审", "review", "S1",
                         ["s1_be_fix"], 20, priority=2)
            self.add_task(fix)
            self.add_task(retry)
            self.log("rework.targeted", trigger="contract_drift",
                     rework_task="s1_be_fix", unaffected=["S2", "S3"])
            return True
        if task.id == "s2_qa" and task.attempts == 1:
            self.defects.append({"id": "D-101", "severity": "致命", "slice": "S2",
                                 "title": "水平越权：GET /records/{id} 未校验 owner",
                                 "status": "open"})
            self.log("defect.found", defect="D-101", severity="致命",
                     file="src/backend/s2/main.py:142",
                     detail="用户 A 可读取用户 B 的记录")
            self.rework_count += 1
            task.state = FAILED
            fix = Task("s2_fix", "越权缺陷修复", "backend", "S2",
                       ["s2_qa"], 35, priority=1)
            retest = Task("s2_qa_retest", "S2 权限回归", "qa", "S2",
                          ["s2_fix"], 40, priority=1)
            self.add_task(fix)
            self.add_task(retest)
            self.log("rework.targeted", trigger="defect:D-101",
                     rework_task="s2_fix", unaffected_evidence="lint:frontend:S2")
            return True
        if task.id == "s3_qa" and task.attempts == 1:
            self.defects.append({"id": "D-102", "severity": "一般", "slice": "S3",
                                 "title": "空数据月份图表显示 NaN", "status": "closed"})
            self.log("defect.found", defect="D-102", severity="一般",
                     detail="已在本任务内修复并回归，不阻塞门禁")
            return False
        return False

    def retry_later(self, task: Task, delay: int) -> None:
        task.state = PENDING
        task.start_after = self.t + delay
        self.log("task.retry_scheduled", task=task.id, after=delay)

    # ---------- 运行 ----------
    def record_tokens(self, task: Task) -> None:
        spent = ROLE_TOKENS.get(task.role, 10000) + task.duration * 90
        task.tokens = spent
        self.tokens += spent
        if self.tokens > 4_000_000 and not self.budget_exceeded:
            self.budget_exceeded = True
            self.fatal = True
            self.log("budget.exceeded", tokens=self.tokens, budget=4_000_000,
                     action="停止新任务并生成决策包")

    def start_ready(self) -> None:
        if self.budget_exceeded:
            return
        while len(self.running) < self.max_concurrency:
            candidates = [t for t in self.tasks.values()
                          if t.state == READY and self.t >= t.start_after
                          and self.deps_ok(t)]
            if not candidates:
                return
            candidates.sort(key=lambda x: (x.priority, -x.duration, x.id))
            task = candidates[0]
            if task.approval and not self.decision_granted(task):
                if task.state != WAITING:
                    task.state = WAITING
                    self.request_decision(task.approval, task.id)
                # 继续尝试其它任务
                candidates = [c for c in candidates if c.id != task.id]
                others = [c for c in candidates if not c.approval]
                if not others:
                    return
                task = others[0]
            task.state = RUNNING
            task.attempts += 1
            task.started_at = self.t
            if task.ready_at is not None:
                task.wait_minutes += self.t - task.ready_at
            self.running[task.id] = self.t + task.duration
            self.peak_concurrency = max(self.peak_concurrency, len(self.running))
            self.record_tokens(task)
            self.log("task.started", task=task.id, role=task.role, slice=task.slice_id,
                     attempt=task.attempts, gate=task.gate)

    def finish_due(self) -> None:
        due = [tid for tid, end in self.running.items() if end <= self.t]
        due.sort()
        for tid in due:
            task = self.tasks[tid]
            del self.running[tid]
            task.ended_at = self.t
            if self.injected_failure(task):
                continue
            if task.gate:
                self.run_gate(task)
                continue
            self.produce(task)
            self.post_checks(task)
            task.state = MERGED if task.role in ("frontend", "backend") else PASSED
            self.log("task.finished", task=task.id, state=task.state,
                     attempt=task.attempts)
            if task.id == "cr_export":
                self.request_decision("H-CR", None)

    def all_terminal(self) -> bool:
        return all(t.state in TERMINAL for t in self.tasks.values())

    def next_time(self) -> int | None:
        times = list(self.running.values())
        times += [d.resolve_at for d in self.decisions if d.status == "pending"]
        times += [t.start_after for t in self.tasks.values()
                  if t.state == PENDING and t.start_after > self.t]
        return min(times) if times else None

    def run(self) -> None:
        self.log("project.created", project="MiniLedger", baseline=BASELINE_VERSION,
                 budget_tokens=4_000_000, approval_mode="external_model_judge",
                 judge="deepseekharness")
        for _ in range(10000):
            self.resolve_decisions()
            self.refresh_ready()
            self.start_ready()
            if self.all_terminal() and not self.running:
                break
            nxt = self.next_time()
            if nxt is None:
                stuck = [t.id for t in self.tasks.values() if t.state in ACTIVE]
                if stuck:
                    self.deadlock = True
                    self.fatal = True
                    self.log("scheduler.deadlock", tasks=stuck)
                break
            self.t = max(self.t, nxt)
            self.finish_due()
        else:
            self.fatal = True
            self.log("scheduler.loop_guard")
        self.log("project.closed", elapsed_minutes=self.t)

    # ---------- 输出 ----------
    def metrics(self) -> dict:
        started = [t for t in self.tasks.values() if t.started_at is not None]
        waits = [t.wait_minutes for t in started]
        cost = self.tokens / 1_000_000 * 6
        gate_tasks = [t for t in self.tasks.values() if t.gate]
        first_pass = len([t for t in gate_tasks if t.id not in self.gates_retried])
        return {
            "elapsed_minutes": self.t,
            "elapsed_days": round(self.t / DAY, 2),
            "tasks_total": len(self.tasks),
            "tasks_done": sum(1 for t in self.tasks.values() if t.state in TERMINAL),
            "peak_concurrency": self.peak_concurrency,
            "avg_queue_wait_min": round(sum(waits) / len(waits), 1) if waits else 0,
            "max_queue_wait_min": max(waits) if waits else 0,
            "gates": len(gate_tasks),
            "gate_first_pass": first_pass,
            "gate_first_pass_rate": round(first_pass / len(gate_tasks), 2)
            if gate_tasks else 0,
            "rework_count": self.rework_count,
            "defects": self.defects,
            "defects_total": len(self.defects),
            "fatal_or_major": sum(1 for d in self.defects
                                  if d["severity"] in ("致命", "严重")),
            "evidence_total": len(self.evidence),
            "evidence_reused": sum(1 for e in self.events
                                   if e["event"] == "evidence.reused"),
            "evidence_invalidated": sum(1 for e in self.events
                                        if e["event"] == "evidence.invalidated"),
            "fatal": self.fatal,
            "deadlock": self.deadlock,
            "budget_exceeded": self.budget_exceeded,
            "retry_cap_violations": self.retry_cap_violations,
            "tokens": self.tokens,
            "budget_tokens": 4_000_000,
            "budget_used_pct": round(self.tokens / 4_000_000 * 100, 1),
            "estimated_cost_usd": round(cost, 2),
            "decision_mode": "external_model_judge",
            "judge_calls": self.judge_calls,
            "judge_tokens": self.judge_tokens,
            "judge_cost_usd": round(self.judge_cost, 3),
            "judge_rejects": self.judge_rejects,
            "judge_need_evidence": self.judge_need_evidence,
            "judge_timeouts": self.judge_timeouts,
            "judge_escalations": self.judge_escalations,
            "judge_disagreements": self.judge_disagreements,
            "judge_canary_total": self.judge_canary_total,
            "judge_canary_caught": self.judge_canary_caught,
            "judge_canary_miss_rate": round(
                (self.judge_canary_total - self.judge_canary_caught)
                / self.judge_canary_total, 2) if self.judge_canary_total else 0,
            "judge_injections_blocked": self.judge_injections_blocked,
            "judge_recheck_added": self.judge_recheck_added,
            "judge_wait_min": self.judge_wait_total,
            "judge_conservative": self.judge_conservative,
            "verdicts_invalidated": len(self.invalidated_verdicts),
            "human_decisions": 0,
            "human_wait_min": 0,
            "backlog": self.backlog,
            "acceptance_covered": sorted(self.acceptance_covered),
        }

    def write_outputs(self) -> dict:
        os.makedirs(OUT_DIR, exist_ok=True)
        m = self.metrics()
        with open(os.path.join(OUT_DIR, "events.jsonl"), "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)

        # 时间线（按事件）
        lines = ["# 开发预演事件时间线", "",
                 f"项目：MiniLedger　虚拟起点：D1 09:00　基线：{BASELINE_VERSION}", ""]
        current_day = None
        for e in self.events:
            day = e["clock"].split()[0]
            if day != current_day:
                current_day = day
                lines += ["", f"## {day}", "", "| 时刻 | 事件 | 对象 | 说明 |",
                          "|---|---|---|---|"]
            detail = "；".join(f"{k}={v}" for k, v in e.items()
                              if k not in ("t", "clock", "event"))
            lines.append(f"| {e['clock']} | {e['event']} | "
                         f"{e.get('task') or e.get('gate') or e.get('defect') or e.get('decision') or '-'} | "
                         f"{detail} |")
        with open(os.path.join(OUT_DIR, "timeline.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        # 任务终态表
        rows = ["| 任务 | 切片 | 角色 | 尝试 | 状态 | 等待(min) | 门禁 |",
                "|---|---|---|---|---|---|---|"]
        for t in sorted(self.tasks.values(), key=lambda x: (x.started_at or 0, x.id)):
            rows.append(f"| {t.id} | {t.slice_id} | {t.role} | {t.attempts} | "
                        f"{t.state} | {t.wait_minutes} | {t.gate or '-'} |")

        report = [
            "# 自动预演报告（编排层）", "",
            "> 本报告由 sim/dryrun.py 生成。Agent 产出为脚本化桩，"
            "仅验证调度、门禁、证据与外部模型裁判协议，不代表模型真实产出质量。", "",
            "## 指标", "",
            f"- 虚拟总工期：{m['elapsed_minutes']} 分钟（{m['elapsed_days']} 天，24h 制）",
            f"- 任务：{m['tasks_done']}/{m['tasks_total']} 完成；峰值并发 {m['peak_concurrency']}",
            f"- 队列平均等待：{m['avg_queue_wait_min']} 分钟；最长 {m['max_queue_wait_min']} 分钟",
            f"- 门禁首过率：{m['gate_first_pass']}/{m['gates']} = {m['gate_first_pass_rate']:.0%}",
            f"- 返工次数：{m['rework_count']}",
            f"- 缺陷：{m['defects_total']}（致命/严重 {m['fatal_or_major']}）",
            f"- 证据：{m['evidence_total']} 条，复用 {m['evidence_reused']} 条，"
            f"失效 {m['evidence_invalidated']} 条",
            f"- Token：{m['tokens']:,} / {m['budget_tokens']:,}"
            f"（{m['budget_used_pct']}%），估算 ${m['estimated_cost_usd']}",
            f"- 裁判：{m['judge_calls']} 次，等待 {m['judge_wait_min']} 分钟，"
            f"Token {m['judge_tokens']:,}（${m['judge_cost_usd']}）",
            f"- 裁判结论：拒绝 {m['judge_rejects']}，需补证 {m['judge_need_evidence']}，"
            f"超时 {m['judge_timeouts']}，升级 {m['judge_escalations']}，"
            f"分歧 {m['judge_disagreements']}",
            f"- 金丝雀：{m['judge_canary_caught']}/{m['judge_canary_total']}"
            f"（漏判率 {m['judge_canary_miss_rate']:.0%}）；注入拦截 "
            f"{m['judge_injections_blocked']}；追加复核 {m['judge_recheck_added']}",
            f"- 人决策：{m['human_decisions']} 次，累计等待 {m['human_wait_min']} 分钟",
            f"- 终止语义：fatal={m['fatal']} deadlock={m['deadlock']} "
            f"budget_exceeded={m['budget_exceeded']} "
            f"retry_cap_violations={m['retry_cap_violations']}",
            "",
            "## 任务终态", "",
            *rows,
            "",
            "## 缺陷", "",
            *[f"- {d['id']} [{d['severity']}] {d['title']} → {d['status']}"
              for d in self.defects],
            "",
            "## 范围变更", "",
            *[f"- {b['item']}：{b['decision']}（{b['reason']}）" for b in self.backlog],
            "",
            "## 验收覆盖", "",
            f"- {', '.join(m['acceptance_covered'])}",
            "",
        ]
        with open(os.path.join(OUT_DIR, "auto-report.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(report) + "\n")
        return m


def build_scenario(sim: Sim) -> None:
    T = sim.add_task
    # 阶段 0/1：产品定义（三片并行）
    T(Task("p_s1", "S1 账户与登录 产品条目", "product", "S1", [], 70, priority=2))
    T(Task("p_s2", "S2 记账录入 产品条目", "product", "S2", [], 70, priority=2))
    T(Task("p_s3", "S3 月度报表 产品条目", "product", "S3", [], 60, priority=2))
    T(Task("p_baseline", "产品基准整合（含非目标清单）", "product", "X0",
           ["p_s1", "p_s2", "p_s3"], 40, priority=1))
    T(Task("qa_testability", "验收标准可测性前置审查", "qa", "X0",
           ["p_s1", "p_s2", "p_s3"], 40, priority=3))
    T(Task("ui_explore", "UI 信息架构草稿（可丢弃）", "ui", "X0", [], 60, priority=6))
    T(Task("judge_calibration", "裁判金丝雀校准（5 例）", "judge", "X0", [], 5,
           priority=9))
    T(Task("gate_product", "产品门禁", "pm", "X0",
           ["p_baseline", "qa_testability"], 15, priority=1,
           gate="product", approval="H1"))
    T(Task("ui_align", "设计稿对齐已批基准", "ui", "X0",
           ["gate_product"], 25, priority=4))

    # 架构定义
    T(Task("arch_contracts", "接口契约 X1/X2/X3 冻结", "arch", "X0",
           ["gate_product"], 100, priority=2))
    T(Task("arch_invariants", "不变量与状态机", "arch", "X0",
           ["gate_product"], 50, priority=2))
    T(Task("arch_security", "架构级威胁建模", "security", "X0",
           ["gate_product"], 60, priority=3))
    T(Task("arch_baseline", "架构基准整合", "arch", "X0",
           ["arch_contracts", "arch_invariants", "arch_security"], 40, priority=1))
    T(Task("gate_arch", "架构门禁", "pm", "X0", ["arch_baseline"], 20,
           priority=1, gate="arch", approval="H2"))
    T(Task("sandbox", "契约沙盒与 mock 生成", "arch", "X0",
           ["gate_arch"], 20, priority=3))

    # S1 切片
    T(Task("s1_qa_cases", "S1 验收用例", "qa", "S1", ["gate_arch"], 40, priority=4))
    T(Task("s1_be", "S1 后端：注册/登录/会话", "backend", "S1",
           ["gate_arch"], 120, priority=2, write_scope=["src/backend/s1/**"],
           acceptance=["AC-1"]))
    T(Task("s1_fe", "S1 前端：注册/登录页", "frontend", "S1",
           ["gate_arch", "ui_align"], 110, priority=2,
           write_scope=["src/frontend/s1/**"], acceptance=["AC-1"]))
    T(Task("s1_review", "S1 增量评审（首个 PR）", "review", "S1",
           ["s1_be", "s1_fe"], 25, priority=2))
    T(Task("s1_gate", "S1 代码门禁", "pm", "S1", ["s1_review_retry"], 10,
           priority=2, gate="s1", approval="H-S1"))
    T(Task("s1_qa", "S1 功能与回归测试", "qa", "S1",
           ["s1_gate", "s1_qa_cases"], 60, priority=3))

    # S2 切片（与 S1 并行）
    T(Task("s2_qa_cases", "S2 验收用例", "qa", "S2", ["gate_arch"], 40, priority=4))
    T(Task("s2_be", "S2 后端：记账 CRUD", "backend", "S2",
           ["gate_arch"], 100, priority=2, write_scope=["src/backend/s2/**"],
           acceptance=["AC-2"]))
    T(Task("s2_fe", "S2 前端：记账表单", "frontend", "S2",
           ["gate_arch", "ui_align"], 100, priority=2,
           write_scope=["src/frontend/s2/**"], acceptance=["AC-2"]))
    T(Task("s2_review", "S2 增量评审", "review", "S2",
           ["s2_be", "s2_fe"], 20, priority=2))
    T(Task("s2_gate", "S2 代码门禁", "pm", "S2", ["s2_review"], 10,
           priority=2, gate="s2", approval="H-S2"))
    T(Task("s2_qa", "S2 功能与权限测试", "qa", "S2",
           ["s2_gate", "s2_qa_cases"], 60, priority=3))
    T(Task("s2_regate", "S2 复评门禁（裁决与证据失效后）", "pm", "S2",
           ["s2_fix", "s2_recheck", "security_rescan_s2", "revalidation_judge",
            "auth_contract_recheck", "migration_sanity"], 10, priority=1,
           gate="s2", approval="H-S2R"))

    # S3 切片（依赖 S2 数据模型）
    T(Task("s3_qa_cases", "S3 验收用例", "qa", "S3", ["gate_arch"], 30, priority=4))
    T(Task("s3_be", "S3 后端：月度聚合报表", "backend", "S3",
           ["s2_be"], 80, priority=3, acceptance=["AC-3"]))
    T(Task("s3_fe", "S3 前端：报表页", "frontend", "S3",
           ["s3_be", "ui_align"], 80, priority=3, acceptance=["AC-3"]))
    T(Task("s3_review", "S3 增量评审", "review", "S3",
           ["s3_be", "s3_fe"], 20, priority=3))
    T(Task("s3_gate", "S3 代码门禁", "pm", "S3", ["s3_review"], 10,
           priority=3, gate="s3", approval="H-S3"))
    T(Task("s3_qa", "S3 功能与性能测试", "qa", "S3",
           ["s3_gate", "s3_qa_cases"], 50, priority=3))

    # 集成、验收、发布、沉淀
    T(Task("security_scan", "全仓安全扫描", "security", "X0",
           ["s1_gate", "s2_gate", "s3_gate"], 40, priority=2))
    T(Task("integration_qa", "跨片集成与端到端", "qa", "X0",
           ["s1_qa", "s2_qa_retest", "s3_qa", "security_scan", "s2_regate"],
           80, priority=1))
    T(Task("gate_accept", "项目验收门禁", "pm", "X0",
           ["integration_qa"], 20, priority=1,
           gate="acceptance", approval="H3"))
    T(Task("release_plan", "发布与回滚方案", "ops", "X0",
           ["gate_accept"], 40, priority=1))
    T(Task("gate_release", "生产发布门禁", "pm", "X0",
           ["release_plan"], 15, priority=1,
           gate="release", approval="H4"))
    T(Task("gray_release", "10% 灰度发布", "ops", "X0",
           ["gate_release"], 30, priority=1))
    T(Task("monitor", "灰度监控 24h", "ops", "X0",
           ["gray_release"], 60, priority=1))
    T(Task("full_release", "全量发布", "ops", "X0",
           ["monitor"], 20, priority=1))
    T(Task("kb_archive", "归档与知识晋升", "kb", "X0",
           ["full_release"], 50, priority=4))
    T(Task("retro", "项目复盘", "retro", "X0",
           ["full_release"], 50, priority=5))
    T(Task("final_report", "最终交付报告", "pm", "X0",
           ["kb_archive", "retro"], 30, priority=2))
    T(Task("gate_close", "项目闭环确认", "pm", "X0",
           ["final_report"], 10, priority=1, approval="H5"))

    # 范围变更（实施中途进入，不阻塞主线）
    T(Task("cr_export", "CR-01 CSV 导出 评估", "product", "X0", [],
           30, priority=8, start_after=600))


def main() -> None:
    sim = Sim()
    build_scenario(sim)
    sim.run()
    m = sim.write_outputs()
    print(json.dumps({k: m[k] for k in (
        "elapsed_minutes", "elapsed_days", "tasks_done", "tasks_total",
        "peak_concurrency", "avg_queue_wait_min", "max_queue_wait_min",
        "gate_first_pass_rate", "rework_count", "defects_total",
        "evidence_total", "evidence_reused", "budget_used_pct",
        "judge_calls", "judge_tokens", "judge_cost_usd", "judge_rejects",
        "judge_need_evidence", "judge_timeouts", "judge_escalations",
        "judge_disagreements", "judge_canary_miss_rate",
        "judge_injections_blocked", "judge_recheck_added", "judge_wait_min",
        "judge_conservative", "human_decisions", "fatal",
        "retry_cap_violations")}, ensure_ascii=False, indent=2))
    print(f"outputs -> {OUT_DIR}")
    sys.exit(1 if m["fatal"] else 0)


if __name__ == "__main__":
    main()
