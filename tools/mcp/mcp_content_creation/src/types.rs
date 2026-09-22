//! Argument and result types for the content creation server.
//!
//! Tool arguments are deserialized into the typed `*Args` structs below, so a
//! wrong-typed or unknown enum value becomes a clean `InvalidParameters` error
//! instead of being silently replaced by a default. Enum values are matched
//! case-insensitively and some accept short aliases (e.g. `"l"` for `"low"`).

use serde::{Deserialize, Serialize};

/// Declare a string-valued enum with case-insensitive parsing, aliases, and
/// serde support. The first literal of each variant is its canonical name.
macro_rules! string_enum {
    (
        $(#[$meta:meta])*
        $name:ident { $( $(#[$vmeta:meta])* $variant:ident => [$canon:literal $(, $alias:literal)*] ),+ $(,)? }
    ) => {
        $(#[$meta])*
        #[derive(Debug, Clone, Copy, PartialEq, Eq)]
        pub enum $name {
            $( $(#[$vmeta])* $variant ),+
        }

        impl $name {
            /// Canonical names of every variant, in declaration order.
            pub const VALUES: &'static [&'static str] = &[$($canon),+];

            /// Canonical string form of this value.
            pub fn as_str(self) -> &'static str {
                match self {
                    $( Self::$variant => $canon ),+
                }
            }
        }

        impl std::str::FromStr for $name {
            type Err = String;

            fn from_str(s: &str) -> Result<Self, String> {
                let lower = s.trim().to_ascii_lowercase();
                $(
                    if lower == $canon $(|| lower == $alias)* {
                        return Ok(Self::$variant);
                    }
                )+
                Err(format!(
                    "invalid value '{}' (expected one of: {})",
                    s,
                    Self::VALUES.join(", ")
                ))
            }
        }

        impl<'de> Deserialize<'de> for $name {
            fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
                let s = String::deserialize(d)?;
                s.parse().map_err(serde::de::Error::custom)
            }
        }

        impl Serialize for $name {
            fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
                s.serialize_str(self.as_str())
            }
        }
    };
}

string_enum! {
    /// Output format for `compile_latex`.
    LatexFormat {
        Pdf => ["pdf"],
        Dvi => ["dvi"],
        Ps => ["ps", "postscript"],
    }
}

impl LatexFormat {
    /// File extension produced for this format.
    pub fn extension(self) -> &'static str {
        self.as_str()
    }
}

string_enum! {
    /// Output format for `render_tikz`.
    TikzFormat {
        Pdf => ["pdf"],
        Png => ["png"],
        Svg => ["svg"],
    }
}

string_enum! {
    /// Document template used to wrap a LaTeX fragment.
    LatexTemplate {
        Article => ["article"],
        Report => ["report"],
        Book => ["book"],
        Beamer => ["beamer"],
        /// Use the content verbatim.
        Custom => ["custom", "none"],
    }
}

string_enum! {
    /// How much detail to include in tool responses.
    ResponseMode {
        /// Paths only.
        Minimal => ["minimal"],
        /// Paths plus metadata (timings, page counts, previews, warnings).
        Standard => ["standard"],
    }
}

string_enum! {
    /// Output format for `create_manim_animation`.
    ManimFormat {
        Mp4 => ["mp4"],
        Gif => ["gif"],
        /// Last frame of the scene as a still image.
        Png => ["png"],
        Webm => ["webm"],
    }
}

string_enum! {
    /// Manim render quality preset.
    ManimQuality {
        /// 480p15
        Low => ["low", "l"],
        /// 720p30
        Medium => ["medium", "m"],
        /// 1080p60
        High => ["high", "h"],
        /// 1440p60
        Production => ["production", "p"],
        /// 2160p60
        FourK => ["fourk", "k", "4k"],
    }
}

impl ManimQuality {
    /// Value for manim's `-q` flag.
    pub fn flag(self) -> &'static str {
        match self {
            ManimQuality::Low => "l",
            ManimQuality::Medium => "m",
            ManimQuality::High => "h",
            ManimQuality::Production => "p",
            ManimQuality::FourK => "k",
        }
    }
}

// ============================================================================
// Tool arguments
// ============================================================================

/// Arguments for `compile_latex`.
#[derive(Debug, Clone, Default, Deserialize)]
pub struct CompileLatexArgs {
    pub content: Option<String>,
    pub input_path: Option<String>,
    /// `format` is accepted as a legacy alias.
    #[serde(alias = "format")]
    pub output_format: Option<LatexFormat>,
    pub template: Option<LatexTemplate>,
    pub response_mode: Option<ResponseMode>,
    pub preview_pages: Option<String>,
    pub preview_dpi: Option<u32>,
    /// Legacy flag: when true and `preview_pages` is unset, preview page 1.
    pub visual_feedback: Option<bool>,
}

/// Arguments for `render_tikz`.
#[derive(Debug, Clone, Default, Deserialize)]
pub struct RenderTikzArgs {
    pub tikz_code: String,
    pub output_format: Option<TikzFormat>,
    pub response_mode: Option<ResponseMode>,
    pub tikz_libraries: Option<Vec<String>>,
    pub packages: Option<Vec<String>>,
    pub dpi: Option<u32>,
}

/// Arguments for `preview_pdf`.
#[derive(Debug, Clone, Default, Deserialize)]
pub struct PreviewPdfArgs {
    pub pdf_path: String,
    pub pages: Option<String>,
    pub dpi: Option<u32>,
    pub response_mode: Option<ResponseMode>,
}

/// Arguments for `create_manim_animation`.
#[derive(Debug, Clone, Default, Deserialize)]
pub struct ManimArgs {
    pub script: String,
    pub output_format: Option<ManimFormat>,
    pub scene_name: Option<String>,
    pub quality: Option<ManimQuality>,
    /// Render only the last frame as a PNG (same as `output_format: "png"`).
    pub preview: Option<bool>,
}

// ============================================================================
// Tool results
// ============================================================================

/// Result of `compile_latex` and `render_tikz`.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CompileResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    /// Host-relative path of the output (what a user outside the container sees).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    /// Path of the output inside the server's filesystem.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub container_path: Option<String>,
    /// Host-relative path of the intermediate PDF (render_tikz PNG/SVG only).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pdf_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub page_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file_size_kb: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub compile_time_seconds: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latex_passes: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preview_paths: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub warnings: Option<Vec<String>>,
}

impl CompileResult {
    /// A failed result carrying only an error message.
    pub fn failure(error: impl Into<String>) -> Self {
        Self {
            success: false,
            error: Some(error.into()),
            ..Default::default()
        }
    }
}

/// Result of `create_manim_animation`.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ManimResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub container_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scene_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub quality: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file_size_kb: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub render_time_seconds: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub warnings: Option<Vec<String>>,
}

impl ManimResult {
    /// A failed result carrying only an error message.
    pub fn failure(error: impl Into<String>) -> Self {
        Self {
            success: false,
            error: Some(error.into()),
            ..Default::default()
        }
    }
}

/// Result of `preview_pdf`.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PreviewResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preview_paths: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pdf_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub page_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pages_exported: Option<Vec<u32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub warnings: Option<Vec<String>>,
}

impl PreviewResult {
    /// A failed result carrying only an error message.
    pub fn failure(error: impl Into<String>) -> Self {
        Self {
            success: false,
            error: Some(error.into()),
            ..Default::default()
        }
    }
}

/// Wrap `Vec<String>` as `None` when empty so it is omitted from JSON.
pub fn non_empty(v: Vec<String>) -> Option<Vec<String>> {
    if v.is_empty() { None } else { Some(v) }
}

/// Round to two decimals for friendlier JSON.
pub fn round2(x: f64) -> f64 {
    (x * 100.0).round() / 100.0
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn enums_parse_case_insensitively_with_aliases() {
        assert_eq!("PDF".parse::<LatexFormat>(), Ok(LatexFormat::Pdf));
        assert_eq!(" ps ".parse::<LatexFormat>(), Ok(LatexFormat::Ps));
        assert_eq!("4K".parse::<ManimQuality>(), Ok(ManimQuality::FourK));
        assert_eq!("m".parse::<ManimQuality>(), Ok(ManimQuality::Medium));
        assert_eq!("none".parse::<LatexTemplate>(), Ok(LatexTemplate::Custom));
    }

    #[test]
    fn enum_errors_list_valid_values() {
        let err = "png".parse::<LatexFormat>().unwrap_err();
        assert!(err.contains("pdf, dvi, ps"), "{err}");
    }

    #[test]
    fn compile_args_accept_legacy_format_alias() {
        let args: CompileLatexArgs =
            serde_json::from_value(json!({"content": "x", "format": "dvi"})).unwrap();
        assert_eq!(args.output_format, Some(LatexFormat::Dvi));
    }

    #[test]
    fn invalid_enum_value_is_rejected() {
        let res: Result<RenderTikzArgs, _> =
            serde_json::from_value(json!({"tikz_code": "x", "output_format": "jpeg"}));
        assert!(res.unwrap_err().to_string().contains("expected one of"));
    }

    #[test]
    fn nulls_are_treated_as_absent() {
        let args: ManimArgs =
            serde_json::from_value(json!({"script": "s", "quality": null, "scene_name": null}))
                .unwrap();
        assert!(args.quality.is_none());
        assert!(args.scene_name.is_none());
    }

    #[test]
    fn enums_serialize_to_canonical_names() {
        assert_eq!(
            serde_json::to_value(ManimQuality::FourK).unwrap(),
            json!("fourk")
        );
    }

    #[test]
    fn failure_results_omit_empty_fields() {
        let v = serde_json::to_value(CompileResult::failure("boom")).unwrap();
        assert_eq!(v, json!({"success": false, "error": "boom"}));
    }
}
