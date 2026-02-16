import typer
from azathoth.cli.commands.ls import main as ls_cmd
from azathoth.cli.commands.ingest import main as ingest_cmd
from azathoth.cli.commands import workflow

app = typer.Typer(
    name="az",
    help="Azathoth: Dual-Protocol AI Intelligence Layer",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)


def init_cli():
    """Register all CLI commands and start the app."""
    # from azathoth.cli.callbacks import register_callbacks
    # from azathoth.cli.commands import register_commands

    app.command(name="ls")(ls_cmd)
    app.command(name="ingest")(ingest_cmd)
    app.add_typer(workflow.app, name="workflow")

    app()
