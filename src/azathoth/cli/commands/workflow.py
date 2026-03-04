"""
CLI commands for git workflow automation.

Three commands:
  az workflow commit   — AI-powered commit message generation
  az workflow status   — At-a-glance repo overview
  az workflow release  — AI-powered release notes + gh release
"""

import asyncio
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typing import Optional

from azathoth.core.workflow import (
    stage_all,
    commit,
    get_diff,
    get_latest_tag,
    get_log_since,
    create_release,
    _run_git,
)
from azathoth.core.prompts import get_commit_system_prompt, get_release_system_prompt
from azathoth.core.llm import generate, LLMError

console = Console()
app = typer.Typer(help="Git workflow automation.", no_args_is_help=True)


# ── commit ───────────────────────────────────────────────────────────────


@app.command("commit")
def commit_cmd(
    focus: Optional[str] = typer.Option(
        None, "--focus", "-f", help="Hint to guide the commit message."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Generate message without committing."
    ),
):
    """Generate an AI commit message and commit staged changes."""

    async def _run():
        # 1. Stage everything
        await stage_all()
        diff = await get_diff(staged=True)
        if not diff:
            console.print("[yellow]No staged changes — nothing to commit.[/]")
            raise typer.Exit()

        console.print(
            f"[dim]Staged diff: {len(diff):,} chars[/]"
        )

        # 2. Ask Gemini
        system_prompt = get_commit_system_prompt(focus)
        with console.status("[bold cyan]Generating commit message…[/]"):
            try:
                raw = await asyncio.to_thread(
                    _sync_generate, system_prompt, diff, True
                )
            except LLMError as exc:
                console.print(f"[bold red]LLM error:[/] {exc}")
                raise typer.Exit(1)

        # 3. Parse JSON response
        try:
            data = json.loads(raw)
            title = data["title"]
            body = data.get("body", "")
        except (json.JSONDecodeError, KeyError) as exc:
            console.print(f"[bold red]Failed to parse LLM response:[/] {exc}")
            console.print(f"[dim]Raw response:[/]\n{raw}")
            raise typer.Exit(1)

        # 4. Preview
        preview = Text()
        preview.append(title, style="bold green")
        preview.append("\n\n")
        preview.append(body, style="dim")
        console.print(Panel(preview, title="📝 Commit Message", border_style="cyan"))

        if dry_run:
            console.print("[yellow]--dry-run: skipping commit.[/]")
            return

        # 5. Confirm + commit
        if not yes and not typer.confirm("Commit with this message?"):
            console.print("[yellow]Aborted.[/]")
            return

        res = await commit(title, body)
        if res.success:
            console.print("[bold green]✓ Committed.[/]")
        else:
            console.print(f"[bold red]✗ Commit failed:[/] {res.stderr}")

    asyncio.run(_run())


# ── status ───────────────────────────────────────────────────────────────


@app.command("status")
def status_cmd():
    """Show a rich overview of the current repo state."""

    async def _run():
        # Branch
        _, branch, _ = await _run_git(["rev-parse", "--abbrev-ref", "HEAD"])

        # Porcelain status
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

        # Tag info
        tag = await get_latest_tag()
        if tag:
            log = await get_log_since(tag)
            commits_since = len(log.splitlines()) if log else 0
        else:
            commits_since = 0

        # Render
        table = Table(
            title="📊 Repository Status",
            border_style="cyan",
            show_header=False,
            pad_edge=True,
        )
        table.add_column("Key", style="bold")
        table.add_column("Value")

        table.add_row("Branch", f"[bold]{branch}[/]")
        table.add_row("Staged", f"[green]{staged}[/]" if staged else "[dim]0[/]")
        table.add_row(
            "Unstaged", f"[yellow]{unstaged}[/]" if unstaged else "[dim]0[/]"
        )
        table.add_row(
            "Untracked", f"[red]{untracked}[/]" if untracked else "[dim]0[/]"
        )
        table.add_row("Latest tag", tag or "[dim]none[/]")
        table.add_row("Commits since tag", str(commits_since))

        console.print(table)

    asyncio.run(_run())


# ── release ──────────────────────────────────────────────────────────────


@app.command("release")
def release_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Generate notes without publishing."
    ),
    pre: bool = typer.Option(False, "--pre", help="Mark as prerelease."),
):
    """Generate AI release notes and publish via `gh release create`."""

    async def _run():
        # 1. Gather context
        tag = await get_latest_tag()
        if not tag:
            console.print(
                "[yellow]No previous tag found — can't determine changelog.[/]"
            )
            raise typer.Exit(1)

        log = await get_log_since(tag)
        if not log:
            console.print(
                f"[yellow]No commits since {tag} — nothing to release.[/]"
            )
            raise typer.Exit()

        console.print(f"[dim]Latest tag: {tag} | {len(log.splitlines())} commits since[/]")

        # 2. Ask Gemini
        system_prompt = get_release_system_prompt()
        user_msg = f"Previous tag: {tag}\n\nCommit log:\n{log}"

        with console.status("[bold cyan]Generating release notes…[/]"):
            try:
                raw = await asyncio.to_thread(
                    _sync_generate, system_prompt, user_msg, True
                )
            except LLMError as exc:
                console.print(f"[bold red]LLM error:[/] {exc}")
                raise typer.Exit(1)

        # 3. Parse
        try:
            data = json.loads(raw)
            new_tag = data["tag"]
            notes = data["notes"]
        except (json.JSONDecodeError, KeyError) as exc:
            console.print(f"[bold red]Failed to parse LLM response:[/] {exc}")
            console.print(f"[dim]Raw response:[/]\n{raw}")
            raise typer.Exit(1)

        # 4. Preview
        console.print(
            Panel(notes, title=f"🚀 Release {new_tag}", border_style="green")
        )

        if dry_run:
            console.print("[yellow]--dry-run: skipping release.[/]")
            return

        # 5. Confirm + release
        if not yes and not typer.confirm(f"Create release {new_tag}?"):
            console.print("[yellow]Aborted.[/]")
            return

        res = await create_release(new_tag, notes, is_prerelease=pre)
        if res.success:
            console.print(f"[bold green]✓ Released {new_tag}.[/]")
        else:
            console.print(f"[bold red]✗ Release failed:[/] {res.stderr}")
            if res.message:
                console.print(f"[dim]{res.message}[/]")

    asyncio.run(_run())


# ── helpers ──────────────────────────────────────────────────────────────


def _sync_generate(system_prompt: str, user_message: str, json_mode: bool) -> str:
    """Synchronous wrapper for the async generate() — used inside to_thread."""
    import asyncio as _aio

    return _aio.run(generate(system_prompt, user_message, json_mode=json_mode))
