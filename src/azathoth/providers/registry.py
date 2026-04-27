"""azathoth.providers.registry — name → factory mapping for LLM providers.

Responsibilities:
  - ``register(name, factory)`` — add a new provider factory.
  - ``get_provider(name)``      — resolve a name to a live Provider instance.
  - ``list_providers()``        — enumerate registered names.

This module decides NOTHING about fallback policy or default selection.
That logic lives exclusively in ``core/llm.py``.

Providers register themselves by importing this module and calling
``register()``, typically at the bottom of their own module or via
``providers/__init__.py``.
"""

from __future__ import annotations

import logging
from typing import Callable

from azathoth.providers.base import Provider, ProviderError

log = logging.getLogger(__name__)

# Internal registry: provider name → zero-argument factory callable.
# The factory is called on demand so expensive SDK clients are only
# instantiated when actually needed.
_PROVIDERS: dict[str, Callable[[], Provider]] = {}


def register(name: str, factory: Callable[[], Provider]) -> None:
    """Register a provider factory under *name*.

    The factory must be a zero-argument callable that returns an object
    satisfying the ``Provider`` Protocol.  Conformance is verified via
    ``isinstance`` at registration time (requires ``@runtime_checkable``).

    Args:
        name:    Registry key (must match ``Provider.name`` on the instance).
        factory: Zero-argument callable returning a ``Provider`` instance.

    Raises:
        TypeError:       If the factory is not callable.
        ProviderError:   If the returned instance does not satisfy the Protocol.
        ValueError:      If *name* is empty or the factory returns an instance
                         whose ``name`` attribute does not match *name*.
    """
    if not callable(factory):
        raise TypeError(
            f"Provider factory for '{name}' must be callable, got {type(factory)!r}"
        )
    if not name:
        raise ValueError("Provider name must be a non-empty string")

    # Instantiate once for conformance check, then discard — the real
    # instance is created on demand in get_provider().
    instance = factory()
    if not isinstance(instance, Provider):
        raise ProviderError(
            f"Factory for '{name}' returned {type(instance)!r} which does not "
            "satisfy the Provider Protocol. Check that it exposes 'name', "
            "'supports_native_tools', and an async 'generate()' method."
        )
    if instance.name != name:
        raise ValueError(
            f"Provider registered as '{name}' but instance.name == '{instance.name}'. "
            "They must match."
        )

    _PROVIDERS[name] = factory
    log.debug("Registered provider '%s' via %r", name, factory)


def get_provider(name: str) -> Provider:
    """Return a fresh Provider instance for *name*.

    A new instance is created on every call so that the resolver can
    construct isolated instances per fallback attempt.

    Raises:
        KeyError: If *name* has not been registered.
    """
    if name not in _PROVIDERS:
        available = list(_PROVIDERS.keys())
        raise KeyError(
            f"Provider '{name}' is not registered. Available providers: {available}"
        )
    return _PROVIDERS[name]()


def list_providers() -> list[str]:
    """Return a sorted list of all registered provider names."""
    return sorted(_PROVIDERS.keys())
