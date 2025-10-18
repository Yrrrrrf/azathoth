use paste::paste;
use rmcp::{
    ErrorData as McpError, ServerHandler, ServiceExt,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{ServerCapabilities, ServerInfo},
    tool, tool_handler, tool_router,
    transport::stdio,
};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

// --- Define the macro for generating directive-related code ---
macro_rules! define_directives {
    ($($lang:ident ($($alias:literal),*) => $content:tt),+ $(,)?) => {
        // --- LanguageGuide Enum ---
        #[derive(Debug, Serialize, Deserialize, JsonSchema)]
        #[serde(rename_all = "camelCase")]
        pub enum LanguageGuide {
            $($lang),+
        }

        impl LanguageGuide {
            pub fn from_string(s: &str) -> Option<Self> {
                match s.to_lowercase().as_str() {
                    $(
                        stringify!($lang) | $($alias)|* => Some(Self::$lang),
                    )+
                    _ => None,
                }
            }
        }

        // --- Guidance Functions for each language ---
        $(
            paste! {
                pub fn [<get_ $lang:lower _guidance>]() -> String {
                    define_directives!(@content $lang $content).to_string()
                }
            }
        )+

        // --- Main get_guidance function ---
        pub fn get_guidance(lang: LanguageGuide) -> String {
            match lang {
                $(
                    LanguageGuide::$lang => paste! { [<get_ $lang:lower _guidance>]() },
                )+
            }
        }
    };
    // --- Content handlers for the macro ---
    (@content $lang:ident {$lang_name:literal, [$($ext:literal),*]}) => {
        concat!(
            $(
                include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/meta-prompt/d-", $lang_name, ".", $ext)),
                "\n"
            ),*
        )
    };
    (@content $lang:ident {$str:literal}) => {
        $str
    };
    (@content $lang:ident {$($file:tt)*}) => {
        include_str!($($file)*)
    };
}

// --- Define the languages, their aliases, and the content to be served ---
define_directives! {
    // LANGUAGE (ALIASES) => CONTENT
    //* Lang(alias) => {file_path} or {"string content"} or {lang_name, [ext1, ext2]}
    Go("golang") => {"Go guidance placeholder"},
    Python("py") => {"python", ["md", "py"]},
    Rust("rs") => {"Rust guidance placeholder"},
    C("cpp", "c++", "objc", "objective-c") => {"C-based languages guidance placeholder"},
    Web("javascript", "js", "typescript", "ts", "html", "css", "svelte", "react", "vue") => {"Web technologies guidance placeholder"},
    Kotlin("java", "kt") => {"Kotlin guidance placeholder"},
    Container("docker", "podman", "dockerfile") => {"Container technologies guidance placeholder"},
    SystemTool("system", "tool", "rg", "ripgrep", "eza", "fd", "fzf", "bat", "exa") => {"System tools guidance placeholder"}
}

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
            Some(lang_guide) => Ok(get_guidance(lang_guide)),
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