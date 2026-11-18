"""Deterministic offline model placeholder used by tests and CI."""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .. import hard_blocks
from .base import ChatResult, ModelTimeout


PRODUCT_ROLE_STUB = {
    "product-lead": ("docs/product-review/00-brief.md", "目标 成功指标 非目标 决策 用户 版本 升级"),
    "doc-analyst": ("docs/product-review/01-document-map.md", "来源 主张 歧义 覆盖 SRC-001 用户 流程 数据 风险"),
    "user-researcher": ("docs/product-review/02-users-journeys.md", "用户 场景 旅程 痛点 假设 失败 恢复 SRC-001"),
    "flow-architect": ("docs/product-review/03-product-flows.md", "状态 事件 转移 失败 恢复 空状态 加载 错误 SRC-001"),
    "feature-designer": ("docs/product-review/04-feature-spec.md", "功能 切片 依赖 非目标 验收 边界 异常 SRC-001"),
    "ux-reviewer": ("docs/product-review/05-ux-review.md", "信息架构 状态 错误 可访问 文案 键盘 对比度 SRC-001"),
    "tech-feasibility": ("docs/product-review/06-tech-feasibility.md", "技术 依赖 性能 安全 风险 架构 假设 SRC-001"),
    "release-strategist": ("docs/product-review/07-upgrade-plan.md", "版本 兼容 迁移 灰度 回滚 特性开关 发布 升级 SRC-001"),
    "qa-rehearsal": ("docs/product-review/08-rehearsal.md", "场景 基线 指标 回滚 Go/No-Go 补丁 小版本 大版本 SRC-001"),
    "red-team": ("docs/product-review/09-red-team.md", "矛盾 缺口 风险 严重度 SRC-001 范围 验收"),
    "knowledge-curator": ("docs/product-review/10-playbook.md", "复用 升级 触发条件 门禁 模板 常见坑 SRC-001"),
}

ROLE_STUB = {
    "pm": "决策包 选项 证据 风险 升级 裁决协调 切片 依赖 门禁",
    "product": "非目标 验收标准 用户场景 范围",
    "ui": "信息架构 交互状态 深色模式 可访问性 设计规范",
    "arch": "接口契约 不变量 状态机 错误码 架构",
    "frontend": "加载 错误 空状态 可访问性 深色模式 组件",
    "backend": "参数校验 状态机 日志 错误码 单元测试 接口",
    "review": "评审 证据引用 整改方向 契约漂移 findings",
    "qa": "正常 异常 边界 权限 回归 证据 用例",
    "security": "威胁 缓解 高危 权限 依赖 合规",
    "ops": "回滚 演练 监控 灰度 发布 告警",
    "kb": "来源 证据 适用条件 失效时间 信任等级 检索 知识 复用",
    "retro": "时间线 根因 行动项 owner deadline verification 验证 残余风险",
}


class StubBackend:
    """Rule-based stand-in for local/remote models.

    Modes:
      good        - produce schema-valid JSON from the packet's deterministic facts
      timeout     - raise ModelTimeout
      schema_error- return invalid JSON
      rubber_stamp- approve everything (used to test canary misses)
    """
    name = "stub"

    def __init__(self, mode: str = "good") -> None:
        self.mode = mode

    def available(self) -> bool:
        return True

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None,
             response_format: str | None = None, temperature: float = 0.0,
             seed: int = 0, timeout_s: int | None = None) -> ChatResult:
        started = time.time()
        if self.mode == "timeout":
            raise ModelTimeout("stub timeout")
        text = "\n".join(m.get("content", "") for m in messages)
        if '"packet"' in text:
            obj = self._judge(self._extract_packet(text))
        else:
            role = self._role(text)
            summary = f"stub {role}: {ROLE_STUB.get(role, 'stub output')}"
            obj = {
                "task_id": "stub-task",
                "role": role,
                "status": "done",
                "artifacts": [],
                "claims": [{"claim": summary, "counts_as_evidence": False}],
                "evidence_refs": [],
                "open_questions": [],
                "summary": summary,
            }
            if "项目运行器约束" in text and role in ("backend", "frontend"):
                obj["files"] = [self._project_file(role, "游戏项目约束" in text)]
            if role in PRODUCT_ROLE_STUB:
                obj = self._product_review(role, text)
        if self.mode == "schema_error":
            content = '{"not": "a verdict"'
        else:
            content = json.dumps(obj, ensure_ascii=False)
        return ChatResult(content=content, backend=self.name, model=model or "stub",
                          model_version="stub@1", latency_ms=int((time.time() - started) * 1000),
                          response_id="stub")

    @staticmethod
    def _product_review(role: str, text: str) -> dict[str, Any]:
        artifact, terms = PRODUCT_ROLE_STUB[role]
        refs = sorted(set(re.findall(r"SRC-\d{3,}", text))) or [f"SRC-{i:03d}" for i in range(1, 7)]
        detail = "".join(
            f"""### {ref}
- 用户/流程/功能/风险均需在下一版回归；当前结论来自文档段落，需产品与 QA 复核。

"""
            for ref in refs)
        content = f"""# {role} · stub product review

来源覆盖：{', '.join(refs)}

## 目标与范围
{terms}

## 关键结论
- 用户、场景、流程、数据与升级影响已按来源建立映射。
- 假设与缺口进入 open_questions，不伪装成已验证事实。

## 详细分析
{detail}## 验收与下一步
- 验收：可观察、可回滚、可追溯到 SRC。
- 角色：{role}；输出：{artifact}。
"""
        findings = [
            {"id": f"{role}-F{i}", "severity": "major" if i == 0 else "minor",
             "claim": f"来源 {refs[i % len(refs)]} 需要明确验收或升级影响",
             "source_refs": [refs[i % len(refs)]],
             "recommendation": "补充流程/验收/回滚说明"}
            for i in range(5 if role == "red-team" else 2)
        ]
        return {
            "task_id": f"stub-{role}", "role": role, "status": "done",
            "source_sections": refs,
            "findings": findings,
            "coverage": {"total_sections": len(refs), "covered_sections": len(refs),
                         "percent": 100 if refs else 0},
            "files": [{"path": artifact, "content": content}],
            "summary": f"stub {role}: {terms}",
            "open_questions": [],
        }

    @staticmethod
    def _project_file(role: str, game: bool = False) -> dict[str, str]:
        if game and role == "backend":
            return {
                "path": "game/js/gameplay/stub_systems.js",
                "content": (
                    "export function cooldownMultiplier(level = 1) {\n"
                    "  return Math.max(0.5, 1 - level * 0.05);\n"
                    "}\n"
                ),
            }
        if game and role == "frontend":
            return {
                "path": "game/js/ui/stub_hud.js",
                "content": (
                    "export function hpPercent(hp, maxHp) {\n"
                    "  return Math.max(0, Math.min(100, (hp / maxHp) * 100));\n"
                    "}\n"
                ),
            }
        if role == "backend":
            return {
                "path": "src/backend/service.py",
                "content": (
                    '"""Stub backend service for offline pipeline verification."""\n'
                    "from __future__ import annotations\n\n"
                    "def summarize(rows: list[dict]) -> dict:\n"
                    '    """Deterministic stub used to exercise compile/tests."""\n'
                    "    return {\"count\": len(rows), \"rows\": rows}\n"
                ),
            }
        return {
            "path": "src/frontend/app.js",
            "content": (
                "export function exportState(status) {\n"
                "  return { ready: status === 'ready', loading: status === 'loading' };\n"
                "}\n"
            ),
        }

    @staticmethod
    def _role(text: str) -> str:
        m = re.search(r"ROLE:\s*([a-z-]+)", text)
        if m and m.group(1) in ("pm", "product", "ui", "arch", "frontend",
                                "backend", "review", "qa", "security",
                                "ops", "kb", "retro", *PRODUCT_ROLE_STUB):
            return m.group(1)
        return "product"

    @staticmethod
    def _extract_packet(text: str) -> dict[str, Any]:
        try:
            return json.loads(text).get("packet", {})
        except Exception:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0)).get("packet", {})
                except Exception:
                    pass
        return {}

    def _judge(self, packet: dict[str, Any]) -> dict[str, Any]:
        blocks = hard_blocks.evaluate(packet)
        decision = "approve"
        findings = []
        required = []
        if blocks:
            decisions = [b.action for b in blocks]
            decision = "reject" if "reject" in decisions else "need_evidence"
            findings = [{"severity": "fatal" if b.action == "reject" else "major",
                         "file": "<packet>", "evidence_ids": [b.evidence_id] if b.evidence_id else [],
                         "remediation": b.message} for b in blocks]
            required = [{"kind": m, "subject": packet.get("subject_hash", ""),
                         "command": f"run {m}", "why": "硬约束要求"} for m in packet.get("missing_evidence", [])]
        if packet.get("content_isolation", {}).get("instruction_like_blocks", 0) > 0:
            decision = "reject"
            findings.append({
                "severity": "major",
                "file": "<packet>",
                "evidence_ids": [],
                "remediation": "决策包含指令性文本，按数据隔离并拒绝自动批准",
            })
        if self.mode == "rubber_stamp":
            decision = "approve"
            findings = []
            required = []
        checks = packet.get("deterministic_checks", [])
        criteria = [{"id": c.get("kind", "check"), "score": 2 if c.get("result") == "pass" else 0,
                     "evidence_ids": [c.get("evidence_id", "")] if c.get("evidence_id") else [],
                     "note": c.get("result", "")} for c in checks]
        if not criteria:
            criteria = [{"id": "packet", "score": 2, "evidence_ids": [], "note": "no deterministic checks"}]
        expiry = int(time.time()) + 24 * 3600
        return {
            "verdict_id": f"vd-stub-{int(time.time() * 1000)}",
            "packet_hash": packet.get("packet_hash", ""),
            "decision": decision,
            "confidence": 0.95 if decision != "approve" else 0.92,
            "rubric_version": "stub@1",
            "criteria": criteria,
            "findings": findings,
            "required_evidence": required,
            "conditions": [],
            "expires_at": expiry,
            "input_hash": packet.get("subject_hash", ""),
            "judge": {"backend": "stub", "model": "stub", "version": "stub@1",
                      "prompt_hash": "stub", "temperature": 0, "seed": 0},
            "signature": "stub",
        }
