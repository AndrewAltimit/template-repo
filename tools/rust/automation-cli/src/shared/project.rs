use std::env;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};

/// Find the project root by walking up from the current directory looking for docker-compose.yml
pub fn find_project_root() -> Result<PathBuf> {
    let mut dir = env::current_dir().context("failed to get current directory")?;
    loop {
        if dir.join("docker-compose.yml").exists() && dir.join("CLAUDE.md").exists() {
            return Ok(dir);
        }
        if !dir.pop() {
            bail!(
                "could not find project root (no docker-compose.yml + CLAUDE.md found in any parent)"
            );
        }
    }
}

/// Get the compose file path from the project root
pub fn compose_file(root: &Path) -> PathBuf {
    root.join("docker-compose.yml")
}

/// Check if running in CI environment (GitHub Actions)
pub fn is_ci() -> bool {
    env::var("CI").is_ok()
}

/// Write a key=value pair to GITHUB_OUTPUT if available
pub fn set_github_output(key: &str, value: &str) {
    if let Ok(path) = env::var("GITHUB_OUTPUT") {
        use std::io::Write;
        if let Ok(mut f) = std::fs::OpenOptions::new().append(true).open(path) {
            let _ = writeln!(f, "{key}={value}");
        }
    }
}

/// Write a key=value pair to GITHUB_ENV if available
pub fn set_github_env(key: &str, value: &str) {
    if let Ok(path) = env::var("GITHUB_ENV") {
        use std::io::Write;
        if let Ok(mut f) = std::fs::OpenOptions::new().append(true).open(path) {
            let _ = writeln!(f, "{key}={value}");
        }
    }
}
