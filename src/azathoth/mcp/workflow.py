"""
mcp/workflow.py — MCP server exposing git workflow tools.

Presentation layer only — every tool wraps exactly one core/workflow.py
use case. Runs on stdio transport via `azathoth-mcp-workflow`.

Each tool catches `AzathothError` locally and returns the message as tool
text — an MCP tool raising is worse than an MCP tool reporting.
"""

from fastmcp import FastMCP

from azathoth.config import check_preview_model
from azathoth.core.exceptions import AzathothError
from azathoth.core.workflow import (
    get_diff as core_get_diff,
)
from azathoth.core.workflow import (
    get_latest_tag,
    get_log_since,
    perform_commit,
    perform_release,
    propose_commit,
    propose_release,
    repo_status,
)

mcp = FastMCP(
    name="azathoth-workflow",
    instructions=(
        "Git workflow automation tools. Use get_status to inspect the repo, "
        "get_diff to see changes, stage_and_commit to AI-commit, "
        "get_log to review history, and create_release to publish."
    ),
)


# ── Tools ────────────────────────────────────────────────────────────────


@mcp.tool()
async def get_status() -> str:
    """Get a structured overview of the current repo: branch, staged/unstaged/untracked counts, latest tag, and commits since tag."""
    try:
        status = await repo_status()
    except AzathothError as exc:
        return f"Error: {exc}"

    return (
        f"Branch: {status.branch}\n"
        f"Staged: {status.staged}\n"
        f"Unstaged: {status.unstaged}\n"
        f"Untracked: {status.untracked}\n"
        f"Latest tag: {status.latest_tag or 'none'}\n"
        f"Commits since tag: {status.commits_since_tag}"
    )


@mcp.tool()
async def get_diff(staged: bool = True) -> str:
    """Get the current git diff. Set staged=True for staged changes, False for unstaged."""
    diff = await core_get_diff(staged=staged)
    return diff if diff else "(no changes)"


@mcp.tool()
async def stage_and_commit(focus: str | None = None) -> str:
    """Stage all changes, generate an AI commit message, and commit. Pass an optional focus hint to guide the message."""
    try:
        proposal = await propose_commit(focus=focus)
        await perform_commit(proposal)
    except AzathothError as exc:
        return f"Error: {exc}"

    return f"✓ Committed: {proposal.message.title}"


@mcp.tool()
async def get_log() -> str:
    """Get the commit log since the latest tag. Useful before deciding to cut a release."""
    tag = await get_latest_tag()
    if not tag:
        return "No tags found — cannot determine changelog."
    log = await get_log_since(tag)
    return f"Commits since {tag}:\n{log}" if log else f"No commits since {tag}."


@mcp.tool()
async def create_release(pre: bool = False) -> str:
    """Generate AI release notes from the commit log and publish via `gh release create`."""
    try:
        proposal = await propose_release()
        await perform_release(proposal, prerelease=pre)
    except AzathothError as exc:
        return f"Error: {exc}"

    return f"✓ Released {proposal.notes.tag}\n\n{proposal.notes.notes}"


# ── Entry point ──────────────────────────────────────────────────────────


def run():
    """Script entry point: `azathoth-mcp-workflow`."""
    check_preview_model()
    mcp.run(transport="stdio")
