"""tests/core/test_llm.py — LLM façade unit tests (Phase 3 rewrite)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from azathoth.core.llm import LLMError, generate, generate_with_tools
from azathoth.providers.base import (
    AllProvidersFailedError,
    LLMResponse,
    ProviderError,
    ProviderUnavailable,
    ToolSpec,
)


# ── Helpers / fixtures ────────────────────────────────────────────────────────


def _make_fake_provider(
    name: str = "fake", text: str = "hello", raises=None, tools_support: bool = True
):
    """Build a minimal Provider-conforming object."""

    class _Fake:
        def __init__(self):
            self.name = name
            self.supports_native_tools = tools_support

        async def generate(
            self, system_prompt, user_message, *, json_mode=False, tools=None
        ):
            if raises:
                raise raises
            return LLMResponse(text=text, provider_name=name, model="fake-model")

    return _Fake()


@pytest.fixture
def patch_providers(monkeypatch):
    """Utility: patch the _load_providers side-effect and registry.get_provider."""

    def _patch(provider):
        monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
        monkeypatch.setattr(
            "azathoth.providers.registry.get_provider",
            lambda name: provider,
        )
        monkeypatch.setattr(
            "azathoth.config.config",
            MagicMock(
                active_providers=["fake"],
                llm_chain_timeout=30.0,
                llm_per_provider_timeout=30.0,
            ),
        )

    return _patch


# ── generate() — basic ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_returns_text(patch_providers):
    patch_providers(_make_fake_provider(text="world"))
    result = await generate("sys", "user")
    assert result == "world"


@pytest.mark.asyncio
async def test_generate_provider_unavailable_falls_through(monkeypatch):
    """First provider raises ProviderUnavailable → second succeeds."""
    p1 = _make_fake_provider("p1", raises=ProviderUnavailable("down"))
    p2 = _make_fake_provider("p2", text="from p2")

    call_count = {"n": 0}

    def _get(name):
        call_count["n"] += 1
        return p1 if name == "p1" else p2

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr("azathoth.providers.registry.get_provider", _get)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    result = await generate("sys", "user")
    assert result == "from p2"
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_generate_non_retryable_halts_chain(monkeypatch):
    """ProviderError (non-retryable) stops chain immediately."""
    p1 = _make_fake_provider("p1", raises=ProviderError("auth failed"))
    p2 = _make_fake_provider("p2", text="should not reach")

    call_order = []

    def _get(name):
        call_order.append(name)
        return p1 if name == "p1" else p2

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr("azathoth.providers.registry.get_provider", _get)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    with pytest.raises(ProviderError):
        await generate("sys", "user")

    assert "p2" not in call_order  # chain halted after p1


@pytest.mark.asyncio
async def test_all_providers_fail_raises_all_failed(monkeypatch):
    p1 = _make_fake_provider("p1", raises=ProviderUnavailable("p1 down"))
    p2 = _make_fake_provider("p2", raises=ProviderUnavailable("p2 down"))

    def _get(name):
        return p1 if name == "p1" else p2

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr("azathoth.providers.registry.get_provider", _get)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await generate("sys", "user")

    assert len(exc_info.value.causes) == 2


# ── generate() — provider override ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_provider_override(monkeypatch):
    """provider= kwarg overrides config chain."""
    fake = _make_fake_provider("override", text="override result")
    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr("azathoth.providers.registry.get_provider", lambda name: fake)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["gemini"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    result = await generate("sys", "user", provider="override")
    assert result == "override result"


# ── LLMError backward compat ──────────────────────────────────────────────────


def test_llm_error_is_alias_for_provider_error():
    """LLMError must remain importable and be ProviderError (legacy compat)."""
    assert LLMError is ProviderError


# ── generate_with_tools ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_with_tools_native_path(monkeypatch):
    """Native tool support: tools passed directly to provider."""
    from azathoth.providers.base import ToolCall

    tc = ToolCall(name="search", arguments={"q": "test"})
    fake_response = LLMResponse(
        text="", tool_calls=[tc], provider_name="fake", model="fake-model"
    )

    class _FakeWithTools:
        name = "fake"
        supports_native_tools = True

        async def generate(
            self, system_prompt, user_message, *, json_mode=False, tools=None
        ):
            return fake_response

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr(
        "azathoth.providers.registry.get_provider", lambda name: _FakeWithTools()
    )
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["fake"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    spec = ToolSpec(name="search", description="Search", parameters_schema={})
    result = await generate_with_tools("sys", "user", [spec])
    assert isinstance(result, LLMResponse)
    assert result.tool_calls[0].name == "search"


@pytest.mark.asyncio
async def test_generate_with_tools_emulator_path(monkeypatch):
    """Emulator path: provider without native tools receives enriched system prompt."""
    import json as _json

    tool_response = _json.dumps({"tool_calls": [{"name": "fn", "arguments": {"x": 1}}]})

    class _FakeNoTools:
        name = "fake"
        supports_native_tools = False
        received_tools = None

        async def generate(
            self, system_prompt, user_message, *, json_mode=False, tools=None
        ):
            _FakeNoTools.received_tools = tools
            return LLMResponse(
                text=tool_response, provider_name="fake", model="fake-model"
            )

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr(
        "azathoth.providers.registry.get_provider", lambda name: _FakeNoTools()
    )
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["fake"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    spec = ToolSpec(name="fn", description="A function", parameters_schema={})
    result = await generate_with_tools("sys", "user", [spec])

    # Tools not passed natively (emulator handles it via system prompt)
    assert _FakeNoTools.received_tools is None
    # Tool calls parsed from JSON response text
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "fn"
    assert result.tool_calls[0].arguments == {"x": 1}
