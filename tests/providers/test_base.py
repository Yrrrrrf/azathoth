"""tests/providers/test_base.py — Provider Protocol contract unit tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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


# ── ToolSpec ──────────────────────────────────────────────────────────────────


def test_tool_spec_basic():
    spec = ToolSpec(name="get_weather", description="Fetch current weather")
    assert spec.name == "get_weather"
    assert spec.parameters_schema == {}


def test_tool_spec_with_schema():
    spec = ToolSpec(
        name="search",
        description="Search the web",
        parameters_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    )
    assert spec.parameters_schema["type"] == "object"


def test_tool_spec_frozen():
    spec = ToolSpec(name="t", description="d")
    with pytest.raises(Exception):  # frozen model
        spec.name = "other"  # type: ignore[misc]


def test_tool_spec_missing_required_fields():
    with pytest.raises(ValidationError):
        ToolSpec()  # type: ignore[call-arg]


# ── ToolCall ──────────────────────────────────────────────────────────────────


def test_tool_call_basic():
    tc = ToolCall(name="do_thing", arguments={"x": 1})
    assert tc.name == "do_thing"
    assert tc.arguments == {"x": 1}
    assert tc.call_id is None


def test_tool_call_with_id():
    tc = ToolCall(name="fn", arguments={}, call_id="abc-123")
    assert tc.call_id == "abc-123"


def test_tool_call_frozen():
    tc = ToolCall(name="fn", arguments={})
    with pytest.raises(Exception):
        tc.name = "other"  # type: ignore[misc]


# ── LLMResponse ───────────────────────────────────────────────────────────────


def test_llm_response_basic():
    r = LLMResponse(
        text="hello", provider="gemini", model="gemini-3.1-flash-lite-preview"
    )
    assert r.text == "hello"
    assert r.tool_calls == []
    assert r.prompt_tokens is None


def test_llm_response_with_tool_calls():
    tc = ToolCall(name="fn", arguments={"a": 1})
    r = LLMResponse(
        text="",
        tool_calls=[tc],
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
    )
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "fn"


def test_llm_response_missing_required():
    with pytest.raises(ValidationError):
        LLMResponse(text="hi")  # missing provider, model


# ── Exception hierarchy ───────────────────────────────────────────────────────


def test_provider_error_is_exception():
    exc = ProviderError("boom")
    assert isinstance(exc, Exception)


def test_provider_unavailable_is_retryable():
    exc = ProviderUnavailable("timeout")
    assert isinstance(exc, ProviderError)


def test_provider_auth_error_hierarchy():
    assert issubclass(ProviderAuthError, ProviderError)


def test_provider_rate_limit_hierarchy():
    assert issubclass(ProviderRateLimitError, ProviderError)


def test_provider_schema_error_hierarchy():
    assert issubclass(ProviderSchemaError, ProviderError)


def test_all_providers_failed_error():
    causes = [ProviderUnavailable("p1"), ProviderError("p2")]
    err = AllProvidersFailedError(causes)
    assert issubclass(AllProvidersFailedError, ProviderError)
    assert err.causes == causes
    assert "p1" in str(err)
    assert "p2" in str(err)


# ── Provider Protocol runtime_checkable ───────────────────────────────────────


def test_provider_is_runtime_checkable():
    """Provider is @runtime_checkable so isinstance() works."""
    assert getattr(Provider, "_is_runtime_protocol", False) or hasattr(
        Provider, "__protocol_attrs__"
    )


def test_non_provider_fails_isinstance():
    class NotAProvider:
        pass

    assert not isinstance(NotAProvider(), Provider)


def test_conforming_class_passes_isinstance():
    """A class with the right shape satisfies the Protocol at runtime."""

    class FakeProvider:
        name = "fake"
        supports_native_tools = False

        async def generate(
            self, system_prompt, user_message, *, json_mode=False, tools=None
        ): ...

    assert isinstance(FakeProvider(), Provider)
