"""
Tests for core/llm.py — mock-based, no network calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from azathoth.core.llm import generate, LLMError


@pytest.fixture
def mock_config():
    """Provide a fake config with a valid API key."""
    with patch("azathoth.core.llm.config") as cfg:
        cfg.gemini_api_key.get_secret_value.return_value = "fake-key"
        cfg.gemini_model = "gemini-2.0-flash"
        yield cfg


@pytest.fixture
def mock_client(mock_config):
    """Patch genai.Client and return the mock instance."""
    with patch("azathoth.core.llm.genai.Client") as ClientCls:
        client = MagicMock()
        ClientCls.return_value = client
        yield client


@pytest.mark.asyncio
async def test_generate_returns_text(mock_client):
    """generate() should return the model's text response."""
    mock_client.models.generate_content.return_value.text = "hello world"
    result = await generate("system", "user")
    assert result == "hello world"


@pytest.mark.asyncio
async def test_generate_json_mode_sets_mime_type(mock_client):
    """When json_mode=True, response_mime_type should be set."""
    mock_client.models.generate_content.return_value.text = '{"ok": true}'
    await generate("system", "user", json_mode=True)

    call_kwargs = mock_client.models.generate_content.call_args
    config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
    assert config.response_mime_type == "application/json"


@pytest.mark.asyncio
async def test_generate_passes_system_instruction(mock_client):
    """System prompt should be forwarded as system_instruction."""
    mock_client.models.generate_content.return_value.text = "ok"
    await generate("Be helpful", "What is 2+2?")

    call_kwargs = mock_client.models.generate_content.call_args
    config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
    assert config.system_instruction == "Be helpful"


@pytest.mark.asyncio
async def test_generate_empty_response_raises(mock_client):
    """An empty response.text should raise LLMError."""
    mock_client.models.generate_content.return_value.text = ""
    with pytest.raises(LLMError, match="empty response"):
        await generate("system", "user")


@pytest.mark.asyncio
async def test_generate_missing_key_raises():
    """Missing API key should raise LLMError early."""
    with patch("azathoth.core.llm.config") as cfg:
        cfg.gemini_api_key.get_secret_value.return_value = ""
        cfg.gemini_model = "gemini-2.0-flash"
        with pytest.raises(LLMError, match="API key not set"):
            await generate("system", "user")


@pytest.mark.asyncio
async def test_generate_sdk_exception_wraps(mock_client):
    """SDK exceptions should be wrapped in LLMError."""
    mock_client.models.generate_content.side_effect = RuntimeError("boom")
    with pytest.raises(LLMError, match="Gemini API call failed"):
        await generate("system", "user")
