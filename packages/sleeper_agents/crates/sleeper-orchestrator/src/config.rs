use std::path::{Path, PathBuf};

/// Configuration for the sleeper agents orchestrator.
#[derive(Debug, Clone)]
pub struct OrchestratorConfig {
    /// Path to docker-compose.gpu.yml (relative to package root).
    pub compose_file: PathBuf,
    /// Port the FastAPI server listens on inside the container.
    pub api_port: u16,
    /// Host to connect to for the API (default: localhost).
    pub api_host: String,
    /// Maximum time to wait for container startup (seconds).
    pub startup_timeout_secs: u64,
    /// Maximum time to wait for a job to complete (seconds).
    pub job_timeout_secs: u64,
}

impl Default for OrchestratorConfig {
    fn default() -> Self {
        Self {
            compose_file: PathBuf::from("docker/docker-compose.gpu.yml"),
            api_port: sleeper_api_client::DEFAULT_API_PORT,
            api_host: "localhost".to_string(),
            startup_timeout_secs: 120,
            job_timeout_secs: 3600,
        }
    }
}

impl OrchestratorConfig {
    /// Resolve the compose file path relative to a package root.
    pub fn compose_path(&self, package_root: &Path) -> PathBuf {
        package_root.join(&self.compose_file)
    }

    /// Get the base URL for the API.
    pub fn api_url(&self) -> String {
        format!("http://{}:{}", self.api_host, self.api_port)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config() {
        let config = OrchestratorConfig::default();
        assert_eq!(config.api_port, 8022);
        assert_eq!(config.api_host, "localhost");
        assert_eq!(config.api_url(), "http://localhost:8022");
    }

    #[test]
    fn compose_path_resolution() {
        let config = OrchestratorConfig::default();
        let root = Path::new("/home/user/packages/sleeper_agents");
        let resolved = config.compose_path(root);
        assert_eq!(
            resolved,
            PathBuf::from("/home/user/packages/sleeper_agents/docker/docker-compose.gpu.yml")
        );
    }
}
