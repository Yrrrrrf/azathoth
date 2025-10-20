use paste::paste;
use rmcp::{
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{ServerCapabilities, ServerInfo},
    tool, tool_handler, tool_router, ErrorData as McpError, ServerHandler, ServiceExt,
    transport::stdio,
};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

// --- This macro is the core of your directive loading system and remains unchanged ---
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
                include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/meta-prompt/d-", $lang_name, ".", $ext))
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
// This section is also unchanged and continues to power the logic.
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
    #[tool(description = "Provides coding guidance and best practices for one or more technologies.")]
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
