"""azathoth.core.exceptions — root exception hierarchy.

All exceptions raised by Azathoth code inherit from ``AzathothError``
so callers can catch the whole family with a single clause.

Provider-specific exceptions are defined in ``providers.base`` and
re-exported here for consumer convenience.
"""

from __future__ import annotations

from azathoth.providers.base import (
    AllProvidersFailedError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderSchemaError,
    ProviderUnavailable,
)


class AzathothError(Exception):
    """Root exception for all Azathoth errors."""


class LLMError(AzathothError):
    """Raised when an LLM façade call fails (legacy; prefer ProviderError subclasses)."""


class I18nError(AzathothError):
    """Base exception for i18n errors."""


class ConfigParseError(I18nError):
    """Raised when inlang config cannot be parsed."""


class TranslationError(I18nError):
    """Raised when translation logic fails."""


class RegistryError(I18nError):
    """Raised when registry ops fail."""


__all__ = [
    "AzathothError",
    "LLMError",
    "I18nError",
    "ConfigParseError",
    "TranslationError",
    "RegistryError",
    # Provider exceptions re-exported for consumer convenience
    "ProviderError",
    "ProviderUnavailable",
    "ProviderAuthError",
    "ProviderRateLimitError",
    "ProviderSchemaError",
    "AllProvidersFailedError",
]
