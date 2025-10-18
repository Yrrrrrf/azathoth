#!/usr/bin/env python3
"""
A simple MCP server with a single tool to get the current time.
This is a Python version of the Rust tool.rs implementation.
"""

from mcp.server.fastmcp import FastMCP
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from datetime import datetime

# Initialize rich console
console = Console()

# Clear screen and show startup message with enhanced visual output
console.clear()
console.print(Panel(Text("🚀 Starting Time MCP Server... (Python Version)", style="bold green blink"), border_style="green"))

# --- MCP SERVER DEFINITION ---
time_server = FastMCP(
    name="Time-Server-Python",
    instructions="A simple server that provides the current time.",
)

# --- TOOL FUNCTION ---

@time_server.tool(
    description="Gets the current system time."
)
def get_now() -> str:
    """
    A simple tool that returns the current system time as a string.
    """
    # Enhanced visual output when the tool is invoked
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    console.print(Panel(
        Text(f"⏰ Time requested: {current_time} (Python Implementation)", style="bold yellow italic"),
        border_style="yellow"
    ))
    
    return current_time

# --- MAIN FUNCTION TO RUN THE SERVER ---
def main():
    """Main function to start the MCP server with enhanced visual output."""
    
    console.print(
        Panel(
            Text("✅ Server is ready with the 'get_now' tool. (Python Version)", style="bold green"),
            border_style="green"
        )
    )
    console.print(
        Text("   🌐 Connect with an MCP client like MCP Inspector to use it.", style="italic dim")
    )
    
    # Keep the server running
    time_server.run()

if __name__ == "__main__":
    main()