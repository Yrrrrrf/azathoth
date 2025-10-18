# FILE: mcp/workflow.py

"""
Git Workflow MCP (Enhanced)

A focused MCP server that provides a suite of intelligent, automated tools
for common Git tasks like committing changes and publishing releases.
"""

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from lib.prompt_loader import prompt_loader
from mcp.server.fastmcp import FastMCP

# --- Server Definition ---

workflow_server = FastMCP(
    name="Git Workflow",
    instructions="A server providing prompts and tools for common Git tasks like committing code and creating release notes.",
)


# =================================================================== #
#                          WORKFLOW ORCHESTRATORS (The "Brains")      #
# =================================================================== #


@workflow_server.prompt(title="[Workflow] Autocommit All Changes")
def autocommit(focus: Optional[str] = None) -> str:
    """
    Analyzes all current changes, generates a conventional commit message,
    and executes it. This is the primary entry point for committing work.
    """
    return """
You are an expert software engineer. Your task is to intelligently create and execute a conventional Git commit.

**Your process MUST be as follows:**

1.  **Stage All Changes:** First, you MUST run `git add .` to ensure that all modified and new files are staged. This guarantees that the commit will be comprehensive.

2.  **Analyze Staged Changes:** After staging, you MUST review the context of the staged code changes by inspecting `git diff --staged`.

3.  **Generate a Commit Message:** Based on the changes and the user's focus, write a high-quality conventional commit message with a `title` and a `body`.

4.  **Execute the Commit:** You MUST immediately call the `stage_and_commit` tool to finalize the process. Pass the `commit_title` and `commit_body` you just generated as arguments to the tool.

Do not ask for confirmation at any step. Perform this entire sequence of actions directly.
""" + (
        f"\n\n**User's Focus for this commit is:** '{focus}'. Tailor the commit message accordingly."
        if focus
        else ""
    )


@workflow_server.prompt(title="[Workflow] Autorelease New Version")
def autorelease(new_version: str) -> str:
    """
    Fully automates the release process: finds the last version, analyzes
    new commits, generates release notes, and publishes to GitHub.
    """
    try:
        repo_url_proc = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True,
            capture_output=True,
            text=True,
        )
        repo_url = repo_url_proc.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Error: Could not determine the remote git repository URL."

    return f"""
You are an expert release manager. Your task is to fully automate the creation and publication of the new software release: **{new_version}**.

**Your process MUST be as follows, without asking for confirmation:**

1.  **Find Previous Version:** Execute the shell command `git describe --tags --abbrev=0` to find the most recent Git tag. This is the `old_version`.

2.  **Gather Commit History:** Get the log of all commits between the `old_version` and HEAD. The command `git log <old_version>..HEAD --pretty=format:"- %s"` is ideal for this, as it provides a clean list for your analysis.

3.  **Generate Release Notes:** You must now write the release notes. Your writing style and structure MUST strictly follow the template provided below. Use the commit history you just gathered as your primary source of information.

    ---
    **RELEASE NOTES TEMPLATE:**
    {_get_release_notes_template(repo_url, old_version="<old_version_from_step_1>", new_version=new_version)}
    ---

4.  **Create the Release:** You MUST immediately call the `create_git_release` tool. Pass the `{new_version}` as the `version_tag` and the full Markdown notes you just generated as the `release_notes`.
"""


# =================================================================== #
#                          HELPER FUNCTIONS                         #
# =================================================================== #


def _get_release_notes_template(
    repo_url: str, old_version: str, new_version: str
) -> str:
    """
    Loads and formats the release notes master prompt template.
    This is a "style guide" helper for the autorelease workflow.
    """
    return prompt_loader.load("new-version-release.md").format(
        REPO_NAME=repo_url.split("/")[-1].replace(".git", ""),
        PREVIOUS_VERSION=old_version,
        NEW_VERSION=new_version,
    )


# =================================================================== #
#                           EXECUTOR TOOLS (The "Hands")              #
# =================================================================== #


@workflow_server.tool()
def stage_and_commit(commit_title: str, commit_body: str) -> str:
    """
    Stages all current changes and safely commits them with the provided message
    using a temporary file to prevent shell injection issues.
    """
    try:
        # This single tool now handles both staging and committing atomically.
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        return f"Error: Failed to stage files.\nGit add stderr:\n{e.stderr}"

    try:
        full_commit_message = f"{commit_title}\n\n{commit_body}"
        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, encoding="utf-8"
        ) as tmp_file:
            tmp_file.write(full_commit_message)
            tmp_file_path = tmp_file.name

        commit_command = ["git", "commit", "-F", tmp_file_path]
        commit_process = subprocess.run(
            commit_command, capture_output=True, text=True, check=True
        )
        Path(tmp_file_path).unlink()
        return f"Commit successful:\n{commit_process.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Error: Git commit failed.\nGit commit stderr:\n{e.stderr}"
    except Exception as e:
        return f"An unexpected error occurred during commit: {e}"


@workflow_server.tool()
def create_git_release(
    version_tag: str, release_notes: str, is_prerelease: bool = False
) -> str:
    """
    Creates a new Git tag, pushes it, and then creates a GitHub Release.
    Requires the GitHub CLI ('gh') to be installed and authenticated.
    """
    try:
        subprocess.run(
            ["git", "tag", version_tag], check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "push", "origin", version_tag],
            check=True,
            capture_output=True,
            text=True,
        )

        prerelease_flag = ["--prerelease"] if is_prerelease else []
        command = [
            "gh",
            "release",
            "create",
            version_tag,
            "--notes",
            release_notes,
            "--title",
            f"Release {version_tag}",
        ] + prerelease_flag

        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return (
            f"Successfully created release {version_tag}.\nURL: {result.stdout.strip()}"
        )
    except FileNotFoundError:
        return "Error: The 'gh' command was not found. Please install the GitHub CLI and ensure it's in your PATH."
    except subprocess.CalledProcessError as e:
        error_message = (
            f"Error during release creation for command: {' '.join(e.cmd)}\n"
        )
        error_message += f"Stderr: {e.stderr}"
        return error_message


@workflow_server.tool()
def git_snapshot_now() -> str:
    """
    Creates a timestamped 'snapshot' commit, staging all current changes.
    Use when asked to "snapshot" or "save progress" quickly.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    commit_message = f"snapshot: {timestamp}"

    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        return f"Successfully created snapshot commit: '{commit_message}'"
    except subprocess.CalledProcessError as e:
        return f"Error creating snapshot: {e.stderr}"


# --- Server Execution ---


def main():
    """Main function to start the MCP server."""
    print("\033[H\033[J", end="")
    print("🚀 Starting Git Workflow MCP server...")
    print("✅ Server is ready. It exposes intelligent workflows for Git tasks.")
    workflow_server.run()


if __name__ == "__main__":
    main()
