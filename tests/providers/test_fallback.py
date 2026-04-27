"""tests/providers/test_fallback.py — fallback chain integration tests (Phase 6).

Uses two in-process synthetic providers registered for the duration of each
test.  No network calls.  The registry is snapshot-isolated per test.

Exit criteria covered:
  EC-6.3 — all tests in this file pass
  Verifies: (a) first provider succeeds → second not tried
             (b) ProviderUnavailable on first → second tried and succeeds
             (c) ProviderError on first → chain halted, second NOT tried
             (d) all providers fail → AllProvidersFailedError with all causes
             (e) asyncio.TimeoutError counted as ProviderUnavailable (chain continues)
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock

from azathoth.providers.base import (
    AllProvidersFailedError,
    LLMResponse,
    ProviderAuthError,
    ProviderError,
    ProviderUnavailable,
    ToolSpec,
)
from azathoth.providers.registry import _PROVIDERS


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Snapshot + restore _PROVIDERS so each test gets a clean slate."""
    snapshot = dict(_PROVIDERS)
    yield
    _PROVIDERS.clear()
    _PROVIDERS.update(snapshot)


def _fake_response(name: str, text: str = "ok") -> LLMResponse:
    return LLMResponse(text=text, provider_name=name, model="fake-model")


def _make_provider(name: str, *, raises=None, text: str = "ok", delay: float = 0.0):
    """Factory for minimal Provider-conforming instances."""

    class _P:
        def __init__(self) -> None:
            self.name = name
            self.supports_native_tools = True
            self.call_count = 0

        async def generate(
            self,
            system_prompt: str,
            user_message: str,
            *,
            json_mode: bool = False,
            tools: list[ToolSpec] | None = None,
        ) -> LLMResponse:
            self.call_count += 1
            if delay:
                await asyncio.sleep(delay)
            if raises:
                raise raises
            return _fake_response(name, text)

    return _P


def _register_pair(name1: str, cls1, name2: str, cls2):
    """Register two providers directly in the registry (bypasses conformance check)."""
    _PROVIDERS[name1] = cls1
    _PROVIDERS[name2] = cls2


# ── Test (a): first provider succeeds ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_first_provider_success_short_circuits(monkeypatch):
    """When p1 succeeds, p2 must never be instantiated."""
    p1_cls = _make_provider("p1", text="from p1")
    p2_cls = _make_provider("p2", text="from p2")
    _register_pair("p1", p1_cls, "p2", p2_cls)

    call_log: list[str] = []
    original_p1 = p1_cls

    class TrackP1(p1_cls):  # type: ignore[valid-type]
        async def generate(self, *args, **kw):
            call_log.append("p1")
            return await super().generate(*args, **kw)

    class TrackP2(p2_cls):  # type: ignore[valid-type]
        async def generate(self, *args, **kw):
            call_log.append("p2")
            return await super().generate(*args, **kw)

    _PROVIDERS["p1"] = TrackP1
    _PROVIDERS["p2"] = TrackP2

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    from azathoth.core.llm import generate

    result = await generate("sys", "user")

    assert result == "from p1"
    assert call_log == ["p1"]  # p2 never called


# ── Test (b): ProviderUnavailable on p1 → p2 called ──────────────────────────


@pytest.mark.asyncio
async def test_unavailable_triggers_fallback(monkeypatch):
    """ProviderUnavailable on p1 must cause p2 to be tried."""
    p1_cls = _make_provider("p1", raises=ProviderUnavailable("p1 down"))
    p2_cls = _make_provider("p2", text="from p2")
    _register_pair("p1", p1_cls, "p2", p2_cls)

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    from azathoth.core.llm import generate

    result = await generate("sys", "user")

    assert result == "from p2"


# ── Test (c): non-retryable ProviderError halts chain ─────────────────────────


@pytest.mark.asyncio
async def test_non_retryable_error_halts_chain(monkeypatch):
    """ProviderAuthError (non-retryable) must stop the chain; p2 must NOT be tried."""
    call_log: list[str] = []

    class P1:
        name = "p1"
        supports_native_tools = True

        async def generate(self, *a, **k):
            call_log.append("p1")
            raise ProviderAuthError("auth failed")

    class P2:
        name = "p2"
        supports_native_tools = True

        async def generate(self, *a, **k):
            call_log.append("p2")
            return _fake_response("p2")

    _PROVIDERS["p1"] = P1
    _PROVIDERS["p2"] = P2

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    from azathoth.core.llm import generate

    with pytest.raises(ProviderAuthError):
        await generate("sys", "user")

    assert "p2" not in call_log


# ── Test (d): all providers fail → AllProvidersFailedError ────────────────────


@pytest.mark.asyncio
async def test_all_providers_fail_raises_all_failed_error(monkeypatch):
    """When every provider in the chain raises ProviderUnavailable,
    AllProvidersFailedError must be raised containing all causes."""

    class P1:
        name = "p1"
        supports_native_tools = True

        async def generate(self, *a, **k):
            raise ProviderUnavailable("p1 gone")

    class P2:
        name = "p2"
        supports_native_tools = True

        async def generate(self, *a, **k):
            raise ProviderUnavailable("p2 gone")

    _PROVIDERS["p1"] = P1
    _PROVIDERS["p2"] = P2

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    from azathoth.core.llm import generate

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await generate("sys", "user")

    err = exc_info.value
    assert len(err.causes) == 2
    assert all(isinstance(c, ProviderUnavailable) for c in err.causes)
    assert "p1 gone" in str(err)
    assert "p2 gone" in str(err)


# ── Test (e): asyncio.TimeoutError treated as ProviderUnavailable ─────────────


@pytest.mark.asyncio
async def test_timeout_falls_through_to_next_provider(monkeypatch):
    """A provider that times out must be skipped (chain continues to p2)."""

    class P1Slow:
        name = "p1"
        supports_native_tools = True

        async def generate(self, *a, **k):
            await asyncio.sleep(999)  # will be cancelled by wait_for
            return _fake_response("p1")  # pragma: no cover

    class P2Fast:
        name = "p2"
        supports_native_tools = True

        async def generate(self, *a, **k):
            return _fake_response("p2", text="p2 quick")

    _PROVIDERS["p1"] = P1Slow
    _PROVIDERS["p2"] = P2Fast

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=0.05,  # 50 ms — p1's 999 s sleep will be cut
        ),
    )

    from azathoth.core.llm import generate

    result = await generate("sys", "user")

    assert result == "p2 quick"


# ── EC-6.1 config default ─────────────────────────────────────────────────────


def test_config_default_providers():
    """EC-6.1: default llm_providers must be ['gemini', 'ollama']."""
    from azathoth.config import Settings

    s = Settings()
    assert s.llm_providers == ["gemini", "ollama"]


# ── EC-6.5 env var parsing ────────────────────────────────────────────────────


def test_providers_env_json_list(monkeypatch):
    """EC-6.5: JSON-list form must be parsed correctly."""
    monkeypatch.setenv("AZATHOTH_LLM_PROVIDERS", '["nonexistent","gemini"]')
    from azathoth.config import Settings

    s = Settings()
    assert s.llm_providers == ["nonexistent", "gemini"]


def test_providers_env_csv(monkeypatch):
    """EC-6.5 (bonus): comma-separated form must also work."""
    monkeypatch.setenv("AZATHOTH_LLM_PROVIDERS", "nonexistent,gemini")
    from azathoth.config import Settings

    s = Settings()
    assert s.llm_providers == ["nonexistent", "gemini"]


def test_providers_env_single(monkeypatch):
    """Single provider name (no comma, no brackets) must produce a 1-element list."""
    monkeypatch.setenv("AZATHOTH_LLM_PROVIDERS", "ollama")
    from azathoth.config import Settings

    s = Settings()
    assert s.llm_providers == ["ollama"]


# ── EC-6.2 exception hierarchy ────────────────────────────────────────────────


def test_all_providers_failed_is_provider_error():
    """EC-6.2: AllProvidersFailedError must be a subclass of ProviderError."""
    assert issubclass(AllProvidersFailedError, ProviderError)


def test_all_providers_failed_causes():
    """causes attribute must hold the list of underlying exceptions."""
    causes = [ProviderUnavailable("a"), ProviderUnavailable("b")]
    err = AllProvidersFailedError(causes)
    assert err.causes is causes


# ── Logging: no sensitive data leakage ────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_log_does_not_leak_api_key(monkeypatch, caplog):
    """Fallback log records must not contain key-shaped tokens (30+ alphanum chars)."""
    import re
    import logging

    fake_key = "A" * 35  # key-shaped token

    class P1Leaky:
        name = "p1"
        supports_native_tools = True

        async def generate(self, *a, **k):
            raise ProviderUnavailable(f"error token={fake_key}")  # key in exc message

    class P2:
        name = "p2"
        supports_native_tools = True

        async def generate(self, *a, **k):
            return _fake_response("p2")

    _PROVIDERS["p1"] = P1Leaky
    _PROVIDERS["p2"] = P2

    monkeypatch.setattr("azathoth.core.llm._load_providers", lambda: None)
    monkeypatch.setattr(
        "azathoth.config.config",
        MagicMock(
            active_providers=["p1", "p2"],
            llm_chain_timeout=30.0,
            llm_per_provider_timeout=30.0,
        ),
    )

    from azathoth.core.llm import generate

    with caplog.at_level(logging.INFO, logger="azathoth.core.llm"):
        await generate("sys", "user")

    # The fallback INFO log must not contain the raw exception message
    # (it only logs provider name, attempt_index, error_class — not str(exc))
    key_pattern = re.compile(r"[A-Za-z0-9_]{30,}")
    for record in caplog.records:
        assert not key_pattern.search(record.getMessage()), (
            f"Log record may contain sensitive token: {record.getMessage()!r}"
        )
