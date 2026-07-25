"""
mcp/i18n.py — MCP server exposing i18n translation tools.

Presentation layer only — every tool wraps exactly one core/i18n.py use case.
Runs on stdio transport via `azathoth-mcp-i18n`.
"""

from pathlib import Path

from fastmcp import FastMCP

from azathoth.config import check_preview_model
from azathoth.core.i18n import (
    apply_translations,
    load_project,
)
from azathoth.core.i18n import (
    audit_project as core_audit_project,
)
from azathoth.core.i18n import (
    translate_project as core_translate_project,
)

mcp = FastMCP("azathoth-i18n")


@mcp.tool()
async def audit_project(settings_path: str) -> str:
    """Audit the translation coverage of a project.

    Args:
        settings_path: Absolute path to project.inlang/settings.json
    """
    project = load_project(Path(settings_path))
    matrix, totals = core_audit_project(project)

    report = [f"i18n Audit for {settings_path}", "-" * 40]
    for key in matrix.keys:
        status = [
            f"{locale}: {'✓' if matrix.matrix[key][locale] else '✗'}"
            for locale in project.config.locales
        ]
        report.append(f"{key}: {' | '.join(status)}")

    report.append("-" * 40)
    totals_line = [f"{c.locale}: {c.translated}/{c.total}" for c in totals]
    report.append(f"TOTALS: {' | '.join(totals_line)}")

    return "\n".join(report)


@mcp.tool()
async def translate_project(settings_path: str, full: bool = False) -> str:
    """Translate missing keys in a project using AI.

    Args:
        settings_path: Absolute path to project.inlang/settings.json
        full: If True, retranslate all keys.
    """
    project = load_project(Path(settings_path))
    outcomes = await core_translate_project(project, full=full)
    apply_translations(project, outcomes)

    lines = []
    for outcome in outcomes:
        if outcome.error:
            lines.append(f"{outcome.locale}: Failed - {outcome.error}")
        elif outcome.keys_touched == 0:
            lines.append(f"{outcome.locale}: Already up to date.")
        else:
            lines.append(f"{outcome.locale}: Translated {outcome.keys_touched} keys.")
    return "\n".join(lines)


# ── Entry point ──────────────────────────────────────────────────────────


def run():
    """Script entry point: `azathoth-mcp-i18n`."""
    check_preview_model()
    mcp.run(transport="stdio")
