//! MCP Desktop Control Server
//!
//! Cross-platform desktop automation (windows, screens, screenshots, mouse and
//! keyboard) exposed as MCP tools. Backends: X11 on Linux (pure-Rust `x11rb`,
//! RandR + XTEST) and Win32 on Windows.
//!
//! Usage:
//!     # STDIO mode (Claude Code / local MCP clients)
//!     mcp-desktop-control --mode stdio
//!
//!     # HTTP mode
//!     mcp-desktop-control --mode standalone --port 8026
//!     curl http://localhost:8026/health
//!     curl http://localhost:8026/mcp/tools

mod actions;
mod args;
mod backend;
mod imaging;
mod keys;
mod output;
mod server;
mod types;

use std::path::PathBuf;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use output::OutputConfig;
use server::{DesktopControlServer, VERSION};

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-desktop-control")]
#[command(about = "MCP server for cross-platform desktop control and automation")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Directory screenshots are written to (overrides
    /// DESKTOP_CONTROL_OUTPUT_DIR; default: <data dir>/mcp-desktop-control/screenshots)
    #[arg(long)]
    output_dir: Option<PathBuf>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    let output = OutputConfig::resolve(args.output_dir);
    tracing::info!("Screenshot output directory: {}", output.dir.display());

    let desktop_server = DesktopControlServer::new(output);

    let mut builder = MCPServer::builder("desktop-control", VERSION);
    builder = args.server.apply_to(builder);
    for tool in desktop_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;
    Ok(())
}
