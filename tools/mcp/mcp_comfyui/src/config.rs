//! Runtime configuration, read from environment variables.
//!
//! Every value has a sane default so the server always starts; malformed
//! values are logged and replaced by the default rather than aborting.

use std::path::PathBuf;
use tracing::warn;

/// Default ComfyUI host. The MCP server normally runs in the same container
/// as ComfyUI (see `docker/comfyui.Dockerfile`), so loopback is correct there.
pub const DEFAULT_HOST: &str = "localhost";
/// Default ComfyUI HTTP port.
pub const DEFAULT_PORT: u16 = 8188;
/// Default ComfyUI installation root (used for local LoRA file management).
pub const DEFAULT_COMFYUI_PATH: &str = "/comfyui";
/// Default time to wait for a generation to finish, in seconds.
pub const DEFAULT_GENERATION_TIMEOUT_SECS: u64 = 300;
/// Default per-request HTTP timeout, in seconds.
pub const DEFAULT_REQUEST_TIMEOUT_SECS: u64 = 60;
/// Default cap on a single image returned inline (20 MiB).
pub const DEFAULT_MAX_IMAGE_BYTES: u64 = 20 * 1024 * 1024;
/// Default cap on a LoRA returned by `download_lora` (512 MiB).
pub const DEFAULT_MAX_LORA_DOWNLOAD_BYTES: u64 = 512 * 1024 * 1024;
/// Upper bound accepted for any user-supplied generation timeout (2 hours).
pub const MAX_GENERATION_TIMEOUT_SECS: u64 = 7200;

/// Server configuration.
#[derive(Debug, Clone, PartialEq)]
pub struct Config {
    /// Base URL of the ComfyUI HTTP API, without a trailing slash.
    pub base_url: String,
    /// ComfyUI installation root; LoRAs live in `<path>/models/loras`.
    pub comfyui_path: PathBuf,
    /// Default generation wait timeout in seconds.
    pub generation_timeout_secs: u64,
    /// Per-request HTTP timeout in seconds.
    pub request_timeout_secs: u64,
    /// Maximum size of an image fetched from ComfyUI for inline return.
    pub max_image_bytes: u64,
    /// Maximum size of a LoRA file returned by `download_lora`.
    pub max_lora_download_bytes: u64,
}

impl Default for Config {
    fn default() -> Self {
        Self::from_lookup(|_| None)
    }
}

impl Config {
    /// Build the configuration from the process environment.
    pub fn from_env() -> Self {
        Self::from_lookup(|key| std::env::var(key).ok())
    }

    /// Build the configuration from an arbitrary key lookup (testable).
    ///
    /// `COMFYUI_URL` (full base URL) takes precedence over
    /// `COMFYUI_HOST` + `COMFYUI_PORT`.
    pub fn from_lookup(get: impl Fn(&str) -> Option<String>) -> Self {
        let non_empty = |key: &str| {
            get(key)
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty())
        };

        let base_url = match non_empty("COMFYUI_URL") {
            Some(url) if url.starts_with("http://") || url.starts_with("https://") => {
                url.trim_end_matches('/').to_string()
            },
            Some(url) => {
                warn!("Ignoring COMFYUI_URL={url:?}: must start with http:// or https://");
                host_port_url(&non_empty)
            },
            None => host_port_url(&non_empty),
        };

        Self {
            base_url,
            comfyui_path: PathBuf::from(
                non_empty("COMFYUI_PATH").unwrap_or_else(|| DEFAULT_COMFYUI_PATH.to_string()),
            ),
            generation_timeout_secs: parse_or(
                &non_empty,
                "COMFYUI_GENERATION_TIMEOUT",
                DEFAULT_GENERATION_TIMEOUT_SECS,
            )
            .clamp(1, MAX_GENERATION_TIMEOUT_SECS),
            request_timeout_secs: parse_or(
                &non_empty,
                "COMFYUI_REQUEST_TIMEOUT",
                DEFAULT_REQUEST_TIMEOUT_SECS,
            )
            .max(1),
            max_image_bytes: parse_or(
                &non_empty,
                "COMFYUI_MAX_IMAGE_BYTES",
                DEFAULT_MAX_IMAGE_BYTES,
            ),
            max_lora_download_bytes: parse_or(
                &non_empty,
                "COMFYUI_MAX_LORA_DOWNLOAD_BYTES",
                DEFAULT_MAX_LORA_DOWNLOAD_BYTES,
            ),
        }
    }

    /// Directory holding LoRA files.
    pub fn lora_dir(&self) -> PathBuf {
        self.comfyui_path.join("models").join("loras")
    }
}

fn host_port_url(get: &impl Fn(&str) -> Option<String>) -> String {
    let host = get("COMFYUI_HOST").unwrap_or_else(|| DEFAULT_HOST.to_string());
    let port: u16 = parse_or(get, "COMFYUI_PORT", DEFAULT_PORT);
    format!("http://{host}:{port}")
}

fn parse_or<T>(get: &impl Fn(&str) -> Option<String>, key: &str, default: T) -> T
where
    T: std::str::FromStr + std::fmt::Display + Copy,
{
    match get(key) {
        None => default,
        Some(raw) => raw.parse().unwrap_or_else(|_| {
            warn!("Invalid {key}={raw:?}; using default {default}");
            default
        }),
    }
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
        assert_eq!(c.base_url, "http://localhost:8188");
        assert_eq!(c.comfyui_path, PathBuf::from("/comfyui"));
        assert_eq!(c.generation_timeout_secs, 300);
        assert_eq!(c.request_timeout_secs, 60);
        assert_eq!(c.lora_dir(), PathBuf::from("/comfyui/models/loras"));
    }

    #[test]
    fn host_and_port() {
        let c = cfg(&[("COMFYUI_HOST", "192.168.0.222"), ("COMFYUI_PORT", "9000")]);
        assert_eq!(c.base_url, "http://192.168.0.222:9000");
    }

    #[test]
    fn url_takes_precedence_and_is_normalized() {
        let c = cfg(&[
            ("COMFYUI_URL", "http://gpu-box:8188/"),
            ("COMFYUI_HOST", "ignored"),
        ]);
        assert_eq!(c.base_url, "http://gpu-box:8188");
    }

    #[test]
    fn invalid_values_fall_back() {
        let c = cfg(&[
            ("COMFYUI_URL", "gpu-box:8188"),
            ("COMFYUI_PORT", "not-a-port"),
            ("COMFYUI_GENERATION_TIMEOUT", "abc"),
            ("COMFYUI_REQUEST_TIMEOUT", "0"),
        ]);
        assert_eq!(c.base_url, "http://localhost:8188");
        assert_eq!(c.generation_timeout_secs, 300);
        assert_eq!(c.request_timeout_secs, 1);
    }

    #[test]
    fn generation_timeout_is_clamped() {
        let c = cfg(&[("COMFYUI_GENERATION_TIMEOUT", "999999")]);
        assert_eq!(c.generation_timeout_secs, MAX_GENERATION_TIMEOUT_SECS);
    }
}
