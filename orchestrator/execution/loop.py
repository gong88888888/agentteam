"""Minimal tool execution loop.

The model may request tools; the program executes them and returns real
observations. A model that stops without calling ``submit_result`` is
``needs_submission``, not completed, no matter what its text claims. Budgets are
hard stops that preserve a checkpoint.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..models.base import ChatResult
from .tools import ToolRegistry


@dataclass
class ToolBudget:
    max_calls: int = 8
    max_seconds: float = 300.0
    max_observation_chars: int = 60_000
    calls: int = 0
    observation_chars: int = 0
    started_at: float = field(default_factory=time.time)

    def consume(self, observation: dict[str, Any]) -> None:
        self.calls += 1
        self.observation_chars += len(str(observation.get("observations", "")))

    def exceeded(self) -> str:
        if self.calls >= self.max_calls:
            return "max_tool_calls"
        if self.observation_chars >= self.max_observation_chars:
            return "max_observation_chars"
        if time.time() - self.started_at >= self.max_seconds:
            return "max_seconds"
        return ""


@dataclass
class ToolLoopResult:
    status: str                 # ready_for_verification | blocked | needs_submission
    summary: str
    trace: list[dict[str, Any]] = field(default_factory=list)
    submitted: dict[str, Any] | None = None
    budget_exceeded: str = ""
    final_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "summary": self.summary,
                "trace": self.trace, "submitted": self.submitted,
                "budget_exceeded": self.budget_exceeded,
                "final_message": self.final_message[:1000]}


def _tool_call_parts(call: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    call_id = str(call.get("id") or "")
    function = call.get("function") if isinstance(call.get("function"), dict) else {}
    name = str(function.get("name") or call.get("name") or "")
    raw_args = function.get("arguments", call.get("arguments", {}))
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            args = {"__invalid_json__": raw_args[:500]}
    elif isinstance(raw_args, dict):
        args = raw_args
    else:
        args = {}
    return call_id, name, args


def run_tool_loop(chat: Callable[[list[dict[str, Any]], list[dict[str, Any]]],
                                 ChatResult],
                  messages: list[dict[str, Any]], *,
                  registry: ToolRegistry,
                  budget: ToolBudget | None = None,
                  submit_tool: str = "submit_result") -> ToolLoopResult:
    budget = budget or ToolBudget()
    messages = list(messages)
    trace: list[dict[str, Any]] = []
    final = ""
    while True:
        reason = budget.exceeded()
        if reason:
            return ToolLoopResult(
                status="blocked",
                summary=f"工具预算耗尽：{reason}；已保留调用链与工作区，等待恢复",
                trace=trace, budget_exceeded=reason, final_message=final)
        result = chat(messages, registry.specs())
        final = result.content
        if not result.tool_calls:
            if final.strip():
                return ToolLoopResult(
                    status="needs_submission",
                    summary="模型停止但没有调用 submit_result；文本声明不构成完成",
                    trace=trace, final_message=final)
            return ToolLoopResult(status="blocked", summary="模型既无文本也无工具调用",
                                  trace=trace, final_message=final)
        messages.append({
            "role": "assistant", "content": final,
            "tool_calls": result.tool_calls,
        })
        for call in result.tool_calls:
            call_id, name, args = _tool_call_parts(call)
            if "__invalid_json__" in args:
                observation = {"success": False, "error_type": "invalid_json",
                               "observations": "工具参数不是合法 JSON",
                               "retryable": True}
            elif not name:
                observation = {"success": False, "error_type": "missing_tool",
                               "observations": "工具调用缺少 name", "retryable": False}
            else:
                observation = registry.execute(name, args)
            budget.consume(observation)
            entry = {"tool": name, "args": args, "call_id": call_id,
                     "success": bool(observation.get("success")),
                     "error_type": observation.get("error_type", ""),
                     "evidence_ref": observation.get("evidence_ref", "")}
            trace.append(entry)
            messages.append({
                "role": "tool", "tool_call_id": call_id, "name": name,
                "content": json.dumps(observation, ensure_ascii=False)[:4000],
            })
            if name == submit_tool and observation.get("success"):
                submitted = observation.get("data") or {}
                return ToolLoopResult(
                    status=str(submitted.get("status", "ready_for_verification")),
                    summary=str(submitted.get("summary", "")),
                    trace=trace, submitted=submitted, final_message=final)
            if observation.get("error_type") == "unknown_tool":
                # Keep going: the model can correct itself, but the trace keeps
                # the failed call visible.
                continue
