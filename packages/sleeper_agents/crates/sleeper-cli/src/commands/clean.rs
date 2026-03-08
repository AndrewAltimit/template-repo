use std::path::PathBuf;

use anyhow::Result;
use sleeper_orchestrator::{config::OrchestratorConfig, docker, output};

pub fn run(containers: bool, volumes: bool, package_root: Option<&str>) -> Result<()> {
    if !containers && !volumes {
        output::warn("Nothing to clean. Specify --containers, --volumes, or --all");
        return Ok(());
    }

    let root = match package_root {
        Some(p) => PathBuf::from(p),
        None => {
            // Try to find the package root
            let mut dir = std::env::current_dir()?;
            loop {
                if dir.join("pyproject.toml").exists()
                    && dir.join("docker/docker-compose.gpu.yml").exists()
                {
                    break dir;
                }
                let candidate = dir.join("packages/sleeper_agents");
                if candidate.join("pyproject.toml").exists()
                    && candidate.join("docker/docker-compose.gpu.yml").exists()
                {
                    break candidate;
                }
                if !dir.pop() {
                    anyhow::bail!(
                        "could not find sleeper_agents package root\n\
                         hint: run from inside the package or pass --package-root"
                    );
                }
            }
        },
    };

    let config = OrchestratorConfig::default();
    let compose = config.compose_path(&root);

    output::header("Sleeper Agents Cleanup");

    if containers {
        if compose.exists() {
            docker::clean_containers(&compose)?;
            output::success("Containers cleaned");
        } else {
            output::warn(&format!(
                "Compose file not found: {} -- skipping container cleanup",
                compose.display()
            ));
        }
    }

    if volumes {
        docker::clean_volumes()?;
        output::success("Volumes removed");
    }

    output::success("Cleanup complete");
    Ok(())
}
