use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use mcp_rs::define_directives;
use rmcp::{
    ErrorData as McpError, ServerHandler, ServiceExt,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{ServerCapabilities, ServerInfo},
    tool, tool_handler, tool_router,
    transport::stdio,
};

define_directives! {
    // 1. For simple, inline string content
    Go("golang") => content!("Go guidance placeholder"),

    // 2. To load a single, specific directive file
    // Python("py") => file!("d-python.md"),
    Python("py") => files!(["d-python.md", "d-python.py"]),

    // 3. To combine multiple files into one master directive
    // Rust("rs") => files!(["d-rust.md"]), // Assuming you create a d-rust.md

    // You can mix and match as needed
    Web("js", "ts", "svelte") => content!("Web technologies guidance placeholder"),
    C("cpp", "c++") => content!("C-based languages guidance placeholder")
}

// --- Define the parameters for the new 'adapt' tool ---
// This now takes a Vec<String> as requested.
#[derive(Serialize, Deserialize, JsonSchema)]
struct AdaptParams {
    languages: Vec<String>,
}

// --- Define the server struct, renamed for clarity ---
#[derive(Clone)]
struct ScoutMcpServer {
    tool_router: ToolRouter<Self>,
}

impl Default for ScoutMcpServer {
    fn default() -> Self {
        Self::new()
    }
}

// --- Define the single 'adapt' tool ---
#[tool_router]
impl ScoutMcpServer {
    pub fn new() -> Self {
        Self {
            tool_router: Self::tool_router(),
        }
    }

    /// Loads and combines language-specific directives to adapt the AI to a preferred coding style.
    #[tool(
        description = "Provides coding guidance and best practices for one or more technologies."
    )]
    async fn adapt(&self, params: Parameters<AdaptParams>) -> Result<String, McpError> {
        let mut result = String::new();
        let core_philosophy = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../assets/meta-prompt/core-philosophy.md"
        ));

        // The core philosophy is always the foundation.
        result.push_str(core_philosophy);

        // Append specific language directives if any are requested.
        for language in &params.0.languages {
            result.push_str("\n\n---\n\n");
            let guidance = match LanguageGuide::from_string(language) {
                Some(lang_guide) => get_guidance(lang_guide),
                None => format!(
                    "Note: No specific guidance available for language: '{}'.",
                    language
                ),
            };
            result.push_str(&guidance);
        }
        Ok(result)
    }
}

// --- Implement the MCP Server Handler ---
#[tool_handler]
impl ServerHandler for ScoutMcpServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            instructions: Some(
                "A server that adapts an AI to a specific coding style using directives."
                    .to_string(),
            ),
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            ..Default::default()
        }
    }
}

// --- Main function to run the server ---
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Clear the screen for a clean start
    print!("\x1B[H\x1B[J");
    println!("🚀 Starting Scout MCP server (Rust)...");

    let server = ScoutMcpServer::new().serve(stdio()).await?;

    println!("✅ Server is ready with the 'adapt' tool.");

    // Wait for the server to finish (e.g., when the client disconnects)
    server.waiting().await?;

    Ok(())
}
