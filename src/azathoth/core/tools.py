"""azathoth.core.tools — universal tool-calling layer (Phase 5).

Responsibilities:
  1. ``ToolSpec`` (re-exported from providers.base) — canonical tool description.
  2. ``tool_spec_from_pydantic`` — derive a ``ToolSpec`` from a Pydantic model.
  3. ``render_tools_as_json_spec`` — serialize tool catalog for prompt injection
     (the JSON-mode emulator path used when a provider lacks native tool support).
  4. ``parse_tool_calls_from_json`` — parse the model's JSON output back into
     ``ToolCall`` instances.
  5. ``dispatch`` — execute a ``ToolCall`` against a registry of callables.

This module makes NO network calls and knows nothing about provider internals.
The emulator path is orchestrated by ``core/llm.py``, not here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Mapping

from pydantic import BaseModel

from azathoth.providers.base import ToolCall, ToolSpec

log = logging.getLogger(__name__)

__all__ = [
    "ToolSpec",
    "ToolCall",
    "tool_spec_from_pydantic",
    "render_tools_as_json_spec",
    "parse_tool_calls_from_json",
    "dispatch",
]

# ── Schema helpers ────────────────────────────────────────────────────────────

_SCALAR_DEFS_KEYS = ("$defs", "definitions")


def _flatten_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline ``$defs`` / ``definitions`` into the schema properties.

    Some providers do not follow JSON Schema ``$ref`` pointers, so we
    flatten them to a self-contained object with no external references.
    This is a best-effort shallow flattening; deeply nested refs are left
    as-is (they work on providers that do support refs).
    """
    defs: dict[str, Any] = {}
    for key in _SCALAR_DEFS_KEYS:
        defs.update(schema.get(key, {}))

    if not defs:
        return schema

    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].split("/")[-1]
                if ref_name in defs:
                    return _resolve(defs[ref_name])
            return {
                k: _resolve(v) for k, v in node.items() if k not in _SCALAR_DEFS_KEYS
            }
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        return node

    return _resolve(schema)  # type: ignore[return-value]


def tool_spec_from_pydantic(
    model: type[BaseModel], *, name: str = "", description: str = ""
) -> ToolSpec:
    """Derive a ``ToolSpec`` from a Pydantic model class.

    Args:
        model:       A Pydantic ``BaseModel`` subclass whose fields describe
                     the tool's arguments.
        name:        Override the tool name.  Defaults to the model's
                     class name converted to snake_case.
        description: Override the description.  Defaults to the model's
                     docstring (first line).

    Returns:
        A ``ToolSpec`` with a flattened JSON Schema 2020-12 ``parameters_schema``.

    Example::

        class WeatherArgs(BaseModel):
            city: str
            units: str = "celsius"

        spec = tool_spec_from_pydantic(WeatherArgs)
        assert spec.parameters_schema["properties"]["city"]["type"] == "string"
    """
    raw_schema = model.model_json_schema()
    flat_schema = _flatten_schema(raw_schema)

    # Strip Pydantic's top-level title / description from the schema itself
    # (they are expressed in ToolSpec.name / .description instead)
    clean_schema = {
        k: v for k, v in flat_schema.items() if k not in ("title", "description")
    }

    resolved_name = name or _camel_to_snake(model.__name__)
    doc_lines = (model.__doc__ or "").strip().splitlines()
    resolved_desc = description or (
        doc_lines[0].strip() if doc_lines else model.__name__
    )

    return ToolSpec(
        name=resolved_name,
        description=resolved_desc,
        parameters_schema=clean_schema,
    )


def _camel_to_snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# ── JSON-mode emulator ────────────────────────────────────────────────────────

_EMULATOR_SYSTEM_SUFFIX = """
--- TOOL INSTRUCTIONS ---
You have access to the following tools. When you want to call a tool, respond
with a JSON object (and ONLY a JSON object) in this exact format:
{
  "tool_calls": [
    {"name": "<tool_name>", "arguments": {<argument key-value pairs>}}
  ]
}
If you do not need to call a tool, respond normally as plain text.
The available tools are:

"""


def render_tools_as_json_spec(tools: list[ToolSpec]) -> str:
    """Serialise a tool catalog as a JSON string for system-prompt injection.

    The emulator appends this to the system prompt when a provider does not
    support native tool calling.
    """
    catalog = [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters_schema,
        }
        for t in tools
    ]
    return json.dumps(catalog, indent=2)


def build_emulator_system_prompt(base_system: str, tools: list[ToolSpec]) -> str:
    """Append the tool catalog to *base_system* for the emulator path."""
    return base_system + _EMULATOR_SYSTEM_SUFFIX + render_tools_as_json_spec(tools)


def parse_tool_calls_from_json(text: str) -> list[ToolCall]:
    """Parse ``ToolCall`` instances from a model's JSON-mode response.

    The emulator path expects the model to emit a JSON object with a
    ``"tool_calls"`` key.  If the text is not a valid JSON object or does
    not contain ``"tool_calls"``, an empty list is returned (the caller
    treats the response as plain text).

    Args:
        text: Raw text from the model's response.

    Returns:
        List of ``ToolCall`` instances, possibly empty.
    """
    text = text.strip()
    if not text.startswith("{"):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    raw_calls = data.get("tool_calls", [])
    if not isinstance(raw_calls, list):
        return []

    result: list[ToolCall] = []
    for raw in raw_calls:
        if not isinstance(raw, dict):
            continue
        result.append(
            ToolCall(
                name=raw.get("name", ""),
                arguments=raw.get("arguments", {}),
                call_id=raw.get("id"),
            )
        )
    return result


# ── Tool dispatch ─────────────────────────────────────────────────────────────


def dispatch(call: ToolCall, registry: Mapping[str, Callable[..., Any]]) -> Any:
    """Execute *call* against *registry* and return the result.

    Args:
        call:     A ``ToolCall`` instance (name + arguments).
        registry: Mapping of tool name → callable.  The callable is invoked
                  with ``**call.arguments``.

    Returns:
        Whatever the matched callable returns.

    Raises:
        KeyError:  If the tool name is not in *registry*.
        TypeError: If the arguments do not match the callable's signature.
    """
    if call.name not in registry:
        raise KeyError(
            f"Tool '{call.name}' not found in dispatch registry. "
            f"Available: {sorted(registry.keys())}"
        )
    fn = registry[call.name]
    log.debug("dispatch tool=%s arguments=%r", call.name, call.arguments)
    return fn(**call.arguments)
