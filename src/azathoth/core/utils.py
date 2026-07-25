import tiktoken

from azathoth.config import get_config


def estimate_tokens(text: str) -> int:
    """
    Estimates LLM token count using tiktoken.
    Falls back to the ~4 chars/token heuristic if tiktoken fails.
    """
    try:
        encoding = tiktoken.get_encoding(get_config().token_model)
        return len(encoding.encode(text))
    except KeyError, ValueError:
        return len(text) // 4


def format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
