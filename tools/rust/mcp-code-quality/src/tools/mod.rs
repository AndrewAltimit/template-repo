//! Code quality tool implementations

pub mod format;
pub mod lint;
pub mod status;
pub mod test;

pub use format::{autoformat, format_check};
pub use lint::{lint, security_scan, type_check};
pub use status::{get_audit_log, get_status};
pub use test::{audit_dependencies, check_markdown_links, run_tests};

use serde::{Deserialize, Serialize};

/// Supported programming languages
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Language {
    Python,
    JavaScript,
    TypeScript,
    Go,
    Rust,
}

impl Language {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "python" | "py" => Some(Language::Python),
            "javascript" | "js" => Some(Language::JavaScript),
            "typescript" | "ts" => Some(Language::TypeScript),
            "go" | "golang" => Some(Language::Go),
            "rust" | "rs" => Some(Language::Rust),
            _ => None,
        }
    }
}

/// Supported linters
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Linter {
    Flake8,
    Pylint,
    Eslint,
    Golint,
    Clippy,
}

impl Linter {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "flake8" => Some(Linter::Flake8),
            "pylint" => Some(Linter::Pylint),
            "eslint" => Some(Linter::Eslint),
            "golint" => Some(Linter::Golint),
            "clippy" => Some(Linter::Clippy),
            _ => None,
        }
    }

    #[allow(dead_code)] // Part of public API
    pub fn command(&self) -> &'static str {
        match self {
            Linter::Flake8 => "flake8",
            Linter::Pylint => "pylint",
            Linter::Eslint => "eslint",
            Linter::Golint => "golint",
            Linter::Clippy => "cargo",
        }
    }
}
