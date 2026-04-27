"""azathoth.dev.import_check — import-health fitness function.

Walks every submodule under ``azathoth.*`` via ``pkgutil.walk_packages``,
attempts to import each one, and reports failures.  Exits non-zero if any
``ImportError`` or ``SyntaxError`` is found.

Usage
-----
  uv run azathoth-import-check            # human-readable, exits 1 on failure
  uv run azathoth-import-check --json     # JSON report on stdout
  uv run python -m azathoth.dev.import_check
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import sys
import time
import traceback
from typing import Any


def _collect_modules(root_package: str) -> list[str]:
    """Return fully-qualified names of every submodule under *root_package*."""
    try:
        root = importlib.import_module(root_package)
    except (ImportError, SyntaxError):
        # The root itself is broken — report immediately.
        return []

    prefix = root_package + "."
    names: list[str] = [root_package]
    for info in pkgutil.walk_packages(root.__path__, prefix=prefix):
        names.append(info.name)
    return names


def run_check(root_package: str = "azathoth") -> dict[str, Any]:
    """Import every module under *root_package*; return a structured result dict."""
    started_at = time.monotonic()
    modules = _collect_modules(root_package)

    checked: list[str] = []
    errors: list[dict[str, str]] = []

    for name in modules:
        try:
            importlib.import_module(name)
            checked.append(name)
        except (ImportError, SyntaxError) as exc:
            errors.append(
                {
                    "module": name,
                    "error_class": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    elapsed = time.monotonic() - started_at
    return {
        "root": root_package,
        "checked": checked,
        "errors": errors,
        "total": len(checked) + len(errors),
        "elapsed_seconds": round(elapsed, 3),
    }


def _print_human(result: dict[str, Any]) -> None:
    ok = len(result["errors"]) == 0
    symbol = "✓" if ok else "✗"
    print(
        f"{symbol} azathoth-import-check  "
        f"[{result['total']} modules, {result['elapsed_seconds']}s]"
    )
    if result["errors"]:
        print(f"\n  {len(result['errors'])} import error(s):\n")
        for err in result["errors"]:
            print(f"  • {err['module']}")
            print(f"    {err['error_class']}: {err['message']}\n")


def main() -> None:
    """Entry point for the ``azathoth-import-check`` CLI script."""
    json_mode = "--json" in sys.argv
    result = run_check()

    if json_mode:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_human(result)

    sys.exit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
