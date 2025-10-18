# FILE: mcp/lib/prompt_loader.py

"""
Centralized Master Prompt Loader

This utility provides a singleton `PromptLoader` instance responsible for
finding the project's prompt vault and loading master prompt files.

It dynamically locates the project root by searching for `pyproject.toml`,
making the MCP server configuration portable and eliminating hardcoded paths.
"""

from pathlib import Path
from functools import lru_cache


class PromptLoader:
    """A class to manage loading master prompts from a central vault."""

    def __init__(self):
        """
        Initializes the loader by finding the project root and defining
        the path to the master prompts vault.
        """
        self.project_root = self._find_project_root()
        if not self.project_root:
            raise FileNotFoundError(
                "Could not find the project root containing 'pyproject.toml'."
            )

        # The path to your prompts vault, relative to the project root.
        self.prompts_path = self.project_root / "mcp" / "prompts"

        if not self.prompts_path.is_dir():
            # NOTE: This check runs at startup. The actual file check is in the load() method.
            print(
                f"Warning: Prompt directory not found at the configured path: {self.prompts_path}"
            )

    def _find_project_root(self, marker: str = "pyproject.toml") -> Path | None:
        """
        Traverses up from the current file to find the project root directory.
        The project root is identified by the presence of a marker file (e.g., 'pyproject.toml').
        """
        current_path = Path(__file__).resolve()
        for parent in current_path.parents:
            if (parent / marker).exists():
                return parent
        return None

    @lru_cache(maxsize=None)
    def load(self, filename: str) -> str:
        """
        Loads a master prompt from the vault.
        The result is cached for efficiency.

        Args:
            filename (str): The name of the markdown file (e.g., 'core-philosophy.md').

        Returns:
            str: The content of the prompt file.
        """
        prompt_file = self.prompts_path / filename
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            error_message = (
                f"Error: Master prompt template '{filename}' not found "
                f"in '{self.prompts_path}'. Please ensure the file exists."
            )
            print(error_message)  # Log to server console
            return error_message  # Return error to the LLM agent


# Create a singleton instance to be imported and used by all MCP servers.
prompt_loader = PromptLoader()
