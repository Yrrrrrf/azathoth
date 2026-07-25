"""azathoth.core.workflow — git workflow primitives and use cases.

Primitives (stage_all, commit, get_diff, get_latest_tag, get_log_since,
create_release) are single-purpose wrappers over core.git. Use cases
(repo_status, propose_commit, perform_commit, propose_release,
perform_release) sequence primitives and the LLM façade into the DTOs
every presentation surface renders. See §3.4 of plan3.md for the contract.
"""

import tempfile
from pathlib import Path

from pydantic import BaseModel

from azathoth.core.exceptions import GitError
from azathoth.core.git import GitResult, run_gh, run_git
from azathoth.core.llm import generate_model
from azathoth.core.prompts import get_commit_system_prompt, get_release_system_prompt
from azathoth.core.utils import estimate_tokens

# ── Primitives ───────────────────────────────────────────────────────────


async def stage_all(cwd: str | None = None) -> GitResult:
    """Stages all changes (git add .)."""
    return await run_git(["add", "."], cwd=cwd)


async def commit(title: str, body: str, cwd: str | None = None) -> GitResult:
    """Commits with a message."""
    full_msg = f"{title}\n\n{body}"

    with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp:
        tmp.write(full_msg)
        tmp_path = tmp.name

    try:
        return await run_git(["commit", "-F", tmp_path], cwd=cwd)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def get_diff(staged: bool = True, cwd: str | None = None) -> str:
    """Gets the current git diff."""
    args = ["diff"]
    if staged:
        args.append("--staged")

    result = await run_git(args, cwd=cwd)
    return result.stdout if result.success else result.stderr


async def get_latest_tag(cwd: str | None = None) -> str | None:
    """Gets the most recent git tag."""
    result = await run_git(["describe", "--tags", "--abbrev=0"], cwd=cwd)
    return result.stdout if result.success else None


async def get_log_since(tag: str, cwd: str | None = None) -> str:
    """Gets commit log since a specific tag."""
    result = await run_git(["log", f"{tag}..HEAD", "--pretty=format:- %s"], cwd=cwd)
    return result.stdout if result.success else ""


async def create_release(
    tag: str, notes: str, is_prerelease: bool = False
) -> GitResult:
    """Creates a release: tag, push, then publish via `gh release create`."""
    tag_result = await run_git(["tag", tag])
    if not tag_result.success:
        return GitResult(
            success=False,
            stdout=tag_result.stdout,
            stderr=tag_result.stderr,
            message="Tagging failed",
        )

    push_result = await run_git(["push", "origin", tag])
    if not push_result.success:
        return GitResult(
            success=False,
            stdout=push_result.stdout,
            stderr=push_result.stderr,
            message="Pushing tag failed",
        )

    cmd = ["release", "create", tag, "--notes", notes, "--title", f"Release {tag}"]
    if is_prerelease:
        cmd.append("--prerelease")

    return await run_gh(cmd)


# ── DTOs ─────────────────────────────────────────────────────────────────


class RepoStatus(BaseModel, frozen=True):
    branch: str
    staged: int
    unstaged: int
    untracked: int
    latest_tag: str | None
    commits_since_tag: int


class CommitMessage(BaseModel, frozen=True):
    title: str
    body: str = ""


class CommitProposal(BaseModel, frozen=True):
    message: CommitMessage
    diff_chars: int
    diff_tokens_estimated: int


class ReleaseNotes(BaseModel, frozen=True):
    tag: str
    notes: str


class ReleaseProposal(BaseModel, frozen=True):
    notes: ReleaseNotes
    previous_tag: str
    commit_count: int


# ── Use cases ────────────────────────────────────────────────────────────


async def repo_status(cwd: str | None = None) -> RepoStatus:
    """Structured overview: branch, staged/unstaged/untracked counts, latest tag."""
    branch_result = await run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if not branch_result.success:
        raise GitError(branch_result.stderr or "Not a git repository")

    porcelain_result = await run_git(["status", "--porcelain"], cwd=cwd)
    staged = unstaged = untracked = 0
    for line in porcelain_result.stdout.splitlines():
        if not line:
            continue
        x, y = line[0], line[1]
        if x == "?":
            untracked += 1
        elif x != " ":
            staged += 1
        if y not in (" ", "?"):
            unstaged += 1

    tag = await get_latest_tag(cwd)
    commits_since = 0
    if tag:
        log = await get_log_since(tag, cwd)
        commits_since = len(log.splitlines()) if log else 0

    return RepoStatus(
        branch=branch_result.stdout,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        latest_tag=tag,
        commits_since_tag=commits_since,
    )


async def propose_commit(
    focus: str | None = None,
    provider: str | None = None,
    cwd: str | None = None,
) -> CommitProposal:
    """Stage everything, generate a commit message from the staged diff."""
    stage_result = await stage_all(cwd)
    if not stage_result.success:
        raise GitError(stage_result.stderr or "git add failed")

    diff = await get_diff(staged=True, cwd=cwd)
    if not diff:
        raise GitError("No staged changes — nothing to commit.")

    system_prompt = get_commit_system_prompt(focus)
    message = await generate_model(
        system_prompt, diff, CommitMessage, provider=provider
    )

    return CommitProposal(
        message=message,
        diff_chars=len(diff),
        diff_tokens_estimated=estimate_tokens(diff),
    )


async def perform_commit(proposal: CommitProposal, cwd: str | None = None) -> GitResult:
    """Commit the staged changes using a previously proposed message."""
    result = await commit(proposal.message.title, proposal.message.body, cwd=cwd)
    if not result.success:
        raise GitError(result.stderr or "git commit failed")
    return result


async def propose_release(
    provider: str | None = None, cwd: str | None = None
) -> ReleaseProposal:
    """Generate release notes from the commit log since the latest tag."""
    tag = await get_latest_tag(cwd)
    if not tag:
        raise GitError("No previous tag found — cannot determine changelog.")

    log = await get_log_since(tag, cwd)
    if not log:
        raise GitError(f"No commits since {tag} — nothing to release.")

    system_prompt = get_release_system_prompt()
    user_msg = f"Previous tag: {tag}\n\nCommit log:\n{log}"
    notes = await generate_model(
        system_prompt, user_msg, ReleaseNotes, provider=provider
    )

    return ReleaseProposal(
        notes=notes,
        previous_tag=tag,
        commit_count=len(log.splitlines()),
    )


async def perform_release(
    proposal: ReleaseProposal, prerelease: bool = False
) -> GitResult:
    """Tag, push, and publish a previously proposed release."""
    result = await create_release(
        proposal.notes.tag, proposal.notes.notes, is_prerelease=prerelease
    )
    if not result.success:
        raise GitError(result.message or result.stderr or "release failed")
    return result
