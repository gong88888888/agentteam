"""Deterministic offline model placeholder used by tests and CI."""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .. import hard_blocks
from .base import ChatResult, ModelTimeout


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
                obj["files"] = [self._project_file(role)]
        if self.mode == "schema_error":
            content = '{"not": "a verdict"'
        else:
            content = json.dumps(obj, ensure_ascii=False)
        return ChatResult(content=content, backend=self.name, model=model or "stub",
                          model_version="stub@1", latency_ms=int((time.time() - started) * 1000),
                          response_id="stub")

    @staticmethod
    def _project_file(role: str) -> dict[str, str]:
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
        m = re.search(r"ROLE:\s*([a-z]+)", text)
        if m and m.group(1) in ("pm", "product", "ui", "arch", "frontend",
                                "backend", "review", "qa", "security",
                                "ops", "kb", "retro"):
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
