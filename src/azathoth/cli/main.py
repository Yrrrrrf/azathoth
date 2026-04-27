from __future__ import annotations

from typing import Annotated, Optional

import typer
from importlib.metadata import version, PackageNotFoundError

from azathoth.cli.commands.ingest import main as ingest_cmd
from azathoth.cli.commands import workflow, i18n

app = typer.Typer(
    name="azathoth",
    help="Azathoth: Dual-Protocol AI Intelligence Layer",
    no_args_is_help=True,
)

app.command(name="ingest")(ingest_cmd)
app.add_typer(workflow.app, name="workflow")
app.add_typer(i18n.app, name="i18n")


def _version_callback(value: bool) -> None:
    if value:
        try:
            v = version("azathoth")
        except PackageNotFoundError:
            v = "dev"
        typer.echo(f"azathoth {v}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", "-v",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """Azathoth: Dual-Protocol AI Intelligence Layer."""


if __name__ == "__main__":
    app()
