"""azathoth.providers.gemini — Google Gemini provider implementation.

Implements the ``Provider`` Protocol using the ``google-genai`` SDK.
All SDK-specific logic is confined to this module; ``core/llm.py`` never
imports ``google.genai`` directly.

Tool call translation (Phase 5) is implemented here for native support.
"""

from __future__ import annotations

import logging
from typing import Any, NoReturn

from google import genai
from google.genai import types

from azathoth.providers.base import (
    LLMResponse,
    ProviderAuthError,
    ProviderError,
    ProviderSchemaError,
    ProviderUnavailable,
    ToolCall,
    ToolSpec,
)

log = logging.getLogger(__name__)

# Google SDK error strings that signal specific failure classes
_AUTH_HINTS = ("api key", "permission denied", "unauthenticated", "forbidden")
_SCHEMA_HINTS = ("invalid argument", "bad request", "schema", "malformed")


def _classify_error(exc: Exception) -> NoReturn:
    """Raise the appropriate typed ProviderError subclass for a google-genai SDK exception."""
    msg = str(exc).lower()
    exc_name = type(exc).__name__.lower()

    if any(h in msg or h in exc_name for h in _AUTH_HINTS):
        raise ProviderAuthError(f"Gemini auth failure: {exc}") from exc
    if any(h in msg or h in exc_name for h in _SCHEMA_HINTS):
        raise ProviderSchemaError(f"Gemini schema error: {exc}") from exc
    if any(
        h in msg or h in exc_name
        for h in ("timeout", "unavailable", "503", "502", "500", "connection")
    ):
        raise ProviderUnavailable(f"Gemini transport failure: {exc}") from exc
    raise ProviderError(f"Gemini error: {exc}") from exc


def _tool_spec_to_gemini(spec: ToolSpec) -> types.FunctionDeclaration:
    """Translate a canonical ``ToolSpec`` to a Gemini ``FunctionDeclaration``."""
    return types.FunctionDeclaration(
        name=spec.name,
        description=spec.description,
        parameters=spec.parameters_schema or None,  # ty: ignore[invalid-argument-type]
    )


def _parse_tool_calls(response: Any) -> list[ToolCall]:
    """Extract ``ToolCall`` instances from a Gemini response object."""
    tool_calls: list[ToolCall] = []
    try:
        if not response.candidates:
            return tool_calls
        content = response.candidates[0].content
        if not content or not content.parts:
            return tool_calls
        for part in content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                tool_calls.append(
                    ToolCall(
                        name=fc.name,
                        arguments=dict(fc.args or {}),
                        call_id=None,
                    )
                )
    except (AttributeError, IndexError, TypeError):
        pass
    return tool_calls


class GeminiProvider:
    """Google Gemini backend satisfying the ``Provider`` Protocol."""

    name: str = "gemini"
    supports_native_tools: bool = True

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        json_mode: bool = False,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        log.debug(
            "GeminiProvider.generate provider=%s model=%s prompt_preview=%.200s",
            self.name,
            self._model,
            user_message,
        )

        try:
            client = genai.Client(api_key=self._api_key)

            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
            )
            if json_mode:
                gen_config.response_mime_type = "application/json"

            gemini_tools: list[types.Tool] | None = None
            if tools:
                declarations = [_tool_spec_to_gemini(t) for t in tools]
                gemini_tools = [types.Tool(function_declarations=declarations)]

            response = client.models.generate_content(
                model=self._model,
                contents=user_message,
                config=gen_config,
                **({"tools": gemini_tools} if gemini_tools else {}),
            )

            text = response.text or ""
            tool_calls = _parse_tool_calls(response) if tools else []

            log.debug(
                "GeminiProvider.generate success provider=%s model=%s",
                self.name,
                self._model,
            )

            return LLMResponse(
                text=text,
                tool_calls=tool_calls,
                provider=self.name,
                model=self._model,
                prompt_tokens=getattr(
                    response.usage_metadata, "prompt_token_count", None
                ),
                completion_tokens=getattr(
                    response.usage_metadata, "candidates_token_count", None
                ),
            )

        except ProviderError:
            raise
        except Exception as exc:
            log.warning(
                "GeminiProvider error provider=%s error_class=%s message=%.200s",
                self.name,
                type(exc).__name__,
                str(exc),
            )
            _classify_error(exc)


def _factory() -> GeminiProvider:
    """Factory callable for the registry — reads config at call time."""
    from azathoth.config import get_config
    _cfg = get_config()  # local import to avoid circular

    api_key = _cfg.gemini_api_key.get_secret_value()
    if not api_key:
        raise ProviderAuthError(
            "Gemini API key not set. Export GEMINI_API_KEY or AZATHOTH_GEMINI_API_KEY."
        )
    return GeminiProvider(api_key=api_key, model=_cfg.gemini_model)


# Self-registration at import time
from azathoth.providers.registry import register as _register  # noqa: E402

_register("gemini", _factory)
