//! Secret masking.
//!
//! Secrets are found by:
//! 1. values of environment variables named in the config,
//! 2. values of environment variables matching the config's auto-detection
//!    globs (and `MASK_ENV_VARS`, for backward compatibility),
//! 3. regex patterns from the config, and
//! 4. a **built-in baseline** of token formats and variables that is always
//!    active. The config is discovered from the working directory, so a
//!    weakened `.secrets.yaml` planted in a checkout cannot turn masking off
//!    for the most important credentials.

use crate::config::Config;
use regex::Regex;
use std::sync::LazyLock;

/// Environment variables that are always masked.
const BUILTIN_SECRET_VARS: &[&str] = &[
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
];

/// Token formats that are always masked (name, pattern).
static BUILTIN_PATTERNS: LazyLock<Vec<(String, Regex)>> = LazyLock::new(|| {
    [
        (
            "GITHUB_TOKEN",
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}",
        ),
        ("GITHUB_PAT", r"\bgithub_pat_[A-Za-z0-9_]{22,}"),
        ("AWS_ACCESS_KEY", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        ("ANTHROPIC_API_KEY", r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
        ("SLACK_TOKEN", r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
        (
            "PRIVATE_KEY_BLOCK",
            r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]*?-----END[A-Z ]*PRIVATE KEY-----",
        ),
    ]
    .iter()
    .map(|(name, pattern)| {
        (
            (*name).to_string(),
            Regex::new(pattern).expect("static regex"),
        )
    })
    .collect()
});

/// Masks secrets in text.
pub struct SecretMasker {
    /// (variable name, secret value), longest value first.
    secrets: Vec<(String, String)>,
    /// (pattern name, regex): config patterns, then built-ins.
    patterns: Vec<(String, Regex)>,
    mask_format: String,
    log_masked: bool,
}

impl SecretMasker {
    /// Build a masker from config and the current environment.
    pub fn new(config: &Config) -> Self {
        Self::from_env(
            config,
            std::env::vars_os().map(|(k, v)| {
                (
                    k.to_string_lossy().into_owned(),
                    v.to_string_lossy().into_owned(),
                )
            }),
        )
    }

    /// Build a masker from config and an explicit environment (testable
    /// without mutating the process environment).
    pub fn from_env(config: &Config, env: impl IntoIterator<Item = (String, String)>) -> Self {
        let env: Vec<(String, String)> = env.into_iter().collect();
        let lookup = |name: &str| env.iter().find(|(k, _)| k == name).map(|(_, v)| v.clone());
        let min_length = config.settings.minimum_secret_length.max(1);
        let mut secrets: Vec<(String, String)> = Vec::new();
        let mut add = |name: &str, value: String| {
            if value.len() >= min_length && !secrets.iter().any(|(n, _)| n == name) {
                secrets.push((name.to_string(), value));
            }
        };

        for name in BUILTIN_SECRET_VARS
            .iter()
            .copied()
            .chain(config.environment_variables.iter().map(String::as_str))
        {
            if let Some(value) = lookup(name) {
                add(name, value);
            }
        }
        if config.auto_detection.enabled {
            for (key, value) in &env {
                if config.should_auto_detect(key) {
                    add(key, value.clone());
                }
            }
        }
        if let Some(list) = lookup("MASK_ENV_VARS") {
            for name in list.split(',').map(str::trim).filter(|n| !n.is_empty()) {
                if let Some(value) = lookup(name) {
                    add(name, value);
                }
            }
        }
        // Mask longer values first so a secret containing another secret is
        // replaced as a whole.
        secrets.sort_by_key(|(_, v)| std::cmp::Reverse(v.len()));

        let mut patterns = config.compile_patterns();
        patterns.extend(BUILTIN_PATTERNS.iter().cloned());

        Self {
            secrets,
            patterns,
            mask_format: config.settings.mask_format.clone(),
            log_masked: config.settings.log_masked_secrets,
        }
    }

    fn mask_for(&self, name: &str) -> String {
        self.mask_format.replace("{name}", name)
    }

    /// Mask all secrets in `text`. Returns (masked text, changed).
    pub fn mask(&self, text: &str) -> (String, bool) {
        let mut result = text.to_string();
        let mut modified = false;

        for (name, value) in &self.secrets {
            if result.contains(value.as_str()) {
                result = result.replace(value.as_str(), &self.mask_for(name));
                modified = true;
                if self.log_masked {
                    eprintln!("[gh-validator] Masked secret: {name}");
                }
            }
        }
        for (name, regex) in &self.patterns {
            if regex.is_match(&result) {
                let mask = self.mask_for(name);
                result = regex
                    .replace_all(&result, regex::NoExpand(&mask))
                    .into_owned();
                modified = true;
                if self.log_masked {
                    eprintln!("[gh-validator] Masked pattern: {name}");
                }
            }
        }
        (result, modified)
    }

    /// Whether `text` contains any secret (no output).
    pub fn contains_secret(&self, text: &str) -> bool {
        self.secrets.iter().any(|(_, v)| text.contains(v.as_str()))
            || self.patterns.iter().any(|(_, r)| r.is_match(text))
    }

    /// Mask every argument. Returns (masked args, any changed).
    pub fn mask_args(&self, args: &[String]) -> (Vec<String>, bool) {
        let mut modified = false;
        let masked = args
            .iter()
            .map(|arg| {
                let (m, changed) = self.mask(arg);
                modified |= changed;
                m
            })
            .collect();
        (masked, modified)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::types::{AutoDetection, PatternDef, Settings};

    fn config() -> Config {
        Config {
            environment_variables: vec!["TEST_SECRET".to_string()],
            patterns: vec![PatternDef {
                name: "CUSTOM".to_string(),
                pattern: r"custom_[a-z]{8}".to_string(),
                description: None,
            }],
            auto_detection: AutoDetection {
                enabled: true,
                include_patterns: vec!["*_TOKEN".to_string(), "*_SECRET".to_string()],
                exclude_patterns: vec!["PUBLIC_*".to_string()],
            },
            settings: Settings {
                log_masked_secrets: false,
                ..Settings::default()
            },
            ..Config::default()
        }
    }

    fn env(pairs: &[(&str, &str)]) -> Vec<(String, String)> {
        pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect()
    }

    #[test]
    fn masks_configured_env_var() {
        let m = SecretMasker::from_env(&config(), env(&[("TEST_SECRET", "my-super-secret")]));
        let (out, changed) = m.mask("The secret is my-super-secret here");
        assert!(changed);
        assert_eq!(out, "The secret is [MASKED_TEST_SECRET] here");
    }

    #[test]
    fn auto_detection_and_excludes() {
        let m = SecretMasker::from_env(
            &config(),
            env(&[
                ("MY_API_TOKEN", "auto-token-value"),
                ("PUBLIC_TOKEN", "visible"),
            ]),
        );
        assert_eq!(m.mask("x auto-token-value").0, "x [MASKED_MY_API_TOKEN]");
        assert!(!m.mask("x visible").1);
    }

    #[test]
    fn mask_env_vars_compat() {
        let m = SecretMasker::from_env(
            &config(),
            env(&[("MASK_ENV_VARS", "FOO, BAR"), ("FOO", "foo-value-1")]),
        );
        assert_eq!(m.mask("foo-value-1").0, "[MASKED_FOO]");
    }

    #[test]
    fn longest_secret_first() {
        let m = SecretMasker::from_env(
            &config(),
            env(&[("A_TOKEN", "secret"), ("B_TOKEN", "supersecret")]),
        );
        assert_eq!(m.mask("supersecret").0, "[MASKED_B_TOKEN]");
    }

    #[test]
    fn builtin_vars_and_patterns_always_apply() {
        // Even an empty config masks GitHub tokens.
        let empty = Config::default();
        let m = SecretMasker::from_env(&empty, env(&[("GH_TOKEN", "gho_short")]));
        assert_eq!(m.mask("t=gho_short").0, "t=[MASKED_GH_TOKEN]");

        let token = format!("ghp_{}", "a".repeat(36));
        assert_eq!(m.mask(&token).0, "[MASKED_GITHUB_TOKEN]");
        assert_eq!(m.mask("AKIAIOSFODNN7EXAMPLE").0, "[MASKED_AWS_ACCESS_KEY]");
        let key = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----";
        assert_eq!(m.mask(key).0, "[MASKED_PRIVATE_KEY_BLOCK]");
        assert!(m.contains_secret(&token));
        assert!(!m.contains_secret("nothing here"));
    }

    #[test]
    fn config_patterns_apply() {
        let m = SecretMasker::from_env(&config(), env(&[]));
        assert_eq!(m.mask("x custom_abcdefgh").0, "x [MASKED_CUSTOM]");
    }

    #[test]
    fn mask_format_is_not_a_regex_template() {
        let mut cfg = config();
        cfg.settings.mask_format = "$1 {name}".to_string();
        let m = SecretMasker::from_env(&cfg, env(&[]));
        assert_eq!(m.mask("custom_abcdefgh").0, "$1 CUSTOM");
    }

    #[test]
    fn short_values_are_ignored() {
        let m = SecretMasker::from_env(&config(), env(&[("X_TOKEN", "abc")]));
        assert!(!m.mask("abc").1);
    }

    #[test]
    fn mask_args_reports_change() {
        let m = SecretMasker::from_env(&config(), env(&[("TEST_SECRET", "hunter22")]));
        let (args, changed) = m.mask_args(&["--body".to_string(), "pw hunter22".to_string()]);
        assert!(changed);
        assert_eq!(args[1], "pw [MASKED_TEST_SECRET]");
    }
}
