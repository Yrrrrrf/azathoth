"""
mcp/scout.py — MCP server exposing codebase reconnaissance tools.

Presentation layer only — every tool wraps exactly one core/scout.py
primitive or use case. Runs on stdio transport via `azathoth-mcp-scout`.

Three tools, per the resequenced Plan 2 decision C:
  - scout()          — full onboarding report (ingest + stack + directives)
  - detect_stack()    — narrow stack re-check, no re-scan
  - get_directives()  — narrow directive lookup, no re-scan
"""

from pathlib import Path

from fastmcp import FastMCP

from azathoth.config import check_preview_model
from azathoth.core.directives import get_master_context
from azathoth.core.exceptions import AzathothError
from azathoth.core.scout import detect_stack as core_detect_stack
from azathoth.core.scout import scout as core_scout

mcp = FastMCP(
    name="azathoth-scout",
    instructions=(
        "Codebase reconnaissance tools. Use scout for a full onboarding report "
        "of a repository, detect_stack for a quick language/manifest check "
        "without re-scanning, and get_directives to fetch the coding "
        "philosophy for specific languages."
    ),
)


@mcp.tool()
async def scout(target_directory: str = ".") -> str:
    """Analyze a codebase: structure, primary language, entry point, and the
    project's coding-philosophy directives, in one report.

    Args:
        target_directory: Path to the repository root to scout.
    """
    try:
        report = await core_scout(target_directory)
    except AzathothError as exc:
        return f"Error: {exc}"

    return (
        f"Directory: {report.directory}\n"
        f"Primary language: {report.stack.primary_language} "
        f"(confidence: {report.stack.confidence:.0%})\n"
        f"Manifests found: {', '.join(report.stack.manifests_found) or 'none'}\n"
        f"Entry point: {report.entry_point or 'not found'}\n"
        f"Directives loaded: {', '.join(report.directives_loaded)}\n"
        f"Files: {report.result.metrics.file_count}\n\n"
        f"--- Master Context ---\n{report.master_context or '(no directives loaded)'}"
    )


@mcp.tool()
def detect_stack(target_directory: str = ".") -> str:
    """Detect the primary language and manifest files for a directory, without
    running a full scout (no ingest, no directive load).

    Args:
        target_directory: Path to the repository root to inspect.
    """
    root = Path(target_directory).resolve()
    stack = core_detect_stack(root)
    return (
        f"Primary language: {stack.primary_language}\n"
        f"Manifests found: {', '.join(stack.manifests_found) or 'none'}\n"
        f"Confidence: {stack.confidence:.0%}"
    )


@mcp.tool()
async def get_directives(languages: list[str] | None = None) -> str:
    """Fetch the coding-philosophy master context for the given languages
    (core philosophy is always included), without running a scout.

    Args:
        languages: Language directive names to load in addition to core
                   (e.g. ["python"]). Omit for core philosophy only.
    """
    context = await get_master_context(languages or [])
    return context or "(no directives loaded)"


# ── Entry point ──────────────────────────────────────────────────────────


def run():
    """Script entry point: `azathoth-mcp-scout`."""
    check_preview_model()
    mcp.run(transport="stdio")
