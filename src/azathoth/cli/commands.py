"""
Command Registration
"""

from typer import Typer
from azathoth.ingest import commands as ingest_cmds


def register_commands(app: Typer):
    """Register all sub-commands and groups."""

    # Register the 'ingest' command group directly or as standalone commands
    # Here we register 'ingest' as a top-level command for speed
    app.command(
        name="ingest",
        help="📦 Ingest codebases, repos, or documentation into a single context file.",
    )(ingest_cmds.ingest)

    # Future command groups can be added here:
    # app.add_typer(scaffold_app, name="scaffold")
    # app.add_typer(audit_app, name="audit")
