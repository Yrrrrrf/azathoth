"""Azathoth: AI Architect & Development Framework."""

from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Discover .env starting from the user's cwd (standard CLI convention),
# falling back to the package's source tree for editable-install dev use.
# override=False means a real exported env var always wins over the file.
_env_path = find_dotenv(usecwd=True) or str(
    Path(__file__).resolve().parents[2] / ".env"
)
load_dotenv(_env_path, override=False)

from azathoth.cli import init_cli  # noqa: E402 — must run after load_dotenv()


def main() -> None:
    """Main entry point for the Azathoth CLI."""
    init_cli()


if __name__ == "__main__":
    main()
