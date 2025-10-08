use rmcp::{
    ErrorData as McpError, ServerHandler, ServiceExt,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{CallToolResult, Content, ServerCapabilities, ServerInfo},
    tool, tool_handler, tool_router,
    transport::stdio,
};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

// --- Define the parameters for our tool ---
#[derive(Serialize, Deserialize, JsonSchema)]
struct AddParams {
    a: i32,
    b: i32,
}

// --- Define the server struct ---
#[derive(Clone)]
struct SimpleMcpServer {
    tool_router: ToolRouter<Self>,
}

impl Default for SimpleMcpServer {
    fn default() -> Self {
        Self::new()
    }
}

// --- Define the tools ---
#[tool_router]
impl SimpleMcpServer {
    pub fn new() -> Self {
        Self {
            tool_router: Self::tool_router(),
        }
    }

    /// A simple tool that adds two numbers.
    #[tool(description = "Adds two integer numbers and returns the sum.")]
    async fn add(&self, params: Parameters<AddParams>) -> Result<String, McpError> {
        let result = params.0.a + params.0.b;
        Ok(result.to_string())
    }
}

// --- Implement the MCP Server Handler ---
#[tool_handler]
impl ServerHandler for SimpleMcpServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            instructions: Some("A simple server with a calculator tool.".to_string()),
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            ..Default::default()
        }
    }
}

/// Example `launch.json` configuration for VSCode to run this example:

//
/// "main-rs-example": {
///     "command": "cargo",
///     "args": ["run",
///     "--example",
///     "main_tester",
///     "--release"
///   ],
///     "cwd": "/home/yrrrrrf/docs/lab/azathoth/mcp-rs",
///     // Wait 30 secs because it could take a bit to compile
///     "timeout": 30000
/// },

// --- Main function to run the server ---
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Clear the screen for a clean start
    print!("\x1B[H\x1B[J");
    println!("🚀 Starting Simple Rust MCP server...");

    let server = SimpleMcpServer::new().serve(stdio()).await?;

    println!("✅ Server is ready with an 'add' tool.");

    // Wait for the server to finish (e.g., when the client disconnects)
    server.waiting().await?;

    Ok(())
}
