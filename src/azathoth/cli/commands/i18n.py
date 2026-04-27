import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from azathoth.core.i18n import (
    InlangConfig,
    TranslationSet,
    resolve_paths,
    load_all_translations,
    diff_against_base,
    translate_locale,
    merge_translations,
    write_translations,
    prune_orphans,
    build_matrix,
    export_registry,
    import_registry,
)
from azathoth.core.exceptions import I18nError

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
):
    """Translate missing keys using AI."""
    try:
        config = InlangConfig.from_json(settings_path)
        paths = resolve_paths(settings_path, config)
        translations = load_all_translations(paths)

        base_locale = config.base_locale
        if base_locale not in translations:
            console.print(
                f"[red]Error: Base locale '{base_locale}' not found in translations.[/red]"
            )
            raise typer.Exit(1)

        base_set = translations[base_locale]
        target_locales = [loc for loc in config.locales if loc != base_locale]

        async def run_translations():
            tasks = []
            results = {}

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                for locale in target_locales:
                    target_set = translations.get(locale)
                    diff = diff_against_base(base_set, target_set)

                    keys_to_translate = diff.missing_keys
                    if full:
                        keys_to_translate = list(base_set.messages.keys())

                    if not keys_to_translate:
                        console.print(
                            f"[yellow]Skipping {locale}: No keys to translate.[/yellow]"
                        )
                        continue

                    values_to_translate = [
                        base_set.messages[k] for k in keys_to_translate
                    ]

                    # Style samples (first 5 existing translations)
                    samples = []
                    existing_keys = [
                        k for k in base_set.messages.keys() if k in target_set.messages
                    ]
                    for k in existing_keys[:5]:
                        samples.append((base_set.messages[k], target_set.messages[k]))

                    task_id = progress.add_task(
                        description=f"Translating {locale} ({len(keys_to_translate)} keys)...",
                        total=None,
                    )

                    async def do_translate(
                        locale_=locale,
                        k=keys_to_translate,
                        v=values_to_translate,
                        s=samples,
                        t_id=task_id,
                    ):
                        try:
                            res = await translate_locale(locale_, k, v, s)
                            progress.update(
                                t_id,
                                completed=True,
                                description=f"[green]Finished {locale_}[/green]",
                            )
                            return locale_, k, res
                        except Exception as e:
                            progress.update(
                                t_id,
                                completed=True,
                                description=f"[red]Failed {locale_}[/red]",
                            )
                            return locale_, k, e

                    tasks.append(do_translate())

                if not tasks:
                    console.print("[green]All translations up to date.[/green]")
                    return

                batch_results = await asyncio.gather(*tasks)
                for locale, keys, result in batch_results:
                    if isinstance(result, Exception):
                        console.print(
                            f"[red]Error translating {locale}: {str(result)}[/red]"
                        )
                    else:
                        results[locale] = (keys, result)
            return results

        results = asyncio.run(run_translations())

        if not results:
            return

        # Apply changes
        for locale, (keys, values) in results.items():
            target_set = translations[locale]
            new_set = merge_translations(target_set, keys, values)

            if prune:
                new_set = prune_orphans(new_set, base_set)

            if not dry_run:
                write_translations(paths[locale], new_set)
                console.print(f"[green]Updated {paths[locale]}[/green]")
            else:
                console.print(
                    f"[yellow][DRY RUN] Would update {paths[locale]}[/yellow]"
                )

    except I18nError as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def audit(
    settings_path: Path = typer.Argument(
        ..., help="Path to project.inlang/settings.json"
    ),
):
    """Display a translation coverage matrix."""
    try:
        config = InlangConfig.from_json(settings_path)
        paths = resolve_paths(settings_path, config)
        translations = load_all_translations(paths)

        locales = config.locales
        matrix = build_matrix(translations, locales)

        table = Table(title="i18n Translation Audit")
        table.add_column("Key", style="cyan", no_wrap=True)
        for locale in locales:
            table.add_column(locale, justify="center")

        for key in matrix.keys:
            row = [key]
            for locale in locales:
                val = matrix.matrix[key][locale]
                if val:
                    row.append("[green]✓[/green]")
                else:
                    row.append("[red]✗[/red]")
            table.add_row(*row)

        # Totals row
        totals = ["TOTAL"]
        for locale in locales:
            count = sum(1 for k in matrix.keys if matrix.matrix[k][locale])
            percent = (count / len(matrix.keys)) * 100 if matrix.keys else 0
            color = "green" if percent == 100 else "yellow" if percent > 80 else "red"
            totals.append(
                f"[{color}]{count}/{len(matrix.keys)} ({percent:.0f}%)[/{color}]"
            )
        table.add_section()
        table.add_row(*totals)

        console.print(table)

    except I18nError as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


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
    try:
        config = InlangConfig.from_json(settings_path)
        paths = resolve_paths(settings_path, config)
        translations = load_all_translations(paths)

        matrix = build_matrix(translations, config.locales)
        export_registry(matrix, output, fmt)
        console.print(f"[green]Exported registry to {output}[/green]")

    except I18nError as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def sync(
    registry_path: Path = typer.Argument(..., help="Path to registry.json"),
    settings_path: Path = typer.Argument(
        ..., help="Path to project.inlang/settings.json"
    ),
):
    """Sync a registry file back to individual locale files."""
    try:
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

    except I18nError as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)
