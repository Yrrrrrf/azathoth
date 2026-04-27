"""azathoth.providers — provider abstraction layer.

Public surface (re-exported here for convenience):
  - ``Provider``          — the structural typing Protocol
  - ``ToolSpec``          — canonical tool definition
  - ``ToolCall``          — model-requested tool invocation
  - ``LLMResponse``       — normalised LLM response
  - ``ProviderError``     — base non-retryable failure
  - ``ProviderUnavailable``    — retryable transport failure
  - ``ProviderAuthError``      — bad credentials
  - ``ProviderRateLimitError`` — quota exhausted
  - ``ProviderSchemaError``    — malformed request
  - ``AllProvidersFailedError`` — all chain members exhausted
  - ``register``, ``get_provider``, ``list_providers``  — registry helpers
"""

from __future__ import annotations

from azathoth.providers.base import (
    AllProvidersFailedError,
    LLMResponse,
    Provider,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderSchemaError,
    ProviderUnavailable,
    ToolCall,
    ToolSpec,
)
from azathoth.providers.registry import get_provider, list_providers, register

__all__ = [
    # Protocol
    "Provider",
    # Transport models
    "ToolSpec",
    "ToolCall",
    "LLMResponse",
    # Exceptions
    "ProviderError",
    "ProviderUnavailable",
    "ProviderAuthError",
    "ProviderRateLimitError",
    "ProviderSchemaError",
    "AllProvidersFailedError",
    # Registry
    "register",
    "get_provider",
    "list_providers",
]
