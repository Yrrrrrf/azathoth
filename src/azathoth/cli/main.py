import typer
from azathoth.cli.commands.ingest import app as ingest_app
from azathoth.cli.commands import workflow

app = typer.Typer(
    name="az",
    help="Azathoth: Dual-Protocol AI Intelligence Layer",
    no_args_is_help=True,
)

app.add_typer(ingest_app, name="ingest")
app.add_typer(workflow.app, name="workflow")

if __name__ == "__main__":
    app()
