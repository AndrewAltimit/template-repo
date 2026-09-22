//! MCP Meme Generator Server
//!
//! Draws captions onto meme templates, saves the result, returns an inline
//! preview, and optionally uploads it to a free image host.
//!
//! Usage:
//!     # STDIO (how .mcp.json launches it)
//!     mcp-meme-generator --mode stdio
//!
//!     # HTTP
//!     mcp-meme-generator --mode standalone --port 8016
//!     curl http://localhost:8016/health
//!     curl http://localhost:8016/mcp/tools

mod fonts;
mod generator;
mod render;
mod server;
mod templates;
mod types;
mod upload;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use std::path::PathBuf;
use std::time::Duration;
use tracing::info;

use server::{AppState, ServerConfig, VERSION};

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-meme-generator")]
#[command(about = "MCP server for meme generation with text overlays")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Templates directory (contains config/*.json and the images).
    /// Default: first existing of <exe dir>/templates, ./templates,
    /// tools/mcp/mcp_meme_generator/templates, <crate dir>/templates.
    #[arg(long, env = "MCP_MEME_TEMPLATES_DIR")]
    templates: Option<PathBuf>,

    /// Output directory for generated memes [default: <system temp>/memes]
    #[arg(long, env = "MCP_OUTPUT_DIR")]
    output: Option<PathBuf>,

    /// TrueType/OpenType font for captions [default: Liberation Sans Bold if
    /// installed, else the embedded DejaVu Sans Bold]
    #[arg(long, env = "MCP_MEME_FONT")]
    font: Option<PathBuf>,

    /// Refuse all uploads (generate_meme still saves files locally)
    #[arg(long, env = "MCP_MEME_DISABLE_UPLOAD")]
    disable_upload: bool,

    /// Per-attempt upload timeout in seconds
    #[arg(long, env = "MCP_MEME_UPLOAD_TIMEOUT", default_value_t = upload::DEFAULT_UPLOAD_TIMEOUT.as_secs(),
          value_parser = clap::value_parser!(u64).range(1..=300))]
    upload_timeout: u64,
}

/// Find the templates directory when none was given.
fn default_templates_dir() -> PathBuf {
    let mut candidates = Vec::new();
    if let Some(dir) = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
    {
        candidates.push(dir.join("templates"));
    }
    candidates.push(PathBuf::from("templates"));
    candidates.push(PathBuf::from("tools/mcp/mcp_meme_generator/templates"));
    candidates.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("templates"));

    candidates
        .iter()
        .find(|c| c.join("config").is_dir())
        .cloned()
        .unwrap_or_else(|| PathBuf::from("templates"))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let config = ServerConfig {
        templates_dir: args.templates.unwrap_or_else(default_templates_dir),
        output_dir: args
            .output
            .unwrap_or_else(|| std::env::temp_dir().join("memes")),
        font_path: args.font,
        uploads_enabled: !args.disable_upload,
        upload_timeout: Duration::from_secs(args.upload_timeout),
    };
    info!(
        "meme-generator {VERSION}: templates={}, output={}, uploads={}",
        config.templates_dir.display(),
        config.output_dir.display(),
        if config.uploads_enabled {
            "enabled"
        } else {
            "disabled"
        }
    );

    let state = AppState::new(config);
    let mut builder = args
        .server
        .apply_to(MCPServer::builder("meme-generator", VERSION));
    for tool in server::build_tools(&state) {
        builder = builder.tool_boxed(tool);
    }
    builder.build().run().await?;
    Ok(())
}
