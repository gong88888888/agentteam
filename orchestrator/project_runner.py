#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Role-based project runner: requirements file -> project workspace -> role records."""
from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from .acceptance_web import run_web_acceptance
from .config import data_dir, load_config, load_schema, signing_key
from .context import ContextAssembler
from .decisions import DecisionStore
from .evidence.resolver import EvidenceResolver
from .evidence.signing import sha256_hex
from .evidence.verdict_store import VerdictStore
from .findings import FindingStore
from .game_check import detect_project_type, run_game_acceptance
from .iterations import build_manifest, write_manifest
from .judge.backend import (ModelJudgeBackend, StubJudgeBackend,
                            parse_json_object)
from .judge.panel import JudgePanel
from .judge.role_review import review_role
from .knowledge import HybridRetriever
from .models.router import ModelRouter
from .persistence import ProjectLedger
from .prompts import load_prompt
from .quality import append_history, score_role
from .process import definition_of_done, preflight, stage_plan, write_stages
from .role_gates import ARTIFACT_PATHS, HIGH_RISK_ROLES, GateResult, evaluate_role
from .sandbox import IsolatedWorkspace
from .templates import apply_template, get_template
from .tool_evidence import PROFILES, collect
from .trust import project_trust


@dataclass(frozen=True)
class RoleSpec:
    role: str
    title: str
    scope: tuple[str, ...]
    instruction: str


ROLE_SPECS: list[RoleSpec] = [
    RoleSpec("pm", "项目计划与切片",
             ("docs/plan/", "artifacts/pm/"),
             "输出项目目标、功能切片、依赖顺序、门禁与角色分工；写 docs/plan/project-plan.md。"),
    RoleSpec("product", "产品基准",
             ("docs/product/", "artifacts/product/"),
             "输出产品定位、功能清单、非目标、验收标准、用户场景；写 docs/product/product-baseline.md。"),
    RoleSpec("ui", "UI/UX 设计规范",
             ("docs/design/", "artifacts/ui/"),
             "输出信息架构、交互状态、设计 token、深浅色与可访问性要求；写 docs/design/ui-spec.md。"),
    RoleSpec("arch", "架构与契约",
             ("docs/architecture/", "contracts/", "artifacts/arch/"),
             "输出分层、状态机、接口契约、错误码、不变量；写 docs/architecture/architecture.md 与 contracts/openapi.yaml。"),
    RoleSpec("backend", "后端实现",
             ("src/backend/", "artifacts/backend/"),
             "按契约实现接口、参数校验、错误处理、日志与单测；需要写代码时用 files 写 src/backend/**。"),
    RoleSpec("frontend", "前端实现",
             ("src/frontend/", "artifacts/frontend/"),
             "按设计稿与契约实现页面、加载/空/错误状态、可访问性；需要写代码时用 files 写 src/frontend/**。"),
    RoleSpec("review", "代码评审",
             ("docs/reviews/", "artifacts/review/"),
             "只输出 findings、证据引用与整改方向，不判定门禁通过；写 docs/reviews/review.md。"),
    RoleSpec("qa", "测试计划与用例",
             ("tests/", "docs/qa/", "artifacts/qa/"),
             "覆盖正常/异常/边界/权限场景，给出可执行用例和证据要求；写 tests/test-plan.md。"),
    RoleSpec("security", "安全与合规",
             ("docs/security/", "artifacts/security/"),
             "输出威胁模型、高风险项、缓解措施与验证方式；写 docs/security/threat-model.md。"),
    RoleSpec("ops", "发布与回滚",
             ("docs/ops/", "scripts/", "artifacts/ops/"),
             "输出构建、灰度、监控、回滚与演练方案；写 docs/ops/release-plan.md。"),
    RoleSpec("kb", "知识沉淀",
             ("knowledge/", "artifacts/kb/"),
             "把本次需求的可复用资产、决策、踩坑与失效条件写成知识条目；写 knowledge/project-notes.md。"),
    RoleSpec("retro", "复盘与改进",
             ("docs/retro/", "artifacts/retro/"),
             "输出时间线、偏差、根因、行动项（owner/deadline/verification）；写 docs/retro/retro.md。"),
]

ROLE_MAP = {r.role: r for r in ROLE_SPECS}
CODE_ROLES = {"backend", "frontend"}
CONTEXT_CONSUMERS = {"backend", "frontend", "ui", "qa", "review", "security", "ops"}

GAME_INSTRUCTIONS: dict[str, str] = {
    "pm": "按产品文档拆出可交付切片：5 层章节、战斗、装备、房间、存档、双人、QA/验收；给出依赖顺序与每项验收命令。",
    "product": "把需求细化为可执行产品流程：主菜单→选职业/难度→5 层房间→战斗/掉落/商店/篝火/事件→Boss→结算→存档/读档→双人复活；逐状态写输入、失败恢复、非目标和量化验收，不能只写功能清单。",
    "arch": "确定 HTML5 Canvas 第一章的模块边界、房间/战斗/装备/存档/双人契约与测试入口；输出 ADR，不引入 React、Python Web 服务或引擎重写。",
    "ui": "输出 HUD/主菜单/背包/商店/篝火/Boss 条/小地图/多人状态的交互规范与 Design Token；覆盖空/加载/错误/暂停状态，可写 game/css 增量。",
    "backend": "实现玩法系统增量（玩家/敌人/战斗/掉落/存档扩展），只写 game/js/gameplay/**；不写 Web API。",
    "frontend": "实现游戏 UI/HUD/菜单增量，只写 game/js/ui/** 与 game/css/**；不写 React 工程。",
    "qa": "先读实际 game/js 模块并运行测试；测试失败必须写入 findings/反馈，不能只写计划；新增可运行的 game/tests/qa_*.mjs 并列出证据。",
    "ops": "输出本地启动、构建、存档备份与回滚方案，写 docs/ops/** 与 scripts/**。",
}

GAME_SCOPES: dict[str, tuple[str, ...]] = {
    "arch": ("docs/architecture/", "contracts/", "artifacts/arch/"),
    "ui": ("game/css/", "docs/design/", "artifacts/ui/"),
    "backend": ("game/js/gameplay/", "artifacts/backend/"),
    "frontend": ("game/js/ui/", "game/css/", "artifacts/frontend/"),
    "qa": ("game/tests/", "tests/", "docs/qa/", "artifacts/qa/"),
    "ops": ("docs/ops/", "scripts/", "artifacts/ops/"),
}


def _acceptance_summary(project_dir: Path) -> dict[str, Any] | None:
    path = project_dir / "acceptance.json"
    if not path.is_file():
        path = project_dir / "acceptance.web.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "status": data.get("status"),
        "engine": data.get("engine") or data.get("profile"),
        "checks": [{"name": c.get("name"), "ok": c.get("ok"),
                    "detail": c.get("detail"), "evidence_id": c.get("evidence_id")}
                   for c in data.get("checks", [])],
        "finished_at": data.get("finished_at"),
    }


class ProjectRunner:
    def __init__(self, *, requirements: str | Path, project_dir: str | Path,
                 cfg: dict[str, Any] | None = None, offline: bool = True,
                 roles: list[str] | None = None, use_kb: bool = False,
                 stop_on_error: bool = False, extra_note: str = "",
                 merge_state: bool = False, template: str = "none",
                 tool_profile: str = "basic", gates: bool = True,
                 sandbox: bool = False, decision_db: str | Path | None = None,
                 stop_on_gate: bool = False, quality: bool = True,
                 run_id: str = "", project_type: str = "auto",
                 mode: str = "formal", scope_roles: list[str] | None = None,
                 partial_run: bool = False, judge_gate: bool = False,
                 allow_local_judge: bool = False) -> None:
        self.requirements_path = Path(requirements)
        if not self.requirements_path.exists():
            raise FileNotFoundError(f"需求文件不存在：{self.requirements_path}")
        if mode not in ("formal", "rehearsal"):
            raise ValueError(f"未知运行模式：{mode}（formal|rehearsal）")
        self.mode = mode
        self.partial_run = partial_run
        self.judge_gate = bool(judge_gate)
        self.allow_local_judge = bool(allow_local_judge)
        self.judge_panel: JudgePanel | None = None
        self.project_dir = Path(project_dir).resolve()
        self.cfg = cfg or load_config()
        self.offline = offline
        self.roles = roles or [r.role for r in ROLE_SPECS]
        unknown = [r for r in self.roles if r not in ROLE_MAP]
        if unknown:
            raise ValueError(f"未知角色：{unknown}")
        self.scope_roles = scope_roles or list(self.roles)
        unknown_scope = [r for r in self.scope_roles if r not in ROLE_MAP]
        if unknown_scope:
            raise ValueError(f"未知承诺角色：{unknown_scope}")
        if tool_profile not in PROFILES:
            raise ValueError(f"未知工具证据 profile：{tool_profile}")
        if template not in ("none", "") and not get_template(template):
            raise ValueError(f"未知项目模板：{template}")
        self.use_kb = use_kb
        self.stop_on_error = stop_on_error
        self.extra_note = extra_note
        self.merge_state = merge_state
        self.template = template or "none"
        self.tool_profile = tool_profile
        self.gates_enabled = gates
        self.sandbox_enabled = sandbox
        self.stop_on_gate = stop_on_gate
        self.quality_enabled = quality
        self.run_id = run_id or (f"{time.strftime('%Y%m%d-%H%M%S')}-"
                                 f"{uuid.uuid4().hex[:6]}")
        self.router = ModelRouter(self.cfg, offline=offline)
        self.schema = load_schema("agent-output.schema.json")
        self.log_path = self.project_dir / "logs" / "events.jsonl"
        self.state_path = self.project_dir / "state" / "roles.json"
        self.evidence_ledger = self.project_dir / "evidence" / "tool-ledger.jsonl"
        self.decision_store = (DecisionStore(decision_db or (data_dir(self.cfg) / "decisions.db"))
                               if gates else None)
        self.template_record: dict[str, Any] = {}
        self.preflight_result: dict[str, Any] = {}
        self.stage_results: list[dict[str, Any]] = []
        self.acceptance_runs = 0
        self.stage_failures: list[str] = []
        self.dod_result: dict[str, Any] = {}
        self.manifest: Any = None
        self.blocked_stage: int | None = None
        self.ledger: ProjectLedger | None = None
        self.finding_store: FindingStore | None = None
        self.baseline_fp = ""
        self.requirement_text = self.requirements_path.read_text(encoding="utf-8")
        self.project_type = (detect_project_type(self.requirement_text)
                             if project_type in ("auto", "", None) else project_type)

    # ---------- workspace ----------
    def prepare(self) -> None:
        for d in ("requirements", "artifacts", "logs", "state", "docs",
                  "src", "tests", "contracts", "knowledge", "evidence", "quality"):
            (self.project_dir / d).mkdir(parents=True, exist_ok=True)
        if self.template != "none":
            self.template_record = apply_template(self.project_dir, self.template)
            self.log("template.applied", template=self.template_record.get("template"),
                     hash=self.template_record.get("hash"),
                     copied=len(self.template_record.get("copied", [])),
                     skipped=len(self.template_record.get("skipped", [])))
        self.baseline_fp = sha256_hex({
            "requirement": self.requirement_text,
            "template": self.template,
            "template_hash": self.template_record.get("hash", ""),
            "profile": self.tool_profile,
        })
        self.manifest = build_manifest(
            project_id=self.project_dir.name, iteration_id=self.run_id,
            project_type=self.project_type, roles=self.scope_roles,
            template=self.template, profile=self.tool_profile, mode=self.mode)
        write_manifest(self.project_dir, self.manifest)
        self.ledger = ProjectLedger(
            self.project_dir, project_id=self.project_dir.name,
            iteration_id=self.run_id, run_id=self.run_id,
            project_type=self.project_type, mode=self.mode)
        self.log("persistence.ready", database=str(self.ledger.db.path),
                 schema_version=self.ledger.db.schema_version())
        recovered = self.ledger.store.recover_expired()
        if recovered:
            self.log("persistence.recovered", tasks=recovered)
        self.finding_store = FindingStore(self.ledger.db)
        if self.judge_gate and self.judge_panel is None:
            verdict_store = VerdictStore(
                self.project_dir / "evidence" / "verdict-ledger.jsonl",
                signing_key())
            backend = (StubJudgeBackend() if self.offline
                       else ModelJudgeBackend(self.router,
                                              allow_local=self.allow_local_judge))
            self.judge_panel = JudgePanel(backend, store=verdict_store)
            self.log("judge.enabled", offline=self.offline,
                     allow_local_judge=self.allow_local_judge)
        self.log("iteration.manifest", iteration_id=self.run_id,
                 roles=self.manifest.required_roles,
                 acceptance=self.manifest.required_acceptance,
                 docs=self.manifest.required_docs,
                 requires_entry=self.manifest.requires_entry)
        self.preflight_result = preflight(self.project_dir, self.project_type, self.template)
        (self.project_dir / "state" / "preflight.json").write_text(
            json.dumps(self.preflight_result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        self.log("process.preflight", status=self.preflight_result["status"],
                 blockers=[b["name"] for b in self.preflight_result["blockers"]])
        target = self.project_dir / "requirements" / "input.md"
        if self.requirements_path.resolve() != target.resolve():
            shutil.copyfile(self.requirements_path, target)
        meta_path = self.project_dir / "project.json"
        previous: dict[str, Any] = {}
        if meta_path.exists():
            try:
                previous = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                previous = {}
        project_roles = sorted(set(previous.get("roles") or [])
                               | set(self.roles) | set(self.scope_roles))
        project = {
            "project_id": self.project_dir.name,
            "created_at": previous.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "requirement": str(target.relative_to(self.project_dir)),
            "offline": self.offline,
            "roles": project_roles,
            "template": self.template,
            "template_hash": self.template_record.get("hash", ""),
            "tool_profile": self.tool_profile,
            "project_type": self.project_type,
            "run_id": self.run_id,
            "mode": self.mode,
            "iteration_id": self.run_id,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "database": "state/agentteam.db",
            "current_role": "",
            "current_index": 0,
            "total_roles": len(self.roles),
            "status": "running",
        }
        (self.project_dir / "project.json").write_text(
            json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def log(self, event: str, **payload) -> None:
        rec = {"ts": time.time(), "clock": time.strftime("%H:%M:%S"), "event": event, **payload}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------- context ----------
    def role_scope(self, role: str) -> tuple[str, ...]:
        if self.project_type == "game" and role in GAME_SCOPES:
            return GAME_SCOPES[role]
        return ROLE_MAP[role].scope

    def kb_context(self) -> str:
        if not self.use_kb:
            return ""
        db = data_dir(self.cfg) / "knowledge.db"
        if not db.exists():
            self.log("kb.skipped", reason="knowledge.db not found")
            return ""
        try:
            r = HybridRetriever(db, self.cfg)
            query = self.requirement_text[:400]
            hits = r.search(query, top_k=3)
            lines = []
            for h in hits:
                if "citation" in h:
                    lines.append(f"- {h['citation']}: {h['text'][:240].replace(chr(10), ' ')}")
            self.log("kb.context", hits=len(lines))
            return "\n".join(lines)
        except Exception as exc:
            self.log("kb.error", error=str(exc)[:300])
            return ""

    def build_context(self, role: str, state: dict[str, Any]):
        """Assemble referenced documents/code instead of only prior summaries."""
        assembler = ContextAssembler(
            self.project_dir,
            budget_chars=16000 if self.project_type == "game" else 12000)
        prior_roles = [spec.role for spec in ROLE_SPECS
                       if spec.role in state and spec.role != role
                       and isinstance(state.get(spec.role), dict)
                       and state[spec.role].get("status") == "done"]
        for producer in ("pm", "product", "ui", "arch", "qa"):
            if producer not in prior_roles:
                continue
            files = state[producer].get("files") or []
            for f in files:
                path = str(f.get("path", "")).replace("\\", "/")
                if f.get("source") != "role" or not path.endswith(
                        (".md", ".yaml", ".yml", ".json")):
                    continue
                required = role in CONTEXT_CONSUMERS and producer in ("product", "arch")
                assembler.add_file(path, kind="artifact",
                                   importance="required" if required else "local",
                                   max_chars=7000, required=required)
        scope = self.role_scope(role)
        for prefix in scope:
            if not prefix.startswith(("src/", "game/")):
                continue
            base = self.project_dir / prefix.rstrip("/")
            if not base.is_dir():
                continue
            files = sorted(p for p in base.rglob("*")
                           if p.is_file() and p.suffix in (".py", ".js", ".mjs",
                                                           ".ts", ".css", ".html"))
            for path in files[:6]:
                assembler.add_file(path.relative_to(self.project_dir).as_posix(),
                                   kind="code", importance="local", max_chars=2200)
            break
        return assembler.build()

    def user_message(self, spec: RoleSpec, prior: list[str], kb: str,
                     context: str = "") -> str:
        scope = ", ".join(self.role_scope(spec.role))
        expected = ARTIFACT_PATHS.get(spec.role, ())
        template = (f"{self.template_record.get('template')} "
                    f"(hash {self.template_record.get('hash')})"
                    if self.template_record else "none")
        game_note = ""
        instruction = GAME_INSTRUCTIONS.get(spec.role, spec.instruction) if self.project_type == "game" else spec.instruction
        if self.project_type == "game":
            game_note = """
# 游戏项目约束（必须遵守）
- 交付物是 **可运行的游戏**，入口为 `game/index.html`，不是 Web API/React 后台。
- 技术栈固定为 HTML5 Canvas + 原生 ES Modules（模板已提供）；不要生成 Python Web 服务、Flask、React 工程或 Unity/Godot 代码。
- 代码角色只写 `game/js/gameplay/` 或 `game/js/ui/` 下的增量 `.js` 模块；不要覆盖基座文件 `game/js/core.js`、`game/js/main.js`、`game/index.html`、`game/tests/game_logic.test.mjs`、`game/tests/smoke.mjs`。
- QA 只新增 `game/tests/qa_*.mjs`；基座逻辑测试与 smoke 是验收基线，不得修改。
- 必须保持 `node --test game/tests/game_logic.test.mjs` 与 `node game/tests/smoke.mjs` 通过。
"""
        return f"""# 项目需求
{self.requirement_text}

# 当前角色
{spec.role} · {spec.title}
{instruction}
{game_note}
# 项目模板
{template}
脚手架不是完成品；必须用本次需求替换 TODO。期望交付物：{', '.join(expected) or '按角色约定'}

# 任务上下文包（程序装配，条目带 ID/哈希）
{context or "（无引用材料）"}

# 前置产物摘要（仅导航，不能替代上面的原文/规范）
{chr(10).join(prior) if prior else "（首个角色，无前置产物）"}

# 知识库引用
{kb or "（未启用或无命中）"}

# 调整要求
{self.extra_note or "（无特别调整）"}

# 输出要求
只输出符合 `specs/agent-output.schema.json` 的 JSON 对象。
如需写文件，增加 `"files":[{{"path":"{scope}...","content":"..."}}]`；
只能写这些前缀：{scope}；不得写项目目录之外；不得写密钥。
摘要必须包含本角色的关键决策与可验证内容，claims 不能当作证据。
"""

    def system_message(self, role: str) -> str:
        p = load_prompt(role)
        scope = ", ".join(self.role_scope(role))
        game_note = ""
        if self.project_type == "game":
            game_note = ("\n这是游戏项目：只产出 game/ 下的增量模块与文档，不生成 Web 后端/React/引擎工程；"
                         "保持 game/tests 的逻辑测试与 smoke 通过。")
        return p.text + f"""

## 项目运行器约束
你正在项目目录 `{self.project_dir.name}` 中作为 {role} 工作。{game_note}
项目需求文档已经完整放在 user 消息中；不要因为缺少“额外附件、上一轮对话或具体代码路径”而返回 blocked。
先基于现有需求完成本角色的交付物；信息缺口写入 open_questions，不要编造证据。
输出只能是 JSON；如需写文件，files[].path 必须落在 `{scope}`。
不得写项目目录之外，不得写密钥；不确定时写 open_questions，不要编造证据。
"""

    # ---------- run ----------
    def stage_index(self, role: str) -> int | None:
        for index, stage in enumerate(stage_plan(self.project_type)):
            if role in stage.get("roles", []):
                return index
        return None

    def stage_id(self, role: str) -> str:
        index = self.stage_index(role)
        if index is None:
            return "unassigned"
        return str(stage_plan(self.project_type)[index]["id"])

    def _block_stage(self, role: str, reason: str) -> None:
        if self.mode != "formal":
            return
        index = self.stage_index(role)
        if index is None:
            return
        if self.blocked_stage is None or index < self.blocked_stage:
            self.blocked_stage = index
            self.log("stage.blocked", role=role, stage_index=index, reason=reason)

    def record_gate_finding(self, role: str, gate: GateResult,
                            obj: dict[str, Any]) -> dict[str, Any] | None:
        if self.finding_store is None:
            return None
        failed = [c.name for c in gate.checks if not c.ok]
        if not failed:
            return None
        category = {
            "product": "requirement_gap", "pm": "requirement_gap",
            "ui": "design_gap", "arch": "contract_conflict",
            "backend": "implementation", "frontend": "implementation",
            "qa": "verification_gap", "ops": "environment",
            "retro": "process_gap",
        }.get(role, "process_gap")
        if any(name.startswith("evidence") or name.startswith("tool")
               for name in failed):
            category = "verification_gap"
        symptom = f"{role} 门禁 {gate.status}：" + ", ".join(failed[:6])
        finding = self.finding_store.create(
            project_id=self.project_dir.name, symptom=symptom,
            category=category, severity="major",
            evidence=[{"gate_id": gate.gate_id, "status": gate.status,
                       "failed": failed,
                       "evidence_errors": gate.evidence_errors}])
        if finding.get("created"):
            self.finding_store.triage(
                finding["finding_id"], category=category,
                root_cause=f"gate {gate.gate_id} {gate.status}")
            self.log("finding.created", role=role,
                     finding_id=finding["finding_id"], category=category)
        return finding

    def run(self) -> dict[str, Any]:
        self.prepare()
        kb = self.kb_context()
        existing: dict[str, Any] = {}
        if self.merge_state and self.state_path.exists():
            existing = json.loads(self.state_path.read_text(encoding="utf-8"))
        prior: list[str] = []
        for spec in ROLE_SPECS:
            if spec.role in existing and spec.role not in self.roles:
                summary_path = self.project_dir / "artifacts" / spec.role / "summary.md"
                if summary_path.exists():
                    text = summary_path.read_text(encoding="utf-8")[:900]
                    prior.append(f"- {spec.role}: {text}")
        state: dict[str, Any] = dict(existing)
        statuses: dict[str, str] = {}
        started_all = time.time()
        self._run_started_at = started_all
        self._run_total = len(self.roles)
        self.live_state(state, "running", None, 0)
        self._start_heartbeat()
        self.log("project.started", offline=self.offline, roles=self.roles)

        for index, role in enumerate(self.roles, 1):
            spec = ROLE_MAP[role]
            role_stage = self.stage_index(role)
            if (self.mode == "formal" and self.blocked_stage is not None
                    and role_stage is not None and role_stage > self.blocked_stage):
                statuses[role] = "skipped"
                state[role] = {
                    "role": role, "title": spec.title, "status": "skipped",
                    "gate": None, "run_id": self.run_id,
                    "reason": f"上游阶段（index={self.blocked_stage}）未通过，"
                              "正式模式阻塞下游阶段",
                    "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.log("role.skipped", role=role, stage_index=role_stage,
                         blocked_stage=self.blocked_stage)
                if self.ledger:
                    self.ledger.skip_role(
                        role, f"blocked by upstream stage {self.blocked_stage}")
                self.live_state(state, "running", None, index)
                continue
            input_fp = sha256_hex({
                "baseline": self.baseline_fp, "role": role,
                "iteration": self.run_id,
                "prior": [str(f.get("sha256", ""))
                          for meta in state.values() if isinstance(meta, dict)
                          for f in (meta.get("files") or [])][-20:],
            })
            role_handle = (self.ledger.start_role(role, stage=self.stage_id(role),
                                                  input_fingerprint=input_fp)
                           if self.ledger else None)
            prompt = load_prompt(role)
            system_text = self.system_message(role)
            context_pack = self.build_context(role, state)
            if context_pack.errors:
                self.log("context.errors", role=role, errors=context_pack.errors,
                         missing=context_pack.missing)
            user_text = self.user_message(spec, prior, kb,
                                          context=context_pack.render())
            messages = [{"role": "system", "content": system_text},
                        {"role": "user", "content": user_text}]
            role_dir = self.project_dir / "artifacts" / role
            role_dir.mkdir(parents=True, exist_ok=True)
            (role_dir / "context-manifest.json").write_text(
                json.dumps(context_pack.manifest(), ensure_ascii=False,
                           indent=2) + "\n", encoding="utf-8")
            (role_dir / "request.md").write_text(
                f"# system\n\n{system_text}\n\n# user\n\n{user_text}\n", encoding="utf-8")
            role_started_at = time.time()
            placeholder = {
                "role": role, "title": spec.title, "status": "running",
                "prompt": prompt.metadata(), "model": "", "backend": "",
                "latency_ms": 0, "tokens": 0, "files": [], "code_pass": False,
                "adjustment": self.extra_note or "", "gate": None, "tools": None,
                "sandbox": ("isolated" if self.sandbox_enabled and role in CODE_ROLES
                            else "direct"),
                "template": self.template, "run_id": self.run_id,
                "started_at": role_started_at,
                "started_clock": time.strftime("%H:%M:%S", time.localtime(role_started_at)),
            }
            (role_dir / "meta.json").write_text(
                json.dumps(placeholder, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            state[role] = placeholder
            self.live_state(state, "running", role, index)
            self.log("role.started", role=role,
                     adjustment=self.extra_note or None,
                     prompt=prompt.metadata())
            started = time.perf_counter()
            obj = None
            result = None
            repairs: list[str] = []
            last_exc: Exception | None = None
            for _attempt in range(2):
                try:
                    result = self.router.execution(role, messages, response_format="json")
                    obj, repairs = self.normalize_envelope(
                        parse_json_object(result.content), role)
                    jsonschema.validate(obj, self.schema)
                    break
                except Exception as exc:
                    last_exc = exc
                    obj = None
                    messages += [
                        {"role": "assistant", "content": result.content if result else ""},
                        {"role": "user", "content": f"输出不符合 schema：{exc}。只输出合法 JSON。"},
                    ]
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            (role_dir / "prompt.md").write_text(prompt.text, encoding="utf-8")
            if obj is None:
                statuses[role] = "error"
                error = {"role": role, "error": str(last_exc), "at": time.time()}
                (role_dir / "error.json").write_text(
                    json.dumps(error, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                state[role] = {**placeholder, "status": "error",
                               "error": str(last_exc)[:500],
                               "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                (role_dir / "meta.json").write_text(
                    json.dumps(state[role], ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                self.log("role.failed", role=role, error=str(last_exc)[:500],
                         prompt=prompt.metadata())
                if self.ledger:
                    self.ledger.finish_role(role_handle, status="error",
                                            summary="", error=str(last_exc)[:500])
                prior.append(f"- {role}: FAILED — {str(last_exc)[:200]}")
                self.live_state(state, "running", None, index)
                self._block_stage(role, "role execution failed")
                if self.stop_on_error:
                    break
                continue
            code_pass = False
            if not self.offline and role in CODE_ROLES and not obj.get("files"):
                code_obj = self.code_files(role, prompt, obj, prior, kb)
                if code_obj and code_obj.get("files"):
                    obj["files"] = code_obj["files"]
                    if code_obj.get("summary"):
                        obj["summary"] = code_obj["summary"]
                    code_pass = True
                else:
                    self.log("code.no_files", role=role)

            raw_files = obj.get("files") or []
            files: list[dict[str, Any]] = []
            tool_result: dict[str, Any] | None = None
            gate: GateResult | None = None
            if self.sandbox_enabled and role in CODE_ROLES and raw_files:
                with IsolatedWorkspace(self.project_dir, role) as ws:
                    files = self.write_files(role, raw_files, root=ws.path)
                    tool_result = (None if self.project_type == "game"
                                   else self.run_tools(ws.path, role, files))
                    gate = self.run_gate(role, obj, files, tool_result,
                                         files_root=ws.path)
                    if gate is not None and gate.status == "pass":
                        promoted = ws.promote([f["path"] for f in files])
                        for f in files:
                            f["promoted"] = f["path"] in promoted
                    else:
                        self.stash_files(role, files, ws.path, role_dir)
                        for f in files:
                            f["promoted"] = False
            else:
                files = self.write_files(role, raw_files)
                if role in CODE_ROLES and self.project_type != "game":
                    tool_result = self.run_tools(self.project_dir, role, files)
                files += self.synthesize_docs(role, spec, obj, files)
                gate = self.run_gate(role, obj, files, tool_result)
                for f in files:
                    f["promoted"] = True
            if self.project_type == "game":
                self.update_extension_manifest(role, files)
            (role_dir / "output.json").write_text(
                json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary = obj.get("summary") or "; ".join(
                c.get("claim", "") for c in obj.get("claims", []))
            (role_dir / "summary.md").write_text(
                self.summary_md(role, spec, obj, files, gate), encoding="utf-8")
            role_status = obj.get("status", "done")
            if gate is not None and gate.status != "pass":
                role_status = "blocked"
            judge_data = None
            if (self.judge_panel is not None and gate is not None
                    and gate.status == "pass" and role in HIGH_RISK_ROLES):
                judged = review_role(
                    role=role, obj=obj, gate=gate, tool_result=tool_result,
                    project_id=self.project_dir.name,
                    baseline_fp=self.baseline_fp, panel=self.judge_panel,
                    risk="high", files=files)
                judge_data = judged.to_dict()
                if not judged.approved:
                    role_status = "blocked"
                    self.log("judge.blocked", role=role,
                             decision=judged.decision, error=judged.error)
                else:
                    self.log("judge.approved", role=role,
                             decision=judged.decision)
            meta = {
                "role": role, "title": spec.title,
                "status": role_status,
                "prompt": prompt.metadata(),
                "model": result.model if result else "",
                "backend": result.backend if result else "",
                "latency_ms": result.latency_ms if result else elapsed_ms,
                "tokens": (result.prompt_tokens + result.completion_tokens) if result else 0,
                "cost_usd": result.cost_usd if result else 0.0,
                "files": files,
                "code_pass": code_pass,
                "adjustment": self.extra_note or "",
                "gate": self._gate_dict(gate) if gate else None,
                "judge": judge_data,
                "tools": self.tools_summary(tool_result),
                "sandbox": ("isolated" if self.sandbox_enabled and role in CODE_ROLES
                            else "direct"),
                "template": self.template,
                "run_id": self.run_id,
                "started_at": role_started_at,
                "started_clock": placeholder["started_clock"],
                "schema_repairs": repairs,
                "context": context_pack.manifest(),
                "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if self.quality_enabled and gate is not None:
                quality = score_role(role, obj, files=files, gate=gate,
                                     tool_result=tool_result,
                                     latency_ms=meta["latency_ms"],
                                     tokens=meta["tokens"])
                meta["quality"] = quality
                append_history(self.project_dir, role=role, quality=quality,
                               gate=gate, obj=obj, meta=meta, run_id=self.run_id)
                self.log("quality.scored", role=role, score=quality["score"],
                         grade=quality["grade"])
            (role_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            statuses[role] = role_status
            state[role] = meta
            if judge_data and not judge_data.get("approved"):
                self._block_stage(role, f"judge:{judge_data.get('decision')}")
            if self.ledger:
                self.ledger.finish_role(
                    role_handle, status=role_status, summary=summary, files=files,
                    gate=self._gate_dict(gate) if gate else None,
                    model=meta.get("model", ""), backend=meta.get("backend", ""))
            self.live_state(state, "running", None, index)
            if role in CODE_ROLES and (role == "frontend" or "frontend" not in self.roles):
                self.run_stage_acceptance("implementation", state)
            if role == "qa":
                self.run_stage_acceptance("quality", state)
            if repairs:
                self.log("schema.repaired", role=role, repairs=repairs)
            prior.append(f"- {role}: {summary[:700]}"
                         f" | gate={gate.status if gate else 'off'}")
            if self.project_type == "game" and role in ("pm", "product", "arch", "ui", "qa"):
                for rel in ARTIFACT_PATHS.get(role, ()):
                    if rel.endswith("/"):
                        continue
                    path = self.project_dir / rel
                    if path.is_file():
                        excerpt = path.read_text(encoding="utf-8", errors="replace")[:2200]
                        prior.append(f"- {role} 文档 `{rel}` 摘要：\n{excerpt}")
            if tool_result is not None:
                self.log("tool.evidence", role=role,
                         profile=tool_result.get("profile"),
                         passed=tool_result.get("passed", []),
                         failed=tool_result.get("failed", []),
                         missing=[m.get("kind") for m in tool_result.get("missing", [])],
                         subject_hash=tool_result.get("subject_hash", ""))
            if gate is not None:
                self.log(f"gate.{gate.status}", role=role, gate_id=gate.gate_id,
                         failed=[c.name for c in gate.checks if not c.ok],
                         evidence_ids=gate.evidence_ids,
                         decision_id=gate.decision_id)
            self.log("role.finished", role=role, status=role_status,
                     model=meta["model"], backend=meta["backend"],
                     prompt=prompt.metadata(), latency_ms=meta["latency_ms"],
                     files=[f["path"] for f in files],
                     gate=gate.status if gate else "off")
            if gate is not None and gate.status != "pass":
                self.record_gate_finding(role, gate, obj)
                self._block_stage(role, f"gate {gate.status}: {gate.gate_id}")
            if gate is not None and gate.status != "pass" and self.stop_on_gate:
                self.log("project.gate_blocked", role=role, gate_id=gate.gate_id)
                break

        if self.partial_run:
            elapsed = int(time.time() - started_all)
            errors = [r for r, v in state.items()
                      if isinstance(v, dict) and v.get("status") == "error"]
            blocked = [r for r, v in state.items()
                       if isinstance(v, dict) and v.get("status") == "blocked"]
            self.dod_result = {"status": "not_run",
                               "reason": "partial_rerun: 单角色重跑不构成项目完成",
                               "checks": []}
            self._stop_heartbeat()
            self.write_state(state, "partial_rerun", elapsed)
            self.write_readme(state, "partial_rerun")
            if self.ledger:
                self.ledger.export_domain_events()
            self.log("project.partial_rerun", statuses=statuses,
                     scope_roles=self.scope_roles)
            return {"project_dir": str(self.project_dir), "status": "partial_rerun",
                    "roles": statuses, "errors": errors, "blocked": blocked,
                    "elapsed_s": elapsed, "model": self.router.summary(),
                    "template": self.template, "tool_profile": self.tool_profile,
                    "partial": True, "scope_roles": self.scope_roles}

        elapsed = int(time.time() - started_all)
        acceptance = None
        if self.project_type == "game":
            acceptance = run_game_acceptance(
                self.project_dir, ledger_path=self.evidence_ledger,
                baseline_fp=self.baseline_fp)
            self.log("game.acceptance", status=acceptance["status"],
                     engine=acceptance["engine"],
                     failed=[c["name"] for c in acceptance["checks"] if not c["ok"]],
                     evidence_ids=acceptance["evidence_ids"])
        elif self.manifest and self.manifest.requires_entry:
            acceptance = run_web_acceptance(
                self.project_dir, ledger_path=self.evidence_ledger,
                baseline_fp=self.baseline_fp)
            self.log("web.acceptance", status=acceptance["status"],
                     entry=acceptance.get("entry"),
                     failed=[c["name"] for c in acceptance["checks"] if not c["ok"]],
                     evidence_ids=acceptance["evidence_ids"])
        self.dod_result = definition_of_done(
            self.project_dir, self.project_type, state,
            acceptance=acceptance, manifest=self.manifest)
        errors = [r for r, v in state.items()
                  if isinstance(v, dict) and v.get("status") == "error"]
        blocked = [r for r, v in state.items()
                   if isinstance(v, dict) and v.get("status") == "blocked"]
        skipped = [r for r, v in state.items()
                   if isinstance(v, dict) and v.get("status") == "skipped"]
        all_statuses = [v.get("status") for v in state.values() if isinstance(v, dict)]
        if self.mode != "formal":
            status = "rehearsal"
        elif all_statuses and all(s in ("error", "blocked", "skipped")
                                  for s in all_statuses):
            status = "failed"
        elif errors or blocked or skipped:
            status = "partial"
        else:
            status = "completed"
        if acceptance is not None and acceptance["status"] != "pass":
            status = "failed"
        if self.dod_result.get("status") != "pass" and self.mode == "formal":
            status = "failed" if acceptance is None or acceptance.get("status") != "pass" \
                else "partial"
        if self.ledger:
            try:
                self.ledger.finish_iteration(status, dod=self.dod_result,
                                             acceptance=acceptance)
            except Exception as exc:
                self.log("persistence.finish_error", error=str(exc)[:300])
        self._stop_heartbeat()
        self.write_state(state, status, elapsed)
        self.write_readme(state, status)
        self.log("project.finished", status=status, elapsed_s=elapsed,
                 errors=errors, blocked=blocked)
        return {"project_dir": str(self.project_dir), "status": status,
                "roles": statuses, "errors": errors, "blocked": blocked,
                "elapsed_s": elapsed, "model": self.router.summary(),
                "template": self.template, "tool_profile": self.tool_profile}

    @staticmethod
    def normalize_envelope(obj: dict[str, Any], role: str) -> tuple[dict[str, Any], list[str]]:
        """Map harmless model wording to the schema, never changing decisions/evidence."""
        out = dict(obj)
        repairs: list[str] = []
        alias = {
            "completed": "done", "complete": "done", "success": "done",
            "ok": "done", "finished": "done", "partial": "done",
            "failed": "blocked", "failure": "blocked", "error": "blocked",
        }
        status = str(out.get("status", "")).lower()
        if status in alias and out.get("status") != alias[status]:
            out["status"] = alias[status]
            repairs.append(f"status:{status}->{alias[status]}")
        defaults = {
            "task_id": f"T-{role.upper()}-{int(time.time())}",
            "artifacts": [], "claims": [], "evidence_refs": [],
            "open_questions": [], "summary": "",
        }
        for key, value in defaults.items():
            if key not in out:
                out[key] = value
                repairs.append(f"missing:{key}")
        if isinstance(out.get("claims"), list):
            fixed = []
            for claim in out["claims"]:
                if isinstance(claim, str):
                    claim = {"claim": claim, "counts_as_evidence": False}
                    repairs.append("claims:string->object")
                if isinstance(claim, dict) and "counts_as_evidence" not in claim:
                    claim = {**claim, "counts_as_evidence": False}
                    repairs.append("claims:counts_as_evidence")
                fixed.append(claim)
            out["claims"] = fixed
        return out, repairs

    def _start_heartbeat(self, interval_s: float = 3.0) -> None:
        if getattr(self, "_heartbeat_thread", None):
            return
        self._heartbeat_stop = threading.Event()

        def loop() -> None:
            while not self._heartbeat_stop.wait(interval_s):
                path = self.project_dir / "state" / "progress.json"
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    now = time.time()
                    data["updated_at"] = now
                    data["clock"] = time.strftime("%H:%M:%S", time.localtime(now))
                    data["elapsed_s"] = int(now - self._run_started_at)
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
                except (OSError, json.JSONDecodeError):
                    continue

        self._heartbeat_thread = threading.Thread(
            target=loop, name=f"progress-{self.project_dir.name}", daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        stop = getattr(self, "_heartbeat_stop", None)
        if stop:
            stop.set()
        thread = getattr(self, "_heartbeat_thread", None)
        if thread:
            thread.join(timeout=2)
        self._heartbeat_thread = None

    def _update_project(self, **fields: Any) -> None:
        path = self.project_dir / "project.json"
        try:
            project = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            project = {"project_id": self.project_dir.name}
        project.update(fields)
        path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    def _project_total(self, state: dict[str, Any]) -> int:
        return len(state) if self.merge_state else getattr(self, "_run_total", len(self.roles))

    def write_progress(self, state: dict[str, Any], status: str,
                       current_role: str | None, index: int) -> None:
        now = time.time()
        progress = {
            "status": status,
            "current_role": current_role or "",
            "current_index": index,
            "total_roles": self._project_total(state),
            "run_started_at": getattr(self, "_run_started_at", now),
            "elapsed_s": int(now - getattr(self, "_run_started_at", now)),
            "updated_at": now,
            "clock": time.strftime("%H:%M:%S", time.localtime(now)),
            "completed": [r for r, v in state.items()
                          if isinstance(v, dict) and v.get("status") == "done"],
            "blocked": [r for r, v in state.items()
                        if isinstance(v, dict) and v.get("status") == "blocked"],
            "failed": [r for r, v in state.items()
                       if isinstance(v, dict) and v.get("status") == "error"],
        }
        path = self.project_dir / "state" / "progress.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    def live_state(self, state: dict[str, Any], status: str,
                   current_role: str | None, index: int) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.write_progress(state, status, current_role, index)
        self._update_project(
            status=status,
            current_role=current_role or "",
            current_index=index,
            total_roles=self._project_total(state),
            progress_updated_at=time.time(),
            updated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    @staticmethod
    def tools_summary(tool_result: dict[str, Any] | None) -> dict[str, Any] | None:
        if not tool_result:
            return None
        evidence = tool_result.get("evidence", [])
        return {
            "profile": tool_result.get("profile"),
            "subject_hash": tool_result.get("subject_hash", ""),
            "ledger": tool_result.get("ledger", ""),
            "passed": tool_result.get("passed", []),
            "failed": tool_result.get("failed", []),
            "missing": [m.get("kind") for m in tool_result.get("missing", [])],
            "evidence": [{"evidence_id": e.get("evidence_id"), "kind": e.get("kind"),
                          "result": e.get("result"), "tool": e.get("tool"),
                          "tool_version": e.get("tool_version")}
                         for e in evidence],
        }

    def run_tools(self, code_root: Path, role: str,
                  files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        scope = next((p.rstrip("/") for p in self.role_scope(role)
                      if p.startswith(("src/", "game/"))), "src")
        paths = [str(f.get("path", "")) for f in (files or [])
                 if str(f.get("path", "")).endswith(".py")]
        try:
            result = collect(self.project_dir, profile=self.tool_profile,
                             code_root=code_root, scope=scope, files=paths or None,
                             ledger_path=self.evidence_ledger,
                             baseline_fp=self.baseline_fp)
            return result
        except Exception as exc:
            self.log("tool.error", role=role, error=str(exc)[:500])
            return {"profile": self.tool_profile, "subject_hash": "", "evidence": [],
                    "passed": [], "failed": [], "error": str(exc)[:500],
                    "missing": [{"kind": "tooling", "reason": str(exc)[:300],
                                 "required": True}]}

    def _process_decision(self, stage: str, result: dict[str, Any]) -> str | None:
        if not self.decision_store:
            return None
        decision_id = f"DEC-{re.sub(r'[^A-Za-z0-9]+', '-', self.project_dir.name).upper()}-STAGE-{stage.upper()}"[:64]
        failed = [c for c in result.get("checks", []) if not c.get("ok")]
        packet = {
            "gate_id": f"STAGE-{stage}", "scope": {"project": self.project_dir.name,
                                                   "stage": stage, "risk": "high"},
            "baseline_fp": self.baseline_fp,
            "deterministic_checks": failed,
            "missing_evidence": [c.get("name") for c in failed],
            "stage": stage, "acceptance": result.get("status"),
        }
        options = [
            {"id": "A", "summary": "按失败项返工后重跑该阶段", "cost": "低", "risk": "低", "reversible": True},
            {"id": "B", "summary": "缩小范围并记录明确豁免", "cost": "低", "risk": "中", "reversible": True},
            {"id": "C", "summary": "阻塞交付，保留证据等待修复", "cost": "中", "risk": "低", "reversible": True},
        ]
        rec = self.decision_store.create(
            decision_id=decision_id, gate_id=f"STAGE-{stage}",
            title=f"{self.project_dir.name} · {stage} 阶段门禁未通过",
            scope=packet["scope"], risk="high", options=options, packet=packet,
            verdicts=[], evidence=[], recommendation="按失败项补齐后再进入下一阶段。")
        return str(rec.get("id", decision_id)) if rec else decision_id

    def run_stage_acceptance(self, stage: str, state: dict[str, Any]) -> dict[str, Any] | None:
        if not self.gates_enabled or self.project_type != "game":
            return None
        try:
            result = run_game_acceptance(
                self.project_dir, ledger_path=self.evidence_ledger,
                baseline_fp=self.baseline_fp,
                report_name=f"acceptance.{stage}.json")
        except Exception as exc:
            result = {"status": "fail", "checks": [{"name": "stage_error", "ok": False,
                                                     "detail": str(exc)[:300]}],
                      "engine": "unknown", "evidence_ids": []}
        self.acceptance_runs += 1
        decision_id = None
        if result["status"] != "pass":
            decision_id = self._process_decision(stage, result)
            self.stage_failures.append(stage)
        row = {"stage": stage, "status": result["status"],
               "checks": result.get("checks", []),
               "evidence_ids": result.get("evidence_ids", []),
               "decision_id": decision_id,
               "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.stage_results.append(row)
        write_stages(self.project_dir, self.stage_results)
        self.log("process.stage", stage=stage, status=result["status"],
                 failed=[c.get("name") for c in result.get("checks", []) if not c.get("ok")],
                 decision_id=decision_id)
        return row

    @staticmethod
    def parse_extension_metadata(text: str) -> dict[str, Any] | None:
        """Read the declarative extension export from a generated JS module."""
        match = re.search(r"export\s+const\s+extension\s*=\s*\{(.*?)\n\}\s*;",
                          text, re.S)
        if not match:
            return None
        body = match.group(1)
        id_match = re.search(r"""id\s*:\s*["']([^"']+)["']""", body)
        if not id_match:
            return None
        actions: list[str] = []
        actions_match = re.search(r"actions\s*:\s*\[([^\]]*)\]", body)
        if actions_match:
            actions = re.findall(r"""["']([^"']+)["']""", actions_match.group(1))
        smoke = None
        smoke_match = re.search(r"smoke\s*:\s*\{(.*?)\}", body, re.S)
        if smoke_match:
            smoke_body = smoke_match.group(1)
            action_match = re.search(r"""action\s*:\s*["']([^"']+)["']""",
                                     smoke_body)
            args: list[Any] = []
            args_match = re.search(r"args\s*:\s*\[([^\]]*)\]", smoke_body)
            if args_match:
                for token in args_match.group(1).split(","):
                    token = token.strip()
                    if not token:
                        continue
                    if token[0] in "\"'":
                        args.append(token.strip("\"'"))
                    elif token in ("true", "false"):
                        args.append(token == "true")
                    elif token in ("null", "undefined"):
                        args.append(None)
                    else:
                        try:
                            args.append(float(token) if "." in token else int(token))
                        except ValueError:
                            args.append(token)
            smoke = {"action": action_match.group(1) if action_match
                     else (actions[0] if actions else ""), "args": args}
            type_match = re.search(r"""expectType\s*:\s*["']([^"']+)["']""",
                                   smoke_body)
            if type_match:
                smoke["expectType"] = type_match.group(1)
        return {"id": id_match.group(1), "actions": actions, "smoke": smoke}

    def update_extension_manifest(self, role: str,
                                  files: list[dict[str, Any]]) -> None:
        """Register generated modules through the single extension manifest.

        This is a deterministic integration step: a module only becomes
        reachable when it declares an extension and is present in the manifest.
        """
        manifest_path = (self.project_dir / "game" / "js" / "extensions"
                         / "manifest.json")
        data: dict[str, Any] = {"schema_version": "1.0", "extensions": []}
        if manifest_path.is_file():
            try:
                loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass
        entries = {str(e.get("id")): dict(e) for e in data.get("extensions") or []
                   if isinstance(e, dict) and e.get("id")}
        changed = False
        for f in files:
            rel = str(f.get("path", "")).replace("\\", "/")
            if f.get("source") != "role" or not f.get("promoted", True):
                continue
            if not rel.endswith(".js") or not rel.startswith(
                    ("game/js/gameplay/", "game/js/ui/")):
                continue
            path = self.project_dir / rel
            if not path.is_file():
                continue
            game_rel = rel[len("game/"):]
            meta = self.parse_extension_metadata(
                path.read_text(encoding="utf-8", errors="replace"))
            for existing in [eid for eid, entry in entries.items()
                             if entry.get("path") == rel
                             or entry.get("module") == rel
                             or entry.get("module") == game_rel]:
                del entries[existing]
                changed = True
            if meta is None:
                self.log("extension.metadata_missing", role=role, path=rel)
                continue
            entry = {"id": meta["id"], "module": game_rel, "path": rel,
                     "role": role, "version": 1, "actions": meta["actions"]}
            if meta.get("smoke"):
                entry["smoke"] = meta["smoke"]
            entries[meta["id"]] = entry
            changed = True
            self.log("extension.registered", role=role, path=rel,
                     extension=meta["id"], actions=meta["actions"])
        if changed:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            data["extensions"] = sorted(entries.values(), key=lambda e: str(e["id"]))
            manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
            self.log("extension.manifest", count=len(entries))

    def _gate_dict(self, gate: GateResult) -> dict[str, Any]:
        data = gate.to_dict()
        data["run_id"] = self.run_id
        data["iteration_id"] = self.run_id
        return data

    def run_gate(self, role: str, obj: dict[str, Any], files: list[dict[str, Any]],
                 tool_result: dict[str, Any] | None,
                 files_root: Path | None = None) -> GateResult | None:
        if not self.gates_enabled:
            return None
        resolver = None
        if tool_result and tool_result.get("ledger"):
            try:
                resolver = EvidenceResolver(tool_result["ledger"], signing_key())
            except Exception as exc:
                self.log("evidence.resolver_error", role=role, error=str(exc)[:300])
        gate = evaluate_role(
            role, obj, project_dir=self.project_dir, files=files,
            tool_result=tool_result, profile=self.tool_profile,
            decision_store=self.decision_store,
            project_name=self.project_dir.name, baseline_fp=self.baseline_fp,
            project_type=self.project_type, evidence_resolver=resolver,
            files_root=files_root)
        return gate

    def stash_files(self, role: str, files: list[dict[str, Any]],
                    workspace: Path, role_dir: Path) -> None:
        """Keep rejected sandbox outputs for review, outside the project tree."""
        for f in files:
            rel = str(f.get("path", "")).replace("\\", "/")
            if not rel or ".." in Path(rel).parts:
                continue
            src = (workspace / rel).resolve()
            if not src.is_file() or not str(src).startswith(str(workspace)):
                continue
            dst = role_dir / "sandbox" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            f["sandbox_copy"] = f"artifacts/{role}/sandbox/{rel}"
            self.log("file.sandboxed", role=role, path=rel,
                     copy=f["sandbox_copy"])

    def synthesize_docs(self, role: str, spec: RoleSpec, obj: dict[str, Any],
                        files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Write a clearly marked summary doc when a role skipped its artifact.

        This is not model-authored content and never counts as tool evidence.
        """
        expected = ARTIFACT_PATHS.get(role, ())
        if not expected or role in CODE_ROLES:
            return []
        authored = {str(f.get("path", "")).replace("\\", "/") for f in files}
        target_rel = next((p for p in expected if not p.endswith("/")), None)
        if not target_rel or target_rel in authored:
            return []
        target = self.project_dir / target_rel
        content = self._summary_doc(role, spec, obj)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        rec = {"path": target_rel, "sha256": sha,
               "bytes": len(content.encode("utf-8")),
               "source": "runner-summary", "promoted": True}
        self.log("file.synthesized", role=role, path=target_rel)
        return [rec]

    def _summary_doc(self, role: str, spec: RoleSpec, obj: dict[str, Any]) -> str:
        claims = obj.get("claims") or []
        questions = obj.get("open_questions") or []
        lines = [
            f"# {role} · {spec.title}", "",
            "> 运行器根据角色结构化输出生成；不是模型直接写入的文件，也不作为工具证据。",
            "",
            f"- 状态：{obj.get('status', 'done')}",
            f"- 摘要：{obj.get('summary', '')}", "",
            "## Claims（不参与门禁）", "",
            *([f"- {c.get('claim', '')}" for c in claims] or ["- 无"]), "",
            "## 未决问题", "",
            *([f"- {q}" for q in questions] or ["- 无"]), "",
        ]
        return "\n".join(lines)

    @staticmethod
    def parse_file_blocks(text: str) -> list[dict[str, str]]:
        files = []
        # Tolerate missing END markers and truncated output: split on FILE headers.
        parts = re.split(r"=== FILE:[ ]*(.+?)[ ]*===", text)
        for i in range(1, len(parts), 2):
            path = parts[i].strip()
            content = parts[i + 1].strip()
            content = re.sub(r"=== END FILE ===.*$", "", content, flags=re.S).strip()
            if content.startswith("```"):
                content = content.split(chr(10), 1)[1] if chr(10) in content else ""
                if content.rstrip().endswith("```"):
                    content = content.rstrip()[:-3].rstrip()
            if path and content:
                files.append({"path": path, "content": content})
        return files

    def code_files(self, role: str, prompt, base: dict[str, Any],
                   prior: list[str], kb: str) -> dict[str, Any] | None:
        """Second pass: plain-text file blocks (robust against JSON escaping)."""
        spec = ROLE_MAP[role]
        scope = ", ".join(spec.scope)
        system = prompt.text + f"""

## 本轮例外：代码文件输出（纯文本，不要 JSON）
忽略上面的 JSON 输出要求。只输出文件块，格式严格如下：
=== FILE: {scope}path/to/file ===
<完整文件内容>
=== END FILE ===
最多 2 个文件，优先 1 个最关键且完整的文件；path 必须以下列前缀之一开头：{scope}。
游戏项目的 path 必须直接以 `game/js/ui/` 或 `game/css/` 开头；不要加 `src/frontend/` 或 `src/backend/`。
不要输出解释、不要输出 Markdown 代码块，内容直接放在 FILE 标记之间。
"""
        user = f"""# 需求
{self.requirement_text}

# 已确认实现摘要
{json.dumps(base, ensure_ascii=False)[:3500]}

# 前置产物摘要
{chr(10).join(prior[-3:])}

# 知识库引用
{kb or "（无）"}

请输出至少 1 个完整代码文件，使用 FILE 块格式。
"""
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        debug_dir = self.project_dir / "artifacts" / role
        debug_dir.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                result = self.router.execution(role, messages, response_format=None)
                (debug_dir / f"code_pass_attempt{attempt + 1}.txt").write_text(
                    result.content, encoding="utf-8")
                files = self.parse_file_blocks(result.content)
                self.log("code.attempt", role=role, attempt=attempt + 1,
                         files=[f["path"] for f in files], mode="file_blocks")
                if files:
                    return {"files": files,
                            "summary": f"代码文件已生成：{', '.join(f['path'] for f in files)}"}
                messages += [{"role": "assistant", "content": result.content},
                             {"role": "user", "content":
                              "没有识别到 FILE 块。请严格使用 === FILE: path === 与 === END FILE ===。"}]
            except Exception as exc:
                self.log("code.attempt_error", role=role, attempt=attempt + 1,
                         error=str(exc)[:500])
                messages += [{"role": "user", "content": f"调用失败：{exc}"}]
        return None

    def summary_md(self, role: str, spec: RoleSpec, obj: dict[str, Any],
                   files: list[dict[str, Any]],
                   gate: GateResult | None = None) -> str:
        claims = obj.get("claims") or []
        questions = obj.get("open_questions") or []
        lines = [f"# {role} · {spec.title}", "",
                 f"- 状态：{obj.get('status', 'done')}",
                 f"- 摘要：{obj.get('summary', '')}", "",
                 *([f"- 调整要求：{self.extra_note}", ""] if self.extra_note else []),
                 *([f"- 门禁：{gate.status} · {gate.gate_id}"
                    + (f" · 决策 {gate.decision_id}" if gate.decision_id else ""), ""]
                   if gate else []),
                 "## Claims（不参与门禁）", "",
                 *[f"- {c.get('claim', '')}" for c in claims], "",
                 "## 写入文件", "",
                 *([f"- `{f['path']}` · {f['sha256'][:12]} · {f.get('source', 'role')}"
                    + ("" if f.get("promoted", True) else " · 沙箱未提升")
                    for f in files] or ["- 无"]), "",
                 "## 未决问题", "",
                 *([f"- {q}" for q in questions] or ["- 无"]), ""]
        if gate:
            failed = [c for c in gate.checks if not c.ok]
            lines += ["## 门禁检查", "",
                      *([f"- ❌ {c.name}：{c.detail}" for c in failed] or ["- 全部通过"]), ""]
        return "\n".join(lines)

    # ---------- files ----------
    def write_files(self, role: str, files: list[dict[str, Any]],
                    *, root: Path | None = None) -> list[dict[str, Any]]:
        scope = self.role_scope(role)
        base = (root or self.project_dir).resolve()
        protected = {
            "game/index.html", "game/js/core.js", "game/js/main.js",
            "game/tests/game_logic.test.mjs", "game/tests/smoke.mjs",
            "game/css/style.css",
        } if self.project_type == "game" else set()
        written: list[dict[str, Any]] = []
        for f in files:
            path = str(f.get("path", "")).replace("\\", "/").lstrip("/")
            content = str(f.get("content", ""))
            if path in protected:
                self.log("file.rejected", role=role, path=path, reason="protected game baseline")
                continue
            if not path or ".." in Path(path).parts:
                self.log("file.rejected", role=role, path=path, reason="path traversal")
                continue
            if not any(path.startswith(prefix) for prefix in scope):
                self.log("file.rejected", role=role, path=path, reason="out of scope")
                continue
            target = (base / path).resolve()
            root_s = str(base)
            if not (str(target) == root_s or str(target).startswith(root_s + os.sep)):
                self.log("file.rejected", role=role, path=path, reason="outside project")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
            written.append({"path": path, "sha256": sha,
                            "bytes": len(content.encode("utf-8")),
                            "source": "role"})
            self.log("file.written", role=role, path=path, sha256=sha)
        return written

    # ---------- reports ----------
    def write_state(self, state: dict[str, Any], status: str, elapsed: int) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        (self.state_path).write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
        gates = {"pass": 0, "fail": 0, "need_evidence": 0, "off": 0}
        scores = []
        for meta in state.values():
            if not isinstance(meta, dict):
                continue
            gate = meta.get("gate") or {}
            gates[gate.get("status", "off")] = gates.get(gate.get("status", "off"), 0) + 1
            if meta.get("quality"):
                scores.append(meta["quality"]["score"])
        project = json.loads((self.project_dir / "project.json").read_text(encoding="utf-8"))
        total_elapsed = elapsed
        if self.merge_state:
            logged = 0
            try:
                for line in self.log_path.read_text(encoding="utf-8").splitlines():
                    rec = json.loads(line)
                    if rec.get("event") == "project.finished":
                        logged += int(rec.get("elapsed_s", 0) or 0)
            except (OSError, json.JSONDecodeError):
                logged = int(project.get("elapsed_s", 0) or 0)
            total_elapsed = logged + elapsed
        project.update({"status": status, "elapsed_s": total_elapsed,
                        "model": self.router.summary(),
                        "template": self.template,
                        "template_hash": self.template_record.get("hash", ""),
                        "tool_profile": self.tool_profile,
                        "gates": gates,
                        "quality_avg": round(sum(scores) / len(scores), 1) if scores else None,
                        "project_type": self.project_type,
                        "acceptance": _acceptance_summary(self.project_dir),
                        "preflight": self.preflight_result,
                        "dod": self.dod_result,
                        "stages": self.stage_results,
                        "process_metrics": {
                            "acceptance_runs": self.acceptance_runs,
                            "stage_failures": self.stage_failures,
                            "false_complete_prevented": sum(
                                1 for r in self.stage_results if r.get("status") != "pass"),
                        },
                        "run_id": self.run_id,
                        "iteration_id": self.run_id,
                        "mode": self.mode,
                        "manifest": self.manifest.to_dict() if self.manifest else None,
                        "persistence": (self.ledger.counts() if self.ledger else None),
                        "model_calls": self.router.calls,
                        "current_role": "",
                        "current_index": self._project_total(state),
                        "total_roles": self._project_total(state),
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")})
        project["trust"] = project_trust(project)
        (self.project_dir / "project.json").write_text(
            json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.write_progress(state, status, None, self._run_total)

    def write_readme(self, state: dict[str, Any], status: str) -> None:
        rows = ["| 角色 | 标题 | 状态 | 门禁 | 质量 | 模型 | Prompt | 文件 |",
                "|---|---|---|---|---|---|---|---|"]
        for spec in ROLE_SPECS:
            role = spec.role
            if role not in state:
                continue
            s = state.get(role, {})
            prompt = s.get("prompt", {})
            files = s.get("files", [])
            gate = (s.get("gate") or {}).get("status", "—")
            quality = (s.get("quality") or {}).get("score", "—")
            rows.append(f"| {role} | {spec.title} | {s.get('status', '—')} | "
                        f"{gate} | {quality} | {s.get('model', '—')} | "
                        f"{prompt.get('version', '—')} / "
                        f"{prompt.get('hash', '—')} | "
                        f"{', '.join(f['path'] for f in files) or '—'} |")
        lines = [
            f"# {self.project_dir.name}", "",
            f"- 状态：**{status}**",
            f"- 需求：`requirements/input.md`",
            f"- 模板：`{self.template}` · 工具证据 profile：`{self.tool_profile}`",
            f"- 角色记录：`artifacts/<role>/{{output.json,summary.md,meta.json,prompt.md,request.md}}`",
            f"- 工具证据账本：`evidence/tool-ledger.jsonl`",
            f"- 质量历史：`quality/history.jsonl`",
            f"- 事件账本：`logs/events.jsonl`",
            f"- 状态：`state/roles.json`",
            "", "## 角色执行记录", "", *rows, "",
        ]
        if self.project_type == "game":
            lines += [
                "## 运行游戏", "",
                "- Windows：双击 `play_game.bat`，或 `cd game && python -m http.server 8787`",
                "- 浏览器打开 `http://localhost:8787/`（或监控页的“打开游戏”）",
                "- 验收记录：`acceptance.json`（入口/模块/逻辑/冒烟/QA/渲染）",
                "- 玩法：P1 WASD + Space + J；P2 方向键 + K；F5 存档、F9 读档",
                "",
            ]
        lines += ["> 这是角色产出记录，不是生产验收；代码/文档仍需门禁、证据与裁判。", ""]
        (self.project_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
