//! Configuration types for .secrets.yaml parsing
//!
//! These types mirror the structure of the .secrets.yaml configuration file.

use regex::Regex;
use serde::Deserialize;

/// Root configuration structure
#[derive(Debug, Deserialize)]
pub struct Config {
    /// Configuration version
    #[serde(default)]
    pub version: String,

    /// Optional description
    #[serde(default)]
    pub description: Option<String>,

    /// Explicit list of environment variables to mask
    #[serde(default)]
    pub environment_variables: Vec<String>,

    /// Regex patterns for secret detection
    #[serde(default)]
    pub patterns: Vec<PatternDef>,

    /// Auto-detection configuration
    #[serde(default)]
    pub auto_detection: AutoDetection,

    /// General settings
    #[serde(default)]
    pub settings: Settings,
}

/// Definition of a regex pattern for secret detection
#[derive(Debug, Deserialize)]
pub struct PatternDef {
    /// Name of the pattern (used in mask: [MASKED_{name}])
    pub name: String,

    /// Regex pattern string
    pub pattern: String,

    /// Optional description
    #[serde(default)]
    pub description: Option<String>,
}

/// Auto-detection configuration for environment variables
#[derive(Debug, Deserialize, Default)]
pub struct AutoDetection {
    /// Whether auto-detection is enabled
    #[serde(default = "default_true")]
    pub enabled: bool,

    /// Glob patterns for variables to include (e.g., "*_TOKEN")
    #[serde(default)]
    pub include_patterns: Vec<String>,

    /// Glob patterns for variables to exclude (e.g., "PUBLIC_*")
    #[serde(default)]
    pub exclude_patterns: Vec<String>,
}

/// General settings
#[derive(Debug, Deserialize)]
pub struct Settings {
    /// Minimum length for a secret to be masked
    #[serde(default = "default_min_length")]
    pub minimum_secret_length: usize,

    /// Whether regex patterns are case-sensitive
    #[serde(default)]
    pub case_sensitive_patterns: bool,

    /// Whether to mask partial matches
    #[serde(default)]
    pub mask_partial_matches: bool,

    /// Whether to log when secrets are masked
    #[serde(default = "default_true")]
    pub log_masked_secrets: bool,

    /// Format for masked secrets (supports {name} placeholder)
    #[serde(default = "default_mask_format")]
    pub mask_format: String,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            minimum_secret_length: default_min_length(),
            case_sensitive_patterns: false,
            mask_partial_matches: false,
            log_masked_secrets: true,
            mask_format: default_mask_format(),
        }
    }
}

fn default_true() -> bool {
    true
}

fn default_min_length() -> usize {
    4
}

fn default_mask_format() -> String {
    "[MASKED_{name}]".to_string()
}

impl Config {
    /// Compile regex patterns from config
    ///
    /// Returns a vector of (pattern_name, compiled_regex) tuples.
    /// Invalid patterns are logged and skipped.
    pub fn compile_patterns(&self) -> Vec<(String, Regex)> {
        self.patterns
            .iter()
            .filter_map(|p| {
                let pattern_str = if self.settings.case_sensitive_patterns {
                    p.pattern.clone()
                } else {
                    format!("(?i){}", p.pattern)
                };

                match Regex::new(&pattern_str) {
                    Ok(regex) => Some((p.name.clone(), regex)),
                    Err(e) => {
                        eprintln!(
                            "[gh-validator] Warning: Invalid regex pattern '{}': {}",
                            p.name, e
                        );
                        None
                    }
                }
            })
            .collect()
    }

    /// Check if an environment variable name should be auto-detected
    pub fn should_auto_detect(&self, name: &str) -> bool {
        if !self.auto_detection.enabled {
            return false;
        }

        let upper = name.to_uppercase();

        // Check excludes first (they take precedence)
        for pattern in &self.auto_detection.exclude_patterns {
            if glob_match(pattern, &upper) {
                return false;
            }
        }

        // Check includes
        for pattern in &self.auto_detection.include_patterns {
            if glob_match(pattern, &upper) {
                return true;
            }
        }

        false
    }
}

/// Simple glob pattern matching
///
/// Supports `*` as wildcard for any characters.
/// Pattern is case-insensitive.
fn glob_match(pattern: &str, text: &str) -> bool {
    let pattern_upper = pattern.to_uppercase();
    let text_upper = text.to_uppercase();

    // Convert glob pattern to regex
    let regex_pattern = pattern_upper
        .replace('.', r"\.")
        .replace('*', ".*")
        .replace('?', ".");

    Regex::new(&format!("^{}$", regex_pattern))
        .map(|r| r.is_match(&text_upper))
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_glob_match() {
        assert!(glob_match("*_TOKEN", "GITHUB_TOKEN"));
        assert!(glob_match("*_TOKEN", "API_TOKEN"));
        assert!(glob_match("TOKEN_*", "TOKEN_ABC"));
        assert!(glob_match("PUBLIC_*", "PUBLIC_KEY"));
        assert!(!glob_match("*_TOKEN", "TOKEN_SOMETHING"));
        assert!(!glob_match("PUBLIC_*", "NOT_PUBLIC"));
    }

    #[test]
    fn test_default_settings() {
        let settings = Settings::default();
        assert_eq!(settings.minimum_secret_length, 4);
        assert!(!settings.case_sensitive_patterns);
        assert!(settings.log_masked_secrets);
        assert_eq!(settings.mask_format, "[MASKED_{name}]");
    }
}
