//! MCP ElevenLabs Speech Server
//!
//! Provides MCP tools for ElevenLabs text-to-speech synthesis, including
//! voice synthesis, sound effects, and streaming audio.
//!
//! Usage:
//!     # Standalone mode (default)
//!     ELEVENLABS_API_KEY=your_key mcp-elevenlabs-speech --mode standalone --port 8018
//!
//!     # Test endpoints
//!     curl http://localhost:8018/health
//!     curl http://localhost:8018/mcp/tools

mod client;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::ElevenLabsSpeechServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-elevenlabs-speech")]
#[command(about = "MCP server for ElevenLabs text-to-speech synthesis")]
#[command(version = "2.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create ElevenLabs speech server
    let speech_server = ElevenLabsSpeechServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("elevenlabs-speech", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in speech_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
