"""azathoth.core.git — the only module that spawns git or gh subprocesses.

Every other module — workflow, ingest, or any future capability domain —
calls ``run_git`` / ``find_git_root`` here rather than shelling out itself.
Consolidating the anti-corruption layer in one file means a future move to
a git library (pygit2, gitoxide bindings) touches exactly one file.
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel

from azathoth.core.exceptions import GitError


class GitResult(BaseModel, frozen=True):
    success: bool
    stdout: str
    stderr: str
    message: str | None = None


async def run_git(args: list[str], cwd: str | Path | None = None) -> GitResult:
    """Run a git subcommand and return its typed result.

    Never raises on a non-zero exit — callers inspect ``GitResult.success``.
    Raises ``GitError`` only when the ``git`` executable itself cannot run.
    """
    return await _run("git", args, cwd=cwd)


async def run_gh(args: list[str], cwd: str | Path | None = None) -> GitResult:
    """Run a `gh` subcommand and return its typed result."""
    return await _run("gh", args, cwd=cwd)


async def _run(program: str, args: list[str], cwd: str | Path | None) -> GitResult:
    try:
        process = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise GitError(f"'{program}' executable not found on PATH") from exc

    stdout, stderr = await process.communicate()
    assert process.returncode is not None
    return GitResult(
        success=process.returncode == 0,
        stdout=stdout.decode().strip(),
        stderr=stderr.decode().strip(),
    )


async def find_git_root(path: str | Path) -> Path | None:
    """Return the git repository root containing *path*, or ``None``."""
    p = Path(path)
    cwd = p if p.is_dir() else p.parent
    result = await run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if not result.success:
        return None
    return Path(result.stdout)
