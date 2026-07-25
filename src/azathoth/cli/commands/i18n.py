import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from azathoth.core.i18n import (
    InlangConfig,
    TranslationSet,
    apply_translations,
    audit_project,
    export_registry,
    import_registry,
    load_project,
    resolve_paths,
    translate_project,
    write_translations,
)

app = typer.Typer(help="i18n translation automation commands.")
console = Console()


@app.command()
def translate(
    settings_path: Path = typer.Argument(
        ..., help="Path to project.inlang/settings.json"
    ),
    full: bool = typer.Option(
        False, "--full", help="Retranslate all keys, not just missing ones."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without writing to files."
    ),
    prune: bool = typer.Option(
        False, "--prune", help="Remove orphan keys from target files."
    ),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Override the LLM provider for this invocation."
    ),
):
    """Translate missing keys using AI."""
    project = load_project(settings_path)
    outcomes = asyncio.run(
        translate_project(project, full=full, prune=prune, provider=provider)
    )

    for outcome in outcomes:
        if outcome.error:
            console.print(
                f"[red]Error translating {outcome.locale}: {outcome.error}[/]"
            )
        elif outcome.keys_touched == 0:
            console.print(
                f"[yellow]Skipping {outcome.locale}: No keys to translate.[/]"
            )
        else:
            console.print(
                f"[green]Translated {outcome.locale}: {outcome.keys_touched} key(s)[/]"
            )
            for warning in outcome.placeholder_warnings:
                console.print(
                    f"  [yellow]⚠ {warning.key}: expected {warning.expected}, "
                    f"got {warning.actual}[/]"
                )

    if dry_run:
        console.print("[yellow]--dry-run: skipping write.[/]")
        return

    written = apply_translations(project, outcomes, prune=prune)
    for path in written:
        console.print(f"[green]Updated {path}[/]")


@app.command()
def audit(
    settings_path: Path = typer.Argument(
        ..., help="Path to project.inlang/settings.json"
    ),
):
    """Display a translation coverage matrix."""
    project = load_project(settings_path)
    matrix, totals = audit_project(project)

    table = Table(title="i18n Translation Audit")
    table.add_column("Key", style="cyan", no_wrap=True)
    for locale in project.config.locales:
        table.add_column(locale, justify="center")

    for key in matrix.keys:
        row = [key]
        for locale in project.config.locales:
            val = matrix.matrix[key][locale]
            row.append("[green]✓[/green]" if val else "[red]✗[/red]")
        table.add_row(*row)

    row = ["TOTAL"]
    for coverage in totals:
        percent = (coverage.translated / coverage.total) * 100 if coverage.total else 0
        color = "green" if percent == 100 else "yellow" if percent > 80 else "red"
        row.append(
            f"[{color}]{coverage.translated}/{coverage.total} ({percent:.0f}%)[/]"
        )
    table.add_section()
    table.add_row(*row)

    console.print(table)


@app.command()
def export(
    settings_path: Path = typer.Argument(
        ..., help="Path to project.inlang/settings.json"
    ),
    output: Path = typer.Option(
        "registry.json", "--output", "-o", help="Output file path."
    ),
    fmt: str = typer.Option("json", "--format", "-f", help="Export format (json, py)."),
):
    """Export all translations to a master registry file."""
    project = load_project(settings_path)
    matrix, _ = audit_project(project)
    export_registry(matrix, output, fmt)
    console.print(f"[green]Exported registry to {output}[/green]")


@app.command()
def sync(
    registry_path: Path = typer.Argument(..., help="Path to registry.json"),
    settings_path: Path = typer.Argument(
        ..., help="Path to project.inlang/settings.json"
    ),
):
    """Sync a registry file back to individual locale files."""
    matrix = import_registry(registry_path)
    config = InlangConfig.from_json(settings_path)
    paths = resolve_paths(settings_path, config)

    for locale in matrix.locales:
        if locale not in paths:
            console.print(
                f"[yellow]Warning: Locale '{locale}' in registry not found in config. Skipping.[/yellow]"
            )
            continue

        messages = {}
        for key in matrix.keys:
            val = matrix.matrix[key].get(locale)
            if val:
                messages[key] = val

        write_translations(
            paths[locale], TranslationSet(locale=locale, messages=messages)
        )
        console.print(f"[green]Synced {paths[locale]}[/green]")
