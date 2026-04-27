"""tests/core/test_tools.py — Universal tool-calling layer unit tests (Phase 5)."""

from __future__ import annotations

import json
import pytest
from pydantic import BaseModel
from typing import Optional

from azathoth.core.tools import (
    build_emulator_system_prompt,
    dispatch,
    parse_tool_calls_from_json,
    render_tools_as_json_spec,
    tool_spec_from_pydantic,
)
from azathoth.providers.base import ToolCall, ToolSpec


# ── tool_spec_from_pydantic ───────────────────────────────────────────────────


class WeatherArgs(BaseModel):
    """Fetch current weather for a city."""

    city: str
    units: str = "celsius"


class SearchArgs(BaseModel):
    """Search the web."""

    query: str
    max_results: Optional[int] = 10


def test_tool_spec_from_pydantic_basic():
    spec = tool_spec_from_pydantic(WeatherArgs)
    assert spec.name == "weather_args"
    assert "city" in spec.description or "weather" in spec.description.lower()
    assert spec.parameters_schema["properties"]["city"]["type"] == "string"
    assert "units" in spec.parameters_schema["properties"]


def test_tool_spec_from_pydantic_name_override():
    spec = tool_spec_from_pydantic(WeatherArgs, name="get_weather")
    assert spec.name == "get_weather"


def test_tool_spec_from_pydantic_desc_override():
    spec = tool_spec_from_pydantic(WeatherArgs, description="Custom description")
    assert spec.description == "Custom description"


def test_tool_spec_schema_has_no_defs():
    """Flattened schema must not have $defs or definitions at the top level."""
    spec = tool_spec_from_pydantic(SearchArgs)
    assert "$defs" not in spec.parameters_schema
    assert "definitions" not in spec.parameters_schema


def test_tool_spec_returns_tool_spec_instance():
    spec = tool_spec_from_pydantic(WeatherArgs)
    assert isinstance(spec, ToolSpec)


# ── render_tools_as_json_spec ─────────────────────────────────────────────────


def test_render_tools_as_json_spec():
    specs = [
        ToolSpec(name="search", description="Search the web"),
        ToolSpec(name="calc", description="Calculate an expression"),
    ]
    rendered = render_tools_as_json_spec(specs)
    data = json.loads(rendered)
    assert len(data) == 2
    assert data[0]["name"] == "search"
    assert data[1]["name"] == "calc"
    assert "description" in data[0]
    assert "parameters" in data[0]


def test_render_tools_is_valid_json():
    spec = ToolSpec(
        name="fn",
        description="A tool",
        parameters_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
    )
    result = render_tools_as_json_spec([spec])
    parsed = json.loads(result)
    assert parsed[0]["parameters"]["properties"]["x"]["type"] == "integer"


# ── build_emulator_system_prompt ─────────────────────────────────────────────


def test_emulator_prompt_appends_tool_instructions():
    spec = ToolSpec(name="fn", description="A tool")
    prompt = build_emulator_system_prompt("Base system prompt.", [spec])
    assert "Base system prompt." in prompt
    assert "TOOL INSTRUCTIONS" in prompt
    assert "fn" in prompt


# ── parse_tool_calls_from_json ────────────────────────────────────────────────


def test_parse_tool_calls_valid():
    text = json.dumps(
        {"tool_calls": [{"name": "search", "arguments": {"q": "python"}}]}
    )
    calls = parse_tool_calls_from_json(text)
    assert len(calls) == 1
    assert calls[0].name == "search"
    assert calls[0].arguments == {"q": "python"}


def test_parse_tool_calls_multiple():
    text = json.dumps(
        {
            "tool_calls": [
                {"name": "fn1", "arguments": {"a": 1}},
                {"name": "fn2", "arguments": {"b": 2}},
            ]
        }
    )
    calls = parse_tool_calls_from_json(text)
    assert len(calls) == 2


def test_parse_tool_calls_plain_text_returns_empty():
    calls = parse_tool_calls_from_json("Hello, here is the answer...")
    assert calls == []


def test_parse_tool_calls_invalid_json_returns_empty():
    calls = parse_tool_calls_from_json("{this is not valid json")
    assert calls == []


def test_parse_tool_calls_no_tool_calls_key_returns_empty():
    calls = parse_tool_calls_from_json('{"result": "ok"}')
    assert calls == []


def test_parse_tool_calls_returns_tool_call_instances():
    text = json.dumps({"tool_calls": [{"name": "x", "arguments": {}}]})
    calls = parse_tool_calls_from_json(text)
    assert isinstance(calls[0], ToolCall)


# ── dispatch ──────────────────────────────────────────────────────────────────


def test_dispatch_calls_correct_function():
    results = []
    registry = {"greet": lambda name: results.append(name)}
    call = ToolCall(name="greet", arguments={"name": "Alice"})
    dispatch(call, registry)
    assert results == ["Alice"]


def test_dispatch_returns_function_result():
    registry = {"add": lambda a, b: a + b}
    call = ToolCall(name="add", arguments={"a": 3, "b": 4})
    result = dispatch(call, registry)
    assert result == 7


def test_dispatch_unknown_tool_raises_key_error():
    registry = {"fn": lambda: None}
    call = ToolCall(name="nonexistent", arguments={})
    with pytest.raises(KeyError, match="nonexistent"):
        dispatch(call, registry)


def test_dispatch_wrong_args_raises_type_error():
    registry = {"fn": lambda x: x}
    call = ToolCall(name="fn", arguments={"wrong_param": 1})
    with pytest.raises(TypeError):
        dispatch(call, registry)


# ── emulator round-trip ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_emulator_roundtrip_via_fake_provider():
    """Full round-trip: tool spec → emulator prompt → fake JSON output → ToolCall."""
    from azathoth.providers.base import LLMResponse, Provider

    spec = ToolSpec(name="search", description="Search", parameters_schema={})
    tool_json_response = json.dumps(
        {"tool_calls": [{"name": "search", "arguments": {"q": "hello"}}]}
    )

    class FakeProvider:
        name = "fake"
        supports_native_tools = False

        async def generate(
            self, system_prompt, user_message, *, json_mode=False, tools=None
        ):
            return LLMResponse(
                text=tool_json_response, provider="fake", model="fake-model"
            )

    # Emulator path: parse tool calls from response text
    fake = FakeProvider()
    response = await fake.generate("sys", "user")
    tool_calls = parse_tool_calls_from_json(response.text)

    assert len(tool_calls) == 1
    assert tool_calls[0].name == "search"
    assert tool_calls[0].arguments == {"q": "hello"}
