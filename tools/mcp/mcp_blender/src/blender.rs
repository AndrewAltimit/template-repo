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

/// Script argument parsing patterns used by different Blender Python scripts
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ScriptType {
    /// Inline JSON: `blender --python script.py -- <json_string>`
    /// Used by: advanced_objects.py, quick_effects.py
    InlineJson,
    /// File with job ID: `blender --python script.py -- args.json job_id`
    /// Used by: render.py, scene_builder.py, animation.py, environment.py,
    ///          geometry_nodes.py, physics_sim.py
    FileWithJobId,
    /// Argparse with --args: `blender --python script.py -- --args <json_string>`
    /// Used by: camera_tools.py, modifiers.py, particles.py
    ArgparseArgs,
}

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

    /// Get the scripts directory
    pub fn scripts_dir(&self) -> &Path {
        &self.scripts_dir
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
            Some(PathBuf::from(
                "/Applications/Blender.app/Contents/MacOS/Blender",
            )),
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
                        info!(
                            "Found Blender at {:?}: {}",
                            path,
                            version.lines().next().unwrap_or("unknown")
                        );

                        let mut bm_path = self.blender_path.write().await;
                        *bm_path = Some(path.clone());

                        let mut initialized = self.initialized.write().await;
                        *initialized = true;

                        // Create necessary directories
                        self.setup_directories().await?;

                        return Ok(path);
                    }
                    Ok(output) => {
                        debug!(
                            "Blender at {:?} failed version check: {:?}",
                            path, output.status
                        );
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

        // Scripts have different argument parsing patterns:
        // - Pattern 1 (inline JSON): advanced_objects.py, quick_effects.py
        //   Expects: blender --python script.py -- <json_string>
        // - Pattern 2 (file + job_id): render.py, scene_builder.py, animation.py, etc.
        //   Expects: blender --python script.py -- args.json job_id
        // - Pattern 3 (argparse --args): camera_tools.py, modifiers.py, particles.py
        //   Expects: blender --python script.py -- --args <json_string>
        let script_type = Self::detect_script_type(script_name);

        // For file-based scripts, write args to a temp file
        let temp_file = if script_type == ScriptType::FileWithJobId {
            let temp_dir = self.base_dir.join("temp");
            tokio::fs::create_dir_all(&temp_dir)
                .await
                .map_err(|e| MCPError::Internal(format!("Failed to create temp dir: {}", e)))?;
            let temp_path = temp_dir.join(format!("{}.json", job_id));
            let json_str = serde_json::to_string(&args).unwrap_or_default();
            tokio::fs::write(&temp_path, &json_str)
                .await
                .map_err(|e| MCPError::Internal(format!("Failed to write temp file: {}", e)))?;
            Some(temp_path)
        } else {
            None
        };

        // Build Blender command with appropriate arguments
        let mut cmd = Command::new(&blender_path);
        cmd.arg("--background").arg("--python").arg(&script_path);

        match script_type {
            ScriptType::InlineJson => {
                cmd.arg("--")
                    .arg(serde_json::to_string(&args).unwrap_or_default());
            }
            ScriptType::FileWithJobId => {
                if let Some(ref temp_path) = temp_file {
                    cmd.arg("--")
                        .arg(temp_path.to_string_lossy().as_ref())
                        .arg(job_id.to_string());
                }
            }
            ScriptType::ArgparseArgs => {
                cmd.arg("--")
                    .arg("--args")
                    .arg(serde_json::to_string(&args).unwrap_or_default());
            }
        }

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

        // Clean up temp file if created
        if let Some(temp_path) = temp_file {
            if let Err(e) = tokio::fs::remove_file(&temp_path).await {
                debug!("Failed to remove temp file {:?}: {}", temp_path, e);
            }
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
            return Err(MCPError::InvalidParameters(
                "Empty path provided".to_string(),
            ));
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

    /// Detect the argument parsing pattern used by a script
    fn detect_script_type(script_name: &str) -> ScriptType {
        match script_name {
            // Pattern 1: Inline JSON parsing
            "advanced_objects.py" | "quick_effects.py" => ScriptType::InlineJson,
            // Pattern 3: Argparse with --args flag
            "camera_tools.py" | "modifiers.py" | "particles.py" => ScriptType::ArgparseArgs,
            // Pattern 2: File with job ID (default for most scripts)
            // render.py, scene_builder.py, animation.py, environment.py,
            // geometry_nodes.py, physics_sim.py
            _ => ScriptType::FileWithJobId,
        }
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

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn create_test_executor() -> (BlenderExecutor, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let executor = BlenderExecutor::new();
        (executor, temp_dir)
    }

    // ========== Path Validation Tests (Security Critical) ==========

    #[test]
    fn test_validate_path_simple_filename() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        let result = executor.validate_path("project.blend", base);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), base.join("project.blend"));
    }

    #[test]
    fn test_validate_path_with_subdirectory() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        let result = executor.validate_path("subdir/project.blend", base);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), base.join("subdir/project.blend"));
    }

    #[test]
    fn test_validate_path_rejects_empty() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        let result = executor.validate_path("", base);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Empty path"));
    }

    #[test]
    fn test_validate_path_rejects_absolute_path() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        let result = executor.validate_path("/etc/passwd", base);
        assert!(result.is_err());
        assert!(
            result
                .unwrap_err()
                .to_string()
                .contains("Absolute paths not allowed")
        );
    }

    #[test]
    fn test_validate_path_rejects_parent_traversal() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        // Direct parent reference
        let result = executor.validate_path("../secret.txt", base);
        assert!(result.is_err());
        assert!(
            result
                .unwrap_err()
                .to_string()
                .contains("Parent directory references not allowed")
        );

        // Nested parent reference
        let result = executor.validate_path("subdir/../../etc/passwd", base);
        assert!(result.is_err());

        // Parent at the end
        let result = executor.validate_path("subdir/..", base);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_path_rejects_current_directory() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        let result = executor.validate_path(".", base);
        assert!(result.is_err());
        assert!(
            result
                .unwrap_err()
                .to_string()
                .contains("Current directory reference not allowed")
        );

        let result = executor.validate_path("./", base);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_path_rejects_hidden_files() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        let result = executor.validate_path(".hidden", base);
        assert!(result.is_err());
        assert!(
            result
                .unwrap_err()
                .to_string()
                .contains("Hidden files/directories not allowed")
        );

        let result = executor.validate_path(".git/config", base);
        assert!(result.is_err());

        let result = executor.validate_path("subdir/.secret", base);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_path_rejects_hidden_directory_in_path() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        let result = executor.validate_path(".hidden/file.txt", base);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_path_allows_dots_in_filename() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        // File extension dots are fine
        let result = executor.validate_path("my.project.blend", base);
        assert!(result.is_ok());

        let result = executor.validate_path("file.tar.gz", base);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_path_multiple_traversal_attempts() {
        let (executor, temp_dir) = create_test_executor();
        let base = temp_dir.path();

        // Various path traversal attack patterns
        // Note: URL-encoded paths (%2e, %2f) are NOT decoded here - that should
        // happen at the HTTP layer before reaching path validation
        let attack_paths = vec![
            "../../../etc/passwd",
            "....//....//etc/passwd",
            "..\\..\\etc\\passwd",
            "foo/../../../etc/passwd",
            "bar/baz/../../..",
        ];

        for path in attack_paths {
            let result = executor.validate_path(path, base);
            assert!(result.is_err(), "Path '{}' should have been rejected", path);
        }
    }

    // ========== Project Path Validation Tests ==========

    #[test]
    fn test_validate_project_path_adds_blend_extension() {
        let executor = BlenderExecutor::new();

        let result = executor.validate_project_path("myproject");
        assert!(result.is_ok());
        let path = result.unwrap();
        assert!(path.to_string_lossy().ends_with("myproject.blend"));
    }

    #[test]
    fn test_validate_project_path_preserves_blend_extension() {
        let executor = BlenderExecutor::new();

        let result = executor.validate_project_path("myproject.blend");
        assert!(result.is_ok());
        let path = result.unwrap();
        assert!(path.to_string_lossy().ends_with("myproject.blend"));
        // Should not double up the extension
        assert!(!path.to_string_lossy().ends_with("myproject.blend.blend"));
    }

    #[test]
    fn test_validate_project_path_rejects_traversal() {
        let executor = BlenderExecutor::new();

        let result = executor.validate_project_path("../../../etc/passwd");
        assert!(result.is_err());

        let result = executor.validate_project_path("..\\..\\secret.blend");
        assert!(result.is_err());
    }

    // ========== Format Detection Tests ==========

    #[test]
    fn test_detect_format() {
        let executor = BlenderExecutor::new();

        assert_eq!(executor.detect_format("model.fbx"), Some("FBX".to_string()));
        assert_eq!(executor.detect_format("model.obj"), Some("OBJ".to_string()));
        assert_eq!(
            executor.detect_format("model.gltf"),
            Some("GLTF".to_string())
        );
        assert_eq!(executor.detect_format("model.stl"), Some("STL".to_string()));
        assert_eq!(
            executor.detect_format("model.blend"),
            Some("BLEND".to_string())
        );
        assert_eq!(executor.detect_format("noextension"), None);
    }

    #[test]
    fn test_detect_format_case_insensitive() {
        let executor = BlenderExecutor::new();

        assert_eq!(executor.detect_format("model.FBX"), Some("FBX".to_string()));
        assert_eq!(executor.detect_format("model.Obj"), Some("OBJ".to_string()));
    }

    // ========== Executor Creation Tests ==========

    #[test]
    fn test_executor_creation() {
        let executor = BlenderExecutor::new();

        // Basic sanity checks
        assert!(executor.base_dir().exists() || !executor.base_dir().starts_with("/app"));
    }

    #[test]
    fn test_executor_default() {
        let executor = BlenderExecutor::default();
        // Should be equivalent to new()
        assert_eq!(executor.base_dir(), BlenderExecutor::new().base_dir());
    }

    #[test]
    fn test_executor_clone() {
        let executor = BlenderExecutor::new();
        let cloned = executor.clone();

        assert_eq!(executor.base_dir(), cloned.base_dir());
        assert_eq!(executor.output_dir(), cloned.output_dir());
    }

    #[test]
    fn test_projects_dir() {
        let executor = BlenderExecutor::new();
        let projects_dir = executor.projects_dir();

        assert!(projects_dir.ends_with("projects"));
    }

    #[test]
    fn test_assets_dir() {
        let executor = BlenderExecutor::new();
        let assets_dir = executor.assets_dir();

        assert!(assets_dir.ends_with("assets"));
    }

    // ========== List Projects Tests ==========

    #[tokio::test]
    async fn test_list_projects_empty_directory() {
        let executor = BlenderExecutor::new();
        // This will return empty if the projects directory doesn't exist or is empty
        let projects = executor.list_projects().await;
        // Should not error, may return empty list
        assert!(projects.is_ok());
    }
}
