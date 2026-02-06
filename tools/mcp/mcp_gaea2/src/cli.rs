//! CLI automation for Gaea2 project execution.
//!
//! Supports Gaea.Swarm.exe 2.2.6.0 with command-line arguments.

use std::path::{Path, PathBuf};
use std::time::Instant;

use tokio::process::Command;
use tokio::time::{timeout, Duration};

use crate::types::ExecutionResult;

/// CLI automation for running Gaea2 projects.
pub struct Gaea2CLI {
    gaea_path: PathBuf,
}

impl Gaea2CLI {
    /// Create a new CLI automation instance.
    pub fn new(gaea_path: PathBuf) -> Self {
        Self { gaea_path }
    }

    /// Run a Gaea2 project and generate terrain outputs.
    ///
    /// # Arguments
    /// * `project_path` - Path to the .terrain file
    /// * `resolution` - Build resolution (512, 1024, 2048, 4096, 8192)
    /// * `build_path` - Output directory (optional)
    /// * `profile` - Build profile name (optional)
    /// * `region` - Specific region to build (optional)
    /// * `seed` - Mutation seed for variations (optional)
    /// * `target_node` - Specific node index to target (optional)
    /// * `variables` - Variable name:value pairs (optional)
    /// * `ignore_cache` - Force rebuild ignoring cache
    /// * `verbose` - Enable verbose logging
    /// * `timeout_secs` - Maximum execution time in seconds
    pub async fn run_project(
        &self,
        project_path: &str,
        resolution: &str,
        build_path: Option<&str>,
        profile: Option<&str>,
        region: Option<&str>,
        seed: Option<i64>,
        target_node: Option<&str>,
        variables: Option<std::collections::HashMap<String, String>>,
        ignore_cache: bool,
        verbose: bool,
        timeout_secs: u64,
    ) -> ExecutionResult {
        let project_path = Path::new(project_path);

        // Verify project exists
        if !project_path.exists() {
            return ExecutionResult {
                success: false,
                error: Some(format!("Project file not found: {:?}", project_path)),
                output_dir: None,
                output_files: vec![],
                file_count: 0,
                execution_time: None,
                note: None,
                stdout: None,
                stderr: None,
            };
        }

        // Determine output directory
        let output_dir = if let Some(bp) = build_path {
            PathBuf::from(bp)
        } else {
            let stem = project_path
                .file_stem()
                .unwrap_or_default()
                .to_string_lossy();
            project_path
                .parent()
                .unwrap_or(Path::new("."))
                .join(format!("output_{}", stem))
        };

        // Create output directory
        if let Err(e) = tokio::fs::create_dir_all(&output_dir).await {
            return ExecutionResult {
                success: false,
                error: Some(format!("Failed to create output directory: {}", e)),
                output_dir: None,
                output_files: vec![],
                file_count: 0,
                execution_time: None,
                note: None,
                stdout: None,
                stderr: None,
            };
        }

        // Build command
        let mut cmd = Command::new(&self.gaea_path);
        cmd.arg("--Filename").arg(project_path);
        cmd.arg("--resolution").arg(resolution);
        cmd.arg("--buildpath").arg(&output_dir);
        cmd.arg("--silent"); // Required for automation

        if let Some(p) = profile {
            cmd.arg("--profile").arg(p);
        }

        if let Some(r) = region {
            cmd.arg("--region").arg(r);
        }

        if let Some(s) = seed {
            cmd.arg("--seed").arg(s.to_string());
        }

        if let Some(n) = target_node {
            cmd.arg("--node").arg(n);
        }

        if let Some(vars) = variables {
            for (key, value) in vars {
                cmd.arg("-v").arg(format!("{}:{}", key, value));
            }
        }

        if ignore_cache {
            cmd.arg("--ignorecache");
        }

        if verbose {
            cmd.arg("--verbose");
        }

        tracing::info!(
            "Running Gaea2: {:?} --Filename {:?} --resolution {} --buildpath {:?}",
            self.gaea_path,
            project_path,
            resolution,
            output_dir
        );

        let start_time = Instant::now();

        // Run with timeout
        let result = timeout(Duration::from_secs(timeout_secs), cmd.output()).await;

        let execution_time = start_time.elapsed().as_secs_f64();

        match result {
            Ok(Ok(output)) => {
                let stdout_str = String::from_utf8_lossy(&output.stdout).to_string();
                let stderr_str = String::from_utf8_lossy(&output.stderr).to_string();

                if output.status.success() {
                    // Find generated files
                    let output_files = find_output_files(&output_dir).await;
                    let file_count = output_files.len();

                    ExecutionResult {
                        success: true,
                        error: None,
                        output_dir: Some(output_dir.to_string_lossy().to_string()),
                        output_files,
                        file_count,
                        execution_time: Some(execution_time),
                        note: None,
                        stdout: if stdout_str.is_empty() {
                            None
                        } else {
                            Some(stdout_str)
                        },
                        stderr: if stderr_str.is_empty() {
                            None
                        } else {
                            Some(stderr_str)
                        },
                    }
                } else {
                    ExecutionResult {
                        success: false,
                        error: Some(format!(
                            "Gaea2 exited with code {:?}: {}",
                            output.status.code(),
                            stderr_str
                        )),
                        output_dir: Some(output_dir.to_string_lossy().to_string()),
                        output_files: vec![],
                        file_count: 0,
                        execution_time: Some(execution_time),
                        note: None,
                        stdout: if stdout_str.is_empty() {
                            None
                        } else {
                            Some(stdout_str)
                        },
                        stderr: if stderr_str.is_empty() {
                            None
                        } else {
                            Some(stderr_str)
                        },
                    }
                }
            },
            Ok(Err(e)) => ExecutionResult {
                success: false,
                error: Some(format!("Failed to execute Gaea2: {}", e)),
                output_dir: None,
                output_files: vec![],
                file_count: 0,
                execution_time: Some(execution_time),
                note: None,
                stdout: None,
                stderr: None,
            },
            Err(_) => ExecutionResult {
                success: false,
                error: Some(format!("Process timed out after {} seconds", timeout_secs)),
                output_dir: Some(output_dir.to_string_lossy().to_string()),
                output_files: vec![],
                file_count: 0,
                execution_time: Some(execution_time),
                note: None,
                stdout: None,
                stderr: None,
            },
        }
    }

    /// Validate the Gaea2 installation.
    pub async fn validate_installation(&self) -> Result<String, String> {
        if !self.gaea_path.exists() {
            return Err(format!(
                "Gaea2 executable not found at {:?}",
                self.gaea_path
            ));
        }

        let output = Command::new(&self.gaea_path)
            .arg("--version")
            .output()
            .await
            .map_err(|e| format!("Failed to run Gaea2: {}", e))?;

        if output.status.success() {
            Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
        } else {
            Ok("Unknown version".to_string())
        }
    }
}

/// Find output files in a directory.
async fn find_output_files(dir: &Path) -> Vec<String> {
    let mut files = Vec::new();

    let extensions = ["exr", "png", "tiff", "tif", "raw", "r16", "r32"];

    if let Ok(mut entries) = tokio::fs::read_dir(dir).await {
        while let Ok(Some(entry)) = entries.next_entry().await {
            let path = entry.path();
            if let Some(ext) = path.extension() {
                let ext_lower = ext.to_string_lossy().to_lowercase();
                if extensions.contains(&ext_lower.as_str()) {
                    files.push(path.to_string_lossy().to_string());
                }
            }
        }
    }

    files.sort();
    files
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_find_output_files_empty_dir() {
        let temp_dir = tempfile::tempdir().unwrap();
        let files = find_output_files(temp_dir.path()).await;
        assert!(files.is_empty());
    }
}
