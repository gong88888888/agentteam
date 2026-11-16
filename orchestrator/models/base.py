"""Model backend interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ModelError(RuntimeError):
    pass


class BackendUnavailable(ModelError):
    pass


class ModelTimeout(ModelError):
    pass


class ModelFormatError(ModelError):
    pass


@dataclass
class ChatResult:
    content: str
    backend: str
    model: str
    model_version: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    response_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class ModelBackend(Protocol):
    name: str

    def available(self) -> bool: ...

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None,
             response_format: str | None = None, temperature: float = 0.0,
             seed: int = 0, timeout_s: int | None = None) -> ChatResult: ...
