"""DeepSeek / deepseekharness OpenAI-compatible backend."""
from __future__ import annotations

import time
from typing import Any

import requests

from .base import BackendUnavailable, ChatResult, ModelTimeout


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

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None,
             response_format: str | None = None, temperature: float = 0.0,
             seed: int = 0, timeout_s: int | None = None) -> ChatResult:
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
            raise BackendUnavailable(f"DeepSeek 调用失败：{exc}") from exc
        choices = data.get("choices") or []
        if not choices:
            raise BackendUnavailable("DeepSeek 返回无 choices")
        content = (choices[0].get("message") or {}).get("content", "")
        if not content:
            raise BackendUnavailable("DeepSeek 返回空内容")
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
        )
