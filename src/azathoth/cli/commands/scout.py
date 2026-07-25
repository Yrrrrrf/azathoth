"""CLI command for codebase reconnaissance (scout).

Presentation layer only — wraps the single core/scout.py `scout` use case.
"""

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from azathoth.core.scout import scout as core_scout

console = Console()
app = typer.Typer(help="Codebase reconnaissance.", no_args_is_help=True)


@app.command("run")
def scout_cmd(
    target_directory: str = typer.Argument(".", help="Path to the repo to scout."),
):
    """Analyze a codebase: structure, language, entry point, and directives."""

    async def _run():
        with console.status("[bold cyan]Scouting…[/]"):
            report = await core_scout(target_directory)

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="dim")
        table.add_column(style="bold cyan")
        table.add_row("Directory", report.directory)
        table.add_row(
            "Language",
            f"{report.stack.primary_language} ({report.stack.confidence:.0%} confidence)",
        )
        table.add_row("Manifests", ", ".join(report.stack.manifests_found) or "none")
        table.add_row("Entry point", report.entry_point or "not found")
        table.add_row("Files", str(report.result.metrics.file_count))
        console.print(Panel(table, title="🔭 Scout Report", border_style="cyan"))

        if report.master_context:
            console.print(Markdown(report.master_context))
        else:
            console.print("[dim](no directives loaded)[/]")

    asyncio.run(_run())
