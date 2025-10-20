//! A simple MCP server with a single tool to get the current time.
//! This tool returns the current system time as a string.
//!  
//! Example configuration to run this server via MCP Inspector:
//! "tool": {
//!   "command": "cargo",
//!   "args": [ "run", "--example", "tool" ],
//!   "cwd": "/home/yrrrrrf/docs/lab/azathoth",
//!   "timeout": 30000
//! }

// --- NECESSARY IMPORTS ---
use rmcp::{
    ServerHandler, ServiceExt,
    handler::server::router::tool::ToolRouter,
    model::{ServerCapabilities, ServerInfo},
    tool, tool_handler, tool_router,
    transport::stdio,
};
// Use the standard chrono crate for time
use chrono::Local;

// --- MCP SERVER DEFINITION ---

#[derive(Clone)]
struct TimeServer {
    tool_router: ToolRouter<Self>,
}

impl Default for TimeServer {
    fn default() -> Self {
        Self::new()
    }
}

#[tool_router]
impl TimeServer {
    pub fn new() -> Self {
        Self {
            tool_router: Self::tool_router(),
        }
    }

    /// A simple tool that returns the current system time as a string.
    #[tool(description = "Gets the current system time.")]
    async fn get_now(&self) -> String {
        // Use chrono to get the current local time and format it
        Local::now().format("%Y-%m-%d %H:%M:%S").to_string()
    }
}

#[tool_handler]
impl ServerHandler for TimeServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            instructions: Some("A simple server that provides the current time.".to_string()),
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            ..Default::default()
        }
    }
}

// --- MAIN FUNCTION TO RUN THE SERVER ---
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    print!("\x1B[H\x1B[J"); // Clear screen
    println!("🚀 Starting Time MCP Server...");

    let server = TimeServer::new().serve(stdio()).await?;

    println!("✅ Server is ready with the 'get_now' tool.");
    println!("   Connect with an MCP client like MCP Inspector to use it.");

    // This will keep the server running until the client disconnects.
    server.waiting().await?;

    Ok(())
}
