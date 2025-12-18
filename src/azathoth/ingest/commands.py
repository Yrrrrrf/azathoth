"""
Ingest Command Definition
"""

import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel

from azathoth.ingest.core import IngestionEngine, IngestType

console = Console()


def ingest(
    target: str = typer.Argument(
        ..., help="The target URL (GitHub repo, User profile) or local path."
    ),
    output: Path = typer.Option(
        Path.home() / "Downloads",
        "--output",
        "-o",
        help="Directory to save the ingested report.",
    ),
    depth: int = typer.Option(
        3, "--depth", "-d", help="Max directory depth for local ingestion."
    ),
    ignore_files: bool = typer.Option(
        True, "--ignore/--no-ignore", help="Respect .gitignore files."
    ),
):
    """
    📦 [bold]Universal Ingest Tool[/bold]

    Automatically detects the target type:
    - [bold green]GitHub Repo:[/bold green] Creates a comprehensive code digest.
    - [bold magenta]GitHub User:[/bold magenta] Fetches ALL public repositories and summarizes them.
    - [bold yellow]Local Path:[/bold yellow] Ingests the local directory structure.
    """
    engine = IngestionEngine(console)

    # Determine type
    ingest_type = engine.detect_type(target)

    console.print(
        Panel(
            f"Target: [bold cyan]{target}[/]\n"
            f"Detected Type: [bold magenta]{ingest_type.name}[/]",
            title="🚀 Ingestion Started",
            border_style="green",
        )
    )

    async def run_ingestion():
        if ingest_type == IngestType.GITHUB_USER:
            await engine.process_user(target, output)
        elif ingest_type == IngestType.GITHUB_REPO:
            await engine.process_repo(target, output)
        elif ingest_type == IngestType.LOCAL:
            await engine.process_local(target, output)
        else:
            console.print("[red]Unknown target type.[/red]")
            raise typer.Exit(1)

    # Run the appropriate workflow within a single event loop
    try:
        asyncio.run(run_ingestion())

    except Exception as e:
        console.print(f"[bold red]Ingestion Failed:[/bold red] {e}")
        raise typer.Exit(1)
