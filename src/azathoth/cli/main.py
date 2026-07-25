from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

import typer

from azathoth.cli.commands import i18n, scout, workflow
from azathoth.cli.commands.ingest import main as ingest_cmd
from azathoth.config import check_preview_model, get_config
from azathoth.core.exceptions import AzathothError

app = typer.Typer(
    name="azathoth",
    help="Azathoth: Dual-Protocol AI Intelligence Layer",
    no_args_is_help=True,
)

app.command(name="ingest")(ingest_cmd)
app.add_typer(workflow.app, name="workflow")
app.add_typer(i18n.app, name="i18n")
app.add_typer(scout.app, name="scout")


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
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """Azathoth: Dual-Protocol AI Intelligence Layer."""
    check_preview_model()
    get_config().ensure_dirs()


def main() -> None:
    """Console-script entry point — the single `AzathothError` boundary.

    Every command raises `AzathothError` subclasses on failure and never
    prints its own error banner; this is the one place that maps a domain
    error to a red message and a non-zero exit code.
    """
    try:
        app()
    except AzathothError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
