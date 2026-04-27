"""azathoth.providers.ollama — Local Ollama provider implementation.

Uses ``httpx.AsyncClient`` against the Ollama HTTP API at ``/api/chat``.
No ``ollama`` Python package dependency — raw HTTP keeps the dep tree lean.

Tool call translation for the native Ollama tools format is implemented
for Phase 5.  Set ``supports_native_tools = True`` — Ollama supports
the OpenAI-style tool calling spec from version 0.20.2+.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

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


def _tool_spec_to_ollama(spec: ToolSpec) -> dict[str, Any]:
    """Translate a canonical ``ToolSpec`` to the Ollama tool object format."""
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters_schema
            or {"type": "object", "properties": {}},
        },
    }


def _parse_tool_calls(raw_calls: list[dict[str, Any]]) -> list[ToolCall]:
    """Parse Ollama's ``tool_calls`` list into canonical ``ToolCall`` instances."""
    result: list[ToolCall] = []
    for raw in raw_calls:
        fn = raw.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        result.append(
            ToolCall(
                name=fn.get("name", ""),
                arguments=args,
                call_id=raw.get("id"),
            )
        )
    return result


class OllamaProvider:
    """Local Ollama backend satisfying the ``Provider`` Protocol."""

    name: str = "ollama"
    supports_native_tools: bool = True  # Ollama ≥ 0.20.2 supports native tool calls

    def __init__(self, host: str, model: str, request_timeout: float) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = request_timeout

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        json_mode: bool = False,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        log.debug(
            "OllamaProvider.generate provider=%s model=%s prompt_preview=%.200s",
            self.name,
            self._model,
            user_message,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        if tools:
            payload["tools"] = [_tool_spec_to_ollama(t) for t in tools]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._host}/api/chat", json=payload)

            if resp.status_code == 401:
                raise ProviderAuthError(f"Ollama auth failure: HTTP {resp.status_code}")
            if resp.status_code == 400:
                raise ProviderSchemaError(
                    f"Ollama rejected request (400): {resp.text[:200]}"
                )
            if resp.status_code >= 500:
                raise ProviderUnavailable(
                    f"Ollama server error: HTTP {resp.status_code} — {resp.text[:200]}"
                )
            resp.raise_for_status()

            data = resp.json()
            message = data.get("message", {})
            text = message.get("content", "")
            raw_tool_calls = message.get("tool_calls", [])
            tool_calls = _parse_tool_calls(raw_tool_calls) if raw_tool_calls else []

            usage = data.get("prompt_eval_count"), data.get("eval_count")

            log.debug(
                "OllamaProvider.generate success provider=%s model=%s",
                self.name,
                self._model,
            )

            return LLMResponse(
                text=text,
                tool_calls=tool_calls,
                provider=self.name,
                model=self._model,
                prompt_tokens=usage[0],
                completion_tokens=usage[1],
            )

        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            log.warning(
                "OllamaProvider timeout provider=%s error_class=%s",
                self.name,
                type(exc).__name__,
            )
            raise ProviderUnavailable(f"Ollama request timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            log.warning(
                "OllamaProvider connection refused provider=%s host=%s",
                self.name,
                self._host,
            )
            raise ProviderUnavailable(
                f"Ollama daemon not reachable at {self._host}: {exc}"
            ) from exc
        except Exception as exc:
            log.warning(
                "OllamaProvider error provider=%s error_class=%s message=%.200s",
                self.name,
                type(exc).__name__,
                str(exc),
            )
            raise ProviderError(f"Ollama error: {exc}") from exc


def _factory() -> OllamaProvider:
    """Factory callable for the registry — reads config at call time."""
    from azathoth.config import get_config
    _cfg = get_config()  # local import to avoid circular

    return OllamaProvider(
        host=_cfg.ollama_host,
        model=_cfg.ollama_model,
        request_timeout=_cfg.ollama_request_timeout,
    )


# Self-registration at import time
from azathoth.providers.registry import register as _register  # noqa: E402

_register("ollama", _factory)
