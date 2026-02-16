import os
import tiktoken
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from azathoth.config import config


class IngestResult(BaseModel):
    content: str
    token_count: int
    file_count: int
    files: List[str]


def estimate_tokens(text: str) -> int:
    """Estimates tokens using tiktoken."""
    try:
        encoding = tiktoken.get_encoding(config.token_model)
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4


async def to_txt(
    targets: List[str], 
    root_path: str = ".", 
    include_header: bool = True
) -> IngestResult:
    """
    Ingests multiple files/globs into a single string.
    """
    root = Path(root_path).resolve()
    full_content = []
    processed_files = []
    total_tokens = 0
    
    for target in targets:
        # Handle globs
        for item in root.glob(target):
            if item.is_file() and not item.name.startswith("."):
                try:
                    content = item.read_text(errors="ignore")
                    rel_path = item.relative_to(root)
                    
                    file_block = []
                    if include_header:
                        file_block.append(f"--- FILE: {rel_path} ---")
                    
                    file_block.append(content)
                    file_block.append("\n")
                    
                    block_text = "\n".join(file_block)
                    full_content.append(block_text)
                    processed_files.append(str(rel_path))
                    total_tokens += estimate_tokens(block_text)
                except Exception:
                    continue

    final_text = "\n".join(full_content)
    
    return IngestResult(
        content=final_text,
        token_count=total_tokens,
        file_count=len(processed_files),
        files=processed_files
    )
