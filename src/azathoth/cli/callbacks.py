"""
Global CLI Callbacks and Flags
"""

import typer
from typing import Optional
from importlib.metadata import version as get_version
from rich.console import Console
from rich.table import Table

console = Console()


def version_callback(value: bool):
    if value:
        try:
            v = get_version("azathoth")
        except:
            v = "dev"

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row("[bold cyan]Azathoth[/]", f"[green]v{v}[/]")
        table.add_row("[dim]Core[/]", "[blue italic]Python[/]")

        console.print(table)
        raise typer.Exit()


def register_callbacks(app: typer.Typer):
    """Register global options."""

    @app.callback()
    def main(
        version: Optional[bool] = typer.Option(
            None,
            "--version",
            "-v",
            help="Show the application version.",
            callback=version_callback,
            is_eager=True,
        ),
    ):
        """
        [bold cyan]Azathoth[/bold cyan] - The Universal Factory Interface.
        """
        pass
