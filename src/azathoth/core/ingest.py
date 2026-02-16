import asyncio
import httpx
import subprocess
from pathlib import Path
from enum import Enum, auto
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel
from gitingest import ingest_async
from azathoth.core.utils import estimate_tokens


class IngestType(Enum):
    LOCAL = auto()
    GITHUB_REPO = auto()
    GITHUB_USER = auto()
    UNKNOWN = auto()


class IngestionMetrics(BaseModel):
    file_count: int
    token_count: int
    size_bytes: int


class IngestionResult(BaseModel):
    summary: str
    tree: str
    content: str
    metrics: IngestionMetrics
    suggested_filename: str
    detected_type: str = "UNKNOWN"

    def format_report(self, fmt: str = "txt") -> str:
        """Formats the ingestion result into the specified format."""
        match fmt.lower():
            case "xml":
                return (
                    f"<report>\n"
                    f"  <summary>{self.summary}</summary>\n"
                    f"  <tree>{self.tree}</tree>\n"
                    f"  <content>{self.content}</content>\n"
                    f"</report>"
                )
            case "md":
                return (
                    f"## Summary\n{self.summary}\n\n"
                    f"## Tree\n```\n{self.tree}\n```\n\n"
                    f"## Content\n{self.content}"
                )
            case _:  # Default to txt
                return (
                    f"SUMMARY\n{'=' * 60}\n{self.summary}\n\n"
                    f"TREE\n{'=' * 60}\n{self.tree}\n\n"
                    f"CONTENT\n{'=' * 60}\n{self.content}"
                )


def detect_type(target: str) -> IngestType:
    if Path(target).exists():
        return IngestType.LOCAL

    if "github.com" in target:
        parts = [p for p in target.split("/") if p and p not in ["http:", "https:"]]
        if len(parts) >= 3:
            return IngestType.GITHUB_REPO
        return IngestType.GITHUB_USER

    if "/" in target:
        return IngestType.GITHUB_REPO

    return IngestType.GITHUB_USER


async def ingest(
    target: str,
    include_patterns: Optional[Set[str]] = None,
    exclude_patterns: Optional[Set[str]] = None,
) -> IngestionResult:
    """
    Pure logic for ingesting a single repository or directory.
    """
    # 1. Perform ingestion
    summary, tree, content = await ingest_async(
        target, include_patterns=include_patterns, exclude_patterns=exclude_patterns
    )

    # 2. Extract metrics
    file_count, token_count = _parse_summary_metrics(summary)
    if token_count == 0:
        token_count = estimate_tokens(content)

    full_report_preview = f"{summary}{tree}{content}"
    size_bytes = len(full_report_preview.encode("utf-8"))

    # 3. Generate suggested filename
    suggested_filename = await _generate_filename(target)

    return IngestionResult(
        summary=summary,
        tree=tree,
        content=content,
        metrics=IngestionMetrics(
            file_count=file_count, token_count=token_count, size_bytes=size_bytes
        ),
        suggested_filename=suggested_filename,
        detected_type=detect_type(target).name,
    )


async def fetch_user_repos(username: str) -> List[Dict[str, Any]]:
    """Fetches public repositories for a GitHub user."""
    clean_username = username.split("/")[-1]
    api_url = f"https://api.github.com/users/{clean_username}/repos"

    async with httpx.AsyncClient() as client:
        resp = await client.get(api_url, params={"per_page": 100, "sort": "updated"})
        resp.raise_for_status()
        repos = resp.json()
        return [r for r in repos if not r.get("fork", False)]


def _parse_summary_metrics(summary: str) -> tuple[int, int]:
    """Extracts file and token counts."""
    file_count = 0
    token_count = 0
    for line in summary.split("\n"):
        if "Files analyzed:" in line:
            try:
                file_count = int(line.split(":")[1].strip())
            except ValueError, IndexError:
                pass
        elif "Estimated tokens:" in line:
            try:
                token_str = line.split(":")[1].strip().lower()
                if "k" in token_str:
                    token_count = int(float(token_str.replace("k", "")) * 1000)
                elif "m" in token_str:
                    token_count = int(float(token_str.replace("m", "")) * 1_000_000)
                else:
                    token_count = int(token_str)
            except ValueError, IndexError:
                pass
    return file_count, token_count


async def _generate_filename(target: str) -> str:
    """RESTORES: Monorepo-aware filename generation (repo--subpath)."""
    target_clean = target.rstrip("/")

    # 1. Handle GitHub URLs
    if "github.com" in target_clean:
        parts = [
            p for p in target_clean.split("/") if p and p not in ["http:", "https:"]
        ]
        # If it's a subpath in a repo (has 'tree' or 'blob')
        if "tree" in parts or "blob" in parts:
            repo_name = parts[2]
            try:
                idx = parts.index("tree") if "tree" in parts else parts.index("blob")
                subpath = "-".join(parts[idx + 2 :])
                return f"{repo_name}--{subpath}"
            except ValueError, IndexError:
                pass
        return parts[-1] if parts else "report"

    # 2. Handle Local Paths
    target_path = Path(target_clean).resolve()
    if target_path.is_dir():
        try:
            cmd = ["git", "rev-parse", "--show-toplevel"]
            result = subprocess.run(
                cmd, cwd=target_path, capture_output=True, text=True, check=True
            )
            git_root = Path(result.stdout.strip())
            if target_path != git_root:
                rel_path = target_path.relative_to(git_root)
                flat_rel = str(rel_path).replace("/", "-").replace("\\", "-")
                return f"{git_root.name}--{flat_rel}"
            return git_root.name
        except subprocess.CalledProcessError, FileNotFoundError:
            pass

    return target_path.name or "report"


async def get_subpath_context(target: str) -> Optional[tuple[str, str]]:
    """Monorepo subdirectory detection."""
    target_path = Path(target).resolve()
    if not target_path.is_dir():
        return None

    try:
        cmd = ["git", "rev-parse", "--show-toplevel"]
        result = subprocess.run(
            cmd, cwd=target_path, capture_output=True, text=True, check=True
        )
        git_root = Path(result.stdout.strip())
        if target_path != git_root:
            return git_root.name, str(target_path.relative_to(git_root))
    except subprocess.CalledProcessError, FileNotFoundError:
        pass
    return None
