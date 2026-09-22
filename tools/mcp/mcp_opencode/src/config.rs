//! Environment-driven configuration for the OpenCode MCP server.

use std::fmt;

use crate::util::{env_bool, env_num, env_string, is_valid_model_id};

/// Default OpenRouter model (kept in line with `.agents.yaml`).
pub const DEFAULT_MODEL: &str = "qwen/qwen3.7-max";

/// Default OpenRouter API base URL (OpenAI-compatible).
pub const DEFAULT_BASE_URL: &str = "https://openrouter.ai/api/v1";

/// OpenCode configuration.
///
/// `Debug` is implemented by hand so the API key can never leak into logs.
#[derive(Clone)]
pub struct OpenCodeConfig {
    /// Whether consultations run without `force` (`OPENCODE_ENABLED`).
    pub enabled: bool,
    /// Advisory auto-consult flag reported to clients (`OPENCODE_AUTO_CONSULT`).
    pub auto_consult: bool,
    /// OpenRouter API key (`OPENROUTER_API_KEY`).
    pub api_key: String,
    /// Default model id (`OPENCODE_MODEL`).
    pub model: String,
    /// OpenAI-compatible API base URL, without trailing slash (`OPENROUTER_BASE_URL`).
    pub base_url: String,
    /// Overall per-consultation deadline in seconds, including retries (`OPENCODE_TIMEOUT`).
    pub timeout_secs: u64,
    /// Maximum characters of query + context sent upstream (`OPENCODE_MAX_PROMPT`).
    pub max_prompt_chars: usize,
    /// Default completion token limit (`OPENCODE_MAX_TOKENS`).
    pub max_tokens: u32,
    /// Default sampling temperature (`OPENCODE_TEMPERATURE`).
    pub temperature: f64,
    /// Retries for 408/429/5xx and connection errors (`OPENCODE_MAX_RETRIES`).
    pub max_retries: u32,
    /// Log a line per completed consultation (`OPENCODE_LOG_CONSULTATIONS`).
    pub log_consultations: bool,
    /// Replay recent exchanges into prompts (`OPENCODE_INCLUDE_HISTORY`).
    pub include_history: bool,
    /// Maximum retained history entries (`OPENCODE_MAX_HISTORY`).
    pub max_history_entries: usize,
}

impl fmt::Debug for OpenCodeConfig {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("OpenCodeConfig")
            .field("enabled", &self.enabled)
            .field("auto_consult", &self.auto_consult)
            .field(
                "api_key",
                &if self.api_key.is_empty() {
                    "<unset>"
                } else {
                    "<redacted>"
                },
            )
            .field("model", &self.model)
            .field("base_url", &self.base_url)
            .field("timeout_secs", &self.timeout_secs)
            .field("max_prompt_chars", &self.max_prompt_chars)
            .field("max_tokens", &self.max_tokens)
            .field("temperature", &self.temperature)
            .field("max_retries", &self.max_retries)
            .field("log_consultations", &self.log_consultations)
            .field("include_history", &self.include_history)
            .field("max_history_entries", &self.max_history_entries)
            .finish()
    }
}

impl Default for OpenCodeConfig {
    fn default() -> Self {
        Self::from_lookup(&|_| None)
    }
}

impl OpenCodeConfig {
    /// Load configuration from the process environment.
    pub fn from_env() -> Self {
        Self::from_lookup(&|k| std::env::var(k).ok())
    }

    /// Load configuration from an arbitrary key lookup (used by tests).
    pub fn from_lookup(lookup: &dyn Fn(&str) -> Option<String>) -> Self {
        let model = match env_string(lookup, "OPENCODE_MODEL") {
            Some(m) if is_valid_model_id(&m) => m,
            Some(m) => {
                tracing::warn!(
                    "OPENCODE_MODEL={m:?} is not a valid model id; using {DEFAULT_MODEL}"
                );
                DEFAULT_MODEL.to_string()
            },
            None => DEFAULT_MODEL.to_string(),
        };
        let base_url = env_string(lookup, "OPENROUTER_BASE_URL")
            .unwrap_or_else(|| DEFAULT_BASE_URL.to_string())
            .trim_end_matches('/')
            .to_string();

        Self {
            enabled: env_bool(lookup, "OPENCODE_ENABLED", true),
            auto_consult: env_bool(lookup, "OPENCODE_AUTO_CONSULT", true),
            api_key: env_string(lookup, "OPENROUTER_API_KEY").unwrap_or_default(),
            model,
            base_url,
            timeout_secs: env_num(lookup, "OPENCODE_TIMEOUT", 300, 1, 3600),
            max_prompt_chars: env_num(lookup, "OPENCODE_MAX_PROMPT", 32_000, 100, 2_000_000),
            max_tokens: env_num(lookup, "OPENCODE_MAX_TOKENS", 4096, 1, 1_000_000),
            temperature: env_num(lookup, "OPENCODE_TEMPERATURE", 0.3, 0.0, 2.0),
            max_retries: env_num(lookup, "OPENCODE_MAX_RETRIES", 2, 0, 10),
            log_consultations: env_bool(lookup, "OPENCODE_LOG_CONSULTATIONS", true),
            include_history: env_bool(lookup, "OPENCODE_INCLUDE_HISTORY", true),
            max_history_entries: env_num(lookup, "OPENCODE_MAX_HISTORY", 5, 0, 100),
        }
    }

    /// Full chat-completions endpoint URL.
    pub fn completions_url(&self) -> String {
        format!("{}/chat/completions", self.base_url)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn config(pairs: &[(&str, &str)]) -> OpenCodeConfig {
        let map: HashMap<&str, &str> = pairs.iter().copied().collect();
        OpenCodeConfig::from_lookup(&|k| map.get(k).map(|v| v.to_string()))
    }

    #[test]
    fn defaults() {
        let c = config(&[]);
        assert!(c.enabled);
        assert!(c.auto_consult);
        assert_eq!(c.model, DEFAULT_MODEL);
        assert_eq!(
            c.completions_url(),
            "https://openrouter.ai/api/v1/chat/completions"
        );
        assert_eq!(c.timeout_secs, 300);
        assert_eq!(c.max_history_entries, 5);
        assert!(c.api_key.is_empty());
    }

    #[test]
    fn overrides_and_validation() {
        let c = config(&[
            ("OPENCODE_ENABLED", "0"),
            ("OPENCODE_MODEL", "bad model!"),
            ("OPENROUTER_BASE_URL", "http://127.0.0.1:9/v1/"),
            ("OPENCODE_TIMEOUT", "0"),
            ("OPENCODE_TEMPERATURE", "0.9"),
        ]);
        assert!(!c.enabled);
        assert_eq!(c.model, DEFAULT_MODEL);
        assert_eq!(
            c.completions_url(),
            "http://127.0.0.1:9/v1/chat/completions"
        );
        assert_eq!(c.timeout_secs, 1);
        assert!((c.temperature - 0.9).abs() < 1e-9);
    }

    #[test]
    fn debug_never_prints_api_key() {
        let c = config(&[("OPENROUTER_API_KEY", "sk-or-v1-supersecret")]);
        let dbg = format!("{c:?}");
        assert!(!dbg.contains("supersecret"));
        assert!(dbg.contains("<redacted>"));
    }
}
