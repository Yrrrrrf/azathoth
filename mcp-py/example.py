# # MCP Example Server.

# This script provides an example of a simple MCP server with a single tool.
# It is intended to be used for testing the MCP framework and as a reference
# for creating new tools.

# This file is part of some MCP server example.

# Configuration example for mcpServers:

# WINDOWS:
# ```json
# {
#     "mcpServers": {
#         "mcp_example": {
#             "command": "uv",  // or your python interpreter command
#             "args": ["run", ".\\mcp\\example.py"],  // the script to run
#             "cwd": "C:\\Users\\fire\\Lab\\ai",  // current working directory
#             "timeout": 10000  // timeout in milliseconds
#         }
#     }
# }
# ```
#
# LINUX:
# ```json
#     "mcp_example": {
#       "command": "uv",  // or your python interpreter command
#       "args": ["run", "./mcp/example.py"],  // the script to run
#       "cwd": "/home/yrrrrrf/lab/ai",  // current working directory
#       "timeout": 10000  // timeout in milliseconds
#     }
# ```

from random import randint
from mcp.server.fastmcp import FastMCP


example_mcp = FastMCP(
    name="Simple Test Server!",
)


@example_mcp.tool()
def example_tool() -> str:
    """
    A simple tool that returns a fixed string.
    """
    string = "\033[92mThis is a test tool that returns a fixed string.\033[0m"
    return string


@example_mcp.tool()
def generate_random_number(max_value: int = 100) -> str:
    """
    Generates a random integer between 1 and the specified max_value.
    """
    # This print will show up in your terminal if you run it manually.
    print(f"INFO: Tool 'generate_random_number' was called with max_value={max_value}.")
    return f"Your random number is: {randint(1, max_value)}"


def main():
    print("\033[H\033[J", end="")
    print("Starting custom MCP server...")
    print("You can now use this server to test your tools.")
    example_mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
