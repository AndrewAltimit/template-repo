//! Configuration for Gaea2 MCP server.

use std::path::PathBuf;

/// Server configuration.
#[derive(Debug, Clone)]
pub struct Gaea2Config {
    /// Path to Gaea2 executable (Gaea.Swarm.exe)
    pub gaea_path: Option<PathBuf>,
    /// Output directory for generated terrain files
    pub output_dir: PathBuf,
    /// Whether to enforce file validation via CLI
    pub enforce_file_validation: bool,
}

impl Gaea2Config {
    /// Create a new configuration.
    pub fn new(gaea_path: Option<String>, output_dir: String) -> Self {
        let gaea_path = gaea_path.map(PathBuf::from).and_then(|p| {
            if p.exists() {
                Some(p)
            } else {
                tracing::warn!("Gaea2 executable not found at {:?}", p);
                None
            }
        });

        // Ensure output directory exists
        let output_path = PathBuf::from(&output_dir);
        if let Err(e) = std::fs::create_dir_all(&output_path) {
            tracing::warn!("Failed to create output directory {:?}: {}", output_path, e);
        }

        Self {
            gaea_path,
            output_dir: output_path,
            enforce_file_validation: false,
        }
    }

    /// Check if Gaea2 CLI is available.
    pub fn has_cli(&self) -> bool {
        self.gaea_path.is_some()
    }

    /// Get the output directory as a string.
    pub fn output_dir_str(&self) -> String {
        self.output_dir.to_string_lossy().to_string()
    }

    /// Generate a unique output path for a project.
    pub fn generate_output_path(&self, project_name: &str) -> PathBuf {
        let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        self.output_dir
            .join(format!("{}_{}.terrain", project_name, timestamp))
    }
}

impl Default for Gaea2Config {
    fn default() -> Self {
        Self::new(None, "/app/output/gaea2".to_string())
    }
}
