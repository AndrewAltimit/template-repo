use std::path::PathBuf;
use std::time::Duration;

use anyhow::{Context, Result};
use sleeper_orchestrator::{config::OrchestratorConfig, docker, health, output};

/// Discover the sleeper_agents package root.
///
/// If `explicit` is provided, use that. Otherwise walk up from CWD looking
/// for a directory containing both `pyproject.toml` and `docker/docker-compose.gpu.yml`.
pub fn find_package_root(explicit: Option<&str>) -> Result<PathBuf> {
    if let Some(path) = explicit {
        return Ok(PathBuf::from(path));
    }

    let mut dir = std::env::current_dir().context("failed to get current directory")?;
    loop {
        if dir.join("pyproject.toml").exists() && dir.join("docker/docker-compose.gpu.yml").exists()
        {
            return Ok(dir);
        }
        let candidate = dir.join("packages/sleeper_agents");
        if candidate.join("pyproject.toml").exists()
            && candidate.join("docker/docker-compose.gpu.yml").exists()
        {
            return Ok(candidate);
        }
        if !dir.pop() {
            anyhow::bail!(
                "could not find sleeper_agents package root\n\
                 hint: run from inside the package or pass --package-root"
            );
        }
    }
}

/// Ensure the GPU container is running and the API is healthy.
///
/// If the container is not running, starts it and waits for the API to
/// become reachable. Returns a configured `SleeperClient`.
pub async fn ensure_api_ready(
    config: &OrchestratorConfig,
    package_root: &std::path::Path,
) -> Result<sleeper_api_client::SleeperClient> {
    let compose = config.compose_path(package_root);
    let api_url = config.api_url();

    // Check if container is running; if not, start it
    if !docker::is_container_running() {
        output::info("Container not running -- starting...");
        if !compose.exists() {
            anyhow::bail!(
                "Compose file not found: {}\nhint: pass --package-root",
                compose.display()
            );
        }
        docker::start_container(&compose)?;
    }

    // Wait for API health
    let timeout = Duration::from_secs(config.startup_timeout_secs);
    health::wait_for_api(&api_url, timeout).await?;

    let api_key = std::env::var("SLEEPER_API_KEY").ok();
    Ok(sleeper_api_client::SleeperClient::new(&api_url, api_key))
}
