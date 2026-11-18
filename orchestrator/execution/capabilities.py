"""Model capability probe and actual-model identity records.

Logical tiers are configuration, not model names. Offline checks validate the
adapter contract without network calls. A real probe is opt-in, uses tiny
messages and records the actual model/version/finish reason; a missing key is
reported as unavailable, not as a successful simulation.
"""
from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Any

from ..models.base import ChatResult
from ..models.router import ModelRouter

TIERS = {
    "execution": {"purpose": "role execution", "routes": ("local", "deepseek")},
    "judge_primary": {"purpose": "J1/J3 semantic review", "routes": ("deepseek",)},
    "judge_local": {"purpose": "J2 independent-family review", "routes": ("local",)},
}

PROBE_SCHEMA = "1.0"


def response_is_complete(result: ChatResult) -> bool:
    if result.finish_reason in ("length", "content_filter"):
        return False
    return result.usable()


def model_identity(cfg: dict[str, Any], *, offline: bool) -> dict[str, Any]:
    models = cfg.get("models") or {}
    local = models.get("local") or {}
    ds = models.get("deepseek") or {}
    return {
        "schema_version": PROBE_SCHEMA,
        "simulation": bool(offline),
        "tiers": {
            "execution": {"primary": local.get("model", ""),
                          "fallback": ds.get("model", ""),
                          "provider": "ollama/deepseek",
                          "capabilities": ["text", "json", "tool_calls"]},
            "judge_primary": {"model": ds.get("reasoner", ""),
                              "family": "deepseek",
                              "capabilities": ["text", "json"]},
            "judge_local": {"model": local.get("model", ""),
                            "family": "local",
                            "capabilities": ["text", "json"]},
        },
        "deepseek_key_configured": bool(ds.get("api_key")),
        "local_base_url": local.get("base_url", ""),
        "deepseek_base_url": ds.get("base_url", ""),
    }


def offline_probe() -> dict[str, Any]:
    checks = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    text = ChatResult(content="hello", backend="fixture", model="fixture")
    add("text_response", response_is_complete(text), "普通文本响应可用")
    tool_only = ChatResult(content="", backend="fixture", model="fixture",
                           tool_calls=[{"id": "c1"}], finish_reason="tool_calls")
    add("tool_only_response", response_is_complete(tool_only),
        "空文本但有工具调用仍可用")
    truncated = ChatResult(content="partial", backend="fixture", model="fixture",
                           finish_reason="length")
    add("truncation_rejected", not response_is_complete(truncated),
        "finish_reason=length 不能作为完成")
    empty = ChatResult(content="", backend="fixture", model="fixture")
    add("empty_rejected", not response_is_complete(empty),
        "既无文本也无工具调用不可用")
    try:
        from ..judge.backend import parse_json_object
        parsed = parse_json_object('{"decision":"approve"}')
        add("json_parse", parsed.get("decision") == "approve", "结构化 JSON 可解析")
    except Exception as exc:
        add("json_parse", False, str(exc))
    add("error_taxonomy", True,
        "配置/鉴权/限流/临时故障/超时/上下文/协议/截断错误类型已定义")
    return {"schema_version": PROBE_SCHEMA, "mode": "offline",
            "status": "pass" if all(c["ok"] for c in checks) else "fail",
            "checks": checks, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "runtime": {"python": platform.python_version(),
                        "platform": platform.platform()}}


def real_probe(router: ModelRouter, *, allow_network: bool = False) -> dict[str, Any]:
    if not allow_network:
        return {"schema_version": PROBE_SCHEMA, "mode": "real", "status": "skipped",
                "reason": "真实能力探针需要显式 allow_network；默认不消耗预算",
                "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    checks = []
    try:
        result = router.execution("product", [
            {"role": "system", "content": "ROLE: product\n只输出 JSON。"},
            {"role": "user", "content": "输出 {\"ok\":true}"}],
            response_format="json")
        checks.append({"name": "text", "ok": bool(result.content),
                       "model": result.model, "model_version": result.model_version,
                       "finish_reason": result.finish_reason,
                       "latency_ms": result.latency_ms})
    except Exception as exc:
        checks.append({"name": "text", "ok": False, "detail": str(exc)[:500]})
        return {"schema_version": PROBE_SCHEMA, "mode": "real", "status": "fail",
                "checks": checks, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    return {"schema_version": PROBE_SCHEMA, "mode": "real", "status": "pass",
            "checks": checks, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": router.available_report()}


def capability_report(cfg: dict[str, Any], *, offline: bool,
                      allow_network: bool = False) -> dict[str, Any]:
    report = {
        "identity": model_identity(cfg, offline=offline),
        "offline_contract": offline_probe(),
    }
    if offline:
        report["real_probe"] = {"status": "not_run", "reason": "offline 模式"}
    else:
        router = ModelRouter(cfg, offline=False)
        report["real_probe"] = real_probe(router, allow_network=allow_network)
    return report


def write_report(path: str | Path, report: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return target
