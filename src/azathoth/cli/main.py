import typer
from azathoth.cli.commands.ls import main as ls_cmd
from azathoth.cli.commands.ingest import main as ingest_cmd
from azathoth.cli.commands import workflow

app = typer.Typer(
    name="az",
    help="Azathoth: Dual-Protocol AI Intelligence Layer",
    no_args_is_help=True,
)

app.command(name="ls")(ls_cmd)
app.command(name="ingest")(ingest_cmd)
app.add_typer(workflow.app, name="workflow")

if __name__ == "__main__":
    app()
