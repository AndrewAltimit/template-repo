//! Secret masking logic
//!
//! Detects and masks secrets in text based on:
//! 1. Explicit environment variable values
//! 2. Auto-detected environment variables matching patterns
//! 3. Regex patterns for common secret formats (tokens, keys, etc.)

use crate::config::Config;
use regex::Regex;
use std::collections::HashMap;

/// Secret masker that loads secrets from environment and config
pub struct SecretMasker {
    /// Environment variable name -> value
    secrets: HashMap<String, String>,
    /// Pattern name -> compiled regex
    patterns: Vec<(String, Regex)>,
    /// Mask format template (e.g., "[MASKED_{name}]")
    mask_format: String,
    /// Whether to log when masking occurs
    log_masked: bool,
}

impl SecretMasker {
    /// Create a new secret masker from configuration
    pub fn new(config: &Config) -> Self {
        let mut secrets = HashMap::new();
        let min_length = config.settings.minimum_secret_length;

        // Load explicitly configured environment variables
        for var_name in &config.environment_variables {
            if let Ok(value) = std::env::var(var_name) {
                if value.len() >= min_length {
                    secrets.insert(var_name.clone(), value);
                }
            }
        }

        // Auto-detect based on patterns
        if config.auto_detection.enabled {
            for (key, value) in std::env::vars() {
                // Skip if already explicitly configured
                if secrets.contains_key(&key) {
                    continue;
                }

                // Check if this variable should be auto-detected
                if config.should_auto_detect(&key) && value.len() >= min_length {
                    secrets.insert(key, value);
                }
            }
        }

        // Load from MASK_ENV_VARS for backward compatibility
        if let Ok(mask_vars) = std::env::var("MASK_ENV_VARS") {
            for var in mask_vars.split(',') {
                let var = var.trim();
                if !var.is_empty() && !secrets.contains_key(var) {
                    if let Ok(value) = std::env::var(var) {
                        if value.len() >= min_length {
                            secrets.insert(var.to_string(), value);
                        }
                    }
                }
            }
        }

        Self {
            secrets,
            patterns: config.compile_patterns(),
            mask_format: config.settings.mask_format.clone(),
            log_masked: config.settings.log_masked_secrets,
        }
    }

    /// Mask all secrets in text
    ///
    /// Returns (masked_text, was_modified)
    pub fn mask(&self, text: &str) -> (String, bool) {
        let mut result = text.to_string();
        let mut modified = false;

        // Sort secrets by length (longest first) to avoid partial masking
        // e.g., mask "SUPER_SECRET" before "SECRET"
        let mut sorted_secrets: Vec<_> = self.secrets.iter().collect();
        sorted_secrets.sort_by(|a, b| b.1.len().cmp(&a.1.len()));

        // Mask environment variable values
        for (name, value) in sorted_secrets {
            if result.contains(value) {
                let mask = self.mask_format.replace("{name}", name);
                result = result.replace(value, &mask);
                modified = true;

                if self.log_masked {
                    eprintln!("[gh-validator] Masked secret: {}", name);
                }
            }
        }

        // Mask pattern-based secrets
        for (name, regex) in &self.patterns {
            let mask = self.mask_format.replace("{name}", name);
            let new_result = regex.replace_all(&result, mask.as_str()).to_string();

            if new_result != result {
                modified = true;
                if self.log_masked {
                    eprintln!("[gh-validator] Masked pattern: {}", name);
                }
                result = new_result;
            }
        }

        (result, modified)
    }

    /// Get the number of loaded secrets (for debugging)
    #[allow(dead_code)]
    pub fn secret_count(&self) -> usize {
        self.secrets.len()
    }

    /// Get the number of loaded patterns (for debugging)
    #[allow(dead_code)]
    pub fn pattern_count(&self) -> usize {
        self.patterns.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::types::{AutoDetection, PatternDef, Settings};

    fn test_config() -> Config {
        Config {
            version: "1.0.0".to_string(),
            description: None,
            environment_variables: vec!["TEST_SECRET".to_string()],
            patterns: vec![
                PatternDef {
                    name: "GITHUB_TOKEN".to_string(),
                    pattern: r"ghp_[A-Za-z0-9_]{36,}".to_string(),
                    description: None,
                },
                PatternDef {
                    name: "AWS_ACCESS_KEY".to_string(),
                    pattern: r"AKIA[0-9A-Z]{16}".to_string(),
                    description: None,
                },
            ],
            auto_detection: AutoDetection {
                enabled: true,
                include_patterns: vec!["*_TOKEN".to_string(), "*_SECRET".to_string()],
                exclude_patterns: vec!["PUBLIC_*".to_string()],
            },
            settings: Settings::default(),
        }
    }

    #[test]
    fn test_mask_env_var() {
        std::env::set_var("TEST_SECRET", "my-super-secret-value");

        let config = test_config();
        let masker = SecretMasker::new(&config);

        let (masked, modified) = masker.mask("The secret is my-super-secret-value here");

        assert!(modified);
        assert!(masked.contains("[MASKED_TEST_SECRET]"));
        assert!(!masked.contains("my-super-secret-value"));

        std::env::remove_var("TEST_SECRET");
    }

    #[test]
    fn test_mask_github_token_pattern() {
        let config = test_config();
        let masker = SecretMasker::new(&config);

        let (masked, modified) =
            masker.mask("Token: ghp_abcdefghijklmnopqrstuvwxyz0123456789AB");

        assert!(modified);
        assert!(masked.contains("[MASKED_GITHUB_TOKEN]"));
        assert!(!masked.contains("ghp_"));
    }

    #[test]
    fn test_mask_aws_key_pattern() {
        let config = test_config();
        let masker = SecretMasker::new(&config);

        let (masked, modified) = masker.mask("AWS Key: AKIAIOSFODNN7EXAMPLE");

        assert!(modified);
        assert!(masked.contains("[MASKED_AWS_ACCESS_KEY]"));
        assert!(!masked.contains("AKIAIOSFODNN7EXAMPLE"));
    }

    #[test]
    fn test_no_modification_when_no_secrets() {
        let config = test_config();
        let masker = SecretMasker::new(&config);

        let (masked, modified) = masker.mask("This text has no secrets");

        assert!(!modified);
        assert_eq!(masked, "This text has no secrets");
    }

    #[test]
    fn test_auto_detection() {
        std::env::set_var("MY_API_TOKEN", "auto-detected-token-value");

        let config = test_config();
        let masker = SecretMasker::new(&config);

        let (masked, modified) = masker.mask("Using auto-detected-token-value here");

        assert!(modified);
        assert!(masked.contains("[MASKED_MY_API_TOKEN]"));

        std::env::remove_var("MY_API_TOKEN");
    }

    #[test]
    fn test_exclude_pattern() {
        std::env::set_var("PUBLIC_TOKEN", "should-not-mask");

        let config = test_config();
        let masker = SecretMasker::new(&config);

        let (masked, modified) = masker.mask("Value: should-not-mask");

        // PUBLIC_* is excluded, so it should not be masked
        assert!(!modified);
        assert!(masked.contains("should-not-mask"));

        std::env::remove_var("PUBLIC_TOKEN");
    }
}
