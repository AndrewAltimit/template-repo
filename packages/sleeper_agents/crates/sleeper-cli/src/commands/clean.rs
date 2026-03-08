use anyhow::Result;
use sleeper_orchestrator::{config::OrchestratorConfig, docker, output};

use crate::common::find_package_root;

pub fn run(containers: bool, volumes: bool, package_root: Option<&str>) -> Result<()> {
    if !containers && !volumes {
        output::warn("Nothing to clean. Specify --containers, --volumes, or --all");
        return Ok(());
    }

    let root = find_package_root(package_root)?;
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
