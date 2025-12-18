"""
CLI Application for Azathoth
"""

from typer import Typer
from rich.console import Console

# Define the main application
app = Typer(
    name="azathoth",
    help="My personal AI architect and development partner.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

# Global console for rich output
console = Console()


def init_cli():
    """Register all CLI commands and start the app."""
    from azathoth.cli.callbacks import register_callbacks
    from azathoth.cli.commands import register_commands

    # Register global callbacks (like --version)
    register_callbacks(app)

    # Register command groups
    register_commands(app)

    app()
