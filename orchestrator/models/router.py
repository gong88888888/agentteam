"""Model routing: local Qwen primary, DeepSeek supplement; judges split by family."""
from __future__ import annotations

import time
from typing import Any

from .base import (BackendUnavailable, ChatResult, ConfigurationError,
                   ModelBackend, ModelError, ModelFormatError, ModelTruncated)
from .deepseek import DeepSeekBackend
from .ollama import OllamaBackend
from .stub import StubBackend

REAL_BACKENDS = ("local", "deepseek")


def validate_routing(cfg: dict[str, Any], *, offline: bool) -> dict[str, dict[str, str]]:
    """Validate the routing table before any attempt is made.

    Unknown backends and ``stub`` outside an explicit offline run are
    configuration errors. A real run must never silently degrade to a stub.
    """
    models = cfg.get("models") or {}
    routing = models.get("routing") or {}
    if not isinstance(routing, dict):
        raise ConfigurationError("models.routing 必须是映射（role -> {primary, fallback}）")
    allowed = set(REAL_BACKENDS) | ({"stub"} if offline else set())
    clean: dict[str, dict[str, str]] = {}
    for role, route in routing.items():
        if route is None:
            continue
        if not isinstance(route, dict):
            raise ConfigurationError(
                f"models.routing.{role} 必须是对象，实际为 {type(route).__name__}")
        item: dict[str, str] = {}
        for key in ("primary", "fallback"):
            name = route.get(key)
            if name is None:
                continue
            name = str(name).strip()
            if name not in allowed:
                legal = ", ".join(sorted(REAL_BACKENDS))
                if offline:
                    legal += ", stub（仅 offline）"
                raise ConfigurationError(
                    f"models.routing.{role}.{key}={name!r} 无效；合法值：{legal}。"
                    "请修正配置，而不是让真实运行退回 stub。")
            item[key] = name
        clean[str(role)] = item
    return clean


class ModelRouter:
    def __init__(self, cfg: dict[str, Any], *, offline: bool = False,
                 stub_mode: str = "good") -> None:
        self.cfg = cfg
        self.offline = offline
        models = cfg.get("models", {}) or {}
        local = models.get("local", {}) or {}
        ds = models.get("deepseek", {}) or {}
        self.local = OllamaBackend(
            local.get("base_url", "http://localhost:11434"),
            local.get("model", "qwen3.6:35b-a3b-mtp-q4_K_M"),
            local.get("fallback_models", []),
            int(local.get("timeout_s", 120)),
            bool(local.get("think", False)),
            int(local.get("num_ctx", 32768)))
        self.deepseek = DeepSeekBackend(
            ds.get("base_url", "https://api.deepseek.com/v1"),
            ds.get("api_key", ""),
            ds.get("model", "deepseek-chat"),
            ds.get("reasoner", "deepseek-reasoner"),
            ds.get("chat_path", "/chat/completions"),
            int(ds.get("timeout_s", 120)),
            float(ds.get("price_in_per_m", 0.5)),
            float(ds.get("price_out_per_m", 1.5)))
        self.stub = StubBackend(stub_mode)
        self.routing = validate_routing(cfg, offline=offline)
        self.calls: list[dict[str, Any]] = []
        self.family_collisions = 0

    def _backend(self, name: str) -> ModelBackend:
        if name == "local":
            return self.local
        if name == "deepseek":
            return self.deepseek
        if name == "stub":
            if not self.offline:
                raise ConfigurationError(
                    "stub 是确定性仿真后端，只能在显式 offline 模式使用；"
                    "真实运行不能退到 stub。")
            return self.stub
        legal = ", ".join(REAL_BACKENDS)
        raise ConfigurationError(
            f"未知模型后端 {name!r}；合法值：{legal}。配置错误不会被当作 stub 运行。")

    def _record(self, role: str, result: ChatResult, purpose: str) -> None:
        self.calls.append({
            "role": role, "purpose": purpose, "backend": result.backend,
            "model": result.model, "model_version": result.model_version,
            "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "cost_usd": result.cost_usd,
            "finish_reason": result.finish_reason,
            "tool_calls": len(result.tool_calls),
        })

    def _run(self, role: str, messages: list[dict[str, Any]], *,
             primary: str, fallback: str | None, purpose: str,
             response_format: str | None, temperature: float, seed: int,
             tools: list[dict[str, Any]] | None = None) -> ChatResult:
        if self.offline:
            res = self.stub.chat(messages, response_format=response_format,
                                 temperature=temperature, seed=seed)
            self._record(role, res, purpose)
            return res
        errors = []
        for name in [primary] + ([fallback] if fallback else []):
            backend = self._backend(name)
            try:
                if not backend.available():
                    raise BackendUnavailable(f"{name} 不可用")
                res = backend.chat(messages, response_format=response_format,
                                   temperature=temperature, seed=seed, tools=tools)
                if res.finish_reason in ("length", "content_filter"):
                    raise ModelTruncated(
                        f"{name} finish_reason={res.finish_reason}；"
                        "截断或不完整输出不能作为业务完成")
                if not res.usable():
                    raise ModelFormatError(
                        f"{name} 返回既没有文本也没有工具调用")
                self._record(role, res, purpose)
                return res
            except ConfigurationError:
                raise
            except ModelError as exc:
                errors.append(f"{name}: {exc}")
        raise BackendUnavailable("；".join(errors) or "无可用模型后端")

    def execution(self, role: str, messages: list[dict[str, Any]], *,
                  response_format: str | None = "json") -> ChatResult:
        route = self.routing.get(role, {"primary": "local", "fallback": "deepseek"})
        return self._run(role, messages, primary=route.get("primary", "local"),
                         fallback=route.get("fallback", "deepseek"),
                         purpose="execution", response_format=response_format,
                         temperature=0.2, seed=7)

    def tool_chat(self, role: str, messages: list[dict[str, Any]], *,
                  tools: list[dict[str, Any]],
                  response_format: str | None = None) -> ChatResult:
        route = self.routing.get(role, {"primary": "local", "fallback": "deepseek"})
        return self._run(role, messages, primary=route.get("primary", "local"),
                         fallback=route.get("fallback", "deepseek"),
                         purpose="tool_chat", response_format=response_format,
                         temperature=0.1, seed=7, tools=tools)

    def judge(self, tier: str, messages: list[dict[str, str]]) -> ChatResult:
        role = f"judge_{tier.lower()}"
        route = self.routing.get(role, {"primary": "deepseek", "fallback": "local"})
        primary = route.get("primary", "deepseek")
        fallback = route.get("fallback", "local")
        if not self.offline and primary == "deepseek" and not self.deepseek.available():
            # No external key: fail closed for judges by default, unless the
            # caller explicitly allows a local fallback (offline eval does).
            self.family_collisions += 1
            raise BackendUnavailable(
                f"{tier} 需要 DeepSeek（{self.deepseek.model}），但 DEEPSEEK_API_KEY 未配置；"
                "按失败关闭处理。设置 --allow-local-judge 可显式降级到本地模型。")
        # Judges never silently fall back to another family; fail closed.
        # The caller may explicitly opt into local fallback for offline eval.
        res = self._run(role, messages, primary=primary, fallback=None,
                        purpose="judge", response_format="json",
                        temperature=0.0, seed=42)
        return res

    def judge_with_local_fallback(self, tier: str, messages: list[dict[str, str]]) -> ChatResult:
        """Explicit opt-in for local-only evaluation; records family collision."""
        route = self.routing.get(f"judge_{tier.lower()}", {"primary": "local"})
        self.family_collisions += 1
        return self._run(f"judge_{tier.lower()}", messages,
                         primary="local", fallback=None,
                         purpose="judge_local_fallback", response_format="json",
                         temperature=0.0, seed=42)

    def available_report(self) -> dict[str, Any]:
        local_models: list[str] = []
        local_error = ""
        try:
            local_models = self.local.list_models(force=True)
        except Exception as exc:
            local_error = str(exc)
        return {
            "local": {
                "available": bool(local_models),
                "models": local_models,
                "configured": self.local.model,
                "error": local_error,
            },
            "deepseek": {
                "available": self.deepseek.available(),
                "base_url": self.deepseek.base_url,
                "model": self.deepseek.model,
                "reasoner": self.deepseek.reasoner,
            },
            "offline": self.offline,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "calls": len(self.calls),
            "by_backend": {b: sum(1 for c in self.calls if c["backend"] == b)
                           for b in {c["backend"] for c in self.calls}},
            "latency_ms": sum(c["latency_ms"] for c in self.calls),
            "tokens": sum(c["prompt_tokens"] + c["completion_tokens"] for c in self.calls),
            "cost_usd": round(sum(c["cost_usd"] for c in self.calls), 6),
            "family_collisions": self.family_collisions,
        }
