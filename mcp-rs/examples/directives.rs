use rmcp::{
    ErrorData as McpError, ServerHandler, ServiceExt,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{ServerCapabilities, ServerInfo},
    tool, tool_handler, tool_router,
    transport::stdio,
};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

// --- Define the parameters for our directive tools ---
#[derive(Serialize, Deserialize, JsonSchema)]
struct GetGuidanceParams {
    language: String,
}

#[derive(Serialize, Deserialize, JsonSchema)]
struct GetMultipleGuidancesParams {
    languages: Vec<String>,
}

// --- Define the server struct ---
#[derive(Clone)]
struct DirectivesMcpServer {
    tool_router: ToolRouter<Self>,
}

impl Default for DirectivesMcpServer {
    fn default() -> Self {
        Self::new()
    }
}

// --- Language guide enum for all technology categories ---
#[derive(Debug, Clone, PartialEq)]
enum LanguageGuide {
    Go,
    Python,
    Rust,
    C,
    Web,
    Kotlin,
    Container,
    SystemTool,
}

impl LanguageGuide {
    fn from_string(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "go" | "golang" => Some(LanguageGuide::Go),
            "python" | "py" => Some(LanguageGuide::Python),
            "rust" | "rs" => Some(LanguageGuide::Rust),
            "c" | "cpp" | "c++" | "objc" | "objective-c" => Some(LanguageGuide::C),
            "web" | "javascript" | "js" | "typescript" | "ts" | "html" | "css" | "svelte"
            | "react" | "vue" => Some(LanguageGuide::Web),
            "java" | "kotlin" | "kt" => Some(LanguageGuide::Kotlin),
            "container" | "docker" | "podman" | "dockerfile" => Some(LanguageGuide::Container),
            "system" | "tool" | "rg" | "ripgrep" | "eza" | "fd" | "fzf" | "bat" | "exa" => {
                Some(LanguageGuide::SystemTool)
            }
            _ => None,
        }
    }
}

// --- Define the tools ---
#[tool_router]
impl DirectivesMcpServer {
    pub fn new() -> Self {
        Self {
            tool_router: Self::tool_router(),
        }
    }

    /// Get guidance for a specific technology
    #[tool(description = "Provides coding guidance and best practices for a specific technology.")]
    async fn get_guidance(
        &self,
        params: Parameters<GetGuidanceParams>,
    ) -> Result<String, McpError> {
        let language = &params.0.language;

        match LanguageGuide::from_string(language) {
            Some(lang_guide) => {
                let guidance = match lang_guide {
                    LanguageGuide::Go => self.get_go_guidance(),
                    LanguageGuide::Python => self.get_python_guidance(),
                    LanguageGuide::Rust => self.get_rust_guidance(),
                    LanguageGuide::C => self.get_c_guidance(),
                    LanguageGuide::Web => self.get_web_guidance(),
                    LanguageGuide::Kotlin => self.get_kotlin_guidance(),
                    LanguageGuide::Container => self.get_container_guidance(),
                    LanguageGuide::SystemTool => self.get_system_tool_guidance(),
                };
                Ok(guidance)
            }
            None => Ok(format!(
                "No specific guidance available for language: {}. Using general development philosophy.",
                language
            )),
        }
    }

    /// Get guidance for multiple technologies
    #[tool(
        description = "Provides coding guidance and best practices for multiple technologies at once."
    )]
    async fn get_multiple_guidances(
        &self,
        params: Parameters<GetMultipleGuidancesParams>,
    ) -> Result<String, McpError> {
        let mut result = String::new();
        for language in &params.0.languages {
            result.push_str(&format!("### {} Guidance:\n", language));
            result.push_str(
                &self
                    .get_guidance(Parameters(GetGuidanceParams {
                        language: language.clone(),
                    }))
                    .await?,
            );
            result.push_str("\n\n---\n\n");
        }
        Ok(result)
    }

    // Individual guidance methods will be implemented in later phases
    fn get_go_guidance(&self) -> String {
        "Go guidance placeholder".to_string()
    }

    fn get_python_guidance(&self) -> String {
        "Python guidance placeholder".to_string()
    }

    fn get_rust_guidance(&self) -> String {
        "Rust guidance placeholder".to_string()
    }

    fn get_c_guidance(&self) -> String {
        "C-based languages guidance placeholder".to_string()
    }

    fn get_web_guidance(&self) -> String {
        "Web technologies guidance placeholder".to_string()
    }

    fn get_kotlin_guidance(&self) -> String {
        "Kotlin guidance placeholder".to_string()
    }

    fn get_container_guidance(&self) -> String {
        "Container technologies guidance placeholder".to_string()
    }

    fn get_system_tool_guidance(&self) -> String {
        "System tools guidance placeholder".to_string()
    }
}

// --- Implement the MCP Server Handler ---
#[tool_handler]
impl ServerHandler for DirectivesMcpServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            instructions: Some("Provides language-specific coding guidance and best practices for various technologies.".to_string()),
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
    println!("🚀 Starting Enhanced Directives MCP server...");

    let server = DirectivesMcpServer::new().serve(stdio()).await?;

    println!("✅ Server is ready with language-specific guidance tools.");

    // Wait for the server to finish (e.g., when the client disconnects)
    server.waiting().await?;

    Ok(())
}
