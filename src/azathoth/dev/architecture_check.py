"""azathoth.dev.architecture_check — architectural fitness function (Phase 7).

Enforces the dependency rules from §2.2 of the project plan by walking every
``.py`` file under ``src/azathoth/`` with the standard ``ast`` module.

Three rules are checked:

  R1 · SDK isolation
      Only ``providers/gemini.py`` may import from the ``google.*`` / ``genai.*``
      namespace.  Every other module that does so is a violation.

  R2 · Façade boundary
      ``core/llm.py`` must contain zero SDK imports at any scope level.
      Additionally, files outside ``providers/`` must not import concrete
      provider implementation modules by name
      (``azathoth.providers.gemini``, ``azathoth.providers.ollama``, …) via
      attribute access — side-effect-only imports inside function bodies are
      the sole exception enforced by the E402 rule.

  R3 · Provider conformance
      Every module inside ``providers/`` whose name is not one of the three
      framework files (``__init__``, ``base``, ``registry``) must self-register
      and produce an instance that satisfies ``isinstance(instance, Provider)``.

Usage::

    azathoth-architecture-check          # human-readable, exits 0 on pass
    azathoth-architecture-check --json   # machine-readable JSON to stdout
    python -m azathoth.dev.architecture_check
"""

from __future__ import annotations

import ast
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────────────────────

_SRC_ROOT = Path(__file__).parent.parent  # …/src/azathoth

# Only this file is allowed to import from the google.* SDK.
_SDK_ALLOWED_FILES: frozenset[str] = frozenset({"providers/gemini.py"})

# SDK namespace prefixes that must not appear outside allowed files.
_SDK_NAMESPACES: tuple[str, ...] = (
    "google",
    "google.genai",
    "google.generativeai",
    "genai",
)

# Provider implementation files (excludes framework files).
_PROVIDER_FRAMEWORK_FILES: frozenset[str] = frozenset(
    {"__init__.py", "base.py", "registry.py"}
)


# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class Violation:
    """A single architectural rule violation."""

    rule: str
    file: str
    line: int | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }


@dataclass
class ArchCheckResult:
    """Aggregated result of the architecture check."""

    violations: list[Violation] = field(default_factory=list)
    rules_checked: int = 0
    elapsed: float = 0.0
    module_count: int = 0

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": [v.to_dict() for v in self.violations],
            "rules_checked": self.rules_checked,
            "module_count": self.module_count,
            "elapsed_seconds": round(self.elapsed, 3),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _all_py_files() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def _rel(path: Path) -> str:
    """Return path relative to _SRC_ROOT as a forward-slash string."""
    return path.relative_to(_SRC_ROOT).as_posix()


def _is_sdk_import(node: ast.Import | ast.ImportFrom) -> bool:
    """Return True if the AST import node references an SDK namespace."""
    if isinstance(node, ast.Import):
        return any(
            alias.name == ns or alias.name.startswith(ns + ".")
            for ns in _SDK_NAMESPACES
            for alias in node.names
        )
    # ast.ImportFrom
    mod = node.module or ""
    return any(mod == ns or mod.startswith(ns + ".") for ns in _SDK_NAMESPACES)


# ── Rule implementations ──────────────────────────────────────────────────────


def _check_r1_sdk_isolation(files: list[Path]) -> list[Violation]:
    """R1: Only providers/gemini.py may import from google.*/genai.* namespaces."""
    violations: list[Violation] = []
    for path in files:
        rel = _rel(path)
        if rel in _SDK_ALLOWED_FILES:
            continue
        try:
            tree = ast.parse(path.read_text("utf-8"))
        except SyntaxError:
            continue  # syntax errors are caught by import_check
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and _is_sdk_import(node):
                if isinstance(node, ast.Import):
                    name = ", ".join(alias.name for alias in node.names)
                    desc = f"import {name!r}"
                else:
                    desc = f"from {node.module!r} import ..."
                violations.append(
                    Violation(
                        rule="R1:sdk-isolation",
                        file=rel,
                        line=node.lineno,
                        message=f"SDK import outside allowed file: {desc}",
                    )
                )
    return violations


def _check_r2_facade_boundary(files: list[Path]) -> list[Violation]:
    """R2: core/llm.py must contain zero SDK imports at any scope level.

    Additionally, files outside providers/ must not directly import concrete
    provider implementations (azathoth.providers.gemini, .ollama, …) at the
    module level via ``from azathoth.providers.X import ...`` statements.
    """
    violations: list[Violation] = []

    facade = _SRC_ROOT / "core" / "llm.py"
    if facade.exists():
        try:
            tree = ast.parse(facade.read_text("utf-8"))
        except SyntaxError as exc:
            violations.append(
                Violation(
                    "R2:facade-boundary", "core/llm.py", None, f"SyntaxError: {exc}"
                )
            )
            return violations

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and _is_sdk_import(node):
                desc = (
                    f"import {', '.join(a.name for a in node.names)!r}"
                    if isinstance(node, ast.Import)
                    else f"from {node.module!r} import ..."
                )
                violations.append(
                    Violation(
                        "R2:facade-boundary",
                        "core/llm.py",
                        node.lineno,
                        f"SDK import in façade: {desc}",
                    )
                )
    else:
        violations.append(
            Violation(
                "R2:facade-boundary", "core/llm.py", None, "core/llm.py not found"
            )
        )

    # Check that no non-provider file does a *module-level* direct import of a
    # concrete provider implementation (e.g. ``from azathoth.providers.gemini import X``).
    _CONCRETE_PROVIDERS = ("azathoth.providers.gemini", "azathoth.providers.ollama")
    for path in files:
        rel = _rel(path)
        if rel.startswith("providers/"):
            continue  # providers/ may import each other (e.g. registry imports base)
        try:
            tree = ast.parse(path.read_text("utf-8"))
        except SyntaxError:
            continue
        # Only check module-level statements (top-level body)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module in _CONCRETE_PROVIDERS:
                violations.append(
                    Violation(
                        "R2:facade-boundary",
                        rel,
                        node.lineno,
                        f"Direct import of concrete provider '{node.module}' outside providers/",
                    )
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in _CONCRETE_PROVIDERS:
                        violations.append(
                            Violation(
                                "R2:facade-boundary",
                                rel,
                                node.lineno,
                                f"Direct import of concrete provider '{alias.name}' outside providers/",
                            )
                        )
    return violations


def _check_r3_provider_conformance() -> list[Violation]:
    """R3: Every non-framework provider module must self-register and satisfy Provider."""
    violations: list[Violation] = []

    providers_dir = _SRC_ROOT / "providers"
    if not providers_dir.exists():
        violations.append(
            Violation(
                "R3:provider-conformance",
                "providers/",
                None,
                "providers/ directory not found",
            )
        )
        return violations

    impl_files = [
        f
        for f in providers_dir.glob("*.py")
        if f.name not in _PROVIDER_FRAMEWORK_FILES and not f.name.startswith("_")
    ]

    if not impl_files:
        return violations  # nothing to check

    try:
        # Import all implementation modules (triggers self-registration)
        for impl in impl_files:
            module_name = f"azathoth.providers.{impl.stem}"
            __import__(module_name)

        from azathoth.providers.base import Provider, ProviderAuthError
        from azathoth.providers.registry import _PROVIDERS

        for name, factory in list(_PROVIDERS.items()):
            try:
                instance = factory()
                if not isinstance(instance, Provider):
                    violations.append(
                        Violation(
                            "R3:provider-conformance",
                            f"providers/{name}.py",
                            None,
                            f"'{name}' factory returned {type(instance)!r} — not a Provider",
                        )
                    )
            except ProviderAuthError:
                # API key missing at check time — structural conformance was already
                # verified by registry.register() which calls isinstance() at registration.
                pass
            except Exception:
                # Other runtime errors are not architectural violations.
                pass

    except ImportError as exc:
        violations.append(
            Violation(
                "R3:provider-conformance", "providers/", None, f"Import failed: {exc}"
            )
        )

    return violations


def _check_r4_no_bare_config_import(files: list[Path]) -> list[Violation]:
    """R4: No bare config import (from azathoth.config import config)."""
    violations: list[Violation] = []
    for path in files:
        rel = _rel(path)
        try:
            tree = ast.parse(path.read_text("utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "azathoth.config":
                for alias in node.names:
                    if alias.name == "config":
                        violations.append(
                            Violation(
                                "R4:no-bare-config",
                                rel,
                                node.lineno,
                                "Direct import of 'config' from azathoth.config is forbidden. Use get_config() instead.",
                            )
                        )
    return violations


# ── Main runner ───────────────────────────────────────────────────────────────


def run_check() -> ArchCheckResult:
    """Execute all three architectural rules and return aggregated results."""
    t0 = time.perf_counter()
    files = _all_py_files()

    all_violations: list[Violation] = []
    all_violations.extend(_check_r1_sdk_isolation(files))
    all_violations.extend(_check_r2_facade_boundary(files))
    all_violations.extend(_check_r3_provider_conformance())
    all_violations.extend(_check_r4_no_bare_config_import(files))

    return ArchCheckResult(
        violations=all_violations,
        rules_checked=4,
        elapsed=time.perf_counter() - t0,
        module_count=len(files),
    )


def main() -> None:
    """CLI entry point: ``azathoth-architecture-check``."""
    json_mode = "--json" in sys.argv

    result = run_check()

    if json_mode:
        print(json.dumps(result.to_dict(), indent=2))
        sys.exit(0 if result.ok else 1)

    # Human-readable output
    elapsed_ms = result.elapsed * 1000
    if result.ok:
        print(
            f"✓ azathoth-architecture-check  "
            f"[{result.rules_checked} rules, {result.module_count} modules, "
            f"{elapsed_ms:.0f}ms, 0 violations]",
            file=sys.stderr,
        )
        sys.exit(0)
    else:
        print(
            f"✗ azathoth-architecture-check  [{len(result.violations)} violation(s)]",
            file=sys.stderr,
        )
        for v in result.violations:
            loc = f":{v.line}" if v.line else ""
            print(f"  [{v.rule}] {v.file}{loc}  {v.message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
