//! Environment-driven configuration for the Crush MCP server.

use std::fmt;
use std::path::PathBuf;

use crate::util::{env_bool, env_num, env_string, is_valid_model_id};

/// Default OpenRouter model handed to crush (kept in line with `.agents.yaml`).
pub const DEFAULT_MODEL: &str = "qwen/qwen3.7-max";

/// Default docker compose service used by the `docker` execution mode.
pub const DEFAULT_DOCKER_SERVICE: &str = "mcp-crush";

/// How the `crush` CLI is executed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExecutionMode {
    /// Use the local binary if it is on PATH, otherwise fall back to docker.
    Auto,
    /// Always run the local binary (`CRUSH_BINARY`).
    Local,
    /// Always run inside a docker compose service (`CRUSH_DOCKER_SERVICE`).
    Docker,
}

impl ExecutionMode {
    fn parse(value: &str) -> Option<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "auto" => Some(Self::Auto),
            "local" | "direct" => Some(Self::Local),
            "docker" | "container" => Some(Self::Docker),
            _ => None,
        }
    }

    /// Lowercase name for status output.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Local => "local",
            Self::Docker => "docker",
        }
    }
}

/// Crush configuration.
///
/// `Debug` is implemented by hand so the API key can never leak into logs.
#[derive(Clone)]
pub struct CrushConfig {
    /// Whether consultations run without `force` (`CRUSH_ENABLED`).
    pub enabled: bool,
    /// Advisory auto-consult flag reported to clients (`CRUSH_AUTO_CONSULT`).
    pub auto_consult: bool,
    /// OpenRouter API key passed to crush (`OPENROUTER_API_KEY`).
    pub api_key: String,
    /// Model forced via a generated crush config (`CRUSH_MODEL`); `None` means
    /// "use crush's own configuration" (set `CRUSH_MODEL=` to an empty value).
    pub model: Option<String>,
    /// Per-consultation deadline in seconds (`CRUSH_TIMEOUT`).
    pub timeout_secs: u64,
    /// Maximum characters of query + context in the prompt (`CRUSH_MAX_PROMPT`).
    pub max_prompt_chars: usize,
    /// Log a line per completed consultation (`CRUSH_LOG_CONSULTATIONS`).
    pub log_consultations: bool,
    /// Prepend recent exchanges to the prompt (`CRUSH_INCLUDE_HISTORY`).
    pub include_history: bool,
    /// Maximum retained history entries (`CRUSH_MAX_HISTORY`).
    pub max_history_entries: usize,
    /// Pass `--quiet` to hide the spinner (`CRUSH_QUIET_MODE`).
    pub quiet_mode: bool,
    /// Execution strategy (`CRUSH_EXECUTION`: auto | local | docker).
    pub execution: ExecutionMode,
    /// Crush executable name or path (`CRUSH_BINARY`).
    pub binary: String,
    /// Writable crush data directory (`CRUSH_DATA_DIR`).
    pub data_dir: PathBuf,
    /// Working directory crush runs in (`CRUSH_WORKDIR`).
    pub workdir: PathBuf,
    /// Compose service for docker mode (`CRUSH_DOCKER_SERVICE`).
    pub docker_service: String,
    /// Optional compose file for docker mode (`CRUSH_COMPOSE_FILE`).
    pub compose_file: Option<String>,
    /// Maximum captured stdout bytes (`CRUSH_MAX_OUTPUT`).
    pub max_output_bytes: usize,
}

impl fmt::Debug for CrushConfig {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("CrushConfig")
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
            .field("timeout_secs", &self.timeout_secs)
            .field("max_prompt_chars", &self.max_prompt_chars)
            .field("log_consultations", &self.log_consultations)
            .field("include_history", &self.include_history)
            .field("max_history_entries", &self.max_history_entries)
            .field("quiet_mode", &self.quiet_mode)
            .field("execution", &self.execution)
            .field("binary", &self.binary)
            .field("data_dir", &self.data_dir)
            .field("workdir", &self.workdir)
            .field("docker_service", &self.docker_service)
            .field("compose_file", &self.compose_file)
            .field("max_output_bytes", &self.max_output_bytes)
            .finish()
    }
}

impl Default for CrushConfig {
    fn default() -> Self {
        Self::from_lookup(&|_| None)
    }
}

/// Characters allowed in a compose service name.
fn is_valid_service(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 128
        && name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.'))
}

impl CrushConfig {
    /// Load configuration from the process environment.
    pub fn from_env() -> Self {
        Self::from_lookup(&|k| std::env::var(k).ok())
    }

    /// Load configuration from an arbitrary key lookup (used by tests).
    pub fn from_lookup(lookup: &dyn Fn(&str) -> Option<String>) -> Self {
        let model = match lookup("CRUSH_MODEL").map(|m| m.trim().to_string()) {
            None => Some(DEFAULT_MODEL.to_string()),
            Some(m) if m.is_empty() => None,
            Some(m) if is_valid_model_id(&m) => Some(m),
            Some(m) => {
                tracing::warn!("CRUSH_MODEL={m:?} is not a valid model id; using {DEFAULT_MODEL}");
                Some(DEFAULT_MODEL.to_string())
            },
        };

        let execution = match env_string(lookup, "CRUSH_EXECUTION") {
            None => ExecutionMode::Auto,
            Some(v) => ExecutionMode::parse(&v).unwrap_or_else(|| {
                tracing::warn!("CRUSH_EXECUTION={v:?} is invalid (auto|local|docker); using auto");
                ExecutionMode::Auto
            }),
        };

        let docker_service = match env_string(lookup, "CRUSH_DOCKER_SERVICE") {
            Some(s) if is_valid_service(&s) => s,
            Some(s) => {
                tracing::warn!(
                    "CRUSH_DOCKER_SERVICE={s:?} is not a valid service name; using {DEFAULT_DOCKER_SERVICE}"
                );
                DEFAULT_DOCKER_SERVICE.to_string()
            },
            None => DEFAULT_DOCKER_SERVICE.to_string(),
        };

        let scratch = std::env::temp_dir().join("mcp-crush");

        Self {
            enabled: env_bool(lookup, "CRUSH_ENABLED", true),
            auto_consult: env_bool(lookup, "CRUSH_AUTO_CONSULT", true),
            api_key: env_string(lookup, "OPENROUTER_API_KEY").unwrap_or_default(),
            model,
            timeout_secs: env_num(lookup, "CRUSH_TIMEOUT", 300, 1, 3600),
            max_prompt_chars: env_num(lookup, "CRUSH_MAX_PROMPT", 32_000, 100, 2_000_000),
            log_consultations: env_bool(lookup, "CRUSH_LOG_CONSULTATIONS", true),
            include_history: env_bool(lookup, "CRUSH_INCLUDE_HISTORY", true),
            max_history_entries: env_num(lookup, "CRUSH_MAX_HISTORY", 5, 0, 100),
            quiet_mode: env_bool(lookup, "CRUSH_QUIET_MODE", true),
            execution,
            binary: env_string(lookup, "CRUSH_BINARY").unwrap_or_else(|| "crush".to_string()),
            data_dir: env_string(lookup, "CRUSH_DATA_DIR")
                .map(PathBuf::from)
                .unwrap_or_else(|| scratch.join("data")),
            workdir: env_string(lookup, "CRUSH_WORKDIR")
                .map(PathBuf::from)
                .unwrap_or_else(|| scratch.join("workspace")),
            docker_service,
            compose_file: env_string(lookup, "CRUSH_COMPOSE_FILE"),
            max_output_bytes: env_num(
                lookup,
                "CRUSH_MAX_OUTPUT",
                1024 * 1024,
                4 * 1024,
                64 * 1024 * 1024,
            ),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn config(pairs: &[(&str, &str)]) -> CrushConfig {
        let map: HashMap<&str, &str> = pairs.iter().copied().collect();
        CrushConfig::from_lookup(&|k| map.get(k).map(|v| v.to_string()))
    }

    #[test]
    fn defaults() {
        let c = config(&[]);
        assert!(c.enabled && c.auto_consult && c.quiet_mode && c.include_history);
        assert_eq!(c.model.as_deref(), Some(DEFAULT_MODEL));
        assert_eq!(c.execution, ExecutionMode::Auto);
        assert_eq!(c.binary, "crush");
        assert_eq!(c.docker_service, DEFAULT_DOCKER_SERVICE);
        assert!(c.data_dir.ends_with("data"));
        assert!(c.workdir.ends_with("workspace"));
        assert_eq!(c.timeout_secs, 300);
    }

    #[test]
    fn lenient_booleans_and_validation() {
        let c = config(&[
            ("CRUSH_ENABLED", "0"),
            ("CRUSH_QUIET_MODE", "no"),
            ("CRUSH_MODEL", ""),
            ("CRUSH_EXECUTION", "DOCKER"),
            ("CRUSH_DOCKER_SERVICE", "bad service; rm"),
            ("CRUSH_TIMEOUT", "99999"),
        ]);
        assert!(!c.enabled);
        assert!(!c.quiet_mode);
        assert_eq!(c.model, None);
        assert_eq!(c.execution, ExecutionMode::Docker);
        assert_eq!(c.docker_service, DEFAULT_DOCKER_SERVICE);
        assert_eq!(c.timeout_secs, 3600);

        let c = config(&[("CRUSH_MODEL", "not valid!"), ("CRUSH_EXECUTION", "??")]);
        assert_eq!(c.model.as_deref(), Some(DEFAULT_MODEL));
        assert_eq!(c.execution, ExecutionMode::Auto);
    }

    #[test]
    fn debug_never_prints_api_key() {
        let c = config(&[("OPENROUTER_API_KEY", "sk-or-v1-supersecret")]);
        let dbg = format!("{c:?}");
        assert!(!dbg.contains("supersecret"));
        assert!(dbg.contains("<redacted>"));
    }
}
