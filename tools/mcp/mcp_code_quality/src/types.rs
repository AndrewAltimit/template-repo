//! Data types for the code quality MCP server.
//!
//! The string enums here are deserialized case-insensitively from tool
//! arguments. An unknown value is a hard `InvalidParameters` error that lists
//! the accepted values -- the previous implementation silently fell back to a
//! default (e.g. `linter: "pylint"` quietly ran ruff), which hid mistakes.

use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::fmt;
use std::str::FromStr;

/// Defines a closed, case-insensitive string enum with `as_str`, `ALL`,
/// `FromStr`, `Display`, and serde impls that round-trip the lowercase name.
macro_rules! string_enum {
    (
        $(#[$meta:meta])*
        $vis:vis enum $name:ident { $($(#[$vmeta:meta])* $variant:ident => $s:literal),+ $(,)? }
    ) => {
        $(#[$meta])*
        #[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
        $vis enum $name { $($(#[$vmeta])* $variant),+ }

        impl $name {
            /// Every accepted value, in declaration order.
            pub const ALL: &'static [$name] = &[$($name::$variant),+];

            /// Canonical lowercase name.
            pub fn as_str(self) -> &'static str {
                match self { $($name::$variant => $s),+ }
            }

            /// Accepted names, for schemas and error messages.
            pub fn names() -> Vec<&'static str> {
                Self::ALL.iter().map(|v| v.as_str()).collect()
            }
        }

        impl FromStr for $name {
            type Err = String;
            fn from_str(s: &str) -> Result<Self, Self::Err> {
                let lower = s.trim().to_ascii_lowercase();
                Self::ALL
                    .iter()
                    .copied()
                    .find(|v| v.as_str() == lower)
                    .ok_or_else(|| format!(
                        "unknown {} '{}' (expected one of: {})",
                        stringify!($name).to_ascii_lowercase(),
                        s,
                        Self::names().join(", ")
                    ))
            }
        }

        impl fmt::Display for $name {
            fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str(self.as_str())
            }
        }

        impl Serialize for $name {
            fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
                s.serialize_str(self.as_str())
            }
        }

        impl<'de> Deserialize<'de> for $name {
            fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
                let s = String::deserialize(d)?;
                s.parse().map_err(serde::de::Error::custom)
            }
        }
    };
}

string_enum! {
    /// Programming language for `format_check` / `autoformat`.
    #[derive(Default)]
    pub enum Language {
        #[default]
        Python => "python",
        Javascript => "javascript",
        Typescript => "typescript",
        Go => "go",
        Rust => "rust",
    }
}

string_enum! {
    /// Python formatter backend.
    #[derive(Default)]
    pub enum PythonFormatter {
        /// `ruff format` -- what this repository's CI uses.
        #[default]
        Ruff => "ruff",
        /// `black`.
        Black => "black",
    }
}

string_enum! {
    /// Linter for the `lint` tool.
    #[derive(Default)]
    pub enum Linter {
        Flake8 => "flake8",
        #[default]
        Ruff => "ruff",
        Eslint => "eslint",
        Golint => "golint",
        Clippy => "clippy",
    }
}

string_enum! {
    /// Severity / confidence threshold for bandit.
    #[derive(Default)]
    pub enum Severity {
        #[default]
        Low => "low",
        Medium => "medium",
        High => "high",
    }
}

/// Machine-readable error categories carried in [`CheckResult::error_type`].
pub mod error_type {
    /// Per-operation rate limit exceeded.
    pub const RATE_LIMIT: &str = "rate_limit";
    /// Path missing, unreadable, or outside the allowlist.
    pub const PATH_VALIDATION: &str = "path_validation";
    /// Argument failed validation (bad range, forbidden characters, ...).
    pub const INVALID_INPUT: &str = "invalid_input";
    /// External tool binary is not installed / not on PATH.
    pub const TOOL_NOT_FOUND: &str = "tool_not_found";
    /// External tool exceeded the configured timeout and was killed.
    pub const TIMEOUT: &str = "timeout";
    /// External tool ran but failed in a way that produced no usable result.
    pub const TOOL_ERROR: &str = "tool_error";
    /// Unexpected I/O failure spawning or talking to the tool.
    pub const EXCEPTION: &str = "exception";
}

/// Result payload returned (as JSON) by every check tool.
///
/// `success` means "the tool ran and produced a usable result"; whether the
/// code actually passed the check is reported separately in `passed` /
/// `formatted`. Fields that do not apply to a tool are omitted.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CheckResult {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub passed: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub formatted: Option<bool>,
    /// Files the formatter reported as needing reformatting (best effort).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unformatted_files: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub command: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issues: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issue_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub findings: Option<Vec<serde_json::Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finding_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vulnerabilities: Option<Vec<serde_json::Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vulnerability_count: Option<usize>,
    /// Aggregated counts (bandit severities, pytest outcome counts, ...).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub summary: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub returncode: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub allowed_paths: Option<Vec<String>>,
    // Markdown link checker fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub files_checked: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total_links: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub broken_links: Option<usize>,
    /// Per-link details for every broken link (file, url, lines, error).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub broken: Option<Vec<serde_json::Value>>,
    /// True when output or a result list was cut to the configured limits.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub truncated: Option<bool>,
    /// Wall-clock time of the external command.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_ms: Option<u64>,
    /// Caveats about how the request was interpreted (ignored options, ...).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes: Option<Vec<String>>,
}

impl CheckResult {
    /// A successful (tool ran) result with no fields populated yet.
    pub fn success() -> Self {
        Self {
            success: true,
            ..Self::default()
        }
    }

    /// A failed result with a message and one of the [`error_type`] codes.
    pub fn error(message: impl Into<String>, error_type: impl Into<String>) -> Self {
        Self {
            success: false,
            error: Some(message.into()),
            error_type: Some(error_type.into()),
            ..Self::default()
        }
    }

    /// Append a caveat to `notes`.
    pub fn note(&mut self, note: impl Into<String>) {
        self.notes.get_or_insert_with(Vec::new).push(note.into());
    }
}

/// One JSON line of the audit log.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub timestamp: String,
    pub operation: String,
    pub path: String,
    pub success: bool,
    #[serde(default)]
    pub details: serde_json::Value,
}

/// Availability of one external tool, reported by `get_status`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolStatus {
    pub available: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enums_parse_case_insensitively() {
        assert_eq!("Python".parse::<Language>().unwrap(), Language::Python);
        assert_eq!(" RUFF ".parse::<Linter>().unwrap(), Linter::Ruff);
        assert_eq!("High".parse::<Severity>().unwrap(), Severity::High);
        assert_eq!(
            "black".parse::<PythonFormatter>().unwrap(),
            PythonFormatter::Black
        );
    }

    #[test]
    fn unknown_enum_value_lists_choices() {
        let err = "pylint".parse::<Linter>().unwrap_err();
        assert!(err.contains("pylint"));
        assert!(err.contains("flake8, ruff, eslint, golint, clippy"));
    }

    #[test]
    fn enums_serde_roundtrip() {
        let v = serde_json::to_value(Language::Typescript).unwrap();
        assert_eq!(v, "typescript");
        let back: Language = serde_json::from_value(serde_json::json!("TypeScript")).unwrap();
        assert_eq!(back, Language::Typescript);
        assert!(serde_json::from_value::<Language>(serde_json::json!("cobol")).is_err());
        assert!(serde_json::from_value::<Language>(serde_json::json!(3)).is_err());
    }

    #[test]
    fn defaults() {
        assert_eq!(Language::default(), Language::Python);
        assert_eq!(Linter::default(), Linter::Ruff);
        assert_eq!(Severity::default(), Severity::Low);
        assert_eq!(PythonFormatter::default(), PythonFormatter::Ruff);
    }

    #[test]
    fn check_result_omits_empty_fields() {
        let v = serde_json::to_value(CheckResult::error("boom", error_type::TIMEOUT)).unwrap();
        let obj = v.as_object().unwrap();
        assert_eq!(obj.len(), 3);
        assert_eq!(obj["success"], false);
        assert_eq!(obj["error_type"], "timeout");
    }

    #[test]
    fn note_accumulates() {
        let mut r = CheckResult::success();
        r.note("a");
        r.note("b");
        assert_eq!(r.notes.unwrap(), vec!["a", "b"]);
    }
}
