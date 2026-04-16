import typer
from azathoth.cli.commands.ingest import main as ingest_cmd
from azathoth.cli.commands import workflow, i18n

app = typer.Typer(
    name="az",
    help="Azathoth: Dual-Protocol AI Intelligence Layer",
    no_args_is_help=True,
)

app.command(name="ingest")(ingest_cmd)
app.add_typer(workflow.app, name="workflow")
app.add_typer(i18n.app, name="i18n")

if __name__ == "__main__":
    app()
