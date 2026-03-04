"""
mcp/workflow.py — MCP server exposing git workflow tools.

Presentation layer only — every tool wraps exactly one core/ operation.
Runs on stdio transport via `uv run workflow`.
"""

import asyncio
import json

from fastmcp import FastMCP

from azathoth.core.workflow import (
    stage_all,
    commit,
    get_diff as core_get_diff,
    get_latest_tag,
    get_log_since,
    create_release as core_create_release,
    _run_git,
)
from azathoth.core.prompts import get_commit_system_prompt, get_release_system_prompt
from azathoth.core.llm import generate, LLMError

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
    _, branch, _ = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    _, porcelain, _ = await _run_git(["status", "--porcelain"])

    staged = unstaged = untracked = 0
    for line in porcelain.splitlines():
        if not line:
            continue
        x, y = line[0], line[1]
        if x == "?":
            untracked += 1
        elif x != " ":
            staged += 1
        if y not in (" ", "?"):
            unstaged += 1

    tag = await get_latest_tag()
    commits_since = 0
    if tag:
        log = await get_log_since(tag)
        commits_since = len(log.splitlines()) if log else 0

    return (
        f"Branch: {branch}\n"
        f"Staged: {staged}\n"
        f"Unstaged: {unstaged}\n"
        f"Untracked: {untracked}\n"
        f"Latest tag: {tag or 'none'}\n"
        f"Commits since tag: {commits_since}"
    )


@mcp.tool()
async def get_diff(staged: bool = True) -> str:
    """Get the current git diff. Set staged=True for staged changes, False for unstaged."""
    diff = await core_get_diff(staged=staged)
    return diff if diff else "(no changes)"


@mcp.tool()
async def stage_and_commit(focus: str | None = None) -> str:
    """Stage all changes, generate an AI commit message, and commit. Pass an optional focus hint to guide the message."""
    await stage_all()
    diff = await core_get_diff(staged=True)
    if not diff:
        return "No staged changes — nothing to commit."

    try:
        system_prompt = get_commit_system_prompt(focus)
        raw = await generate(system_prompt, diff, json_mode=True)
        data = json.loads(raw)
        title = data["title"]
        body = data.get("body", "")
    except LLMError as exc:
        return f"LLM error: {exc}"
    except (json.JSONDecodeError, KeyError) as exc:
        return f"Failed to parse LLM response: {exc}"

    res = await commit(title, body)
    if res.success:
        return f"✓ Committed: {title}"
    else:
        return f"✗ Commit failed: {res.stderr}"


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
    tag = await get_latest_tag()
    if not tag:
        return "No previous tag found — cannot determine changelog."

    log = await get_log_since(tag)
    if not log:
        return f"No commits since {tag} — nothing to release."

    try:
        system_prompt = get_release_system_prompt()
        user_msg = f"Previous tag: {tag}\n\nCommit log:\n{log}"
        raw = await generate(system_prompt, user_msg, json_mode=True)
        data = json.loads(raw)
        new_tag = data["tag"]
        notes = data["notes"]
    except LLMError as exc:
        return f"LLM error: {exc}"
    except (json.JSONDecodeError, KeyError) as exc:
        return f"Failed to parse LLM response: {exc}"

    res = await core_create_release(new_tag, notes, is_prerelease=pre)
    if res.success:
        return f"✓ Released {new_tag}\n\n{notes}"
    else:
        msg = f"✗ Release failed: {res.stderr}"
        if res.message:
            msg += f"\n{res.message}"
        return msg


# ── Entry point ──────────────────────────────────────────────────────────


def run():
    """Script entry point: `uv run workflow`."""
    mcp.run(transport="stdio")
