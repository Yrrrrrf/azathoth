# FILE: mcp/workflow.py

"""
Git Workflow MCP (Enhanced)

A focused MCP server that provides a suite of intelligent, automated tools
for common Git tasks like committing changes and publishing releases.
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp_py.lib.prompt_loader import prompt_loader
from mcp.server.fastmcp import Context, FastMCP

# --- Server Definition ---

workflow_server = FastMCP(
    name="Git Workflow",
    instructions="A server providing prompts and tools for common Git tasks like committing code and creating release notes.",
)


# =================================================================== #
#                          WORKFLOW ORCHESTRATORS                     #
# =================================================================== #


@workflow_server.prompt(name="Autocommit All Changes")
def autocommit(focus: Optional[str] = None) -> str:
    """
    Analyzes all current changes, generates a conventional commit message,
    and executes it. This is the primary entry point for committing work.
    """
    return """
You are an expert software engineer. Your task is to intelligently create and execute a conventional Git commit.

**Your process MUST be as follows:**

THE ZERO LAW OF GIT COMMITS:
0. **UNDEBATABLE RULE**: You MUST NEVER! Add some kind of coauthor or sign-off lines to the commit message. The commit MUST be clean and professional!

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


@workflow_server.prompt(name="Autorelease New Version")
def autorelease(new_version: str) -> str:
    """
    Fully automates the release process: finds the last version, analyzes
    new commits, generates release notes, and publishes to GitHub.
    """
    # Note: Prompts can be synchronous as they don't block the event loop for long.
    # We perform a quick git check here.
    try:
        # We use standard subprocess here for the prompt generation as it's a quick read
        # and prompts usually run in a threadpool in FastMCP if they block, or we can make this async.
        repo_url = (
            _run_command_sync(["git", "config", "--get", "remote.origin.url"])
            .strip()
        )
    except Exception:
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
    """
    return prompt_loader.load("new-version-release.md").format(
        REPO_NAME=repo_url.split("/")[-1].replace(".git", ""),
        PREVIOUS_VERSION=old_version,
        NEW_VERSION=new_version,
    )


def _run_command_sync(args: list[str]) -> str:
    """Helper for synchronous command execution (used in prompts)."""
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout


async def _run_command_async(args: list[str]) -> tuple[str, str]:
    """
    Helper for asynchronous command execution.
    Returns (stdout, stderr). Raises Exception on failure.
    """
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\nStderr: {stderr.decode()}"
        )
    
    return stdout.decode(), stderr.decode()


# =================================================================== #
#                           EXECUTOR TOOLS                            #
# =================================================================== #


@workflow_server.tool()
async def stage_and_commit(
    commit_title: str, 
    commit_body: str, 
    ctx: Context
) -> str:
    """
    Stages all current changes and safely commits them with the provided message.
    """
    try:
        await ctx.info("Staging all files...")
        await _run_command_async(["git", "add", "."])
        
        full_commit_message = f"{commit_title}\n\n{commit_body}"
        
        # We still use a temp file for the message to avoid shell injection,
        # but we do the file I/O synchronously as it's negligible.
        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, encoding="utf-8"
        ) as tmp_file:
            tmp_file.write(full_commit_message)
            tmp_file_path = tmp_file.name

        await ctx.info(f"Committing with title: {commit_title}")
        
        # Run git commit using the temp file
        stdout, _ = await _run_command_async(["git", "commit", "-F", tmp_file_path])
        
        Path(tmp_file_path).unlink()
        return f"Commit successful:\n{stdout}"
        
    except RuntimeError as e:
        await ctx.error(f"Git operation failed: {e}")
        return f"Error: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        return f"An unexpected error occurred: {e}"


@workflow_server.tool()
async def create_git_release(
    version_tag: str, 
    release_notes: str, 
    ctx: Context,
    is_prerelease: bool = False
) -> str:
    """
    Creates a new Git tag, pushes it, and then creates a GitHub Release.
    Requires the GitHub CLI ('gh') to be installed and authenticated.
    """
    try:
        await ctx.info(f"Tagging release {version_tag}...")
        await _run_command_async(["git", "tag", version_tag])
        
        await ctx.info("Pushing tag to origin...")
        await _run_command_async(["git", "push", "origin", version_tag])

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

        await ctx.info("Creating GitHub release via 'gh' CLI...")
        stdout, _ = await _run_command_async(command)
        
        return f"Successfully created release {version_tag}.\nURL: {stdout.strip()}"
        
    except FileNotFoundError:
        return "Error: The 'gh' command was not found. Please install the GitHub CLI."
    except RuntimeError as e:
        await ctx.error(f"Release failed: {e}")
        return f"Error during release creation: {e}"


@workflow_server.tool()
async def git_snapshot_now(ctx: Context) -> str:
    """
    Creates a timestamped 'snapshot' commit, staging all current changes.
    Use when asked to "snapshot" or "save progress" quickly.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    commit_message = f"snapshot: {timestamp}"

    try:
        await ctx.info("Creating snapshot...")
        await _run_command_async(["git", "add", "."])
        await _run_command_async(["git", "commit", "-m", commit_message])
        return f"Successfully created snapshot commit: '{commit_message}'"
    except RuntimeError as e:
        return f"Error creating snapshot: {e}"


# --- Server Execution ---

def main():
    """Main function to start the MCP server."""
    # Note: FastMCP handles the event loop and stdio transport automatically.
    print("\033[H\033[J", end="")
    print("🚀 Starting Git Workflow MCP server...")
    workflow_server.run()

if __name__ == "__main__":
    # Import subprocess for the synchronous parts used in prompts
    import subprocess
    main()
