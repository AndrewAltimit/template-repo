//! GitHub Projects v2 board manager CLI.
//!
//! Coordinates AI agent work on GitHub issues through a Projects v2 board:
//! ready-work queries, comment-based claims with conflict resolution,
//! status and dependency fields, approval checks and stale-claim cleanup.

mod approval;
mod board;
mod claims;
mod cli;
mod client;
mod config;
mod error;
mod manager;
mod models;
mod queries;
mod security;

use clap::Parser;

#[tokio::main]
async fn main() {
    let cli = cli::Cli::parse();

    if let Err(e) = cli::run(cli).await {
        eprintln!("Error: {}", e);
        std::process::exit(1);
    }
}
