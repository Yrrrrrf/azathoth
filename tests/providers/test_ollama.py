"""tests/providers/test_ollama.py — OllamaProvider unit tests (mocked httpx)."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from azathoth.providers.base import (
    LLMResponse,
    ProviderAuthError,
    ProviderSchemaError,
    ProviderUnavailable,
    ToolSpec,
)
from azathoth.providers.ollama import OllamaProvider


@pytest.fixture
def provider():
    return OllamaProvider(
        host="http://localhost:11434",
        model="test-model",
        request_timeout=10.0,
    )


def _mock_response(status: int = 200, body: dict | None = None):
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = json.dumps(body or {})
    resp.json.return_value = body or {}
    if status >= 400:
        from httpx import HTTPStatusError
        resp.raise_for_status.side_effect = HTTPStatusError("err", request=MagicMock(), response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


def _mock_client_ctx(response):
    """Return a context-manager mock wrapping an async httpx.AsyncClient."""
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ── generate() — basic ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_returns_text(provider):
    body = {"message": {"role": "assistant", "content": "hello ollama"}}
    with patch("azathoth.providers.ollama.httpx.AsyncClient", return_value=_mock_client_ctx(_mock_response(200, body))):
        result = await provider.generate("sys", "user")
    assert isinstance(result, LLMResponse)
    assert result.text == "hello ollama"
    assert result.provider == "ollama"


@pytest.mark.asyncio
async def test_generate_json_mode_sets_format(provider):
    body = {"message": {"role": "assistant", "content": '{"ok": true}'}}
    ctx = _mock_client_ctx(_mock_response(200, body))
    with patch("azathoth.providers.ollama.httpx.AsyncClient", return_value=ctx):
        await provider.generate("sys", "user", json_mode=True)
    call_kwargs = ctx.__aenter__.return_value.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["format"] == "json"


@pytest.mark.asyncio
async def test_generate_passes_messages(provider):
    body = {"message": {"role": "assistant", "content": "ok"}}
    ctx = _mock_client_ctx(_mock_response(200, body))
    with patch("azathoth.providers.ollama.httpx.AsyncClient", return_value=ctx):
        await provider.generate("Be helpful", "2+2?")
    payload = ctx.__aenter__.return_value.post.call_args.kwargs["json"]
    messages = payload["messages"]
    assert messages[0] == {"role": "system", "content": "Be helpful"}
    assert messages[1] == {"role": "user", "content": "2+2?"}


# ── error mapping ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_401_maps_to_auth_error(provider):
    body = {"error": "unauthorized"}
    with patch("azathoth.providers.ollama.httpx.AsyncClient",
               return_value=_mock_client_ctx(_mock_response(401, body))):
        with pytest.raises(ProviderAuthError):
            await provider.generate("sys", "user")


@pytest.mark.asyncio
async def test_400_maps_to_schema_error(provider):
    body = {"error": "bad request"}
    with patch("azathoth.providers.ollama.httpx.AsyncClient",
               return_value=_mock_client_ctx(_mock_response(400, body))):
        with pytest.raises(ProviderSchemaError):
            await provider.generate("sys", "user")


@pytest.mark.asyncio
async def test_500_maps_to_unavailable(provider):
    body = {"error": "internal error"}
    with patch("azathoth.providers.ollama.httpx.AsyncClient",
               return_value=_mock_client_ctx(_mock_response(500, body))):
        with pytest.raises(ProviderUnavailable):
            await provider.generate("sys", "user")


@pytest.mark.asyncio
async def test_timeout_maps_to_unavailable(provider):
    import httpx
    ctx = _mock_client_ctx(None)
    ctx.__aenter__.return_value.post.side_effect = httpx.TimeoutException("timed out")
    with patch("azathoth.providers.ollama.httpx.AsyncClient", return_value=ctx):
        with pytest.raises(ProviderUnavailable, match="timed out"):
            await provider.generate("sys", "user")


@pytest.mark.asyncio
async def test_connect_error_maps_to_unavailable(provider):
    import httpx
    ctx = _mock_client_ctx(None)
    ctx.__aenter__.return_value.post.side_effect = httpx.ConnectError("refused")
    with patch("azathoth.providers.ollama.httpx.AsyncClient", return_value=ctx):
        with pytest.raises(ProviderUnavailable, match="not reachable"):
            await provider.generate("sys", "user")


# ── tool calls ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_calls_parsed(provider):
    body = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "search", "arguments": {"q": "weather"}}}
            ],
        }
    }
    with patch("azathoth.providers.ollama.httpx.AsyncClient",
               return_value=_mock_client_ctx(_mock_response(200, body))):
        spec = ToolSpec(name="search", description="Search", parameters_schema={})
        result = await provider.generate("sys", "user", tools=[spec])
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[0].arguments == {"q": "weather"}


@pytest.mark.asyncio
async def test_tools_included_in_payload(provider):
    body = {"message": {"role": "assistant", "content": "ok"}}
    ctx = _mock_client_ctx(_mock_response(200, body))
    spec = ToolSpec(name="fn", description="A function", parameters_schema={})
    with patch("azathoth.providers.ollama.httpx.AsyncClient", return_value=ctx):
        await provider.generate("sys", "user", tools=[spec])
    payload = ctx.__aenter__.return_value.post.call_args.kwargs["json"]
    assert "tools" in payload
    assert payload["tools"][0]["function"]["name"] == "fn"
