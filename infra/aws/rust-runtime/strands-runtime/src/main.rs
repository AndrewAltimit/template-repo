//! Strands Runtime - Main entry point
//!
//! HTTP server implementing the AWS AgentCore protocol for running
//! Strands agents in production.

use strands_runtime::Server;
use tracing::error;

#[tokio::main]
async fn main() {
    // Create and run server
    let server = Server::from_env();

    if let Err(e) = server.run().await {
        error!(error = %e, "Server failed");
        std::process::exit(1);
    }
}
