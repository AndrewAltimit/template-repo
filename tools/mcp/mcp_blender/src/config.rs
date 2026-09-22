//! Runtime configuration, read once from environment variables.

use std::path::{Path, PathBuf};
use std::time::Duration;

/// Default wall-clock limit for a synchronous (scene editing) operation.
pub const DEFAULT_OPERATION_TIMEOUT_SECS: u64 = 600;
/// Default wall-clock limit for an asynchronous job (render / bake).
pub const DEFAULT_JOB_TIMEOUT_SECS: u64 = 7200;
/// Default retention for finished jobs before they are forgotten.
pub const DEFAULT_JOB_RETENTION_HOURS: u64 = 24;

/// Directory layout, limits and timeouts for the server.
#[derive(Debug, Clone)]
pub struct Config {
    /// Root for all state (`/app` in the container).
    pub base_dir: PathBuf,
    /// `.blend` project files.
    pub projects_dir: PathBuf,
    /// Input assets (models, HDRIs, images, fonts) that tools may read.
    pub assets_dir: PathBuf,
    /// Renders, exports and job status files.
    pub output_dir: PathBuf,
    /// Per-invocation argument files.
    pub temp_dir: PathBuf,
    /// Python scripts executed inside Blender.
    pub scripts_dir: PathBuf,
    /// Explicit Blender executable (`BLENDER_PATH`); auto-detected when unset.
    pub blender_path: Option<PathBuf>,
    /// Concurrent asynchronous jobs (renders, bakes).
    pub max_concurrent_jobs: usize,
    /// Concurrent synchronous operations (scene edits).
    pub max_concurrent_operations: usize,
    /// Timeout for synchronous operations.
    pub operation_timeout: Duration,
    /// Timeout for asynchronous jobs.
    pub job_timeout: Duration,
    /// How long finished jobs stay queryable.
    pub job_retention: Duration,
}

impl Config {
    /// Build the configuration from the process environment.
    pub fn from_env() -> Self {
        Self::from_vars(
            |key| std::env::var(key).ok().filter(|v| !v.trim().is_empty()),
            Path::new("/app").is_dir(),
        )
    }

    /// Build the configuration from an arbitrary variable source (testable).
    ///
    /// `in_container` selects `/app` as the default base directory.
    pub fn from_vars(var: impl Fn(&str) -> Option<String>, in_container: bool) -> Self {
        let path = |key: &str| var(key).map(PathBuf::from);
        let base_dir = path("MCP_BLENDER_BASE_DIR").unwrap_or_else(|| {
            if in_container {
                PathBuf::from("/app")
            } else {
                std::env::temp_dir().join("blender-mcp")
            }
        });
        let scripts_dir = path("MCP_BLENDER_SCRIPTS_DIR").unwrap_or_else(|| {
            let container = PathBuf::from("/app/blender/scripts");
            if in_container && container.is_dir() {
                container
            } else {
                PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("scripts")
            }
        });
        let cpus = std::thread::available_parallelism().map_or(2, |n| n.get());
        let number = |key: &str| var(key).and_then(|v| v.trim().parse::<u64>().ok());

        Self {
            projects_dir: path("MCP_BLENDER_PROJECT_DIR")
                .unwrap_or_else(|| base_dir.join("projects")),
            assets_dir: path("MCP_BLENDER_ASSETS_DIR").unwrap_or_else(|| base_dir.join("assets")),
            output_dir: path("MCP_BLENDER_OUTPUT_DIR").unwrap_or_else(|| base_dir.join("outputs")),
            temp_dir: path("MCP_BLENDER_TEMP_DIR").unwrap_or_else(|| base_dir.join("temp")),
            scripts_dir,
            blender_path: path("BLENDER_PATH"),
            max_concurrent_jobs: number("MAX_CONCURRENT_JOBS")
                .map_or((cpus / 2).max(1), |n| n as usize)
                .max(1),
            max_concurrent_operations: number("MAX_CONCURRENT_OPERATIONS")
                .map_or(cpus.max(2), |n| n as usize)
                .max(1),
            operation_timeout: Duration::from_secs(
                number("BLENDER_JOB_TIMEOUT_SECS")
                    .filter(|&s| s > 0)
                    .unwrap_or(DEFAULT_OPERATION_TIMEOUT_SECS),
            ),
            job_timeout: Duration::from_secs(
                number("BLENDER_RENDER_TIMEOUT_SECS")
                    .filter(|&s| s > 0)
                    .unwrap_or(DEFAULT_JOB_TIMEOUT_SECS),
            ),
            job_retention: Duration::from_secs(
                3600 * number("BLENDER_JOB_RETENTION_HOURS").unwrap_or(DEFAULT_JOB_RETENTION_HOURS),
            ),
            base_dir,
        }
    }

    /// Directory for job status files shared with the scripts
    /// (`BLENDER_MCP_JOBS_DIR` in the child environment).
    pub fn jobs_dir(&self) -> PathBuf {
        self.output_dir.join("jobs")
    }

    /// Create every working directory (best effort; failures are reported by
    /// the operations that need them).
    pub fn ensure_dirs(&self) -> Vec<String> {
        let mut errors = Vec::new();
        for dir in [
            &self.projects_dir,
            &self.assets_dir,
            &self.output_dir,
            &self.temp_dir,
            &self.jobs_dir(),
        ] {
            if let Err(e) = std::fs::create_dir_all(dir) {
                errors.push(format!("{}: {}", dir.display(), e));
            }
        }
        errors
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn config(vars: &[(&str, &str)], in_container: bool) -> Config {
        let map: HashMap<String, String> = vars
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        Config::from_vars(|k| map.get(k).cloned(), in_container)
    }

    #[test]
    fn container_defaults_live_under_app() {
        let c = config(&[], true);
        assert_eq!(c.base_dir, PathBuf::from("/app"));
        assert_eq!(c.projects_dir, PathBuf::from("/app/projects"));
        assert_eq!(c.assets_dir, PathBuf::from("/app/assets"));
        assert_eq!(c.output_dir, PathBuf::from("/app/outputs"));
        assert_eq!(c.jobs_dir(), PathBuf::from("/app/outputs/jobs"));
        assert_eq!(
            c.operation_timeout,
            Duration::from_secs(DEFAULT_OPERATION_TIMEOUT_SECS)
        );
        assert_eq!(c.job_timeout, Duration::from_secs(DEFAULT_JOB_TIMEOUT_SECS));
        assert!(c.blender_path.is_none());
        assert!(c.max_concurrent_jobs >= 1 && c.max_concurrent_operations >= 1);
    }

    #[test]
    fn host_defaults_use_temp_dir() {
        let c = config(&[], false);
        assert_eq!(c.base_dir, std::env::temp_dir().join("blender-mcp"));
        assert!(c.scripts_dir.ends_with("scripts"));
    }

    #[test]
    fn env_overrides_are_honoured() {
        let c = config(
            &[
                ("MCP_BLENDER_BASE_DIR", "/data"),
                ("MCP_BLENDER_PROJECT_DIR", "/p"),
                ("MCP_BLENDER_SCRIPTS_DIR", "/s"),
                ("BLENDER_PATH", "/opt/blender/blender"),
                ("MAX_CONCURRENT_JOBS", "3"),
                ("MAX_CONCURRENT_OPERATIONS", "5"),
                ("BLENDER_JOB_TIMEOUT_SECS", "30"),
                ("BLENDER_RENDER_TIMEOUT_SECS", "90"),
                ("BLENDER_JOB_RETENTION_HOURS", "2"),
            ],
            true,
        );
        assert_eq!(c.projects_dir, PathBuf::from("/p"));
        assert_eq!(c.assets_dir, PathBuf::from("/data/assets"));
        assert_eq!(c.scripts_dir, PathBuf::from("/s"));
        assert_eq!(c.blender_path, Some(PathBuf::from("/opt/blender/blender")));
        assert_eq!(c.max_concurrent_jobs, 3);
        assert_eq!(c.max_concurrent_operations, 5);
        assert_eq!(c.operation_timeout, Duration::from_secs(30));
        assert_eq!(c.job_timeout, Duration::from_secs(90));
        assert_eq!(c.job_retention, Duration::from_secs(7200));
    }

    #[test]
    fn invalid_numbers_fall_back_to_defaults() {
        let c = config(
            &[
                ("MAX_CONCURRENT_JOBS", "0"),
                ("BLENDER_JOB_TIMEOUT_SECS", "0"),
                ("BLENDER_RENDER_TIMEOUT_SECS", "abc"),
            ],
            true,
        );
        assert_eq!(c.max_concurrent_jobs, 1);
        assert_eq!(
            c.operation_timeout,
            Duration::from_secs(DEFAULT_OPERATION_TIMEOUT_SECS)
        );
        assert_eq!(c.job_timeout, Duration::from_secs(DEFAULT_JOB_TIMEOUT_SECS));
    }

    #[test]
    fn ensure_dirs_creates_layout() {
        let tmp = tempfile::tempdir().unwrap();
        let base = tmp.path().to_string_lossy().to_string();
        let c = config(&[("MCP_BLENDER_BASE_DIR", &base)], false);
        assert!(c.ensure_dirs().is_empty());
        assert!(c.projects_dir.is_dir());
        assert!(c.jobs_dir().is_dir());
    }
}
