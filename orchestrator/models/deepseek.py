"""DeepSeek / deepseekharness OpenAI-compatible backend."""
from __future__ import annotations

import time
from typing import Any

import requests

from .base import (BackendUnavailable, ChatResult, ModelAuthError,
                   ModelContextOverflow, ModelProtocolError, ModelRateLimit,
                   ModelTimeout, ModelTransientError, ModelTruncated)


def _http_error(exc: requests.RequestException) -> Exception:
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", 0) or 0
    text = ""
    try:
        text = (response.text or "")[:600] if response is not None else ""
    except Exception:
        text = ""
    if code in (401, 403):
        return ModelAuthError(f"DeepSeek 鉴权失败（{code}）：{text}")
    if code == 429:
        return ModelRateLimit(f"DeepSeek 限流（429）：{text}")
    if code == 400 and any(word in text.lower() for word in
                           ("context", "too long", "maximum")):
        return ModelContextOverflow(f"DeepSeek 上下文过长：{text}")
    if 500 <= code < 600:
        return ModelTransientError(f"DeepSeek 临时故障（{code}）：{text}")
    return ModelProtocolError(f"DeepSeek 调用失败（{code or 'network'}）：{text or exc}")


class DeepSeekBackend:
    name = "deepseekharness"

    def __init__(self, base_url: str, api_key: str, model: str,
                 reasoner: str = "deepseek-reasoner", chat_path: str = "/chat/completions",
                 timeout_s: int = 120, price_in_per_m: float = 0.5,
                 price_out_per_m: float = 1.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.reasoner = reasoner
        self.chat_path = chat_path
        self.timeout_s = timeout_s
        self.price_in_per_m = price_in_per_m
        self.price_out_per_m = price_out_per_m

    def available(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _url(self) -> str:
        if self.base_url.endswith(("/chat/completions", "/v1/chat/completions")):
            return self.base_url
        return self.base_url + self.chat_path

    def chat(self, messages: list[dict[str, Any]], *, model: str | None = None,
             response_format: str | None = None, temperature: float = 0.0,
             seed: int = 0, timeout_s: int | None = None,
             tools: list[dict[str, Any]] | None = None) -> ChatResult:
        if not self.available():
            raise BackendUnavailable("DeepSeek API Key 未配置")
        chosen = model or self.model
        payload: dict[str, Any] = {
            "model": chosen,
            "messages": messages,
            "temperature": temperature,
            "seed": seed,
            "stream": False,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        started = time.time()
        try:
            r = requests.post(self._url(), json=payload, headers=headers,
                              timeout=(5, timeout_s or self.timeout_s))
            r.raise_for_status()
            data = r.json()
        except requests.Timeout as exc:
            raise ModelTimeout(f"DeepSeek 超时：{exc}") from exc
        except requests.RequestException as exc:
            raise _http_error(exc) from exc
        choices = data.get("choices") or []
        if not choices:
            raise ModelProtocolError("DeepSeek 返回无 choices")
        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []
        finish_reason = str(choice.get("finish_reason") or "stop")
        if not content and not tool_calls:
            if finish_reason == "length":
                raise ModelTruncated("DeepSeek 输出被截断且没有可用片段")
            raise ModelProtocolError("DeepSeek 返回空内容且没有工具调用")
        usage = data.get("usage", {})
        pt = int(usage.get("prompt_tokens", 0))
        ct = int(usage.get("completion_tokens", 0))
        cost = pt / 1_000_000 * self.price_in_per_m + ct / 1_000_000 * self.price_out_per_m
        return ChatResult(
            content=content,
            backend=self.name,
            model=chosen,
            model_version=str(data.get("model", chosen)),
            prompt_tokens=pt,
            completion_tokens=ct,
            latency_ms=int((time.time() - started) * 1000),
            cost_usd=cost,
            response_id=str(data.get("id", r.headers.get("x-request-id", ""))),
            raw=data,
            tool_calls=list(tool_calls),
            finish_reason=finish_reason,
            provider_metadata={"usage": usage, "system_fingerprint":
                               data.get("system_fingerprint", ""),
                               "base_url": self.base_url},
        )
