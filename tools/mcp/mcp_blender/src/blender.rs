//! Blender subprocess execution and path management.

use mcp_core::error::{MCPError, Result};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::process::Command;
use tokio::sync::{RwLock, Semaphore};
use tracing::{debug, error, info, warn};
use uuid::Uuid;

/// Blender executor for running Python scripts in headless Blender
pub struct BlenderExecutor {
    blender_path: Arc<RwLock<Option<PathBuf>>>,
    scripts_dir: PathBuf,
    base_dir: PathBuf,
    output_dir: PathBuf,
    initialized: Arc<RwLock<bool>>,
    /// Semaphore for limiting concurrent Blender processes
    semaphore: Arc<Semaphore>,
    /// Track running processes for cancellation
    processes: Arc<RwLock<HashMap<Uuid, tokio::process::Child>>>,
}

impl BlenderExecutor {
    /// Create a new Blender executor
    pub fn new() -> Self {
        // Determine base directory
        let base_dir = if Path::new("/app").exists() {
            PathBuf::from("/app")
        } else {
            std::env::temp_dir().join("blender-mcp")
        };

        // Scripts are in the mcp_blender/scripts directory relative to binary
        let scripts_dir = if Path::new("/app/blender/scripts").exists() {
            PathBuf::from("/app/blender/scripts")
        } else {
            // For development, look relative to cargo manifest
            let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
                .map(PathBuf::from)
                .unwrap_or_else(|_| PathBuf::from("."));
            manifest_dir.join("scripts")
        };

        let output_dir = base_dir.join("outputs");

        // Get max concurrent jobs from environment
        let max_concurrent = std::env::var("MAX_CONCURRENT_JOBS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(|| num_cpus::get() / 2)
            .max(1);

        Self {
            blender_path: Arc::new(RwLock::new(None)),
            scripts_dir,
            base_dir,
            output_dir,
            initialized: Arc::new(RwLock::new(false)),
            semaphore: Arc::new(Semaphore::new(max_concurrent)),
            processes: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Get the base directory for projects
    pub fn base_dir(&self) -> &Path {
        &self.base_dir
    }

    /// Get the projects directory
    pub fn projects_dir(&self) -> PathBuf {
        self.base_dir.join("projects")
    }

    /// Get the assets directory
    pub fn assets_dir(&self) -> PathBuf {
        self.base_dir.join("assets")
    }

    /// Get the outputs directory
    pub fn output_dir(&self) -> &Path {
        &self.output_dir
    }

    /// Ensure Blender is available
    pub async fn ensure_initialized(&self) -> Result<PathBuf> {
        // Check if already initialized
        {
            let initialized = self.initialized.read().await;
            if *initialized {
                let path = self.blender_path.read().await;
                if let Some(p) = path.as_ref() {
                    return Ok(p.clone());
                }
            }
        }

        info!("Initializing Blender executor...");

        // Find Blender binary in common locations
        let search_paths = [
            // Container path
            Some(PathBuf::from("/usr/local/bin/blender")),
            // System paths
            Some(PathBuf::from("/usr/bin/blender")),
            // macOS paths
            Some(PathBuf::from("/Applications/Blender.app/Contents/MacOS/Blender")),
            // Via which crate (PATH lookup)
            which::which("blender").ok(),
            // Home directory
            dirs::home_dir().map(|h| h.join(".local/bin/blender")),
        ];

        for path in search_paths.into_iter().flatten() {
            if path.is_file() {
                // Verify it's executable by running --version
                match Command::new(&path).arg("--version").output().await {
                    Ok(output) if output.status.success() => {
                        let version = String::from_utf8_lossy(&output.stdout);
                        info!("Found Blender at {:?}: {}", path, version.lines().next().unwrap_or("unknown"));

                        let mut bm_path = self.blender_path.write().await;
                        *bm_path = Some(path.clone());

                        let mut initialized = self.initialized.write().await;
                        *initialized = true;

                        // Create necessary directories
                        self.setup_directories().await?;

                        return Ok(path);
                    }
                    Ok(output) => {
                        debug!("Blender at {:?} failed version check: {:?}", path, output.status);
                    }
                    Err(e) => {
                        debug!("Blender at {:?} not executable: {}", path, e);
                    }
                }
            }
        }

        Err(MCPError::Internal(
            "Blender executable not found. Install Blender or set BLENDER_PATH environment variable."
                .to_string(),
        ))
    }

    /// Setup necessary directories
    async fn setup_directories(&self) -> Result<()> {
        let dirs = [
            self.projects_dir(),
            self.assets_dir(),
            self.output_dir.clone(),
            self.base_dir.join("templates"),
            self.base_dir.join("temp"),
        ];

        for dir in dirs {
            if let Err(e) = tokio::fs::create_dir_all(&dir).await {
                warn!("Failed to create directory {:?}: {}", dir, e);
            }
        }

        Ok(())
    }

    /// Execute a Blender Python script with arguments
    pub async fn execute_script(
        &self,
        script_name: &str,
        args: Value,
        job_id: Uuid,
    ) -> Result<Value> {
        let blender_path = self.ensure_initialized().await?;
        let script_path = self.scripts_dir.join(script_name);

        if !script_path.exists() {
            return Err(MCPError::Internal(format!(
                "Script not found: {}",
                script_path.display()
            )));
        }

        // Acquire semaphore permit
        let _permit = self
            .semaphore
            .acquire()
            .await
            .map_err(|e| MCPError::Internal(format!("Semaphore error: {}", e)))?;

        debug!(
            "Executing Blender script {} with args: {:?}",
            script_name, args
        );

        // Build Blender command
        let mut cmd = Command::new(&blender_path);
        cmd.arg("--background")
            .arg("--python")
            .arg(&script_path)
            .arg("--")
            .arg(serde_json::to_string(&args).unwrap_or_default());

        // Set environment variables
        if let Ok(cuda_devices) = std::env::var("CUDA_VISIBLE_DEVICES") {
            cmd.env("CUDA_VISIBLE_DEVICES", cuda_devices);
        }

        // Spawn the process
        let child = cmd
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| MCPError::Internal(format!("Failed to spawn Blender: {}", e)))?;

        // Note: Process cancellation would require storing Child handles differently.
        // For now, cancellation is handled at the job level.

        // Wait for completion
        let output = child
            .wait_with_output()
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to wait for Blender: {}", e)))?;

        // Remove from tracking
        {
            let mut processes = self.processes.write().await;
            processes.remove(&job_id);
        }

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("Blender script failed: {}", stderr);
            return Err(MCPError::Internal(format!(
                "Blender script failed: {}",
                stderr.trim()
            )));
        }

        // Parse JSON output from stdout
        let stdout = String::from_utf8_lossy(&output.stdout);

        // Find JSON output (scripts should print JSON to stdout)
        // Look for the last JSON object in the output
        let json_output = stdout
            .lines()
            .rev()
            .find(|line| line.trim().starts_with('{') && line.trim().ends_with('}'))
            .unwrap_or("{}");

        let result: Value = serde_json::from_str(json_output).unwrap_or_else(|_| {
            serde_json::json!({
                "success": output.status.success(),
                "raw_output": stdout.trim()
            })
        });

        Ok(result)
    }

    /// Execute a script asynchronously (for long-running operations)
    pub async fn execute_script_async(
        &self,
        script_name: &str,
        args: Value,
        job_id: Uuid,
    ) -> Result<()> {
        let executor = self.clone();
        let script = script_name.to_string();

        tokio::spawn(async move {
            if let Err(e) = executor.execute_script(&script, args, job_id).await {
                error!("Async script execution failed for job {}: {}", job_id, e);
            }
        });

        Ok(())
    }

    /// Kill a running process by job ID
    pub async fn kill_process(&self, job_id: Uuid) -> bool {
        // Note: Due to Rust's ownership model, we'd need a different approach
        // for actual process cancellation. This is a placeholder.
        warn!(
            "Process cancellation requested for job {} (not fully implemented)",
            job_id
        );
        false
    }

    /// Validate a path to prevent directory traversal attacks
    pub fn validate_path(&self, user_path: &str, base_dir: &Path) -> Result<PathBuf> {
        // Reject empty paths
        if user_path.is_empty() {
            return Err(MCPError::InvalidParameters("Empty path provided".to_string()));
        }

        let path = Path::new(user_path);

        // Reject absolute paths
        if path.is_absolute() {
            return Err(MCPError::InvalidParameters(
                "Absolute paths not allowed".to_string(),
            ));
        }

        // Reject paths with parent directory references
        if user_path.contains("..") {
            warn!("Path traversal attempt blocked: {}", user_path);
            return Err(MCPError::InvalidParameters(
                "Parent directory references not allowed".to_string(),
            ));
        }

        // Reject single dot (current directory)
        if user_path == "." || user_path == "./" {
            return Err(MCPError::InvalidParameters(
                "Current directory reference not allowed".to_string(),
            ));
        }

        // Check path components
        for component in path.components() {
            use std::path::Component;
            match component {
                Component::ParentDir => {
                    return Err(MCPError::InvalidParameters(
                        "Parent directory references not allowed".to_string(),
                    ));
                }
                Component::Normal(s) => {
                    let s_str = s.to_string_lossy();
                    if s_str.starts_with('.') {
                        return Err(MCPError::InvalidParameters(format!(
                            "Hidden files/directories not allowed: {}",
                            s_str
                        )));
                    }
                }
                _ => {}
            }
        }

        // Construct the safe path
        let safe_path = base_dir.join(path);

        // Canonicalize and verify it's within base_dir
        // Note: We use the path as-is since canonicalize requires the file to exist
        if let Ok(canonical_base) = base_dir.canonicalize() {
            // For existing paths, verify they're within the base directory
            if let Ok(canonical_path) = safe_path.canonicalize() {
                if !canonical_path.starts_with(&canonical_base) {
                    warn!(
                        "Path traversal attempt blocked: {} resolved outside base",
                        user_path
                    );
                    return Err(MCPError::InvalidParameters(
                        "Path traversal attempt detected".to_string(),
                    ));
                }
            }
        }

        Ok(safe_path)
    }

    /// Validate a project path
    pub fn validate_project_path(&self, project_path: &str) -> Result<PathBuf> {
        let projects_dir = self.projects_dir();

        // If it already starts with the projects directory, extract relative path
        if let Ok(stripped) = Path::new(project_path).strip_prefix(&projects_dir) {
            return self.validate_path(&stripped.to_string_lossy(), &projects_dir);
        }

        // Handle paths that might already be full container paths
        if project_path.starts_with("/app/projects/") {
            let relative = project_path
                .strip_prefix("/app/projects/")
                .unwrap_or(project_path);
            return self.validate_path(relative, &projects_dir);
        }

        // Add .blend extension if missing
        let path_str = if project_path.ends_with(".blend") {
            project_path.to_string()
        } else {
            format!("{}.blend", project_path)
        };

        self.validate_path(&path_str, &projects_dir)
    }

    /// Detect import format from file extension
    pub fn detect_format(&self, path: &str) -> Option<String> {
        let path = Path::new(path);
        path.extension()
            .and_then(|ext| ext.to_str())
            .map(|ext| ext.to_uppercase())
    }

    /// List available projects
    pub async fn list_projects(&self) -> Result<Vec<String>> {
        let projects_dir = self.projects_dir();

        if !projects_dir.exists() {
            return Ok(vec![]);
        }

        let mut projects = vec![];
        let mut entries = tokio::fs::read_dir(&projects_dir)
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to read projects directory: {}", e)))?;

        while let Some(entry) = entries
            .next_entry()
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to read directory entry: {}", e)))?
        {
            let path = entry.path();
            if path.extension().map_or(false, |ext| ext == "blend") {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    projects.push(name.to_string());
                }
            }
        }

        projects.sort();
        Ok(projects)
    }
}

impl Default for BlenderExecutor {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for BlenderExecutor {
    fn clone(&self) -> Self {
        Self {
            blender_path: self.blender_path.clone(),
            scripts_dir: self.scripts_dir.clone(),
            base_dir: self.base_dir.clone(),
            output_dir: self.output_dir.clone(),
            initialized: self.initialized.clone(),
            semaphore: self.semaphore.clone(),
            processes: self.processes.clone(),
        }
    }
}
