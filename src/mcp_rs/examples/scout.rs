use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use mcp_rs::define_directives;
use rmcp::{
    ErrorData as McpError, RoleServer, ServerHandler, ServiceExt,
    handler::server::{
        router::prompt::PromptRouter, router::tool::ToolRouter, wrapper::Parameters,
    },
    model::*,
    prompt, prompt_handler, prompt_router,
    service::RequestContext,
    tool, tool_handler, tool_router,
    transport::stdio,
};

define_directives! {
    // * meta project directives
    Readme("readme") => file!("d-readme.md"),
    // * language-specific directives
    Rust("rs") => files!(["d-rust.md", "d-rust.rs"]),
    Python("py") => files!(["d-python.md", "d-python.py"]),
    Web("js", "ts", "svelte") => content!("Web technologies guidance placeholder"),
    // todo: complete these directives with actual content files
    Go("go") => content!("Go guidance placeholder"),
    C("c", "cpp", "c++") => content!("C-based languages guidance placeholder")
}

// --- Define the parameters for the new 'adapt' tool ---
#[derive(Debug, Serialize, Deserialize, JsonSchema)]
struct AdaptParams {
    languages: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, JsonSchema)]
struct ExploreParams {
    target_directory: Option<String>,
}

// --- Define the server struct ---
#[derive(Clone)]
struct ScoutMcpServer {
    tool_router: ToolRouter<Self>,
    prompt_router: PromptRouter<Self>,
}

impl Default for ScoutMcpServer {
    fn default() -> Self {
        Self::new()
    }
}

// --- Define the 'adapt' tool and 'explore' prompt ---
#[tool_router]
#[prompt_router]
impl ScoutMcpServer {
    pub fn new() -> Self {
        Self {
            tool_router: Self::tool_router(),
            prompt_router: Self::prompt_router(),
        }
    }

    /// Loads and combines language-specific directives to adapt the AI to a preferred coding style.
    #[tool(
        description = "Provides coding guidance and best practices for one or more technologies."
    )]
    async fn adapt(&self, params: Parameters<AdaptParams>) -> Result<CallToolResult, McpError> {
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

        Ok(CallToolResult::success(vec![Content::text(result)]))
    }

    /// Instructs the LLM to act as a 'Code Scout' to analyze a codebase.
    #[prompt(description = "Instructs the LLM to act as a 'Code Scout' to analyze a codebase.")]
    async fn explore(&self, params: Parameters<ExploreParams>) -> Result<Vec<PromptMessage>, McpError> {
        let target_directory = params.0.target_directory.as_deref().unwrap_or(".");
        let prompt_text = format!(
            r#"You are an expert software architect acting as a 'Code Scout'. Your mission is to explore the codebase in '{target_directory}' and produce a high-level overview report, adapted to the project's specific coding philosophy.

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
---"#
        );

        Ok(vec![PromptMessage::new_text(
            PromptMessageRole::User,
            prompt_text,
        )])
    }
}

// --- Implement the MCP Server Handler ---
#[tool_handler]
#[prompt_handler]
impl ServerHandler for ScoutMcpServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::LATEST,
            server_info: Implementation::from_build_env(),
            instructions: Some(
                "A server that acts as an autonomous agent to explore, analyze, and report on codebases."
                    .to_string(),
            ),
            capabilities: ServerCapabilities::builder()
                .enable_tools()
                .enable_prompts()
                .build(),
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
