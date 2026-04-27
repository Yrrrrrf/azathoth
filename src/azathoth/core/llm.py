"""azathoth.core.llm — LLM façade (Phase 3+).

Public surface:
  - ``generate(system, user, *, json_mode, provider)``        → str
  - ``generate_with_tools(system, user, tools, *, provider)`` → LLMResponse
  - ``LLMError``                   (legacy alias; prefer ProviderError subclasses)
  - ``ProviderError``, ``ProviderUnavailable``, ``ProviderAuthError``,
    ``ProviderRateLimitError``, ``ProviderSchemaError``, ``AllProvidersFailedError``

Consumer code imports from HERE only — never from ``providers/*`` directly.
The google-genai SDK (or any other provider SDK) is never imported here.
"""

from __future__ import annotations

import asyncio
import logging

from azathoth.providers.base import (
    AllProvidersFailedError,
    LLMResponse,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderSchemaError,
    ProviderUnavailable,
    ToolSpec,
)

log = logging.getLogger(__name__)

# ── Public re-exports (legacy compat) ─────────────────────────────────────────

# LLMError kept as an alias so existing callers (core/i18n.py, tests) don't break.
LLMError = ProviderError

__all__ = [
    "generate",
    "generate_with_tools",
    "LLMError",
    "LLMResponse",
    "ProviderError",
    "ProviderUnavailable",
    "ProviderAuthError",
    "ProviderRateLimitError",
    "ProviderSchemaError",
    "AllProvidersFailedError",
]


# ── Internal resolver ─────────────────────────────────────────────────────────


def _get_provider_chain(provider_override: str | None = None):
    """Return an ordered list of provider name strings for the resolver."""
    from azathoth.config import get_config
    config = get_config()  # late import — avoids import-time circular

    if provider_override:
        return [provider_override]
    return config.active_providers


def _load_providers() -> None:
    """Import concrete provider modules so they self-register.

    This is the ONE place in ``core/`` that imports from ``providers/*``.
    Importing the modules triggers their ``register()`` call at module level.
    """
    import azathoth.providers.gemini  # noqa: F401  (side-effect: registers "gemini")
    import azathoth.providers.ollama  # noqa: F401  (side-effect: registers "ollama")


# ── Public API ────────────────────────────────────────────────────────────────


async def generate(
    system_prompt: str,
    user_message: str,
    *,
    json_mode: bool = False,
    provider: str | None = None,
) -> str:
    """Send a prompt to the configured LLM and return the raw text response.

    Resolves the provider chain from config (or the *provider* override),
    tries each in order, falls through on ``ProviderUnavailable``, halts
    on any other ``ProviderError``.

    Args:
        system_prompt: The system instruction / framing.
        user_message:  The user turn content.
        json_mode:     Constrain the response to valid JSON.
        provider:      Override the config chain for this call only
                       (e.g. ``"ollama"``).

    Returns:
        The model's text response as a plain string.

    Raises:
        ProviderError (or subclass) on non-retryable failure.
        AllProvidersFailedError if every provider in the chain fails.
    """
    response = await _resolve(
        system_prompt, user_message, json_mode=json_mode, tools=None, provider=provider
    )
    return response.text


async def generate_with_tools(
    system_prompt: str,
    user_message: str,
    tools: list[ToolSpec],
    *,
    provider: str | None = None,
) -> LLMResponse:
    """Send a prompt with tool specs and return a full ``LLMResponse``.

    Providers with ``supports_native_tools=True`` receive the tools natively.
    Providers without native tool support fall through to the JSON-mode
    emulator in ``core/tools.py``.

    Args:
        system_prompt: System instruction.
        user_message:  User turn content.
        tools:         List of ``ToolSpec`` objects to expose to the model.
        provider:      Override the config chain for this call only.

    Returns:
        ``LLMResponse`` with ``text`` and ``tool_calls`` populated.
    """
    return await _resolve(
        system_prompt, user_message, json_mode=False, tools=tools, provider=provider
    )


async def _resolve(
    system_prompt: str,
    user_message: str,
    *,
    json_mode: bool,
    tools: list[ToolSpec] | None,
    provider: str | None,
) -> LLMResponse:
    """Core resolver — tries each provider in the chain, handles fallback."""
    from azathoth.providers.registry import get_provider
    from azathoth.core.tools import (
        build_emulator_system_prompt,
        parse_tool_calls_from_json,
    )
    from azathoth.config import get_config
    _cfg = get_config()

    _load_providers()

    chain = _get_provider_chain(provider)
    per_provider_timeout = _cfg.llm_per_provider_timeout
    causes: list[Exception] = []

    try:
        async with asyncio.timeout(_cfg.llm_chain_timeout):
            for attempt, name in enumerate(chain):
                try:
                    p = get_provider(name)
                    
                    from rich.console import Console
                    model_name = getattr(p, "model", getattr(p, "_model", "unknown"))
                    Console(stderr=True).print(f"\n🔄 Requesting [bold cyan]{name}[/] (model: [dim]{model_name}[/])")

                    # Emulator path: inject tool catalog into system prompt for providers
                    # that don't support native tool calling.
                    effective_system = system_prompt
                    effective_tools: list[ToolSpec] | None = tools
                    emulator_mode = bool(tools) and not p.supports_native_tools

                    if emulator_mode:
                        effective_system = build_emulator_system_prompt(
                            system_prompt, tools or []
                        )
                        effective_tools = None  # don't pass tools natively

                    response = await asyncio.wait_for(
                        p.generate(
                            effective_system,
                            user_message,
                            json_mode=json_mode or emulator_mode,
                            tools=effective_tools,
                        ),
                        timeout=per_provider_timeout,
                    )

                    # For emulator path: parse tool calls from the text response
                    if emulator_mode and not response.tool_calls:
                        parsed_calls = parse_tool_calls_from_json(response.text)
                        if parsed_calls:
                            response = LLMResponse(
                                text=response.text,
                                tool_calls=parsed_calls,
                                provider_name=response.provider_name,
                                model=response.model,
                                prompt_tokens=response.prompt_tokens,
                                completion_tokens=response.completion_tokens,
                            )

                    return response

                except (ProviderUnavailable, asyncio.TimeoutError) as exc:
                    log.info(
                        "Provider fallback provider=%s attempt_index=%d error_class=%s",
                        name,
                        attempt,
                        type(exc).__name__,
                    )
                    causes.append(exc)
                    continue

                except ProviderError:
                    # Non-retryable — halt chain immediately
                    raise

                except KeyError:
                    log.warning("Provider '%s' is not registered; skipping.", name)
                    causes.append(KeyError(f"Provider '{name}' not registered"))
                    continue

    except asyncio.TimeoutError as exc:
        causes.append(exc)
        
    raise AllProvidersFailedError(causes)
