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
