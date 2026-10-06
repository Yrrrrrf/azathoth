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

from azathoth.config import get_config
from azathoth.core.workflow import (
    perform_commit,
    perform_release,
    propose_commit,
    propose_release,
    repo_status,
)

console = Console()
app = typer.Typer(help="Git workflow automation.", no_args_is_help=True)


def _format_provider_panel(provider_name: str, model_name: str | None = None) -> Panel:
    """Render a Rich panel showing which provider and model fulfilled the request, and its route."""
    cfg = get_config()
    p_name = provider_name.lower() if provider_name else "gemini"

    if p_name == "gemini":
        display_name = "Google Gemini"
        model = model_name or cfg.gemini_model
        route = "Cloud API (Google AI)"
        icon = "☁️ "
        prov_style = "bold cyan"
    elif p_name == "ollama":
        display_name = "Ollama"
        model = model_name or cfg.ollama_model
        route = f"Local Daemon ({cfg.ollama_host})"
        icon = "💻"
        prov_style = "bold yellow"
    else:
        display_name = provider_name
        model = model_name or "default"
        route = "Custom Endpoint"
        icon = "⚡"
        prov_style = "bold green"

    text = Text()
    text.append(f"{icon} Provider: ", style="bold white")
    text.append(display_name, style=prov_style)
    text.append("  •  🎯 Model: ", style="bold white")
    text.append(model, style="bold magenta")
    text.append("  •  🌐 Route: ", style="bold white")
    text.append(route, style="bold green")
    text.append("  •  💻 Local: ", style="bold white")
    text.append("Deactivated (Ollama)", style="dim red")

    return Panel(
        text,
        border_style="cyan",
        title="[bold bright_cyan]🤖 Active LLM Provider[/]",
        padding=(0, 1),
    )


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
        cfg = get_config()
        active_target = provider or (
            cfg.active_providers[0] if cfg.active_providers else "gemini"
        )
        target_model = (
            cfg.gemini_model if active_target == "gemini" else cfg.ollama_model
        )
        route = "Cloud API" if active_target == "gemini" else "Local"

        with console.status(
            f"[bold cyan]Connecting to [magenta]{active_target}[/] "
            f"[dim]({target_model} • {route})[/] to generate commit message…[/]"
        ):
            proposal = await propose_commit(focus=focus, provider=provider)

        console.print(
            _format_provider_panel(
                proposal.provider or active_target, proposal.model or target_model
            )
        )

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
        cfg = get_config()
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

        active_p = cfg.active_providers[0] if cfg.active_providers else "none"
        active_model = cfg.gemini_model if active_p == "gemini" else cfg.ollama_model
        table.add_row(
            "LLM Provider",
            f"☁️  [bold cyan]Google Gemini[/] ([bold magenta]{active_model}[/])",
        )
        table.add_row("LLM Route", "🌐 [bold green]Cloud API (Google AI Studio)[/]")
        table.add_row("Local LLM", "💻 [dim red]Deactivated (Ollama)[/]")

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
        cfg = get_config()
        active_target = provider or (
            cfg.active_providers[0] if cfg.active_providers else "gemini"
        )
        target_model = (
            cfg.gemini_model if active_target == "gemini" else cfg.ollama_model
        )
        route = "Cloud API" if active_target == "gemini" else "Local"

        with console.status(
            f"[bold cyan]Connecting to [magenta]{active_target}[/] "
            f"[dim]({target_model} • {route})[/] to generate release notes…[/]"
        ):
            proposal = await propose_release(provider=provider)

        console.print(
            _format_provider_panel(
                proposal.provider or active_target, proposal.model or target_model
            )
        )

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
