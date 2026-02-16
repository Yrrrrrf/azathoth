import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    MofNCompleteColumn,
    ProgressColumn,
    Task,
)
from rich.text import Text

from azathoth.config import config
from azathoth.core.ingest import (
    ingest, IngestionResult, detect_type, IngestType, 
    fetch_user_repos, get_subpath_context
)
from azathoth.core.utils import format_size

# --- AGGRESSIVE LOG SILENCING ---
try:
    from loguru import logger
    logger.remove()
    logger.disable("gitingest")
except ImportError:
    pass

console = Console()
app = typer.Typer(help="Ingest codebases into a single file.", no_args_is_help=True)


class StatusSpinnerColumn(ProgressColumn):
    """Morphs from spinner to ✓/✗ on completion."""
    def __init__(self):
        super().__init__()
        self.spinner = SpinnerColumn(spinner_name="dots")

    def render(self, task: "Task") -> RenderableType:
        if task.finished:
            icon = task.fields.get("status_icon", "[bold green]✓[/]")
            return Text.from_markup(icon)
        return self.spinner.render(task)


def _display_info_panel(target: str, detected_type: IngestType):
    """The blue info panel at the start."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim")
    table.add_column(style="bold cyan")
    table.add_row("Target:", target)
    table.add_row("Type:", detected_type.name)
    
    panel = Panel(
        table,
        title="🚀 [bold]Ingestion Started[/bold]",
        border_style="blue",
        expand=False,
    )
    console.print(panel)


def _display_metrics_panel(result: IngestionResult, save_path: Path):
    """The green summary panel at the end."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim")
    table.add_column(style="bold cyan")
    
    table.add_row("Files", str(result.metrics.file_count))
    table.add_row("Tokens", f"{result.metrics.token_count:,}")
    table.add_row("Size", format_size(result.metrics.size_bytes))
    table.add_row("Saved to", f"@{save_path}")
    
    panel = Panel(
        table,
        title="[bold green]✓ Ingestion Complete![/]",
        expand=False,
        border_style="green",
    )
    console.print(panel)


def list_reports():
    """List all saved ingestion reports."""
    reports = sorted(
        config.reports_dir.glob("*.*"), 
        key=lambda p: p.stat().st_mtime, 
        reverse=True
    )
    
    if not reports:
        console.print("[yellow]No reports found.[/]")
        return

    table = Table(title="Ingestion Reports", box=box.SIMPLE)
    table.add_column("Filename", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Size", style="green")

    for r in reports:
        size = format_size(r.stat().st_size)
        mtime = datetime.fromtimestamp(r.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(r.name, mtime, size)
        
    console.print(table)


async def _ingest_single(target: str, output: Optional[Path], fmt: str, clipboard: bool):
    """Handles ingestion for a single target."""
    ctx = await get_subpath_context(target)
    if ctx:
        root_name, rel_path = ctx
        console.print(f"[dim]Context:[/dim] Detected Git Root at [bold]{root_name}[/]")
        console.print(f"[dim]Scope:[/dim]   Restricting ingestion to [bold]{rel_path}[/]")

    itype = detect_type(target)
    _display_info_panel(target, itype)

    with console.status(f"⠋ Ingesting [cyan]{target}[/cyan]...", spinner="dots"):
        try:
            result = await ingest(target)
        except Exception as e:
            console.print(f"[bold red]✗ Ingestion failed:[/] {e}")
            raise typer.Exit(1)

    # Determine save path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{result.suggested_filename}-{timestamp}.{fmt}"
    save_path = output or (config.reports_dir / filename)

    full_report = result.format_report(fmt=fmt)
    save_path.write_text(full_report, encoding="utf-8")

    if clipboard:
        try:
            import pyperclip
            pyperclip.copy(full_report)
            console.print("[dim]→ Copied to clipboard[/]")
        except ImportError:
            pass

    # REDUNDANT MESSAGES REMOVED — ONLY THE PANEL REMAINS
    _display_metrics_panel(result, save_path)


async def _ingest_user(target: str, output_dir: Path, fmt: str, separate: bool):
    """Concurrent multi-repo ingestion for GitHub users."""
    username = target.rstrip("/").split("/")[-1]
    
    try:
        repos = await fetch_user_repos(username)
    except Exception as e:
        console.print(f"[bold red]✗ Error fetching repos for {username}:[/] {e}")
        return

    if not repos:
        console.print(f"[yellow]No public source repositories found for {username}.[/]")
        return

    console.print(f"[bold green]✓[/] Found [bold]{len(repos)}[/] source repositories.")
    
    semaphore = asyncio.Semaphore(5)
    full_content = []
    
    progress_cols = (
        TextColumn("  "),
        StatusSpinnerColumn(),
        TextColumn("[bold blue]{task.description}[/]"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )

    with Progress(*progress_cols, console=console, expand=False) as progress:
        main_task = progress.add_task(f"Ingesting {username}...", total=len(repos))

        async def _work(repo: Dict[str, Any]):
            async with semaphore:
                try:
                    res = await ingest(repo["clone_url"])
                    if separate:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        path = output_dir / f"{res.suggested_filename}-{timestamp}.{fmt}"
                        path.write_text(res.format_report(fmt=fmt), encoding="utf-8")
                    else:
                        full_content.append(f"\n\n{'='*40}\nREPO: {res.suggested_filename}\n{'='*40}\n{res.content}")
                    progress.update(main_task, advance=1)
                except Exception:
                    progress.update(main_task, advance=1, status_icon="[bold red]✗[/]")

        await asyncio.gather(*[_work(r) for r in repos])

    if not separate and full_content:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = output_dir / f"{username}-profile-{timestamp}.{fmt}"
        save_path.write_text("\n".join(full_content), encoding="utf-8")
        console.print(f"\n[bold green]✓[/] Profile digest saved to: [bold]{save_path}[/]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    target: Optional[str] = typer.Argument(None, help="Path, GitHub URL, or Username"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Custom output path"),
    format: str = typer.Option("txt", "--format", "-f", help="txt, md, xml"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c"),
    separate: bool = typer.Option(False, "--separate", "-s", help="Split user repos into files"),
    list_flag: bool = typer.Option(False, "--list", "-l", help="List reports"),
):
    """Pack code into LLM context. Automatically detects type."""
    if list_flag:
        list_reports()
        return

    if not target:
        console.print("[yellow]Usage: az ingest [TARGET] or az ingest --list[/]")
        return

    async def _run():
        itype = detect_type(target)
        if itype == IngestType.GITHUB_USER:
            await _ingest_user(target, output or config.reports_dir, format, separate)
        else:
            await _ingest_single(target, output, format, clipboard)

    asyncio.run(_run())
