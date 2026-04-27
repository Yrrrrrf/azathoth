"""tests/providers/test_registry.py — provider registry unit tests."""

from __future__ import annotations

import pytest

from azathoth.providers.base import LLMResponse, Provider, ProviderError, ToolSpec
from azathoth.providers.registry import (
    _PROVIDERS,
    get_provider,
    list_providers,
    register,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_fake(name: str = "fake", tools: bool = False):
    """Return a factory that produces a minimal Provider-conforming instance."""

    class _Fake:
        def __init__(self) -> None:
            self.name = name
            self.supports_native_tools = tools

        async def generate(
            self,
            system_prompt: str,
            user_message: str,
            *,
            json_mode: bool = False,
            tools: list[ToolSpec] | None = None,
        ) -> LLMResponse:
            return LLMResponse(text="ok", provider=self.name, model="fake-model")

    return _Fake


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate each test: snapshot the registry before and restore after."""
    snapshot = dict(_PROVIDERS)
    yield
    _PROVIDERS.clear()
    _PROVIDERS.update(snapshot)


# ── register ──────────────────────────────────────────────────────────────────


def test_register_and_list():
    register("fake", _make_fake("fake"))
    assert "fake" in list_providers()


def test_register_multiple():
    register("alpha", _make_fake("alpha"))
    register("beta", _make_fake("beta"))
    providers = list_providers()
    assert "alpha" in providers
    assert "beta" in providers


def test_list_providers_sorted():
    register("zzz", _make_fake("zzz"))
    register("aaa", _make_fake("aaa"))
    names = list_providers()
    assert names == sorted(names)


def test_register_non_callable_raises():
    with pytest.raises(TypeError):
        register("bad", "not-a-callable")  # ty: ignore[invalid-argument-type]


def test_register_empty_name_raises():
    with pytest.raises(ValueError):
        register("", _make_fake(""))


def test_register_name_mismatch_raises():
    with pytest.raises(ValueError, match="must match"):
        register("wrong-name", _make_fake("actual-name"))


def test_register_non_provider_raises():
    class NotProvider:
        pass

    with pytest.raises(ProviderError, match="Protocol"):
        register("bad", NotProvider)  # ty: ignore[invalid-argument-type]


# ── get_provider ──────────────────────────────────────────────────────────────


def test_get_provider_returns_instance():
    register("fake", _make_fake("fake"))
    p = get_provider("fake")
    assert isinstance(p, Provider)
    assert p.name == "fake"


def test_get_provider_unknown_raises_key_error():
    with pytest.raises(KeyError, match="not registered"):
        get_provider("nonexistent-xyz")


def test_get_provider_returns_fresh_instance():
    """Each call must return a new instance (not a cached singleton)."""
    register("fake", _make_fake("fake"))
    p1 = get_provider("fake")
    p2 = get_provider("fake")
    assert p1 is not p2


def test_get_provider_native_tools_flag():
    register("tools-provider", _make_fake("tools-provider", tools=True))
    p = get_provider("tools-provider")
    assert p.supports_native_tools is True
