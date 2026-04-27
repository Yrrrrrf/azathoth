"""azathoth.providers.base — Provider Protocol contract and shared types.

This module defines:
  - The ``Provider`` Protocol: the single contract every LLM backend must satisfy.
  - Transport models: ``ToolSpec``, ``ToolCall``, ``LLMResponse`` (Pydantic, frozen).
  - Exception hierarchy:
      ProviderError (base, non-retryable)
      ├── ProviderAuthError       (bad key / no permission)
      ├── ProviderRateLimitError  (quota exhausted — non-retryable here)
      ├── ProviderSchemaError     (request payload rejected by the API)
      └── ProviderUnavailable     (retryable: 5xx, timeout, connection refused)

NO provider implementation code lives here.
NO SDK imports live here.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from collections.abc import Sequence

from pydantic import BaseModel, Field


# ── Transport models ──────────────────────────────────────────────────────────


class ToolSpec(BaseModel, frozen=True):
    """Canonical description of a callable tool exposed to the LLM.

    ``parameters_schema`` must be a JSON Schema 2020-12 object describing the
    tool's arguments.  Providers with native tool support translate this to
    their own format internally; providers without native support receive it
    via the JSON-mode emulator in ``core/tools.py``.
    """

    name: str = Field(..., description="Unique tool name (snake_case)")
    description: str = Field(
        ..., description="One-sentence tool description for the model"
    )
    parameters_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema 2020-12 object for the tool's arguments",
    )


class ToolCall(BaseModel, frozen=True):
    """A single tool invocation requested by the model."""

    name: str = Field(..., description="Name of the tool to invoke")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Parsed argument dict matching ToolSpec.parameters_schema",
    )
    call_id: str | None = Field(
        default=None,
        description="Provider-assigned call ID (preserved for multi-turn correlation)",
    )


class LLMResponse(BaseModel, frozen=True):
    """Normalised response returned by every Provider.generate() call."""

    text: str = Field(..., description="Raw text content of the model's reply")
    tool_calls: list[ToolCall] = Field(
        default_factory=list,
        description="Tool calls requested by the model (empty when none)",
    )
    provider_name: str = Field(
        ..., description="Name of the provider that produced this response"
    )
    model: str = Field(..., description="Model identifier used for the call")
    prompt_tokens: int | None = Field(
        default=None, description="Input token count if reported"
    )
    completion_tokens: int | None = Field(
        default=None, description="Output token count if reported"
    )


# ── Provider Protocol ─────────────────────────────────────────────────────────


@runtime_checkable
class Provider(Protocol):
    """Structural typing contract for every LLM backend.

    Implementors do NOT need to inherit from this class — they only need to
    expose the attributes and method with matching signatures (PEP 544).

    ``pyright --strict`` will verify conformance at type-check time.
    The registry performs an ``isinstance(instance, Provider)`` check at
    registration time thanks to ``@runtime_checkable``.
    """

    #: Unique registry key for this provider (e.g. ``"gemini"``, ``"ollama"``).
    name: str

    #: Whether this provider/model combo supports native tool calling.
    #: When ``False`` the resolver in ``core/llm.py`` wraps the call with the
    #: JSON-mode emulator from ``core/tools.py``.
    supports_native_tools: bool

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        json_mode: bool = False,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        """Send a prompt to the backend and return a normalised response.

        Args:
            system_prompt:  System / instruction turn.
            user_message:   User turn content.
            json_mode:      When ``True``, constrain the response to valid JSON.
            tools:          Tool specs to expose to the model.  ``None`` means
                            no tools.  Ignored if ``supports_native_tools`` is
                            ``False`` (the resolver handles the emulator path).

        Raises:
            ProviderUnavailable: Retryable transport failures (5xx, timeout,
                                 connection refused).  The resolver catches
                                 these and tries the next provider.
            ProviderAuthError:   Invalid API key or insufficient permissions.
            ProviderRateLimitError: Quota exhausted; retry would not help
                                    immediately.
            ProviderSchemaError: Request payload rejected by the API (bad
                                 tool spec, unsupported parameter, etc.).
            ProviderError:       Any other non-retryable provider failure.
        """
        ...  # pragma: no cover


# ── Exception hierarchy ───────────────────────────────────────────────────────


class ProviderError(Exception):
    """Base class for all provider failures.

    Non-retryable by default — subclass ``ProviderUnavailable`` for errors
    where the resolver should try the next provider in the chain.
    """


class ProviderUnavailable(ProviderError):
    """Retryable transport failure: 5xx, connection refused, read timeout.

    The fallback chain in ``core/llm.py`` catches *only* this exception class
    to decide whether to try the next provider.  Consumer code must never
    catch this directly.
    """


class ProviderAuthError(ProviderError):
    """Authentication / authorisation failure (bad key, no permission).

    Non-retryable: switching to the next provider with the same key will also
    fail.  The resolver stops the chain and re-raises immediately.
    """


class ProviderRateLimitError(ProviderError):
    """Rate limit or quota exhaustion.

    Treated as non-retryable within a single call (immediate retry of a
    different provider is fine; per-provider retry logic is Phase 8+).
    """


class ProviderSchemaError(ProviderError):
    """The request payload was rejected by the provider's API.

    Typical causes: malformed tool spec, unsupported parameter combination,
    token-count exceeded.  Non-retryable.
    """


class AllProvidersFailedError(ProviderError):
    """Raised by the resolver when every provider in the chain has been tried.

    The ``causes`` attribute holds the list of underlying exceptions in the
    order they were encountered.
    """

    def __init__(self, causes: Sequence[Exception]) -> None:
        self.causes: Sequence[Exception] = causes
        summary = "; ".join(f"{type(e).__name__}: {e}" for e in causes)
        super().__init__(f"All providers failed: {summary}")
