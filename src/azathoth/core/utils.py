import tiktoken
from azathoth.config import config


def estimate_tokens(text: str) -> int:
    """
    Estimates LLM token count using tiktoken.
    Falls back to the ~4 chars/token heuristic if tiktoken fails.
    """
    try:
        encoding = tiktoken.get_encoding(config.token_model)
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4


def format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} TB"
