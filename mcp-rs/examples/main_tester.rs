// ALL NECESSARY IMPORTS ARE NOW INCLUDED
use rmcp::{
    handler::server::{router::prompt::PromptRouter, router::tool::ToolRouter, wrapper::Parameters},
    model::{
        GetPromptRequestParam, GetPromptResult, ListPromptsResult, PaginatedRequestParam,
        PromptMessage, PromptMessageRole, ServerCapabilities, ServerInfo,
    },
    prompt, prompt_handler, prompt_router,
    service::{RequestContext, RoleServer},
    tool, tool_handler, tool_router, ErrorData as McpError, ServerHandler, ServiceExt,
    transport::stdio,
};
use schemars::JsonSchema;
use serde::Deserialize;

// --- Server Definition (Your code is correct and remains unchanged) ---

#[derive(Debug, Deserialize, JsonSchema)]
struct ParseStrParams {
    values: Vec<String>,
}

#[derive(Clone)]
struct ComplexMcpServer {
    tool_router: ToolRouter<Self>,
    prompt_router: PromptRouter<Self>,
}

impl Default for ComplexMcpServer {
    fn default() -> Self {
        Self::new()
    }
}

#[tool_router]
#[prompt_router]
impl ComplexMcpServer {
    pub fn new() -> Self {
        Self {
            tool_router: Self::tool_router(),
            prompt_router: Self::prompt_router(),
        }
    }

    #[tool(description = "Parses a list of string values and returns a formatted summary.")]
    async fn parse_str(&self, params: Parameters<ParseStrParams>) -> Result<String, McpError> {
        static TOOL_USAGE_COUNTER: std::sync::atomic::AtomicUsize =
            std::sync::atomic::AtomicUsize::new(1);
        let usage_count = TOOL_USAGE_COUNTER.fetch_add(1, std::sync::atomic::Ordering::SeqCst);

        let values = &params.0.values;
        println!(
            "\x1b[33mTool usage {}:\x1b[0m {}",
            usage_count,
            values.join(" ")
        );
        let formatted_string = format!(
            "\x1b[1;32m✅ Parsed Values:\x1b[0m \x1b[34m[{}]\x1b[0m",
            values.join(", ")
        );
        Ok(formatted_string)
    }

    #[prompt(description = "Instructs the AI to call the 'parse_str' tool multiple times.")]
    async fn instruct_parse(&self) -> Vec<PromptMessage> {
        vec![PromptMessage::new_text(
            PromptMessageRole::User,
            // The server name is likely 'main-tester' based on your example file name.
            // If you named it something else in your client's config, use that name.
            "You MUST call the `main-tester.parse_str` tool exactly two times with no other text or explanation.

    1. First, call the `main-tester.parse_str` tool with the following values: `[\"1\", \"2\", \"3\"]`
    2. Second, call the `main-tester.parse_str` tool with the following values: `[\"a\", \"b\", \"c\"]`",
        )]
    }
}

#[tool_handler]
#[prompt_handler]
impl ServerHandler for ComplexMcpServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            instructions: Some(
                "A server with a tool to parse strings and a prompt to instruct its use."
                    .to_string(),
            ),
            capabilities: ServerCapabilities::builder()
                .enable_tools()
                .enable_prompts()
                .build(),
            ..Default::default()
        }
    }
}

// --- Corrected Main Function ---
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Clear the screen for a clean start
    print!("\x1B[H\x1B[J");
    println!("🚀 Starting Complex Rust MCP server...");

    // Create and serve the server over standard I/O
    let server = ComplexMcpServer::new().serve(stdio()).await?;

    println!("✅ Server is ready with the 'parse_str' tool and the 'instruct_parse' prompt.");
    println!("   Waiting for a client connection (e.g., from MCP Inspector)...");

    // Keeps the server running until the client disconnects or the process is terminated.
    server.waiting().await?;

    Ok(())
}