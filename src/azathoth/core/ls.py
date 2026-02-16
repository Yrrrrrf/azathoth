import os
import tiktoken
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from azathoth.config import config


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size_bytes: int
    token_estimate: Optional[int] = None


class DirectoryListing(BaseModel):
    path: str
    entries: List[FileEntry]
    total_files: int
    total_dirs: int
    total_tokens: Optional[int] = None


def estimate_tokens(text: str) -> int:
    """Estimates tokens using tiktoken."""
    try:
        encoding = tiktoken.get_encoding(config.token_model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to ~4 chars per token
        return len(text) // 4


async def list_directory(
    target_path: str, 
    recursive: bool = False, 
    show_tokens: bool = False
) -> DirectoryListing:
    """
    Lists files and directories with optional token estimation.
    """
    root = Path(target_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {target_path}")

    entries = []
    total_files = 0
    total_dirs = 0
    total_tokens = 0

    # Define common ignore patterns
    ignore = {".git", "__pycache__", "node_modules", "target", ".venv", ".next"}

    def _walk(current_path: Path, depth: int):
        nonlocal total_files, total_dirs, total_tokens
        
        try:
            for item in sorted(current_path.iterdir()):
                if item.name in ignore:
                    continue
                
                is_dir = item.is_dir()
                size = item.stat().st_size if not is_dir else 0
                
                entry = FileEntry(
                    name=item.name,
                    path=str(item.relative_to(root)),
                    is_dir=is_dir,
                    size_bytes=size
                )
                
                if is_dir:
                    total_dirs += 1
                    if recursive:
                        _walk(item, depth + 1)
                else:
                    total_files += 1
                    if show_tokens:
                        try:
                            content = item.read_text(errors="ignore")
                            tokens = estimate_tokens(content)
                            entry.token_estimate = tokens
                            total_tokens += tokens
                        except Exception:
                            entry.token_estimate = 0
                            
                entries.append(entry)
        except PermissionError:
            pass

    _walk(root, 0)

    return DirectoryListing(
        path=str(root),
        entries=entries,
        total_files=total_files,
        total_dirs=total_dirs,
        total_tokens=total_tokens if show_tokens else None
    )
