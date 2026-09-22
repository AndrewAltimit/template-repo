//! Runtime configuration, read from environment variables.

use std::fmt;
use std::path::PathBuf;
use std::time::Duration;

/// Default ElevenLabs API origin.
pub const DEFAULT_BASE_URL: &str = "https://api.elevenlabs.io";
/// Default model when `ELEVENLABS_DEFAULT_MODEL` is unset.
pub const DEFAULT_MODEL: &str = "eleven_v3";
/// Default voice when `ELEVENLABS_DEFAULT_VOICE` is unset.
pub const DEFAULT_VOICE: &str = "george";
/// Default total HTTP timeout per request.
pub const DEFAULT_TIMEOUT_SECS: u64 = 120;

/// Server configuration.
///
/// `Debug` is implemented by hand so the API key is never printed.
#[derive(Clone)]
pub struct Config {
    /// ElevenLabs API key (`ELEVENLABS_API_KEY`). `None` when unset/blank.
    pub api_key: Option<String>,
    /// API origin without trailing slash or `/v1` (`ELEVENLABS_BASE_URL`).
    pub base_url: String,
    /// Directory generated audio is written to.
    pub output_dir: PathBuf,
    /// Default model ID.
    pub default_model: String,
    /// Default voice name or ID.
    pub default_voice: String,
    /// Total per-request HTTP timeout.
    pub timeout: Duration,
}

impl fmt::Debug for Config {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Config")
            .field("api_key", &self.api_key.as_ref().map(|_| "<redacted>"))
            .field("base_url", &self.base_url)
            .field("output_dir", &self.output_dir)
            .field("default_model", &self.default_model)
            .field("default_voice", &self.default_voice)
            .field("timeout", &self.timeout)
            .finish()
    }
}

impl Config {
    /// Build configuration from the process environment.
    ///
    /// | Variable | Default |
    /// |---|---|
    /// | `ELEVENLABS_API_KEY` | unset (API tools return an error) |
    /// | `ELEVENLABS_BASE_URL` | `https://api.elevenlabs.io` |
    /// | `ELEVENLABS_OUTPUT_DIR`, then `MCP_OUTPUT_DIR` | `~/elevenlabs_outputs` |
    /// | `ELEVENLABS_DEFAULT_MODEL` | `eleven_v3` |
    /// | `ELEVENLABS_DEFAULT_VOICE` | `george` |
    /// | `ELEVENLABS_TIMEOUT_SECS` | `120` |
    pub fn from_env() -> Self {
        Self::from_lookup(|k| std::env::var(k).ok())
    }

    /// Build configuration from an arbitrary key lookup (testable).
    pub fn from_lookup(get: impl Fn(&str) -> Option<String>) -> Self {
        let non_blank = |k: &str| {
            get(k)
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty())
        };

        let output_dir = non_blank("ELEVENLABS_OUTPUT_DIR")
            .or_else(|| non_blank("MCP_OUTPUT_DIR"))
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                dirs::home_dir()
                    .unwrap_or_else(std::env::temp_dir)
                    .join("elevenlabs_outputs")
            });

        let timeout_secs = non_blank("ELEVENLABS_TIMEOUT_SECS")
            .and_then(|v| v.parse::<u64>().ok())
            .filter(|v| *v > 0)
            .unwrap_or(DEFAULT_TIMEOUT_SECS);

        let base_url = non_blank("ELEVENLABS_BASE_URL")
            .filter(|u| u.starts_with("http://") || u.starts_with("https://"))
            .unwrap_or_else(|| DEFAULT_BASE_URL.to_string());

        Self {
            api_key: non_blank("ELEVENLABS_API_KEY"),
            base_url: normalize_base_url(&base_url),
            output_dir,
            default_model: non_blank("ELEVENLABS_DEFAULT_MODEL")
                .unwrap_or_else(|| DEFAULT_MODEL.to_string()),
            default_voice: non_blank("ELEVENLABS_DEFAULT_VOICE")
                .unwrap_or_else(|| DEFAULT_VOICE.to_string()),
            timeout: Duration::from_secs(timeout_secs),
        }
    }
}

/// Strip trailing slashes and a trailing `/v1` so both
/// `https://api.elevenlabs.io` and `https://api.elevenlabs.io/v1/` work.
fn normalize_base_url(url: &str) -> String {
    let trimmed = url.trim_end_matches('/');
    trimmed
        .strip_suffix("/v1")
        .unwrap_or(trimmed)
        .trim_end_matches('/')
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn cfg(pairs: &[(&str, &str)]) -> Config {
        let map: HashMap<String, String> = pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        Config::from_lookup(|k| map.get(k).cloned())
    }

    #[test]
    fn defaults() {
        let c = cfg(&[]);
        assert!(c.api_key.is_none());
        assert_eq!(c.base_url, DEFAULT_BASE_URL);
        assert_eq!(c.default_model, DEFAULT_MODEL);
        assert_eq!(c.default_voice, DEFAULT_VOICE);
        assert_eq!(c.timeout, Duration::from_secs(DEFAULT_TIMEOUT_SECS));
        assert!(c.output_dir.ends_with("elevenlabs_outputs"));
    }

    #[test]
    fn output_dir_precedence() {
        assert_eq!(
            cfg(&[("MCP_OUTPUT_DIR", "/output")]).output_dir,
            PathBuf::from("/output")
        );
        assert_eq!(
            cfg(&[
                ("MCP_OUTPUT_DIR", "/output"),
                ("ELEVENLABS_OUTPUT_DIR", "/a")
            ])
            .output_dir,
            PathBuf::from("/a")
        );
    }

    #[test]
    fn blank_key_is_none_and_debug_redacts() {
        assert!(cfg(&[("ELEVENLABS_API_KEY", "   ")]).api_key.is_none());
        let c = cfg(&[("ELEVENLABS_API_KEY", "sk_supersecret")]);
        let dbg = format!("{c:?}");
        assert!(!dbg.contains("supersecret"));
        assert!(dbg.contains("<redacted>"));
    }

    #[test]
    fn base_url_normalization_and_validation() {
        assert_eq!(
            cfg(&[(
                "ELEVENLABS_BASE_URL",
                "https://api.eu.residency.elevenlabs.io/v1/"
            )])
            .base_url,
            "https://api.eu.residency.elevenlabs.io"
        );
        assert_eq!(
            cfg(&[("ELEVENLABS_BASE_URL", "ftp://nope")]).base_url,
            DEFAULT_BASE_URL
        );
    }

    #[test]
    fn bad_timeout_falls_back() {
        assert_eq!(
            cfg(&[("ELEVENLABS_TIMEOUT_SECS", "abc")]).timeout,
            Duration::from_secs(DEFAULT_TIMEOUT_SECS)
        );
        assert_eq!(
            cfg(&[("ELEVENLABS_TIMEOUT_SECS", "0")]).timeout,
            Duration::from_secs(DEFAULT_TIMEOUT_SECS)
        );
        assert_eq!(
            cfg(&[("ELEVENLABS_TIMEOUT_SECS", "30")]).timeout,
            Duration::from_secs(30)
        );
    }
}
