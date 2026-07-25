"""
CLI commands for git workflow automation.

Three commands:
  az workflow commit   — AI-powered commit message generation
  az workflow status   — At-a-glance repo overview
  az workflow release  — AI-powered release notes + gh release

Presentation layer only — every command wraps exactly one core/workflow.py
use case. Errors are raised as `AzathothError` subclasses and handled by the
single boundary in `cli/main.py`.
"""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from azathoth.core.workflow import (
    perform_commit,
    perform_release,
    propose_commit,
    propose_release,
    repo_status,
)

console = Console()
app = typer.Typer(help="Git workflow automation.", no_args_is_help=True)


# ── commit ───────────────────────────────────────────────────────────────


@app.command("commit")
def commit_cmd(
    focus: str | None = typer.Option(
        None, "--focus", "-f", help="Hint to guide the commit message."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Generate message without committing."
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Override the LLM provider for this invocation (e.g. 'ollama', 'gemini').",
    ),
):
    """Generate an AI commit message and commit staged changes."""

    async def _run():
        with console.status("[bold cyan]Generating commit message…[/]"):
            proposal = await propose_commit(focus=focus, provider=provider)

        console.print(
            f"[dim]Staged diff: {proposal.diff_chars:,} chars, "
            f"~{proposal.diff_tokens_estimated:,} tokens[/]"
        )

        preview = Text()
        preview.append(proposal.message.title, style="bold green")
        preview.append("\n\n")
        preview.append(proposal.message.body, style="dim")
        console.print(Panel(preview, title="📝 Commit Message", border_style="cyan"))

        if dry_run:
            console.print("[yellow]--dry-run: skipping commit.[/]")
            return

        if not yes and not typer.confirm("Commit with this message?"):
            console.print("[yellow]Aborted.[/]")
            return

        await perform_commit(proposal)
        console.print("[bold green]✓ Committed.[/]")

    asyncio.run(_run())


# ── status ───────────────────────────────────────────────────────────────


@app.command("status")
def status_cmd():
    """Show a rich overview of the current repo state."""

    async def _run():
        status = await repo_status()

        table = Table(
            title="📊 Repository Status",
            border_style="cyan",
            show_header=False,
            pad_edge=True,
        )
        table.add_column("Key", style="bold")
        table.add_column("Value")

        table.add_row("Branch", f"[bold]{status.branch}[/]")
        table.add_row(
            "Staged", f"[green]{status.staged}[/]" if status.staged else "[dim]0[/]"
        )
        table.add_row(
            "Unstaged",
            f"[yellow]{status.unstaged}[/]" if status.unstaged else "[dim]0[/]",
        )
        table.add_row(
            "Untracked",
            f"[red]{status.untracked}[/]" if status.untracked else "[dim]0[/]",
        )
        table.add_row("Latest tag", status.latest_tag or "[dim]none[/]")
        table.add_row("Commits since tag", str(status.commits_since_tag))

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
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Override the LLM provider for this invocation (e.g. 'ollama', 'gemini').",
    ),
):
    """Generate AI release notes and publish via `gh release create`."""

    async def _run():
        with console.status("[bold cyan]Generating release notes…[/]"):
            proposal = await propose_release(provider=provider)

        console.print(
            f"[dim]Latest tag: {proposal.previous_tag} | "
            f"{proposal.commit_count} commits since[/]"
        )
        console.print(
            Panel(
                proposal.notes.notes,
                title=f"🚀 Release {proposal.notes.tag}",
                border_style="green",
            )
        )

        if dry_run:
            console.print("[yellow]--dry-run: skipping release.[/]")
            return

        if not yes and not typer.confirm(f"Create release {proposal.notes.tag}?"):
            console.print("[yellow]Aborted.[/]")
            return

        await perform_release(proposal, prerelease=pre)
        console.print(f"[bold green]✓ Released {proposal.notes.tag}.[/]")

    asyncio.run(_run())
