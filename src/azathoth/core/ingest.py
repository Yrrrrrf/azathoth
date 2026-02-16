from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel
from gitingest import ingest_async
from azathoth.core.ls import estimate_tokens


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


async def ingest(
    target: str, 
    include_patterns: Optional[Set[str]] = None,
    exclude_patterns: Optional[Set[str]] = None
) -> IngestionResult:
    """
    Pure logic for ingesting a repository (local or remote).
    """
    # 1. Perform ingestion
    summary, tree, content = await ingest_async(
        target, 
        include_patterns=include_patterns, 
        exclude_patterns=exclude_patterns
    )

    # 2. Extract metrics
    file_count, token_count = _parse_summary_metrics(summary)
    
    # If summary parsing failed, use tiktoken estimation
    if token_count == 0:
        token_count = estimate_tokens(content)

    full_report = f"SUMMARY\n{'=' * 20}\n{summary}\n\nTREE\n{'=' * 20}\n{tree}\n\nCONTENT\n{'=' * 20}\n{content}"
    size_bytes = len(full_report.encode("utf-8"))

    # 3. Generate suggested filename
    suggested_filename = _generate_filename(target)

    return IngestionResult(
        summary=summary,
        tree=tree,
        content=content,
        metrics=IngestionMetrics(
            file_count=file_count,
            token_count=token_count,
            size_bytes=size_bytes
        ),
        suggested_filename=suggested_filename
    )


def _parse_summary_metrics(summary: str) -> tuple[int, int]:
    """Extracts file and token counts from gitingest summary."""
    file_count = 0
    token_count = 0
    for line in summary.split("\n"):
        if "Files analyzed:" in line:
            try:
                file_count = int(line.split(":")[1].strip())
            except (ValueError, IndexError): pass
        elif "Estimated tokens:" in line:
            try:
                token_str = line.split(":")[1].strip().lower()
                if "k" in token_str:
                    token_count = int(float(token_str.replace("k", "")) * 1000)
                elif "m" in token_str:
                    token_count = int(float(token_str.replace("m", "")) * 1_000_000)
                else:
                    token_count = int(token_str)
            except (ValueError, IndexError): pass
    return file_count, token_count


def _generate_filename(target: str) -> str:
    """Generates a clean filename from target path or URL."""
    # Simple logic for now, similar to original but cleaner
    target = target.rstrip("/")
    if target.endswith(".git"):
        target = target[:-4]
    
    if "github.com" in target:
        parts = target.split("/")
        # User/Repo or Repo
        return parts[-1]
    
    # Local path
    return Path(target).name
