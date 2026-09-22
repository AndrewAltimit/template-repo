//! Configuration and path handling for the AI Toolkit MCP server.
//!
//! Every user-supplied name or path goes through one of the validators in this
//! module before it touches the filesystem:
//!
//! - [`validate_name`] for single-component resource names (configs, datasets,
//!   training runs). These end up as file or directory names, so only a
//!   conservative character set is accepted.
//! - [`validate_filename`] for uploaded image file names.
//! - [`validate_path`] for relative paths that may contain sub-directories
//!   (model names such as `my_lora/my_lora_000000250`, export destinations).

use std::path::{Component, Path, PathBuf};
use thiserror::Error;

/// Default AI Toolkit installation directory (matches the Docker image).
pub const DEFAULT_BASE_PATH: &str = "/ai-toolkit";

/// Maximum length of a resource name.
const MAX_NAME_LEN: usize = 128;

/// Configuration / validation errors.
#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Invalid path: {0}")]
    InvalidPath(String),
    #[error("Path traversal attempt detected: {0}")]
    PathTraversal(String),
    #[error("Empty path provided")]
    EmptyPath,
    #[error("Absolute path not allowed")]
    AbsolutePath,
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

/// Filesystem layout and runtime settings for the AI Toolkit installation.
#[derive(Clone, Debug)]
pub struct AIToolkitPaths {
    /// AI Toolkit checkout (contains `run.py`); training runs with this as cwd.
    pub base_path: PathBuf,
    /// Directory holding one sub-directory per dataset.
    pub datasets_path: PathBuf,
    /// Directory where training runs, logs and exports are written.
    pub outputs_path: PathBuf,
    /// Directory holding `<name>.yaml` training configs.
    pub configs_path: PathBuf,
    /// Python interpreter used to launch `run.py`.
    pub python: String,
}

impl AIToolkitPaths {
    /// Build the layout from environment variables.
    ///
    /// | Variable | Default |
    /// |----------|---------|
    /// | `AI_TOOLKIT_PATH` | `/ai-toolkit` |
    /// | `AI_TOOLKIT_CONFIGS_PATH` | `$AI_TOOLKIT_PATH/config` |
    /// | `AI_TOOLKIT_DATASETS_PATH` | `$AI_TOOLKIT_PATH/datasets` |
    /// | `AI_TOOLKIT_OUTPUTS_PATH` | `$AI_TOOLKIT_PATH/outputs` |
    /// | `AI_TOOLKIT_PYTHON` | `python3` |
    pub fn from_env() -> Self {
        let env = |key: &str| std::env::var(key).ok().filter(|v| !v.trim().is_empty());

        let base = env("AI_TOOLKIT_PATH").unwrap_or_else(|| DEFAULT_BASE_PATH.to_string());
        let mut paths = Self::from_base(base);
        if let Some(p) = env("AI_TOOLKIT_CONFIGS_PATH") {
            paths.configs_path = PathBuf::from(p);
        }
        if let Some(p) = env("AI_TOOLKIT_DATASETS_PATH") {
            paths.datasets_path = PathBuf::from(p);
        }
        if let Some(p) = env("AI_TOOLKIT_OUTPUTS_PATH") {
            paths.outputs_path = PathBuf::from(p);
        }
        if let Some(p) = env("AI_TOOLKIT_PYTHON") {
            paths.python = p;
        }
        paths
    }

    /// Build the default layout under `base` (no environment lookups).
    pub fn from_base(base: impl Into<PathBuf>) -> Self {
        let base_path = base.into();
        Self {
            datasets_path: base_path.join("datasets"),
            outputs_path: base_path.join("outputs"),
            configs_path: base_path.join("config"),
            python: "python3".to_string(),
            base_path,
        }
    }

    /// Ensure the datasets, outputs and configs directories exist.
    pub fn ensure_directories(&self) -> Result<(), ConfigError> {
        std::fs::create_dir_all(&self.datasets_path)?;
        std::fs::create_dir_all(&self.outputs_path)?;
        std::fs::create_dir_all(&self.configs_path)?;
        Ok(())
    }

    /// Path of the AI Toolkit entry point script.
    pub fn run_script(&self) -> PathBuf {
        self.base_path.join("run.py")
    }

    /// Path of the YAML file for config `name` (validated).
    pub fn config_file(&self, name: &str) -> Result<PathBuf, ConfigError> {
        validate_name(name, "config")?;
        Ok(self.configs_path.join(format!("{name}.yaml")))
    }

    /// Directory of dataset `name` (validated).
    pub fn dataset_dir(&self, name: &str) -> Result<PathBuf, ConfigError> {
        validate_name(name, "dataset")?;
        Ok(self.datasets_path.join(name))
    }

    /// Directory holding exported model copies.
    pub fn exports_path(&self) -> PathBuf {
        self.outputs_path.join("exports")
    }
}

/// Validate a single-component resource name (config, dataset, training run).
///
/// Accepts `[A-Za-z0-9._-]`, at most 128 characters, not starting with `.`.
pub fn validate_name(name: &str, kind: &str) -> Result<(), ConfigError> {
    if name.is_empty() {
        return Err(ConfigError::EmptyPath);
    }
    if name.len() > MAX_NAME_LEN {
        return Err(ConfigError::InvalidPath(format!(
            "{kind} name is longer than {MAX_NAME_LEN} characters"
        )));
    }
    if name.starts_with('.') {
        return Err(ConfigError::InvalidPath(format!(
            "{kind} name must not start with '.'"
        )));
    }
    if let Some(bad) = name
        .chars()
        .find(|c| !(c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.')))
    {
        return Err(ConfigError::InvalidPath(format!(
            "{kind} name '{name}' contains invalid character {bad:?} (allowed: letters, digits, '_', '-', '.')"
        )));
    }
    Ok(())
}

/// Validate and resolve a user-provided relative path inside `base_dir`.
///
/// Rejects empty/absolute paths and any `.`/`..`/root/prefix component. When the
/// target (or its nearest existing ancestor) exists, it is canonicalized and must
/// still lie inside `base_dir`, which defeats symlink escapes.
pub fn validate_path(
    user_path: &str,
    base_dir: &Path,
    path_type: &str,
) -> Result<PathBuf, ConfigError> {
    if user_path.trim().is_empty() {
        return Err(ConfigError::EmptyPath);
    }
    // Treat both separators as separators regardless of host OS.
    let normalized = user_path.replace('\\', "/");
    if normalized.starts_with('/') || Path::new(user_path).is_absolute() {
        return Err(ConfigError::AbsolutePath);
    }

    let mut relative = PathBuf::new();
    for component in Path::new(&normalized).components() {
        match component {
            Component::Normal(part) => relative.push(part),
            Component::CurDir | Component::ParentDir => {
                return Err(ConfigError::PathTraversal(format!(
                    "Invalid {path_type} path: '.' and '..' components are not allowed"
                )));
            },
            Component::RootDir | Component::Prefix(_) => return Err(ConfigError::AbsolutePath),
        }
    }
    if relative.as_os_str().is_empty() {
        return Err(ConfigError::EmptyPath);
    }

    let safe_path = base_dir.join(&relative);
    ensure_within(&safe_path, base_dir, path_type)?;
    Ok(safe_path)
}

/// Verify that `path` (or its nearest existing ancestor) resolves inside `base_dir`.
fn ensure_within(path: &Path, base_dir: &Path, path_type: &str) -> Result<(), ConfigError> {
    let Ok(canonical_base) = base_dir.canonicalize() else {
        // Base does not exist yet: nothing on disk can redirect us.
        return Ok(());
    };
    let mut probe = Some(path);
    while let Some(candidate) = probe {
        if candidate.exists() {
            let canonical = candidate.canonicalize()?;
            if !canonical.starts_with(&canonical_base) {
                return Err(ConfigError::PathTraversal(format!(
                    "Invalid {path_type} path: resolves outside its base directory"
                )));
            }
            return Ok(());
        }
        if candidate == base_dir {
            break;
        }
        probe = candidate.parent();
    }
    Ok(())
}

/// Validate a plain file name (no directory components).
pub fn validate_filename(filename: &str, file_type: &str) -> Result<(), ConfigError> {
    if filename.is_empty() {
        return Err(ConfigError::EmptyPath);
    }
    if filename.contains('/') || filename.contains('\\') {
        return Err(ConfigError::InvalidPath(format!(
            "Invalid {file_type} filename: path separators not allowed"
        )));
    }
    if filename == "." || filename == ".." || filename.starts_with('.') {
        return Err(ConfigError::InvalidPath(format!(
            "Invalid {file_type} filename: must not start with '.'"
        )));
    }
    if filename.len() > 255 || filename.chars().any(|c| c.is_control()) {
        return Err(ConfigError::InvalidPath(format!(
            "Invalid {file_type} filename: too long or contains control characters"
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validate_path_normal() {
        let base = PathBuf::from("/tmp/test-nonexistent-base");
        let result = validate_path("config.yaml", &base, "config").unwrap();
        assert_eq!(result, base.join("config.yaml"));
    }

    #[test]
    fn validate_path_subdirectory_and_backslash() {
        let base = PathBuf::from("/tmp/test-nonexistent-base");
        assert!(validate_path("subdir/file.txt", &base, "file").is_ok());
        assert_eq!(
            validate_path("a\\b", &base, "file").unwrap(),
            base.join("a").join("b")
        );
    }

    #[test]
    fn validate_path_rejects_traversal_absolute_empty() {
        let base = PathBuf::from("/tmp/test");
        assert!(validate_path("../etc/passwd", &base, "config").is_err());
        assert!(validate_path("a/../../x", &base, "config").is_err());
        assert!(validate_path("..\\x", &base, "config").is_err());
        assert!(validate_path("/etc/passwd", &base, "config").is_err());
        assert!(validate_path("\\etc\\passwd", &base, "config").is_err());
        assert!(validate_path("", &base, "config").is_err());
        assert!(validate_path("./", &base, "config").is_err());
    }

    #[test]
    fn validate_path_allows_double_dots_inside_names() {
        let base = PathBuf::from("/tmp/test");
        assert!(validate_path("my..lora", &base, "model").is_ok());
    }

    #[cfg(unix)]
    #[test]
    fn validate_path_rejects_symlink_escape() {
        let base = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        std::os::unix::fs::symlink(outside.path(), base.path().join("link")).unwrap();
        assert!(validate_path("link/file", base.path(), "x").is_err());
        assert!(validate_path("link", base.path(), "x").is_err());
    }

    #[test]
    fn validate_name_rules() {
        assert!(validate_name("my_lora-v1.2", "config").is_ok());
        assert!(validate_name("", "config").is_err());
        assert!(validate_name(".hidden", "config").is_err());
        assert!(validate_name("a/b", "config").is_err());
        assert!(validate_name("a b", "config").is_err());
        assert!(validate_name("..", "config").is_err());
        assert!(validate_name(&"x".repeat(129), "config").is_err());
    }

    #[test]
    fn validate_filename_rules() {
        assert!(validate_filename("image.png", "image").is_ok());
        assert!(validate_filename("subdir/image.png", "image").is_err());
        assert!(validate_filename("..", "image").is_err());
        assert!(validate_filename(".png", "image").is_err());
        assert!(validate_filename("a\nb.png", "image").is_err());
    }

    #[test]
    fn from_base_layout() {
        let p = AIToolkitPaths::from_base("/x");
        assert_eq!(p.configs_path, PathBuf::from("/x/config"));
        assert_eq!(p.datasets_path, PathBuf::from("/x/datasets"));
        assert_eq!(p.outputs_path, PathBuf::from("/x/outputs"));
        assert_eq!(p.run_script(), PathBuf::from("/x/run.py"));
        assert!(p.config_file("../x").is_err());
        assert_eq!(
            p.config_file("lora").unwrap(),
            PathBuf::from("/x/config/lora.yaml")
        );
    }
}
