"""azathoth.core.serde — JSON file I/O.

One storage backend (the filesystem), forever. ``read_json`` / ``write_json``
is the honest abstraction — no repository pattern, no ORM.
"""

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """Read and parse a JSON file.

    Raises:
        OSError:            If the file cannot be opened.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Write *data* to *path* as JSON, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
