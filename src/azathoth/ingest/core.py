"""
Modified version of src/azathoth/ingest/core.py
Add this helper function to calculate file sizes and enhance logging
"""

import asyncio
import logging
import httpx
import subprocess
from pathlib import Path
from enum import Enum, auto
from typing import List, Dict, Any
import tiktoken  # You'll need to add this dependency if not already present

# --- 1. AGGRESSIVE LOG SILENCING ---
# We must silence Loguru (used by gitingest) and standard logging
# BEFORE they interfere with the Rich UI.

# Silence standard logging
logging.basicConfig(level=logging.CRITICAL)
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

# Silence Loguru (The main culprit for the logs you were seeing)
try:
    from loguru import logger

    logger.remove()  # Remove all handlers (stdout/stderr)
    logger.disable("gitingest")  # Disable the specific library
except ImportError:
    pass

# -----------------------------------

from gitingest import ingest_async
from rich.console import Console, RenderableType
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    MofNCompleteColumn,
    ProgressColumn,
    Task,
)
from rich.text import Text
from rich.panel import Panel
from rich.table import Table


class IngestType(Enum):
    GITHUB_REPO = auto()
    GITHUB_USER = auto()
    LOCAL = auto()
    UNKNOWN = auto()


# --- Helper Functions for Size and Token Calculation ---


def calculate_report_size_bytes(summary: str, tree: str, content: str) -> int:
    """Calculate the size of the generated report in bytes."""
    # Combine all sections as they will be in the final file
    full_report = f"SUMMARY\n{'=' * 20}\n{summary}\n\nTREE\n{'=' * 20}\n{tree}\n\nCONTENT\n{'=' * 20}\n{content}"

    # Calculate size in bytes (using UTF-8 encoding)
    return len(full_report.encode("utf-8"))


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    try:
        # Use tiktoken with cl100k_base encoding (used by GPT-4 and newer models)
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate of ~4 chars per token
        return len(text) // 4


def format_token_count(token_count: int) -> str:
    """Format token count in human-readable format (k for thousands, M for millions)."""
    if token_count >= 1_000_000:
        return f"{token_count / 1_000_000:.1f}M"
    elif token_count >= 1_000:
        return f"{token_count / 1_000:.1f}k"
    else:
        return str(token_count)


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format (B, KB, MB, GB, etc.)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def parse_summary_for_metrics(summary: str) -> tuple[int, int]:
    """
    Parse the summary string to extract file count and token count.
    Returns: (file_count, token_count)
    """
    file_count = 0
    token_count = 0

    for line in summary.split("\n"):
        if "Files analyzed:" in line:
            try:
                file_count = int(line.split(":")[1].strip())
            except (ValueError, IndexError):
                pass
        elif "Estimated tokens:" in line:
            try:
                # Parse formats like "28.9k" or "1.2M"
                token_str = line.split(":")[1].strip()
                if "k" in token_str:
                    token_count = int(float(token_str.replace("k", "")) * 1000)
                elif "M" in token_str:
                    token_count = int(float(token_str.replace("M", "")) * 1_000_000)
                else:
                    token_count = int(token_str)
            except (ValueError, IndexError):
                pass

    return file_count, token_count


# --- Custom Rich UI Components ---


class StatusSpinnerColumn(ProgressColumn):
    """A custom progress column that shows a spinner for active tasks
    and a completion icon ('✓' or '✗') for finished tasks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spinner = SpinnerColumn(spinner_name="dots")

    def render(self, task: "Task") -> RenderableType:
        if task.finished:
            icon = task.fields.get("status_icon", "[bold green]✓[/]")
            return Text.from_markup(icon)
        return self.spinner.render(task)


class IngestionEngine:
    def __init__(self, console: Console):
        self.console = console
        self.max_concurrent_tasks = 5

    def detect_type(self, target: str) -> IngestType:
        if Path(target).exists():
            return IngestType.LOCAL
        if "github.com" in target or len(target.split("/")) == 2:
            return IngestType.GITHUB_REPO
        return IngestType.GITHUB_USER

    def _save_report(
        self, name: str, summary: str, tree: str, content: str, output_dir: Path
    ):
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"{name}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                f"SUMMARY\n{'=' * 20}\n{summary}\n\nTREE\n{'=' * 20}\n{tree}\n\nCONTENT\n{'=' * 20}\n{content}"
            )

        self.console.print(f"   [dim]Saved report to: {file_path}[/]")

    def _display_ingestion_metrics(
        self,
        target: str,
        detected_type: IngestType,
        file_count: int,
        token_count: int,
        size_bytes: int,
    ):
        """Display enhanced ingestion metrics in a nice table format."""

        # Create a table for metrics
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="dim")
        table.add_column("Value", style="bold cyan")

        # Add rows
        table.add_row("Target:", target)
        table.add_row("Detected Type:", detected_type.name)
        table.add_row("", "")  # Spacer
        table.add_row("📊 Files:", str(file_count))
        table.add_row("🔢 Tokens:", format_token_count(token_count))
        table.add_row("💾 Size:", format_size(size_bytes))

        # Display in a panel
        panel = Panel(
            table,
            title="🚀 [bold]Ingestion Started[/bold]",
            border_style="blue",
            expand=False,
        )

        self.console.print(panel)

    def _generate_filename_from_url(self, url: str) -> str:
        """
        Generates a standardized filename from a URL.
        Format: {Repo} or {Repo}--{Subpath}
        """
        url = url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]

        parts = url.split("/")

        # Check for GitHub structure to enforce [Project]--[Scope]
        if "github.com" in parts:
            try:
                idx = parts.index("github.com")
                # Structure: .../github.com/User/Repo
                if len(parts) >= idx + 3:
                    repo_name = parts[idx + 2]

                    # Handle tree/blob for subpaths (e.g. .../Repo/tree/main/docs)
                    # Parts indices: Repo(idx+2), tree(idx+3), branch(idx+4), subdir(idx+5)
                    if len(parts) > idx + 5 and parts[idx + 3] in ["tree", "blob"]:
                        # Join the remaining path parts with double dashes or single dashes
                        # Recommendation: "Repo--path-to-dir"
                        subpath = "-".join(parts[idx + 5 :])
                        return f"{repo_name}--{subpath}"

                    return repo_name
            except ValueError:
                pass

        # Fallback: Use the last meaningful segment of the URL
        return parts[-1]

    async def process_repo(self, url: str, output_dir: Path):
        with self.console.status(
            f"[bold blue]Ingesting Repo:[/] {url}...", spinner="dots"
        ):
            summary, tree, content = await ingest_async(url)

        # Extract metrics
        file_count, token_count = parse_summary_for_metrics(summary)

        # Calculate the size of the generated report
        report_size_bytes = calculate_report_size_bytes(summary, tree, content)

        # CHANGED: Use the helper to generate the source-agnostic name
        name = self._generate_filename_from_url(url)

        # Display enhanced metrics
        self._display_ingestion_metrics(
            target=url,
            detected_type=IngestType.GITHUB_REPO,
            file_count=file_count,
            token_count=token_count,
            size_bytes=report_size_bytes,
        )

        self._save_report(name, summary, tree, content, output_dir)
        self.console.print(f"[bold green]✓[/] Completed: [bold cyan]{name}[/]")

    async def process_local(self, path: str, output_dir: Path):
        target_path = Path(path).resolve()

        # Defaults
        ingest_path = target_path
        include_patterns = None  # Valid: None
        name = target_path.name

        try:
            # 1. Find the Git Root
            cmd = ["git", "rev-parse", "--show-toplevel"]
            result = subprocess.run(
                cmd, cwd=target_path, capture_output=True, text=True, check=True
            )
            git_root = Path(result.stdout.strip())
            repo_name = git_root.name

            if target_path == git_root:
                name = repo_name
            else:
                # Monorepo/Subdirectory context
                rel_path = target_path.relative_to(git_root)

                flat_rel_path = str(rel_path).replace("/", "-").replace("\\", "-")
                name = f"{repo_name}--{flat_rel_path}"

                # CRITICAL FIX: Use the Git Root as base, but filter for the subdir
                ingest_path = git_root

                # CHANGED: Use a set {} instead of a list []
                include_patterns = {str(rel_path)}

                self.console.print(
                    f"[dim]Context:[/dim] Detected Git Root at [bold]{git_root.name}[/]"
                )
                self.console.print(
                    f"[dim]Scope:[/dim] Restricting ingestion to [bold]{rel_path}[/]"
                )

        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        with self.console.status(
            f"[bold blue]Ingesting:[/bold blue] {name}...", spinner="dots"
        ):
            # ingest_async expects include_patterns to be Set[str] | str | None
            summary, tree, content = await ingest_async(
                str(ingest_path), include_patterns=include_patterns
            )

        # Extract metrics from summary
        file_count, token_count = parse_summary_for_metrics(summary)

        # Calculate the size of the generated report
        report_size_bytes = calculate_report_size_bytes(summary, tree, content)

        # Display enhanced metrics
        self._display_ingestion_metrics(
            target=str(target_path),
            detected_type=IngestType.LOCAL,
            file_count=file_count,
            token_count=token_count,
            size_bytes=report_size_bytes,
        )

        self._save_report(name, summary, tree, content, output_dir)
        self.console.print(f"[bold green]✓[/] Completed: [bold cyan]{name}[/]")

    async def process_user(
        self, username: str, output_dir: Path, separate_files: bool = False
    ):
        # 1. Fetch Repositories
        api_url = f"https://api.github.com/users/{username}/repos"

        with self.console.status(
            f"[dim]Fetching repositories for user: {username}...[/]", spinner="dots"
        ):
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    api_url, params={"per_page": 100, "sort": "updated"}
                )
                if resp.status_code != 200:
                    self.console.print(
                        f"[bold red]Error fetching user repos: {resp.status_code}[/]"
                    )
                    return
                repos = resp.json()

        source_repos = [r for r in repos if not r.get("fork", False)]
        source_repos = [
            r for r in source_repos if r["name"].lower() != username.lower()
        ]

        if not source_repos:
            self.console.print("[yellow]No source repositories found.[/]")
            return

        self.console.print(
            f"[bold green]✓[/] Found [bold]{len(source_repos)}[/] source repositories."
        )
        self.console.print()

        # 2. Setup Concurrent Ingestion
        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
        full_content_accumulator = []
        user_summary_lines = [f"User: {username}", f"Repos: {len(source_repos)}"]
        failed_repos = []

        progress_columns = (
            TextColumn("  "),
            StatusSpinnerColumn(),
            TextColumn("[bold blue]{task.description}[/]"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        )

        with Progress(
            *progress_columns, console=self.console, expand=False
        ) as progress:
            main_task = progress.add_task(
                f"[bold]Ingesting {username}...[/]", total=len(source_repos)
            )

            async def ingest_single_repo(repo: Dict[str, Any]):
                repo_name = repo["name"]
                repo_url = repo["clone_url"]

                async with semaphore:
                    try:
                        s, t, c = await ingest_async(repo_url)

                        if separate_files:
                            # CHANGED: Use just the repo name (e.g., "Leaflet.txt")
                            self._save_report(repo_name, s, t, c, output_dir)
                        else:
                            # Accumulate content for single digest
                            repo_content = (
                                f"\n\n{'=' * 30}\nREPO: {repo_name}\n{'=' * 30}\n{c}"
                            )
                            full_content_accumulator.append(repo_content)
                            user_summary_lines.append(
                                f"\n- {repo_name}: {len(c)} chars"
                            )

                    except Exception as e:
                        failed_repos.append((repo_name, str(e)))
                    finally:
                        progress.advance(main_task)

            tasks = [ingest_single_repo(repo) for repo in source_repos]
            await asyncio.gather(*tasks)

        # 3. Finalize
        self.console.print()
        self.console.print("[bold green]Ingestion Complete![/]")

        success_count = len(source_repos) - len(failed_repos)
        self.console.print(f"  [green]Successful:[/green] {success_count}")

        if failed_repos:
            self.console.print(f"  [red]Failed:[/red] {len(failed_repos)}")
            for repo_name, error in failed_repos[:5]:  # Show first 5 failures
                self.console.print(f"    - {repo_name}: {error}")

        if not separate_files and full_content_accumulator:
            # Save combined report
            combined_summary = "\n".join(user_summary_lines)
            combined_tree = ""
            combined_content = "\n".join(full_content_accumulator)
            self._save_report(
                username, combined_summary, combined_tree, combined_content, output_dir
            )
