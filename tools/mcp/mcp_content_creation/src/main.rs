//! MCP Content Creation Server
//!
//! Provides content creation tools via MCP: sandboxed LaTeX compilation,
//! TikZ rendering, PDF page previews, and Manim animations.
//!
//! Usage:
//!     # STDIO mode (what .mcp.json uses)
//!     mcp-content-creation --mode stdio
//!
//!     # HTTP mode (docker compose uses port 8011)
//!     mcp-content-creation --mode standalone --port 8011
//!     curl http://localhost:8011/health
//!     curl http://localhost:8011/mcp/tools

mod engine;
mod latex;
mod manim;
mod paths;
mod process;
mod server;
mod types;

use std::path::PathBuf;
use std::time::Duration;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use engine::EngineConfig;
use server::{ContentCreationServer, SERVER_NAME, SERVER_VERSION};

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-content-creation")]
#[command(about = "MCP server for content creation - LaTeX, TikZ, PDF previews, and Manim")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Output directory for generated content
    #[arg(long, default_value = "/app/output", env = "MCP_OUTPUT_DIR")]
    output_dir: PathBuf,

    /// Project root: input files must live here (or in the output directory)
    #[arg(long, default_value = "/app", env = "MCP_PROJECT_ROOT")]
    project_root: PathBuf,

    /// Project root as seen by the host; absolute host paths under it are
    /// translated to --project-root
    #[arg(long, env = "MCP_HOST_PROJECT_ROOT")]
    host_project_root: Option<PathBuf>,

    /// Host-relative location of --output-dir, used for reported output paths
    #[arg(
        long,
        default_value = "outputs/mcp-content",
        env = "MCP_HOST_OUTPUT_DIR"
    )]
    host_output_dir: String,

    /// Deadline in seconds for each LaTeX / poppler / pdf2svg subprocess
    #[arg(long, default_value_t = 120, env = "MCP_LATEX_TIMEOUT_SECS",
          value_parser = clap::value_parser!(u64).range(1..=3600))]
    latex_timeout_secs: u64,

    /// Deadline in seconds for a Manim render
    #[arg(long, default_value_t = 600, env = "MCP_MANIM_TIMEOUT_SECS",
          value_parser = clap::value_parser!(u64).range(1..=7200))]
    manim_timeout_secs: u64,

    /// Maximum number of compile/render jobs running at once
    #[arg(long, default_value_t = 2, env = "MCP_MAX_CONCURRENT_JOBS",
          value_parser = clap::value_parser!(u64).range(1..=64))]
    max_concurrent_jobs: u64,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    let mut config = EngineConfig::new(args.output_dir, args.project_root);
    config.host_project_root = args.host_project_root;
    config.host_output_dir = args.host_output_dir;
    config.latex_timeout = Duration::from_secs(args.latex_timeout_secs);
    config.manim_timeout = Duration::from_secs(args.manim_timeout_secs);
    config.max_concurrent_jobs = usize::try_from(args.max_concurrent_jobs).unwrap_or(2);

    let content_server = ContentCreationServer::new(config);

    let mut builder = MCPServer::builder(SERVER_NAME, SERVER_VERSION);
    builder = args.server.apply_to(builder);
    for tool in content_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;
    Ok(())
}
