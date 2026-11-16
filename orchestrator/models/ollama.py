"""Local Qwen backend via Ollama's HTTP API."""
from __future__ import annotations

import time
from typing import Any

import requests

from .base import BackendUnavailable, ChatResult, ModelTimeout


class OllamaBackend:
    name = "local"

    def __init__(self, base_url: str, model: str,
                 fallback_models: list[str] | None = None,
                 timeout_s: int = 120, think: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback_models = fallback_models or []
        self.timeout_s = timeout_s
        self.think = think
        self._tags_cache: list[str] | None = None
        self._tags_at = 0.0

    def list_models(self, force: bool = False) -> list[str]:
        now = time.time()
        if not force and self._tags_cache is not None and now - self._tags_at < 10:
            return self._tags_cache
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=4)
            r.raise_for_status()
            self._tags_cache = [m.get("name", "") for m in r.json().get("models", [])]
            self._tags_at = now
            return self._tags_cache
        except requests.RequestException as exc:
            raise BackendUnavailable(f"Ollama 不可用：{exc}") from exc

    def resolve_model(self) -> str:
        tags = self.list_models()
        if self.model in tags:
            return self.model
        for candidate in self.fallback_models:
            if candidate in tags:
                return candidate
        raise BackendUnavailable(
            f"本地模型不存在：{self.model}；可用：{', '.join(tags[:8])}")

    def available(self) -> bool:
        try:
            return bool(self.list_models())
        except BackendUnavailable:
            return False

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None,
             response_format: str | None = None, temperature: float = 0.0,
             seed: int = 0, timeout_s: int | None = None) -> ChatResult:
        chosen = model or self.resolve_model()
        payload: dict[str, Any] = {
            "model": chosen,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "seed": seed},
            "think": self.think,
        }
        if response_format == "json":
            payload["format"] = "json"
        started = time.time()
        try:
            r = requests.post(f"{self.base_url}/api/chat", json=payload,
                              timeout=(5, timeout_s or self.timeout_s))
            r.raise_for_status()
            data = r.json()
        except requests.Timeout as exc:
            raise ModelTimeout(f"本地模型超时：{exc}") from exc
        except requests.RequestException as exc:
            raise BackendUnavailable(f"本地模型调用失败：{exc}") from exc
        message = data.get("message") or {}
        content = message.get("content", "")
        if not content and message.get("thinking"):
            # Reasoning models may put the final JSON in `thinking`; recover it.
            import re as _re
            thinking = message["thinking"]
            blocks = _re.findall(r"```(?:json)?\s*(.*?)```", thinking, _re.S)
            candidates = list(blocks)
            start, end = thinking.find("{"), thinking.rfind("}")
            if start >= 0 and end > start:
                candidates.append(thinking[start:end + 1])
            for cand in candidates:
                cand = cand.strip()
                if cand.startswith("{"):
                    content = cand
                    break
        if not content:
            raise BackendUnavailable("本地模型返回空内容")
        return ChatResult(
            content=content,
            backend=self.name,
            model=chosen,
            model_version=str(data.get("model", chosen)),
            prompt_tokens=int(data.get("prompt_eval_count", 0)),
            completion_tokens=int(data.get("eval_count", 0)),
            latency_ms=int((time.time() - started) * 1000),
            cost_usd=0.0,
            response_id=str(data.get("created_at", "")),
            raw=data,
        )
