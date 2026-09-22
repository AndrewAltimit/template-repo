//! Server configuration and filesystem policy.
//!
//! Configuration is read once from the environment at startup
//! ([`ServerConfig::from_env`]). Tests build a config rooted in a temporary
//! directory with [`ServerConfig::for_root`], so nothing touches real paths.
//!
//! The config also owns the *output path policy*: every file the server writes
//! (renders, clips, captions, EDLs) must resolve to a location under one of the
//! allowed output roots. This stops a tool call (for example one produced by a
//! prompt-injected agent) from overwriting arbitrary files via `ffmpeg -y`.

use std::path::{Component, Path, PathBuf};

use anyhow::{Context, Result, bail};

/// Runtime configuration for the video editor server.
#[derive(Debug, Clone)]
pub struct ServerConfig {
    /// Root directory for all generated output (renders, clips, EDLs, captions).
    pub output_dir: PathBuf,
    /// Directory for persistent caches (transcripts).
    pub cache_dir: PathBuf,
    /// Scratch directory for intermediate files (extracted audio, segments).
    pub temp_dir: PathBuf,
    /// Additional directories outputs may be written to (besides `output_dir`).
    pub extra_output_roots: Vec<PathBuf>,
    /// Whisper executable name or path.
    pub whisper_bin: String,
    /// Whisper model name (tiny, base, small, medium, large, ...).
    pub whisper_model: String,
    /// Whisper device (`cpu` or `cuda`).
    pub whisper_device: String,
    /// Default cross-fade duration in seconds for EDL transitions.
    pub transition_duration: f64,
    /// Default minimum time between speaker switches, in seconds.
    pub speaker_switch_delay: f64,
    /// Default minimum silence duration (seconds) that counts as removable.
    pub silence_threshold: f64,
    /// Loudness (dBFS) below which audio is considered silent.
    pub silence_db: f64,
    /// Punch-in factor used by the `zoom_in` effect (1.0 = no zoom).
    pub zoom_factor: f64,
    /// Default picture-in-picture size as a fraction of output width.
    pub pip_size: f64,
    /// Maximum number of heavy operations (render/transcribe/encode) at once.
    pub max_parallel_jobs: usize,
    /// Whether GPU (NVENC) encoding may be used when available.
    pub enable_gpu: bool,
    /// Maximum number of finished jobs kept in memory for status queries.
    pub max_retained_jobs: usize,
}

fn env_string(key: &str, default: &str) -> String {
    std::env::var(key)
        .ok()
        .filter(|v| !v.trim().is_empty())
        .unwrap_or_else(|| default.to_string())
}

fn env_parse<T: std::str::FromStr>(key: &str, default: T) -> T {
    std::env::var(key)
        .ok()
        .and_then(|v| v.trim().parse().ok())
        .unwrap_or(default)
}

/// Parse a boolean flag leniently (`1/true/yes/on` vs `0/false/no/off`).
pub fn parse_bool_flag(value: &str) -> Option<bool> {
    match value.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => None,
    }
}

impl ServerConfig {
    /// Build the configuration from environment variables.
    ///
    /// See the crate README for the full list of variables and defaults.
    pub fn from_env() -> Self {
        let output_dir = std::env::var_os("MCP_VIDEO_OUTPUT_DIR")
            .filter(|v| !v.is_empty())
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("outputs").join("video-editor"));
        let cache_dir = std::env::var_os("MCP_VIDEO_CACHE_DIR")
            .filter(|v| !v.is_empty())
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                dirs::cache_dir()
                    .unwrap_or_else(std::env::temp_dir)
                    .join("mcp-video-editor")
            });
        let temp_dir = std::env::var_os("MCP_VIDEO_TEMP_DIR")
            .filter(|v| !v.is_empty())
            .map(PathBuf::from)
            .unwrap_or_else(|| std::env::temp_dir().join("video_editor"));
        let extra_output_roots: Vec<PathBuf> = std::env::var_os("MCP_VIDEO_ALLOWED_OUTPUT_DIRS")
            .map(|v| {
                std::env::split_paths(&v)
                    .filter(|p| !p.as_os_str().is_empty())
                    .collect()
            })
            .unwrap_or_default();

        Self {
            output_dir: absolutize(&output_dir),
            cache_dir: absolutize(&cache_dir),
            temp_dir: absolutize(&temp_dir),
            extra_output_roots: extra_output_roots.iter().map(|p| absolutize(p)).collect(),
            whisper_bin: env_string("WHISPER_BIN", "whisper"),
            whisper_model: env_string("WHISPER_MODEL", "medium"),
            whisper_device: env_string("WHISPER_DEVICE", "cpu"),
            transition_duration: env_parse("TRANSITION_DURATION", 0.5_f64).clamp(0.0, 5.0),
            speaker_switch_delay: env_parse("SPEAKER_SWITCH_DELAY", 0.5_f64).max(0.0),
            silence_threshold: env_parse("SILENCE_THRESHOLD", 2.0_f64).max(0.1),
            silence_db: env_parse("SILENCE_DB", -40.0_f64).clamp(-120.0, 0.0),
            zoom_factor: env_parse("ZOOM_FACTOR", 1.3_f64).clamp(1.0, 4.0),
            pip_size: env_parse("PIP_SIZE", 0.25_f64).clamp(0.05, 0.9),
            max_parallel_jobs: env_parse("MAX_PARALLEL_JOBS", 2_usize).max(1),
            enable_gpu: std::env::var("ENABLE_GPU")
                .ok()
                .and_then(|v| parse_bool_flag(&v))
                .unwrap_or(true),
            max_retained_jobs: env_parse("MAX_RETAINED_JOBS", 200_usize).max(1),
        }
    }

    /// Build a self-contained configuration rooted at `root` (used by tests).
    #[cfg(test)]
    pub fn for_root(root: &Path) -> Self {
        Self {
            output_dir: root.join("output"),
            cache_dir: root.join("cache"),
            temp_dir: root.join("tmp"),
            extra_output_roots: Vec::new(),
            whisper_bin: "whisper-binary-that-does-not-exist".to_string(),
            whisper_model: "tiny".to_string(),
            whisper_device: "cpu".to_string(),
            transition_duration: 0.5,
            speaker_switch_delay: 0.5,
            silence_threshold: 2.0,
            silence_db: -40.0,
            zoom_factor: 1.3,
            pip_size: 0.25,
            max_parallel_jobs: 2,
            enable_gpu: false,
            max_retained_jobs: 50,
        }
    }

    /// Directory for rendered videos.
    pub fn renders_dir(&self) -> PathBuf {
        self.output_dir.join("renders")
    }

    /// Directory for extracted clips.
    pub fn clips_dir(&self) -> PathBuf {
        self.output_dir.join("clips")
    }

    /// Directory for saved edit decision lists.
    pub fn edl_dir(&self) -> PathBuf {
        self.output_dir.join("edl")
    }

    /// Create the output/cache/temp directory tree.
    pub fn ensure_dirs(&self) -> Result<()> {
        for dir in [
            self.output_dir.clone(),
            self.renders_dir(),
            self.clips_dir(),
            self.edl_dir(),
            self.cache_dir.join("transcripts"),
            self.temp_dir.clone(),
        ] {
            std::fs::create_dir_all(&dir)
                .with_context(|| format!("Failed to create directory {}", dir.display()))?;
        }
        Ok(())
    }

    /// All roots an output path may live under.
    pub fn output_roots(&self) -> Vec<PathBuf> {
        let mut roots = vec![self.output_dir.clone()];
        roots.extend(self.extra_output_roots.iter().cloned());
        roots
    }

    /// Resolve a user-supplied output path against the output policy.
    ///
    /// * `None` -> `default_dir/default_name`.
    /// * Relative paths are resolved against `output_dir`.
    /// * Absolute paths must lie under an allowed output root.
    ///
    /// `..` components are rejected outright, and the deepest existing ancestor
    /// is canonicalized so a symlink inside the root cannot escape it. The
    /// parent directory is created on success.
    pub fn resolve_output_path(
        &self,
        requested: Option<&str>,
        default_dir: &Path,
        default_name: &str,
    ) -> Result<PathBuf> {
        let path = match requested.map(str::trim).filter(|s| !s.is_empty()) {
            None => default_dir.join(default_name),
            Some(raw) => {
                let p = PathBuf::from(raw);
                if p.components().any(|c| matches!(c, Component::ParentDir)) {
                    bail!("Output path must not contain '..' components: {raw}");
                }
                if p.is_absolute() {
                    p
                } else {
                    self.output_dir.join(p)
                }
            },
        };
        self.check_output_allowed(&path)?;
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).with_context(|| {
                format!("Failed to create output directory {}", parent.display())
            })?;
        }
        Ok(path)
    }

    /// Resolve a user-supplied output *directory* against the output policy.
    pub fn resolve_output_dir(
        &self,
        requested: Option<&str>,
        default_dir: &Path,
    ) -> Result<PathBuf> {
        let dir = match requested.map(str::trim).filter(|s| !s.is_empty()) {
            None => default_dir.to_path_buf(),
            Some(raw) => {
                let p = PathBuf::from(raw);
                if p.components().any(|c| matches!(c, Component::ParentDir)) {
                    bail!("Output directory must not contain '..' components: {raw}");
                }
                if p.is_absolute() {
                    p
                } else {
                    self.output_dir.join(p)
                }
            },
        };
        // Validate as if writing a file inside the directory.
        self.check_output_allowed(&dir.join("probe"))?;
        std::fs::create_dir_all(&dir)
            .with_context(|| format!("Failed to create output directory {}", dir.display()))?;
        Ok(dir)
    }

    fn check_output_allowed(&self, path: &Path) -> Result<()> {
        let resolved = canonicalize_lenient(path);
        let allowed = self
            .output_roots()
            .iter()
            .any(|root| resolved.starts_with(canonicalize_lenient(root)));
        if !allowed {
            let roots: Vec<String> = self
                .output_roots()
                .iter()
                .map(|r| r.display().to_string())
                .collect();
            bail!(
                "Output path {} is outside the allowed output directories [{}]. Use a relative \
                 path (resolved under the output directory) or add the directory to \
                 MCP_VIDEO_ALLOWED_OUTPUT_DIRS.",
                path.display(),
                roots.join(", ")
            );
        }
        Ok(())
    }
}

/// Make a path absolute relative to the current directory (without touching
/// the filesystem).
fn absolutize(path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .map(|cwd| cwd.join(path))
            .unwrap_or_else(|_| path.to_path_buf())
    }
}

/// Canonicalize the deepest existing ancestor of `path` and re-append the
/// non-existent remainder. Works for paths that do not exist yet.
fn canonicalize_lenient(path: &Path) -> PathBuf {
    let path = absolutize(path);
    let mut existing = path.as_path();
    let mut tail: Vec<&std::ffi::OsStr> = Vec::new();
    loop {
        if let Ok(canon) = existing.canonicalize() {
            let mut out = canon;
            for part in tail.iter().rev() {
                out.push(part);
            }
            return out;
        }
        match (existing.parent(), existing.file_name()) {
            (Some(parent), Some(name)) => {
                tail.push(name);
                existing = parent;
            },
            _ => return path.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_bool_flag_variants() {
        assert_eq!(parse_bool_flag("TRUE"), Some(true));
        assert_eq!(parse_bool_flag("1"), Some(true));
        assert_eq!(parse_bool_flag("off"), Some(false));
        assert_eq!(parse_bool_flag("maybe"), None);
    }

    #[test]
    fn relative_output_resolves_under_output_dir() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = ServerConfig::for_root(tmp.path());
        let p = cfg
            .resolve_output_path(Some("sub/out.mp4"), &cfg.renders_dir(), "x.mp4")
            .unwrap();
        assert!(p.ends_with(Path::new("sub").join("out.mp4")));
        assert!(p.parent().unwrap().is_dir());
    }

    #[test]
    fn default_output_uses_default_dir() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = ServerConfig::for_root(tmp.path());
        let p = cfg
            .resolve_output_path(None, &cfg.renders_dir(), "x.mp4")
            .unwrap();
        assert_eq!(p, cfg.renders_dir().join("x.mp4"));
    }

    #[test]
    fn parent_dir_components_rejected() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = ServerConfig::for_root(tmp.path());
        let err = cfg
            .resolve_output_path(Some("../escape.mp4"), &cfg.renders_dir(), "x.mp4")
            .unwrap_err();
        assert!(err.to_string().contains(".."));
    }

    #[test]
    fn absolute_output_outside_roots_rejected() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = ServerConfig::for_root(&tmp.path().join("root"));
        let outside = tmp.path().join("elsewhere").join("x.mp4");
        let err = cfg
            .resolve_output_path(Some(outside.to_str().unwrap()), &cfg.renders_dir(), "x.mp4")
            .unwrap_err();
        assert!(err.to_string().contains("outside the allowed"));
    }

    #[test]
    fn extra_roots_are_allowed() {
        let tmp = tempfile::tempdir().unwrap();
        let mut cfg = ServerConfig::for_root(&tmp.path().join("root"));
        let extra = tmp.path().join("extra");
        cfg.extra_output_roots.push(extra.clone());
        let target = extra.join("deep").join("x.mp4");
        let p = cfg
            .resolve_output_path(Some(target.to_str().unwrap()), &cfg.renders_dir(), "x.mp4")
            .unwrap();
        assert_eq!(p, target);
    }

    #[test]
    fn output_dir_policy() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = ServerConfig::for_root(tmp.path());
        let d = cfg
            .resolve_output_dir(Some("myclips"), &cfg.clips_dir())
            .unwrap();
        assert!(d.is_dir());
        assert!(
            cfg.resolve_output_dir(Some("a/../../b"), &cfg.clips_dir())
                .is_err()
        );
    }
}
