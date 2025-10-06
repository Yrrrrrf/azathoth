# FILE: mcp/directives.py

"""
AI Directives MCP

This server provides a suite of master prompts designed to act as a persistent
system context or behavioral framework for an AI assistant. Its purpose is to
configure the AI's personality, coding style, and strategic approach at the
beginning of a work session.
"""

from mcp.server.fastmcp import FastMCP
from lib.prompt_loader import prompt_loader

# --- Server Definition ---

directives_server = FastMCP(
    name="AI Directives",
    instructions="Provides behavioral and stylistic directives to configure an AI assistant for a work session.",
)

# --- Prompt Definitions ---


@directives_server.prompt(title="Set Core Development Philosophy")
def get_core_philosophy() -> str:
    """
    Provides the baseline AI directive for coding style. This prompt should be used
    at the start of a session to ensure the AI adheres to modern syntax, functional
    principles, and strict typing. It is language-agnostic.
    """
    return prompt_loader.load("core-philosophy.md")


@directives_server.prompt(title="Activate Proactive Advisor Mode")
def get_proactive_advisor() -> str:
    """
    Appends a directive that instructs the AI to act as a strategic partner.
    After fulfilling the primary request, the AI will provide a distinct section
    with suggestions for technical improvements, architectural patterns, and feature ideas.
    """
    return prompt_loader.load("proactive-advisor.md")


@directives_server.prompt(title="Load Svelte 5 Directive")
def directive_svelte5() -> str:
    """
    Loads a technology-specific mandate for Svelte 5 development, enforcing a
    personal, preferred coding style and specific patterns using Runes.
    """
    return prompt_loader.load("directive-svelte5.md")


# --- Server Execution ---


def main():
    """Main function to start the MCP server."""
    print("\033[H\033[J", end="")
    print("🚀 Starting AI Directives MCP server...")
    print(
        "✅ Server is ready. It exposes prompts to configure your AI assistant's behavior."
    )
    directives_server.run()


if __name__ == "__main__":
    main()
