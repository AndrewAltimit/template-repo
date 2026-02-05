//! MCP BioForge Server
//!
//! Provides biological automation tools via MCP -- liquid handling, thermal
//! control, plate imaging, colony counting, and protocol management.
//!
//! Phase 2: Tools validate inputs through SafetyEnforcer. Hardware calls
//! still return mock responses.
//!
//! Usage:
//!     mcp-bioforge --mode standalone --port 8030
//!     mcp-bioforge --mode stdio
//!     mcp-bioforge --config-dir /path/to/bioforge/config

mod tools;

use std::path::PathBuf;
use std::sync::Arc;

use bioforge_safety::enforcer::{SafetyEnforcer, WorkspaceBounds};
use bioforge_types::config::{HardwareConfig, SafetyLimits};
use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

/// CLI arguments for the BioForge MCP server.
#[derive(Parser)]
#[command(name = "mcp-bioforge")]
#[command(about = "MCP server for BioForge biological automation platform")]
#[command(version = "0.1.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Path to the BioForge config directory containing safety_limits.toml
    /// and hardware.toml.
    #[arg(long, default_value = "config")]
    config_dir: PathBuf,
}

fn load_config(config_dir: &std::path::Path) -> anyhow::Result<(SafetyLimits, WorkspaceBounds)> {
    let safety_path = config_dir.join("safety_limits.toml");
    let hw_path = config_dir.join("hardware.toml");

    let safety_str = std::fs::read_to_string(&safety_path)
        .map_err(|e| anyhow::anyhow!("failed to read {}: {e}", safety_path.display()))?;
    let limits: SafetyLimits = toml::from_str(&safety_str)
        .map_err(|e| anyhow::anyhow!("failed to parse {}: {e}", safety_path.display()))?;

    let hw_str = std::fs::read_to_string(&hw_path)
        .map_err(|e| anyhow::anyhow!("failed to read {}: {e}", hw_path.display()))?;
    let hw: HardwareConfig = toml::from_str(&hw_str)
        .map_err(|e| anyhow::anyhow!("failed to parse {}: {e}", hw_path.display()))?;

    let bounds = WorkspaceBounds {
        x_max_mm: hw.motion.x_max_mm,
        y_max_mm: hw.motion.y_max_mm,
        z_max_mm: hw.motion.z_max_mm,
    };

    Ok((limits, bounds))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    let (limits, bounds) = load_config(&args.config_dir)?;
    let enforcer = Arc::new(SafetyEnforcer::new(limits, bounds));

    tracing::info!(
        config_dir = %args.config_dir.display(),
        "loaded safety limits and hardware config"
    );

    let bioforge = tools::BioForgeServer::new(enforcer);

    let mut builder = MCPServer::builder("bioforge", "0.1.0");
    builder = args.server.apply_to(builder);

    for tool in bioforge.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();
    server.run().await?;

    Ok(())
}
