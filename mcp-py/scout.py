# FILE: mcp/scout.py

"""
Scout MCP Server

An intelligent agent designed to autonomously explore and analyze codebases.
It adapts to your preferred coding style for a given language before
delivering its high-level insights and summaries.
"""

from mcp.server.fastmcp import FastMCP
from lib.prompt_loader import prompt_loader

# --- Server Definition ---

scout_server = FastMCP(
    name="Scout",
    instructions="A server that acts as an autonomous agent to explore, analyze, and report on codebases.",
)


# =================================================================== #
#                            EXECUTOR TOOL                            #
# =================================================================== #


@scout_server.tool()
def adapt(language: str) -> str:
    """
    Loads and combines the core development philosophy with a language-specific
    directive to create a master context for the AI. This adapts the AI to a
    preferred coding style for a specific language.

    Args:
        language (str): The programming language to adapt to (e.g., 'python', 'svelte', 'rust').
    """
    directives = []
    core_philosophy = prompt_loader.load("core-philosophy.md")
    if "Error:" in core_philosophy:
        return "Error: The essential 'core-philosophy.md' directive is missing. Cannot adapt."
    directives.append(core_philosophy)

    lang_directive_filename = f"directive-{language.lower()}.md"
    language_directive = prompt_loader.load(lang_directive_filename)

    if "Error:" not in language_directive:
        directives.append(language_directive)
        return "\n\n---\n\n".join(directives)
    else:
        # Gracefully fall back to core philosophy if specific directive is not found.
        return (
            f"Note: Language-specific directive '{lang_directive_filename}' not found. "
            "Proceeding with the core development philosophy only.\n\n---\n\n"
            + core_philosophy
        )


# =================================================================== #
#                       PRIMARY WORKFLOW PROMPT                       #
# =================================================================== #


@scout_server.prompt(title="Explore, Adapt, and Report on a Codebase")
def explore(target_directory: str = ".") -> str:
    """
    Instructs the LLM to act as a 'Code Scout' to analyze a codebase.
    It explores, identifies the language, adapts to your coding style,
    and then produces a comprehensive overview report.
    """
    return f"""
You are an expert software architect acting as a 'Code Scout'. Your mission is to explore the codebase in '{target_directory}' and produce a high-level overview report, adapted to the project's specific coding philosophy.

You MUST base your entire analysis on the output of the tools you run.

**Your Scouting Process MUST be as follows:**

1.  **Reconnaissance:** Get a high-level view of the project structure using the `ls -R` command.

2.  **Identify Language and Stack:** Find and use the `ReadFile` tool on the project's manifest (`pyproject.toml`, `package.json`, etc.) to determine the primary programming language and key dependencies.

3.  **Adapt to Coding Style:** Based on the primary language you just identified, you MUST immediately call the `adapt` tool. Pass the language name (e.g., 'python') as the argument. The output of this tool is now your **prime directive** and will inform the tone and content of your final report.

4.  **Find the Entry Point:** Locate the application's primary entry point (`main.py`, `src/index.ts`, etc.) and use `ReadFile` on it to understand the high-level architecture and startup sequence.

5.  **Synthesize and Report:** After completing your investigation, you MUST synthesize your findings into a single Markdown overview. Your final output must ONLY be this report. Use the following template:

---
# Codebase Overview

### 1. Project Mission & Core Purpose
*   **What it is:** A concise, one-sentence summary of the project's goal, derived from the project manifest.
*   **Why it exists:** The problem this project aims to solve.

### 2. Technology Stack & Key Dependencies
*   **Language/Runtime:** The primary language and version identified.
*   **Core Libraries:** The 3-5 most important dependencies and their likely role.

### 3. Architecture & High-Level Structure
*   **Architectural Pattern:** [e.g., Command-Line Application, Monolithic Web Server, Library]
*   **Startup Sequence:** A brief description of what happens when the application starts, based on the entry point file.

### 4. Coding Style & Best Practices
*   **Directives Loaded:** Briefly state which style directives were loaded by the `adapt` tool (e.g., 'Core Philosophy + Python').
*   **Key Pattern:** Based on the directives and the code, describe one key pattern or best practice that a new developer MUST follow to contribute to this project.

### 5. Key Insights for a New Developer
*   **Core Logic Location:** The directory or file where the central, most important business logic appears to be located.
*   **First File to Read:** The single file a new developer should read first to get the best understanding of the project's architecture.
---
"""


# --- Server Execution ---


def main():
    """Main function to start the MCP server."""
    print("\033[H\033[J", end="")
    print("🚀 Starting Scout MCP server...")
    print(
        "✅ Server is ready. It provides an `explore` prompt for autonomous code analysis and adaptation."
    )
    scout_server.run()


if __name__ == "__main__":
    main()

