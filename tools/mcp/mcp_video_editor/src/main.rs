//! MCP Video Editor Server
//!
//! Automated video editing over MCP: ffprobe media info, audio loudness and
//! silence analysis, Whisper transcription, scene detection, multi-camera
//! speaker switching, EDL generation, ffmpeg rendering with transitions,
//! clip extraction and captioning.
//!
//! Usage:
//!     # STDIO mode (Claude Code / MCP clients)
//!     mcp-video-editor --mode stdio
//!
//!     # Standalone HTTP mode
//!     mcp-video-editor --mode standalone --port 8019
//!     curl http://localhost:8019/health
//!     curl http://localhost:8019/mcp/tools

mod audio;
mod captions;
mod config;
mod edl;
mod ffmpeg;
mod jobs;
mod process;
mod server;
mod types;
mod video;

#[cfg(test)]
mod integration_tests;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use config::ServerConfig;
use server::VideoEditorServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-video-editor")]
#[command(about = "MCP server for automated video editing (ffmpeg + Whisper)")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let config = ServerConfig::from_env();
    tracing::info!(
        "Output dir: {}, cache dir: {}, temp dir: {}",
        config.output_dir.display(),
        config.cache_dir.display(),
        config.temp_dir.display()
    );
    if which::which("ffmpeg").is_err() || which::which("ffprobe").is_err() {
        tracing::warn!("ffmpeg/ffprobe not found in PATH; media tools will fail until installed");
    }

    let video_server = VideoEditorServer::new(config);
    let mut builder = MCPServer::builder("video-editor", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in video_server.tools() {
        builder = builder.tool_boxed(tool);
    }
    builder.build().run().await?;
    Ok(())
}
