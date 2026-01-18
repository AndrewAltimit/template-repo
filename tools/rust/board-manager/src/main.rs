//! GitHub Projects v2 board manager CLI.
//!
//! A Rust implementation of the board manager for coordinating AI agent work
//! on GitHub issues via Projects v2 GraphQL API.

mod cli;
mod client;
mod config;
mod error;
mod manager;
mod models;

use clap::Parser;

#[tokio::main]
async fn main() {
    let cli = cli::Cli::parse();

    if let Err(e) = cli::run(cli).await {
        eprintln!("Error: {}", e);
        std::process::exit(1);
    }
}
