//! MCP BioForge Server
//!
//! Exposes the BioForge lab-automation platform (liquid handling, thermal
//! control, gantry motion, plate imaging, protocol validation, human gates
//! and emergency stop) as MCP tools. Every actuator command passes through
//! `bioforge-safety`'s `SafetyEnforcer` before it reaches the hardware layer.
//!
//! Hardware is currently **simulated** (see [`sim`]): responses carry
//! `"simulated": true`. Real `bioforge-hal` drivers can be substituted in
//! [`sim::simulated_hardware`]'s place without touching the tools.
//!
//! Usage:
//!     mcp-bioforge --mode stdio --config-dir packages/bioforge/config
//!     mcp-bioforge --mode standalone --port 8030 --config-dir /path/to/config

mod config;
mod error;
mod lab;
mod protocols;
mod sim;
mod tools;
mod validate;

#[cfg(test)]
mod tests;

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Context;
use bioforge_safety::{AuditLog, SafetyEnforcer};
use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use crate::lab::{Lab, LabOptions, Timeouts};

/// CLI arguments for the BioForge MCP server.
#[derive(Parser)]
#[command(name = "mcp-bioforge")]
#[command(
    about = "MCP server for the BioForge biological automation platform (simulated hardware)"
)]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Directory containing safety_limits.toml and hardware.toml.
    #[arg(long, env = "BIOFORGE_CONFIG_DIR", default_value = "config")]
    config_dir: PathBuf,

    /// Directory containing protocol TOML files (and an optional custom/
    /// subdirectory). Defaults to <config-dir>/../protocols, which matches
    /// the packages/bioforge layout.
    #[arg(long, env = "BIOFORGE_PROTOCOLS_DIR")]
    protocols_dir: Option<PathBuf>,

    /// Directory where the operator confirms human-action gates by creating
    /// `<action_id>.confirmed`. Without it, gates can only expire.
    #[arg(long, env = "BIOFORGE_CONFIRM_DIR")]
    confirm_dir: Option<PathBuf>,

    /// Append-only JSON Lines audit log of every mutating tool call.
    #[arg(long, env = "BIOFORGE_AUDIT_LOG")]
    audit_log: Option<PathBuf>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let cfg = config::load_config(&args.config_dir)?;
    tracing::info!(
        config_dir = %args.config_dir.display(),
        "loaded safety limits and hardware config"
    );
    let enforcer = Arc::new(SafetyEnforcer::new(cfg.limits, cfg.bounds));

    let protocols_dir = args
        .protocols_dir
        .clone()
        .unwrap_or_else(|| args.config_dir.join("..").join("protocols"));
    if !protocols_dir.is_dir() {
        tracing::warn!(
            protocols_dir = %protocols_dir.display(),
            "protocols directory does not exist; list_protocols/load_protocol will fail"
        );
    }

    if let Some(dir) = &args.confirm_dir {
        std::fs::create_dir_all(dir)
            .with_context(|| format!("cannot create confirm dir {}", dir.display()))?;
    }
    let audit_log = args
        .audit_log
        .as_ref()
        .map(|p| AuditLog::new(p).with_context(|| format!("cannot open audit log {}", p.display())))
        .transpose()?;

    let lab = Arc::new(Lab::new(
        enforcer,
        sim::simulated_hardware(),
        LabOptions {
            protocols_dir,
            confirm_dir: args.confirm_dir.clone(),
            audit_log,
            timeouts: Timeouts::default(),
        },
    ));
    tracing::warn!(
        run_id = lab.run_id(),
        "hardware is SIMULATED: no physical actuators are driven"
    );

    let mut builder = MCPServer::builder("bioforge", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in tools::all_tools(lab) {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;
    Ok(())
}
