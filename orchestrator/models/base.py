"""Model backend interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ModelError(RuntimeError):
    pass


class ConfigurationError(ModelError):
    """Raised for an invalid model/routing configuration.

    Configuration errors are never retried and never degrade to a stub: a real
    run with a misspelled backend must stop before any output is produced.
    """


class BackendUnavailable(ModelError):
    pass


class ModelTimeout(ModelError):
    pass


class ModelFormatError(ModelError):
    pass


class ModelAuthError(ModelError):
    """Invalid credentials/permission. Never retried."""


class ModelRateLimit(ModelError):
    """Retry later with backoff; budget should be checked first."""


class ModelTransientError(ModelError):
    """Temporary provider failure; retryable."""


class ModelContextOverflow(ModelError):
    """The request exceeded the model context window."""


class ModelProtocolError(ModelError):
    """The provider returned a response the adapter cannot interpret."""


class ModelTruncated(ModelError):
    """finish_reason indicates truncation; the content is not a complete result."""


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
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def usable(self) -> bool:
        """A response is usable if it has text or a valid tool call."""
        return bool(self.content.strip()) or bool(self.tool_calls)


class ModelBackend(Protocol):
    name: str

    def available(self) -> bool: ...

    def chat(self, messages: list[dict[str, Any]], *, model: str | None = None,
             response_format: str | None = None, temperature: float = 0.0,
             seed: int = 0, timeout_s: int | None = None,
             tools: list[dict[str, Any]] | None = None) -> ChatResult: ...
