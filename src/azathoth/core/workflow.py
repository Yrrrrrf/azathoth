import asyncio
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from pydantic import BaseModel


class GitResult(BaseModel):
    success: bool
    stdout: str
    stderr: str
    message: Optional[str] = None


async def _run_git(args: list[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """Internal helper to run git commands."""
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode().strip(), stderr.decode().strip()


async def stage_all(cwd: Optional[str] = None) -> GitResult:
    """Stages all changes (git add .)."""
    code, out, err = await _run_git(["add", "."], cwd=cwd)
    return GitResult(success=(code == 0), stdout=out, stderr=err)


async def commit(title: str, body: str, cwd: Optional[str] = None) -> GitResult:
    """Commits with a message."""
    full_msg = f"{title}\n\n{body}"

    with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp:
        tmp.write(full_msg)
        tmp_path = tmp.name

    try:
        code, out, err = await _run_git(["commit", "-F", tmp_path], cwd=cwd)
        return GitResult(success=(code == 0), stdout=out, stderr=err)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def get_diff(staged: bool = True, cwd: Optional[str] = None) -> str:
    """Gets the current git diff."""
    args = ["diff"]
    if staged:
        args.append("--staged")

    code, out, err = await _run_git(args, cwd=cwd)
    return out if code == 0 else err


async def get_latest_tag(cwd: Optional[str] = None) -> Optional[str]:
    """Gets the most recent git tag."""
    code, out, err = await _run_git(["describe", "--tags", "--abbrev=0"], cwd=cwd)
    return out if code == 0 else None


async def get_log_since(tag: str, cwd: Optional[str] = None) -> str:
    """Gets commit log since a specific tag."""
    code, out, err = await _run_git(
        ["log", f"{tag}..HEAD", "--pretty=format:- %s"], cwd=cwd
    )
    return out if code == 0 else ""


async def create_release(
    tag: str, notes: str, is_prerelease: bool = False
) -> GitResult:
    """
    Creates a release using 'gh' CLI.
    """
    # First, tag and push
    t_code, t_out, t_err = await _run_git(["tag", tag])
    if t_code != 0:
        return GitResult(
            success=False, stdout=t_out, stderr=t_err, message="Tagging failed"
        )

    p_code, p_out, p_err = await _run_git(["push", "origin", tag])
    if p_code != 0:
        return GitResult(
            success=False, stdout=p_out, stderr=p_err, message="Pushing tag failed"
        )

    # Use gh CLI
    cmd = [
        "gh",
        "release",
        "create",
        tag,
        "--notes",
        notes,
        "--title",
        f"Release {tag}",
    ]
    if is_prerelease:
        cmd.append("--prerelease")

    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    return GitResult(
        success=(process.returncode == 0),
        stdout=stdout.decode().strip(),
        stderr=stderr.decode().strip(),
    )
