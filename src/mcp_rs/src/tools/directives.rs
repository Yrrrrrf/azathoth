#[macro_export]
macro_rules! define_directives {
    ($($lang:ident ($($alias:literal),*) => $content:tt),+ $(,)?) => {
        // --- LanguageGuide Enum ---
        #[derive(Debug, Serialize, Deserialize, JsonSchema)]
        #[serde(rename_all = "camelCase")]
        pub enum LanguageGuide {
            $($lang),+
        }

        impl LanguageGuide {
            /// Case-insensitively checks the input string against the language
            /// names and their defined aliases.
            pub fn from_string(s: &str) -> Option<Self> {
                let s_lower = s.to_lowercase();
                $(
                    // This check now correctly handles the primary language name (e.g., "Python")
                    // by converting it to lowercase before comparing. It also iterates
                    // through all provided aliases.
                    if s_lower == stringify!($lang).to_lowercase() $( || s_lower.as_str() == $alias )* {
                        return Some(Self::$lang);
                    }
                )+
                None
            }
        }

        // --- Guidance Functions for each language (unchanged) ---
        $(
            paste! {
                pub fn [<get_ $lang:lower _guidance>]() -> String {
                    define_directives!(@content $lang $content).to_string()
                }
            }
        )+

        // --- Main get_guidance function (unchanged) ---
        pub fn get_guidance(lang: LanguageGuide) -> String {
            match lang {
                $(
                    LanguageGuide::$lang => paste! { [<get_ $lang:lower _guidance>]() },
                )+
            }
        }
    };
    // --- Content handlers for the macro (unchanged) ---
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
