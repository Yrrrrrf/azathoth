#!/usr/bin/env python3
"""
A simple MCP server demonstrating a single, powerful prompt.
This prompt is a Python version of the 'explore' prompt from the scout.py script.
"""

from mcp.server.fastmcp import FastMCP
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
import sys

# . aska
# Initialize rich console
console = Console()

# Create the server with enhanced visual output
console.clear()
console.print(
    Panel(
        Text(
            "🚀 Starting Scout Prompt MCP Server... (Python Version)",
            style="bold green blink",
        ),
        border_style="green",
    )
)

# --- MCP SERVER DEFINITION ---
scout_server = FastMCP(
    name="Scout-Prompt-Python",
    instructions="A server that provides a powerful 'explore' prompt for code analysis.",
)

# --- PROMPT PARAMETERS and FUNCTION ---


@scout_server.prompt(
    title="Explore, Adapt, and Report on a Codebase",
    description="Instructs the AI to act as a 'Code Scout' to analyze a codebase",
)
def explore(target_directory: str = ".") -> str:
    """
    Instructs the LLM to act as a 'Code Scout' to analyze a codebase.
    It explores, identifies the language, adapts to your coding style,
    and then produces a comprehensive overview report.
    """

    # Enhanced visual output when the prompt is invoked
    console.print(
        Panel(
            Text(
                f"🔍 Exploring directory: {target_directory} (Python Implementation)",
                style="bold yellow italic",
            ),
            border_style="yellow",
        )
    )

    # This is the instructional text for the AI, taken directly from scout.py
    instructions = f"""
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

    # Enhanced visual output when returning the prompt
    console.print(
        Panel(
            Text(
                "📋 Prompt instructions prepared for AI (Python Version)",
                style="bold dim",
            ),
            border_style="blue",
        )
    )

    return instructions


# --- MAIN FUNCTION TO RUN THE SERVER ---
def main():
    """Main function to start the MCP server with enhanced visual output."""

    console.print(
        Panel(
            Text(
                "✅ Server is ready with the 'explore' prompt. (Python Version)",
                style="bold green",
            ),
            border_style="green",
        )
    )
    console.print(
        Text(
            "   🌐 Connect with an MCP client like MCP Inspector to use it.",
            style="italic dim",
        )
    )

    # Keep the server running
    scout_server.run()


if __name__ == "__main__":
    main()
