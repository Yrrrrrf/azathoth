import asyncio
import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from azathoth.core.ingest import ingest

console = Console()

def main(
    target: str = typer.Argument(..., help="Path or URL to ingest"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Pack a repository into a single context file."""
    async def _run():
        with console.status(f"[bold blue]Ingesting {target}..."):
            try:
                result = await ingest(target)
            except Exception as e:
                console.print(f"[bold red]Error:[/] {e}")
                raise typer.Exit(1)
            
        metrics_text = (
            f"[bold green]✓ Ingestion Complete![/]\n\n"
            f"Files: {result.metrics.file_count}\n"
            f"Tokens: {result.metrics.token_count}\n"
            f"Size: {result.metrics.size_bytes / 1024:.2f} KB"
        )
        console.print(Panel(
            metrics_text,
            title=result.suggested_filename,
            expand=False
        ))
        
        if output:
            out_path = Path(output)
            out_path.write_text(result.content)
            console.print(f"\n[dim]Saved to: {out_path}[/]")

    asyncio.run(_run())
