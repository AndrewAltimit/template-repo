use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use sleeper_orchestrator::{config::OrchestratorConfig, docker, output};

/// Discover the sleeper_agents package root.
///
/// If `explicit` is provided, use that. Otherwise walk up from CWD looking
/// for a directory containing both `pyproject.toml` and `docker/docker-compose.gpu.yml`.
fn find_package_root(explicit: Option<&str>) -> Result<PathBuf> {
    if let Some(path) = explicit {
        return Ok(PathBuf::from(path));
    }

    let mut dir = std::env::current_dir().context("failed to get current directory")?;
    loop {
        if dir.join("pyproject.toml").exists() && dir.join("docker/docker-compose.gpu.yml").exists()
        {
            return Ok(dir);
        }
        // Also check if we're in the repo root and the package is under packages/
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

pub async fn run(package_root: Option<&str>, json: bool) -> Result<()> {
    let root = find_package_root(package_root)?;
    let config = OrchestratorConfig::default();

    if json {
        return run_json(&root, &config).await;
    }

    output::header("Sleeper Agents Status");

    // Container status
    output::subheader("Container");
    match docker::container_status() {
        docker::ContainerState::Running(s) => output::success(&format!("Container running: {s}")),
        docker::ContainerState::Stopped(s) => output::warn(&format!("Container stopped: {s}")),
        docker::ContainerState::NotFound => output::info("Container not found (not yet created)"),
        docker::ContainerState::DockerUnavailable => output::fail("Docker not available"),
    }

    // Docker compose file
    let compose = config.compose_path(&root);
    if compose.exists() {
        output::success(&format!("Compose file: {}", compose.display()));
    } else {
        output::fail(&format!("Compose file not found: {}", compose.display()));
    }

    // API connectivity (only if container is running)
    output::subheader("API");
    if docker::is_container_running() {
        let client = sleeper_api_client::SleeperClient::new(&config.api_url(), None);
        match client.health().await {
            Ok(resp) => output::success(&format!("API healthy (status: {})", resp.status)),
            Err(e) => output::warn(&format!("API not responding: {e}")),
        }

        match client.status().await {
            Ok(status) => {
                if status.model_loaded {
                    output::success(&format!(
                        "Model loaded: {}",
                        status.model_name.as_deref().unwrap_or("unknown")
                    ));
                } else {
                    output::info("No model loaded");
                }
                if let Some(gpu) = status.gpu_available {
                    if gpu {
                        output::success("GPU available");
                    } else {
                        output::warn("GPU not available");
                    }
                }
            },
            Err(e) => output::detail(&format!("Could not fetch status: {e}")),
        }
    } else {
        output::info("Container not running -- skipping API check");
    }

    // Database
    output::subheader("Database");
    show_db_status(&root);

    Ok(())
}

async fn run_json(root: &Path, config: &OrchestratorConfig) -> Result<()> {
    let container = match docker::container_status() {
        docker::ContainerState::Running(s) => serde_json::json!({"state": "running", "detail": s}),
        docker::ContainerState::Stopped(s) => serde_json::json!({"state": "stopped", "detail": s}),
        docker::ContainerState::NotFound => serde_json::json!({"state": "not_found"}),
        docker::ContainerState::DockerUnavailable => {
            serde_json::json!({"state": "docker_unavailable"})
        },
    };

    let compose_exists = config.compose_path(root).exists();

    let api = if docker::is_container_running() {
        let client = sleeper_api_client::SleeperClient::new(&config.api_url(), None);
        match client.status().await {
            Ok(status) => serde_json::json!({
                "reachable": true,
                "model_loaded": status.model_loaded,
                "model_name": status.model_name,
                "gpu_available": status.gpu_available,
            }),
            Err(e) => serde_json::json!({"reachable": false, "error": e.to_string()}),
        }
    } else {
        serde_json::json!({"reachable": false, "reason": "container_not_running"})
    };

    let db = db_summary_json(root);

    let output = serde_json::json!({
        "container": container,
        "compose_file_exists": compose_exists,
        "api": api,
        "database": db,
    });

    println!("{}", serde_json::to_string_pretty(&output)?);
    Ok(())
}

fn show_db_status(root: &Path) {
    let db_path = root.join("evaluation_results.db");
    if !db_path.exists() {
        output::info("No evaluation database found");
        return;
    }

    match sleeper_db::SleeperDb::open(&db_path) {
        Ok(db) => {
            match db.summary() {
                Ok(tables) => {
                    if tables.is_empty() {
                        output::info("Database exists but has no tables");
                    } else {
                        output::success(&format!("Database: {}", db_path.display()));
                        for table in &tables {
                            output::detail(&format!("{}: {} rows", table.name, table.row_count));
                        }
                    }
                },
                Err(e) => output::warn(&format!("Failed to read database: {e}")),
            }

            match db.models() {
                Ok(models) if !models.is_empty() => {
                    output::detail(&format!("Models evaluated: {}", models.join(", ")));
                },
                _ => {},
            }
        },
        Err(e) => output::warn(&format!("Failed to open database: {e}")),
    }
}

fn db_summary_json(root: &Path) -> serde_json::Value {
    let db_path = root.join("evaluation_results.db");
    if !db_path.exists() {
        return serde_json::json!({"exists": false});
    }

    match sleeper_db::SleeperDb::open(&db_path) {
        Ok(db) => {
            let tables = db
                .summary()
                .unwrap_or_default()
                .into_iter()
                .map(|t| serde_json::json!({"name": t.name, "rows": t.row_count}))
                .collect::<Vec<_>>();
            let models = db.models().unwrap_or_default();
            serde_json::json!({
                "exists": true,
                "path": db_path.display().to_string(),
                "tables": tables,
                "models": models,
            })
        },
        Err(e) => serde_json::json!({"exists": true, "error": e.to_string()}),
    }
}
