//! A simple MCP server demonstrating a single, powerful prompt.
//! This prompt is a Rust version of the 'explore' prompt from the scout.py script.
use rmcp::RoleServer;
use rmcp::model::GetPromptResult;
use rmcp::model::PaginatedRequestParam;
use rmcp::model::ListPromptsResult;

// --- NECESSARY IMPORTS ---
use rmcp::{
    service::RequestContext,
    handler::server::{router::prompt::PromptRouter, wrapper::Parameters},
    model::{
        GetPromptRequestParam,
        PromptMessage, PromptMessageRole, ServerCapabilities, ServerInfo,
    },
    prompt, prompt_handler, prompt_router, ErrorData as McpError, ServerHandler, ServiceExt,
    transport::stdio,
};
use schemars::JsonSchema;
use serde::Deserialize;

// --- PROMPT PARAMETERS ---

/// Defines the arguments for the 'explore' prompt.
#[derive(Debug, Deserialize, JsonSchema)]
struct ExploreParams {
    /// The target directory to analyze, defaults to the current directory "."
    #[serde(default = "default_target_directory")]
    target_directory: String,
}

/// Helper function to provide a default value for the target_directory.
fn default_target_directory() -> String {
    ".".to_string()
}

// --- MCP SERVER DEFINITION ---

#[derive(Clone)]
struct ScoutServer {
    prompt_router: PromptRouter<Self>,
}

impl Default for ScoutServer {
    fn default() -> Self {
        Self::new()
    }
}

#[prompt_router]
impl ScoutServer {
    pub fn new() -> Self {
        Self {
            prompt_router: Self::prompt_router(),
        }
    }

    /// Instructs the LLM to act as a 'Code Scout' to analyze a codebase.
    /// It explores, identifies the language, adapts to your coding style,
    /// and then produces a comprehensive overview report.
    #[prompt(name = "explore", description = "Explore, Adapt, and Report on a Codebase")]
    async fn explore(&self, params: Parameters<ExploreParams>) -> Result<Vec<PromptMessage>, McpError> {
        let target_directory = &params.0.target_directory;

        // This is the instructional text for the AI, taken directly from scout.py
        let instructions = format!(
            r#"
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
"#
        );

        // Prompts return a vector of messages. For an instructional prompt like this,
        // it's typically a single user message containing the instructions for the AI.
        Ok(vec![PromptMessage::new_text(
            PromptMessageRole::User,
            instructions,
        )])
    }
}

#[prompt_handler]
impl ServerHandler for ScoutServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            instructions: Some("A server that provides a powerful 'explore' prompt for code analysis.".to_string()),
            capabilities: ServerCapabilities::builder().enable_prompts().build(),
            ..Default::default()
        }
    }
}

// --- MAIN FUNCTION TO RUN THE SERVER ---
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    print!("\x1B[H\x1B[J"); // Clear screen
    println!("🚀 Starting Scout Prompt MCP Server...");

    let server = ScoutServer::new().serve(stdio()).await?;

    println!("✅ Server is ready with the 'explore' prompt.");
    println!("   Connect with an MCP client like MCP Inspector to use it.");

    // Keep the server running until the client disconnects
    server.waiting().await?;

    Ok(())
}