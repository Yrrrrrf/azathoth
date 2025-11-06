// FILE: src/mcp_rs/examples/workflow.rs

//! A focused MCP server that provides a suite of intelligent, automated tools
//! for common Git tasks like committing changes and publishing releases.
//!
//! To run this server, add a configuration to your MCP client:
//! "workflow": {
//!   "command": "cargo",
//!   "args": [ "run", "--example", "workflow", "--release" ],
//!   "cwd": "/path/to/your/project/that/uses/git", // IMPORTANT: This ensures commands run in the correct repo
//!   "timeout": 60000
//! }

// --- Corrected and complete imports ---
use rmcp::{
    ErrorData as McpError, ServerHandler, ServiceExt,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{GetPromptRequestParam, GetPromptResult, ListPromptsResult, PaginatedRequestParam},
    model::{PromptMessage, PromptMessageRole, ServerCapabilities, ServerInfo},
    prompt, prompt_handler, prompt_router,
    service::{RequestContext, RoleServer},
    tool, tool_handler, tool_router,
    transport::stdio,
};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::io::Write;
use std::process::Command;
use tempfile::NamedTempFile;

// --- Helper for command execution ---

/// Executes a command and returns its stdout if successful, or an McpError otherwise.
/// Crucially, this runs in the current working directory, which the MCP client sets.
fn run_command(program: &str, args: &[&str]) -> Result<String, McpError> {
    let output = Command::new(program)
        .args(args)
        .output()
        // FIX: The internal_error function requires a second argument of Option<Value>.
        .map_err(|e| {
            McpError::internal_error(
                format!("Failed to execute command '{}': {}", program, e),
                None,
            )
        })?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        // FIX: The internal_error function requires a second argument of Option<Value>.
        Err(McpError::internal_error(
            format!(
                "Command '{} {}' failed with status {}:\n{}",
                program,
                args.join(" "),
                output.status,
                stderr
            ),
            None,
        ))
    }
}

// --- Tool Parameters Definition ---

#[derive(Debug, Deserialize, Serialize, JsonSchema)]
struct StageAndCommitParams {
    commit_title: String,
    commit_body: String,
}

#[derive(Debug, Deserialize, Serialize, JsonSchema)]
struct CreateGitReleaseParams {
    version_tag: String,
    release_notes: String,
    #[serde(default)]
    is_prerelease: bool,
}

// --- Server Definition ---

#[derive(Clone)]
struct WorkflowServer {
    tool_router: ToolRouter<Self>,
    prompt_router: rmcp::handler::server::router::prompt::PromptRouter<Self>,
}

impl Default for WorkflowServer {
    fn default() -> Self {
        Self::new()
    }
}

#[tool_router]
#[prompt_router]
impl WorkflowServer {
    pub fn new() -> Self {
        Self {
            tool_router: Self::tool_router(),
            prompt_router: Self::prompt_router(),
        }
    }

    // --- Prompts (The "Brains") ---

    #[prompt(description = "[Workflow] Autocommit All Changes")]
    async fn autocommit(
        &self,
        params: Parameters<Option<String>>, // The optional 'focus' string
    ) -> Result<Vec<PromptMessage>, McpError> {
        let focus_instruction = params
            .0
            .map(|focus| {
                format!("\n\n**User's Focus for this commit is:** '{focus}'. Tailor the commit message accordingly.")
            })
            .unwrap_or_default();

        let instructions = format!(
            r#"
You are an expert software engineer. Your task is to intelligently create and execute a conventional Git commit.

**Your process MUST be as follows:**

THE ZERO LAW OF GIT COMMITS:
0. **UNDEBATABLE RULE**: You MUST NEVER add any kind of co-author or sign-off lines to the commit message. The commit MUST be clean and professional!

1.  **Stage All Changes:** First, you MUST run `git add .` to ensure that all modified and new files are staged. This guarantees that the commit will be comprehensive.

2.  **Analyze Staged Changes:** After staging, you MUST review the context of the staged code changes by inspecting `git diff --staged`.

3.  **Generate a Commit Message:** Based on the changes and the user's focus, write a high-quality conventional commit message with a `title` and a `body`.

4.  **Execute the Commit:** You MUST immediately call the `workflow.stage_and_commit` tool to finalize the process. Pass the `commit_title` and `commit_body` you just generated as arguments to the tool.

Do not ask for confirmation at any step. Perform this entire sequence of actions directly.
{}"#,
            focus_instruction
        );

        Ok(vec![PromptMessage::new_text(
            PromptMessageRole::User,
            instructions,
        )])
    }

    #[prompt(description = "[Workflow] Autorelease New Version")]
    async fn autorelease(
        &self,
        params: Parameters<String>, // The 'new_version' string
    ) -> Result<Vec<PromptMessage>, McpError> {
        let new_version = params.0;
        let instructions = format!(
            r#"
You are an expert release manager. Your task is to fully automate the creation and publication of the new software release: **{new_version}**.

**Your process MUST be as follows, without asking for confirmation:**

1.  **Find Previous Version:** Execute the shell command `git describe --tags --abbrev=0` to find the most recent Git tag. This is the `old_version`. If this command fails (e.g., no tags exist), you must find the very first commit hash of the repository to use as a starting point.

2.  **Gather Commit History:** Get the log of all commits between the `old_version` and HEAD. The command `git log <old_version>..HEAD --pretty=format:"- %s"` is ideal for this, as it provides a clean list for your analysis.

3.  **Generate Release Notes:** You must now write the release notes. Your writing style and structure MUST be professional and clear. Use the commit history you just gathered as your primary source of information to describe what's new, what's improved, and what's fixed.

4.  **Create the Release:** You MUST immediately call the `workflow.create_git_release` tool. Pass the `{new_version}` as the `version_tag` and the full Markdown notes you just generated as the `release_notes`.
"#
        );

        Ok(vec![PromptMessage::new_text(
            PromptMessageRole::User,
            instructions,
        )])
    }

    // --- Tools (The "Hands") ---

    #[tool(
        description = "Stages all current changes and safely commits them with a provided message."
    )]
    async fn stage_and_commit(
        &self,
        params: Parameters<StageAndCommitParams>,
    ) -> Result<String, McpError> {
        // Stage all changes first.
        run_command("git", &["add", "."])?;

        // Use a temp file for the commit message to handle multi-line bodies safely.
        let full_commit_message = format!("{}\n\n{}", params.0.commit_title, params.0.commit_body);
        let mut tmp_file = NamedTempFile::new()
            // FIX: The internal_error function requires a second argument of Option<Value>.
            .map_err(|e| {
                McpError::internal_error(format!("Failed to create temp file: {e}"), None)
            })?;

        write!(tmp_file, "{}", full_commit_message)
            // FIX: The internal_error function requires a second argument of Option<Value>.
            .map_err(|e| {
                McpError::internal_error(format!("Failed to write to temp file: {e}"), None)
            })?;

        let commit_output =
            run_command("git", &["commit", "-F", tmp_file.path().to_str().unwrap()])?;

        Ok(format!("Commit successful:\n{}", commit_output))
    }

    #[tool(description = "Creates a Git tag, pushes it, and creates a GitHub Release.")]
    async fn create_git_release(
        &self,
        params: Parameters<CreateGitReleaseParams>,
    ) -> Result<String, McpError> {
        let p = params.0;
        run_command("git", &["tag", &p.version_tag])?;
        run_command("git", &["push", "origin", &p.version_tag])?;

        let title_arg = format!("Release {}", p.version_tag);
        let mut args = vec![
            "release",
            "create",
            &p.version_tag,
            "--notes",
            &p.release_notes,
            "--title",
            &title_arg,
        ];

        if p.is_prerelease {
            args.push("--prerelease");
        }

        let release_output = run_command("gh", &args)?;

        Ok(format!(
            "Successfully created release {}.\nURL: {}",
            p.version_tag, release_output
        ))
    }
}

#[tool_handler]
#[prompt_handler]
impl ServerHandler for WorkflowServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            instructions: Some(
                "A server providing prompts and tools for common Git tasks like committing code and creating release notes.".to_string(),
            ),
            capabilities: ServerCapabilities::builder()
                .enable_tools()
                .enable_prompts()
                .build(),
            ..Default::default()
        }
    }
}

// --- Main function to run the server ---
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    print!("\x1B[H\x1B[J"); // Clear screen
    println!("🚀 Starting Git Workflow MCP server (Rust)...");

    let server = WorkflowServer::new().serve(stdio()).await?;

    println!("✅ Server is ready. It exposes intelligent workflows for Git tasks.");
    println!("   Ensure the client's 'cwd' is set to the target git repository.");

    server.waiting().await?;

    Ok(())
}
