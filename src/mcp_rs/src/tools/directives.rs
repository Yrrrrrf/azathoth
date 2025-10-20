#[macro_export]
macro_rules! define_directives {
    (
        $($lang:ident ($($alias:literal),*) => $content_type:ident ! ( $($content:tt)* ) ),+
        $(,)?
    ) => {
        // --- LanguageGuide Enum (Unchanged) ---
        #[derive(Debug, Serialize, Deserialize, JsonSchema)]
        #[serde(rename_all = "camelCase")]
        pub enum LanguageGuide {
            $($lang),+
        }

        // --- from_string Implementation (Unchanged from our fix) ---
        impl LanguageGuide {
            pub fn from_string(s: &str) -> Option<Self> {
                let s_lower = s.to_lowercase();
                $(
                    if s_lower == stringify!($lang).to_lowercase() $( || s_lower.as_str() == $alias )* {
                        return Some(Self::$lang);
                    }
                )+
                None
            }
        }

        // --- Enhanced get_guidance function ---
        // This now generates the content-loading logic directly inside the match arm,
        // which is cleaner and more efficient than creating many small functions.
        pub fn get_guidance(lang: LanguageGuide) -> String {
            match lang {
                $(
                    LanguageGuide::$lang => {
                        // The macro calls a helper rule to process the content.
                        define_directives!(@process_content $content_type ! ( $($content)* ))
                    }
                )+
            }
        }
    };

    // --- Helper rule for processing 'content!("...")' ---
    // Handles simple inline strings.
    (@process_content content ! ($str:literal)) => {
        $str.to_string()
    };

    // --- Helper rule for processing 'file!("...")' ---
    // Handles including a single file's content.
    (@process_content file ! ($path:literal)) => {
        include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/meta-prompt/", $path)).to_string()
    };

    // --- Helper rule for processing 'files!(["...", "..."])' ---
    // Handles combining multiple files into a single string.
    (@process_content files ! ([$($path:literal),+])) => {
        {
            let mut combined = String::new();
            $(
                let content = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/meta-prompt/", $path));
                if !combined.is_empty() {
                    combined.push_str("\n\n---\n\n");
                }
                combined.push_str(content);
            )+
            combined
        }
    };
}
