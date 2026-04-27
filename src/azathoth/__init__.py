"""
Azathoth: AI Architect & Development Framework
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env from azathoth's own directory, not the cwd
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from azathoth.cli import init_cli  # noqa: E402 — must run after load_dotenv()


def main() -> None:
    """Main entry point for the Azathoth CLI."""
    init_cli()


if __name__ == "__main__":
    main()
