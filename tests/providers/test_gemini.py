"""tests/providers/test_gemini.py — GeminiProvider unit tests (mocked SDK)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from azathoth.providers.base import (
    LLMResponse,
    ProviderAuthError,
    ProviderError,
    ProviderUnavailable,
    ToolSpec,
)


@pytest.fixture
def provider():
    """Return a GeminiProvider with a fake key — no network calls."""
    from azathoth.providers.gemini import GeminiProvider

    return GeminiProvider(api_key="fake-key", model="gemini-test")


@pytest.fixture
def mock_genai_client(provider):
    """Patch genai.Client so no real SDK calls are made."""
    with patch("azathoth.providers.gemini.genai.Client") as ClientCls:
        client = MagicMock()
        ClientCls.return_value = client
        yield client


# ── generate() — basic ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_returns_text(provider, mock_genai_client):
    mock_genai_client.models.generate_content.return_value.text = "hello"
    mock_genai_client.models.generate_content.return_value.candidates = []
    mock_genai_client.models.generate_content.return_value.usage_metadata = MagicMock(
        prompt_token_count=10, candidates_token_count=5
    )
    result = await provider.generate("sys", "user")
    assert isinstance(result, LLMResponse)
    assert result.text == "hello"
    assert result.provider_name == "gemini"
    assert result.prompt_tokens == 10


@pytest.mark.asyncio
async def test_generate_json_mode(provider, mock_genai_client):
    mock_genai_client.models.generate_content.return_value.text = '{"ok": true}'
    mock_genai_client.models.generate_content.return_value.candidates = []
    mock_genai_client.models.generate_content.return_value.usage_metadata = MagicMock(
        prompt_token_count=None, candidates_token_count=None
    )
    result = await provider.generate("sys", "user", json_mode=True)
    call_kwargs = mock_genai_client.models.generate_content.call_args
    cfg = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
    assert cfg.response_mime_type == "application/json"


@pytest.mark.asyncio
async def test_generate_passes_system_instruction(provider, mock_genai_client):
    mock_genai_client.models.generate_content.return_value.text = "ok"
    mock_genai_client.models.generate_content.return_value.candidates = []
    mock_genai_client.models.generate_content.return_value.usage_metadata = MagicMock(
        prompt_token_count=None, candidates_token_count=None
    )
    await provider.generate("Be helpful", "2+2?")
    call_kwargs = mock_genai_client.models.generate_content.call_args
    cfg = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
    assert cfg.system_instruction == "Be helpful"


# ── error mapping ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_network_error_maps_to_unavailable(provider, mock_genai_client):
    mock_genai_client.models.generate_content.side_effect = Exception(
        "connection refused"
    )
    with pytest.raises(ProviderUnavailable):
        await provider.generate("sys", "user")


@pytest.mark.asyncio
async def test_auth_error_maps_to_auth_error(provider, mock_genai_client):
    mock_genai_client.models.generate_content.side_effect = Exception(
        "API key not valid"
    )
    with pytest.raises(ProviderAuthError):
        await provider.generate("sys", "user")


@pytest.mark.asyncio
async def test_generic_error_maps_to_provider_error(provider, mock_genai_client):
    mock_genai_client.models.generate_content.side_effect = RuntimeError(
        "something broke"
    )
    with pytest.raises(ProviderError):
        await provider.generate("sys", "user")


# ── attributes ────────────────────────────────────────────────────────────────


def test_provider_name():
    from azathoth.providers.gemini import GeminiProvider

    assert GeminiProvider.name == "gemini"


def test_supports_native_tools():
    from azathoth.providers.gemini import GeminiProvider

    assert GeminiProvider.supports_native_tools is True


# ── tool call translation ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_with_tools_passes_tool_declarations(
    provider, mock_genai_client
):
    mock_genai_client.models.generate_content.return_value.text = ""
    mock_genai_client.models.generate_content.return_value.candidates = []
    mock_genai_client.models.generate_content.return_value.usage_metadata = MagicMock(
        prompt_token_count=None, candidates_token_count=None
    )
    spec = ToolSpec(
        name="search",
        description="Search the web",
        parameters_schema={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    await provider.generate("sys", "user", tools=[spec])
    call_kwargs = mock_genai_client.models.generate_content.call_args
    assert "tools" in (call_kwargs.kwargs or {})
