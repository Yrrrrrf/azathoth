"""azathoth.core.directives — Composite loader for coding-philosophy directives.

A master context is composed from the universal core directive plus zero or
more language directives, each rendered to Markdown and concatenated.

Format (Phase 6, per §3.7/§5.10 of plan3.md): a directive is a folder —
structured ``meta.toml`` (name, version, applies-to, rules) plus prose
``philosophy.md`` and an optional ``examples.md``. Rules are key-value data
and belong in TOML; philosophy is prose with code fences and belongs in
Markdown. There is no dual-format reader and no migration path — the format
is a cutover, not a compatibility layer.
"""

import tomllib
from pathlib import Path

from pydantic import BaseModel

from azathoth.config import get_config
from azathoth.core.exceptions import DirectiveError

_BUILTIN_DIRECTIVES_DIR = Path(__file__).parent.parent / "directives"


class DirectiveMeta(BaseModel, frozen=True):
    name: str
    version: str
    applies_to: list[str]


class Directive(BaseModel, frozen=True):
    meta: DirectiveMeta
    rules: dict[str, str]
    philosophy: str
    examples: str | None = None

    def render(self) -> str:
        """Renders the directive as a markdown string for the LLM."""
        lines = [f"# Directive: {self.meta.name} (v{self.meta.version})", ""]

        if self.rules:
            lines.append("## Rules")
            for key, value in self.rules.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        lines.append("## Philosophy")
        lines.append(self.philosophy.strip())

        if self.examples:
            lines.append("")
            lines.append("## Examples")
            lines.append(self.examples.strip())

        return "\n".join(lines)


def _load_directive_folder(folder: Path) -> Directive:
    """Load a directive from *folder*. Raises DirectiveError if malformed."""
    meta_path = folder / "meta.toml"
    philosophy_path = folder / "philosophy.md"

    if not meta_path.is_file():
        raise DirectiveError(f"Directive folder '{folder}' is missing meta.toml")
    if not philosophy_path.is_file():
        raise DirectiveError(f"Directive folder '{folder}' is missing philosophy.md")

    with open(meta_path, "rb") as f:
        data = tomllib.load(f)

    if "meta" not in data:
        raise DirectiveError(f"'{meta_path}' is missing the [meta] table")

    examples_path = folder / "examples.md"
    examples = (
        examples_path.read_text(encoding="utf-8") if examples_path.is_file() else None
    )

    return Directive(
        meta=DirectiveMeta(**data["meta"]),
        rules=data.get("rules", {}),
        philosophy=philosophy_path.read_text(encoding="utf-8"),
        examples=examples,
    )


async def load_directive(name: str) -> Directive | None:
    """Load a directive by name, searching user overrides first, then built-ins.

    Returns None only when no folder for *name* exists anywhere — a folder
    that exists but is missing required files raises DirectiveError rather
    than silently returning an empty directive.
    """
    user_dir = get_config().directives_dir / name
    builtin_dir = _BUILTIN_DIRECTIVES_DIR / name

    if user_dir.is_dir():
        return _load_directive_folder(user_dir)
    if builtin_dir.is_dir():
        return _load_directive_folder(builtin_dir)
    return None


async def get_master_context(languages: list[str]) -> str:
    """Combines core philosophy with language-specific directives."""
    directives = []

    core = await load_directive("core")
    if core:
        directives.append(core.render())

    for lang in languages:
        d = await load_directive(lang.lower())
        if d:
            directives.append(d.render())

    return "\n\n---\n\n".join(directives)
