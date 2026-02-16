# Python coding style example

# FILE: d-python.py

# Example of a small, compliant CLI tool.
# To run: uv run d-python.py --source-dir ./assets

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeAlias

import typer
from rich.console import Console

# Rule 3: Use TypeAlias for complex type definitions. (Updated to include float)
JsonPayload: TypeAlias = dict[str, str | int | float]

# Rule 4: Typer for CLIs, rich for output.
app = typer.Typer(
    name="file-analyzer",
    help="A CLI tool demonstrating the preferred Python coding style.",
    no_args_is_help=True,
    add_completion=False,  # A cleaner help menu for this example
)
console = Console()


def process_file(file_path: Path) -> JsonPayload | None:
    """Processes a file based on its suffix using pattern matching."""
    # Rule 3: Use match...case for complex conditions.
    match file_path.suffix:
        case ".md":
            # Rule 3: Use the walrus operator within a simple if.
            if (size := file_path.stat().st_size) > 1024:
                console.print(
                    f"[yellow]Large markdown file found: {file_path.name}[/yellow]"
                )
            return {
                "file": file_path.name,
                "type": "markdown",
                "size_kb": round(size / 1024, 2),
            }
        case ".json":
            try:
                content = json.loads(file_path.read_text(encoding="utf-8"))

                # Rule 3: Use match...case for complex conditions - handle different JSON types
                match content:
                    case dict():
                        count = len(content.keys())
                        payload_type = "json_object"
                    case list():
                        count = len(content)
                        payload_type = "json_array"
                    case _:
                        # Handle other valid JSON types like a single string or number
                        count = 1
                        payload_type = "json_value"

                return {"file": file_path.name, "type": payload_type, "count": count}

            except json.JSONDecodeError, UnicodeDecodeError:
                console.print(
                    f"[bold red]Error parsing invalid JSON file: {file_path.name}[/bold red]"
                )
                return None
        case _:
            return None


@app.command()
def analyze(
    source_dir: Path = typer.Option(
        ...,  # Make it a required option
        "--source-dir",
        "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="The source directory to analyze.",
    ),
    recursive: bool = typer.Option(
        True,  # Default to recursive search
        "--recursive/--no-recursive",
        "-r/-nr",
        help="Search for files recursively through subdirectories.",
    ),
) -> None:
    """Analyzes all supported files in the target directory."""
    console.print(f"🚀 Analyzing directory: [bold cyan]{source_dir}[/bold cyan]")
    console.print(
        f"   Recursive search: {'[green]Enabled[/green]' if recursive else '[yellow]Disabled[/yellow]'}"
    )

    iterator = source_dir.rglob("*") if recursive else source_dir.iterdir()

    # Rule 3: Use a generator expression for memory efficiency and conciseness.
    # Rule 3: Use the walrus operator to process and filter in one pass.
    valid_files = (
        processed
        for file in iterator
        if file.is_file() and (processed := process_file(file))
    )

    # Rule 3: Use a list comprehension to realize the final list for output.
    results = [result for result in valid_files if result]

    if not results:
        console.print("[bold red]No supported files found to analyze.[/bold red]")
        raise typer.Exit(1)

    console.print(results)
    console.print("\n[bold green]Analysis complete![/bold green]")


if __name__ == "__main__":
    app()
