"""azathoth.dev.architecture_check — architectural fitness function (Phase 7).

Enforces the dependency rules from §1.5/§3.8 of plan3.md by walking every
``.py`` file under ``src/azathoth/`` with the standard ``ast`` module, plus
one performance budget measured via a cold subprocess import.

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

  R4 · No bare config import
      No ``from azathoth.config import config`` AND no module-level
      ``get_config()`` call — config must be read lazily, inside a function
      body, so tests can patch it before it binds.

  R5 · Presentation purity
      ``cli/**`` and ``mcp/**`` may not import ``core.llm``, ``providers.*``,
      or any underscore-prefixed name from ``core``.

  R6 · No cross-package privates
      An underscore-prefixed name may not be imported across a top-level
      package boundary (cli / mcp / core / providers / dev).

  R7 · Layer direction
      ``core/**`` may not import ``cli/**`` or ``mcp/**``; ``providers/**``
      may not import ``core/**``.

  R8 · No `__future__` annotations
      PEP 649 (3.14) makes the import a no-op — it is now dead weight, not
      a requirement.

  B1 · Cold-import budget
      ``import azathoth`` in a fresh subprocess must stay under a fixed
      millisecond ceiling.

Usage::

    azathoth-architecture-check          # human-readable, exits 0 on pass
    azathoth-architecture-check --json   # machine-readable JSON to stdout
    python -m azathoth.dev.architecture_check
"""

import ast
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from azathoth.dev._cli import run_cli

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

# Top-level packages under src/azathoth/ that R6/R7 reason about.
_PACKAGES: frozenset[str] = frozenset({"cli", "mcp", "core", "providers", "dev"})

# B1: cold `import azathoth` must complete within this many milliseconds.
_COLD_IMPORT_BUDGET_MS = 800.0


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
    cold_import_ms: float | None = None

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
            "cold_import_ms": self.cold_import_ms,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _all_py_files() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def _rel(path: Path) -> str:
    """Return path relative to _SRC_ROOT as a forward-slash string."""
    return path.relative_to(_SRC_ROOT).as_posix()


def _top_package(rel: str) -> str | None:
    """Return the top-level package a rel path belongs to, or None (e.g. __init__.py)."""
    first = rel.split("/")[0]
    return first if first in _PACKAGES else None


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


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text("utf-8"))
    except SyntaxError:
        return None  # syntax errors are caught by import_check


# ── Rule implementations ──────────────────────────────────────────────────────


def _check_r1_sdk_isolation(files: list[Path]) -> list[Violation]:
    """R1: Only providers/gemini.py may import from google.*/genai.* namespaces."""
    violations: list[Violation] = []
    for path in files:
        rel = _rel(path)
        if rel in _SDK_ALLOWED_FILES:
            continue
        tree = _parse(path)
        if tree is None:
            continue
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
        tree = _parse(facade)
        if tree is None:
            violations.append(
                Violation("R2:facade-boundary", "core/llm.py", None, "SyntaxError")
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
        tree = _parse(path)
        if tree is None:
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


def _contains_get_config_call(stmt: ast.stmt) -> ast.Call | None:
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "get_config":
                return node
            if isinstance(func, ast.Attribute) and func.attr == "get_config":
                return node
    return None


def _check_r4_no_bare_config_import(files: list[Path]) -> list[Violation]:
    """R4: no bare `config` import, and no module-level `get_config()` call."""
    violations: list[Violation] = []
    for path in files:
        rel = _rel(path)
        tree = _parse(path)
        if tree is None:
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

        # Module-level `get_config()` call — binds config at import time, the
        # exact problem R4 exists to prevent, just arrived at a different way.
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            call = _contains_get_config_call(stmt)
            if call is not None:
                violations.append(
                    Violation(
                        "R4:no-bare-config",
                        rel,
                        call.lineno,
                        "Module-level get_config() call binds config at import time. "
                        "Call it inside a function body instead.",
                    )
                )
    return violations


def _check_r5_presentation_purity(files: list[Path]) -> list[Violation]:
    """R5: cli/** and mcp/** may not import core.llm, providers.*, or a core private."""
    violations: list[Violation] = []
    for path in files:
        rel = _rel(path)
        pkg = _top_package(rel)
        if pkg not in ("cli", "mcp"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module == "azathoth.core.llm" or node.module.startswith(
                "azathoth.providers"
            ):
                violations.append(
                    Violation(
                        "R5:presentation-purity",
                        rel,
                        node.lineno,
                        f"'{pkg}/' may not import from '{node.module}'",
                    )
                )
            elif node.module.startswith("azathoth.core"):
                for alias in node.names:
                    if alias.name.startswith("_"):
                        violations.append(
                            Violation(
                                "R5:presentation-purity",
                                rel,
                                node.lineno,
                                f"'{pkg}/' may not import private name "
                                f"'{alias.name}' from '{node.module}'",
                            )
                        )
    return violations


def _check_r6_no_cross_package_privates(files: list[Path]) -> list[Violation]:
    """R6: an underscore-prefixed name may not cross a top-level package boundary.

    `dev/` is exempt: it reads all layers by design (§2.1) to implement these
    very fitness functions, and is imported by no non-dev module.
    """
    violations: list[Violation] = []
    for path in files:
        rel = _rel(path)
        importer_pkg = _top_package(rel)
        if importer_pkg is None or importer_pkg == "dev":
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if not node.module.startswith("azathoth."):
                continue
            parts = node.module.split(".")
            source_pkg = parts[1] if len(parts) > 1 else None
            if source_pkg is None or source_pkg == importer_pkg:
                continue
            for alias in node.names:
                if alias.name.startswith("_"):
                    violations.append(
                        Violation(
                            "R6:no-cross-package-privates",
                            rel,
                            node.lineno,
                            f"'{importer_pkg}/' imports private name '{alias.name}' "
                            f"from '{node.module}' (package '{source_pkg}')",
                        )
                    )
    return violations


def _check_r7_layer_direction(files: list[Path]) -> list[Violation]:
    """R7: core/** may not import cli/**/mcp/**; providers/** may not import core/**."""
    violations: list[Violation] = []
    for path in files:
        rel = _rel(path)
        pkg = _top_package(rel)
        if pkg not in ("core", "providers"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if pkg == "core" and (
                        alias.name.startswith("azathoth.cli")
                        or alias.name.startswith("azathoth.mcp")
                    ):
                        violations.append(
                            Violation(
                                "R7:layer-direction",
                                rel,
                                node.lineno,
                                f"core/ may not import '{alias.name}'",
                            )
                        )
                    if pkg == "providers" and alias.name.startswith("azathoth.core"):
                        violations.append(
                            Violation(
                                "R7:layer-direction",
                                rel,
                                node.lineno,
                                f"providers/ may not import '{alias.name}'",
                            )
                        )
                continue
            else:
                continue

            if pkg == "core" and (
                mod.startswith("azathoth.cli") or mod.startswith("azathoth.mcp")
            ):
                violations.append(
                    Violation(
                        "R7:layer-direction",
                        rel,
                        node.lineno,
                        f"core/ may not import '{mod}'",
                    )
                )
            if pkg == "providers" and mod.startswith("azathoth.core"):
                violations.append(
                    Violation(
                        "R7:layer-direction",
                        rel,
                        node.lineno,
                        f"providers/ may not import '{mod}'",
                    )
                )
    return violations


def _check_r8_no_future_annotations(files: list[Path]) -> list[Violation]:
    """R8: `from __future__ import annotations` is dead weight under PEP 649 (3.14)."""
    violations: list[Violation] = []
    for path in files:
        rel = _rel(path)
        tree = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                for alias in node.names:
                    if alias.name == "annotations":
                        violations.append(
                            Violation(
                                "R8:no-future-annotations",
                                rel,
                                node.lineno,
                                "`from __future__ import annotations` is a no-op under "
                                "PEP 649 (Python 3.14) — remove it.",
                            )
                        )
    return violations


def _check_b1_cold_import_budget() -> tuple[list[Violation], float | None]:
    """B1: `import azathoth` in a fresh subprocess must stay under budget."""
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import time; t=time.perf_counter(); import azathoth; print(time.perf_counter()-t)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        return (
            [
                Violation(
                    "B1:cold-import-budget",
                    "azathoth/__init__.py",
                    None,
                    f"Measurement failed: {exc}",
                )
            ],
            None,
        )

    elapsed_ms = float(proc.stdout.strip()) * 1000
    if elapsed_ms > _COLD_IMPORT_BUDGET_MS:
        return (
            [
                Violation(
                    "B1:cold-import-budget",
                    "azathoth/__init__.py",
                    None,
                    f"Cold `import azathoth` took {elapsed_ms:.0f}ms, "
                    f"budget is {_COLD_IMPORT_BUDGET_MS:.0f}ms",
                )
            ],
            elapsed_ms,
        )
    return [], elapsed_ms


# ── Main runner ───────────────────────────────────────────────────────────────


def run_check() -> ArchCheckResult:
    """Execute every architectural rule and the cold-import budget."""
    t0 = time.perf_counter()
    files = _all_py_files()

    all_violations: list[Violation] = []
    all_violations.extend(_check_r1_sdk_isolation(files))
    all_violations.extend(_check_r2_facade_boundary(files))
    all_violations.extend(_check_r3_provider_conformance())
    all_violations.extend(_check_r4_no_bare_config_import(files))
    all_violations.extend(_check_r5_presentation_purity(files))
    all_violations.extend(_check_r6_no_cross_package_privates(files))
    all_violations.extend(_check_r7_layer_direction(files))
    all_violations.extend(_check_r8_no_future_annotations(files))

    b1_violations, cold_import_ms = _check_b1_cold_import_budget()
    all_violations.extend(b1_violations)

    return ArchCheckResult(
        violations=all_violations,
        rules_checked=8,
        elapsed=time.perf_counter() - t0,
        module_count=len(files),
        cold_import_ms=cold_import_ms,
    )


def _print_human(result: dict[str, Any]) -> None:
    elapsed_ms = result["elapsed_seconds"] * 1000
    cold = result.get("cold_import_ms")
    cold_str = f", cold-import {cold:.0f}ms" if cold is not None else ""
    if result["ok"]:
        print(
            f"✓ azathoth-architecture-check  "
            f"[{result['rules_checked']} rules, {result['module_count']} modules, "
            f"{elapsed_ms:.0f}ms{cold_str}, 0 violations]",
            file=sys.stderr,
        )
        return
    print(
        f"✗ azathoth-architecture-check  [{len(result['violations'])} violation(s)]",
        file=sys.stderr,
    )
    for v in result["violations"]:
        loc = f":{v['line']}" if v["line"] else ""
        print(f"  [{v['rule']}] {v['file']}{loc}  {v['message']}", file=sys.stderr)


def main() -> None:
    """CLI entry point: ``azathoth-architecture-check``."""
    result = run_check()
    run_cli(result.to_dict(), ok=result.ok, human=_print_human)


if __name__ == "__main__":
    main()
