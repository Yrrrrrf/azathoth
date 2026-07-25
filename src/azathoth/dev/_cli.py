"""azathoth.dev._cli — shared --json/human/exit harness for fitness-function CLIs.

Both ``import_check`` and ``architecture_check`` need the same three things:
parse ``--json`` off argv, print either a JSON blob or a human-readable
report, and exit non-zero on failure. This module is that harness, extracted
so a third fitness function costs zero new plumbing.
"""

import json
import sys
from collections.abc import Callable
from typing import Any


def run_cli(
    result: dict[str, Any],
    *,
    ok: bool,
    human: Callable[[dict[str, Any]], None],
    argv: list[str] | None = None,
) -> None:
    """Emit *result*, then exit 0 if *ok* else 1.

    With ``--json`` on argv, dumps *result* as JSON to stdout. Otherwise
    calls *human* to render it.
    """
    argv = sys.argv[1:] if argv is None else argv
    if "--json" in argv:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        human(result)
    sys.exit(0 if ok else 1)
