import asyncio
import logging
import httpx
from pathlib import Path
from enum import Enum, auto
from typing import List, Dict, Any

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


class IngestType(Enum):
    GITHUB_REPO = auto()
    GITHUB_USER = auto()
    LOCAL = auto()
    UNKNOWN = auto()


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
                        subpath = "-".join(parts[idx + 5:])
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
        
        # CHANGED: Use the helper to generate the source-agnostic name
        name = self._generate_filename_from_url(url)
        
        self._save_report(name, summary, tree, content, output_dir)
        self.console.print(f"[bold green]✓[/] Completed: [bold cyan]{name}[/]")

    async def process_local(self, path: str, output_dir: Path):
        with self.console.status(
            f"[bold blue]Ingesting Local Path:[/] {path}...", spinner="dots"
        ):
            summary, tree, content = await ingest_async(path)
        
        # CHANGED: Just use the resolved directory name (e.g., "azathoth")
        name = Path(path).resolve().name
        
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
            self.console.print(f"  [red]Failed:    [/red] {len(failed_repos)}")
            for name, reason in failed_repos:
                self.console.print(f"  - {name}: [dim]{reason}[/]")

        # Only save the digest if we didn't separate files
        if not separate_files:
            full_content = "".join(full_content_accumulator)
            user_summary = "\n".join(user_summary_lines)
            
            # CHANGED: Use just the username for the digest (e.g., "yrrrrrf.txt")
            self._save_report(
                username,
                user_summary,
                "See individual repo sections",
                full_content,
                output_dir,
            )
