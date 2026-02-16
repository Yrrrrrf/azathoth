import asyncio
import typer
from rich.console import Console
from azathoth.core.ls import list_directory

console = Console()

def main(
    path: str = typer.Argument(".", help="Path to list"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursive listing"),
    tokens: bool = typer.Option(False, "--tokens", "-t", help="Show token estimates")
):
    """List directory contents with token estimation."""
    async def _run():
        with console.status("[bold blue]Listing directory..."):
            try:
                result = await list_directory(path, recursive=recursive, show_tokens=tokens)
            except FileNotFoundError:
                console.print(f"[bold red]Error:[/] Path '{path}' not found.")
                raise typer.Exit(1)
        
        console.print(f"\n[bold]Directory:[/] {result.path}")
        console.print(f"[dim]Files: {result.total_files} | Dirs: {result.total_dirs}[/]")
        if tokens:
            console.print(f"[bold cyan]Total Tokens:[/] {result.total_tokens}")
            
        for entry in result.entries:
            prefix = "📂" if entry.is_dir else "📄"
            token_str = f" [dim]({entry.token_estimate} tokens)[/]" if tokens and not entry.is_dir else ""
            console.print(f"  {prefix} {entry.path}{token_str}")

    asyncio.run(_run())
