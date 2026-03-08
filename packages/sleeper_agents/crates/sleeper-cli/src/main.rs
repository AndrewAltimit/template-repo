mod commands;

use anyhow::Result;
use clap::{Parser, Subcommand};
use tracing_subscriber::EnvFilter;

#[derive(Parser)]
#[command(
    name = "sleeper-cli",
    about = "Rust CLI for sleeper agent detection -- orchestrates the Python ML core",
    version
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    /// Log level (trace, debug, info, warn, error)
    #[arg(long, default_value = "warn", global = true)]
    log_level: String,
}

#[derive(Subcommand)]
enum Commands {
    /// Show system status (container, GPU, API, database)
    Status {
        /// Path to the sleeper_agents package root
        #[arg(long, short)]
        package_root: Option<String>,

        /// Output as JSON
        #[arg(long)]
        json: bool,
    },

    /// Clean up containers, volumes, and/or results
    Clean {
        /// Remove stopped containers and dangling images
        #[arg(long)]
        containers: bool,

        /// Remove named Docker volumes (model cache, results, GPU cache)
        #[arg(long)]
        volumes: bool,

        /// Remove everything (containers + volumes)
        #[arg(long)]
        all: bool,

        /// Path to the sleeper_agents package root
        #[arg(long, short)]
        package_root: Option<String>,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(&cli.log_level)),
        )
        .with_target(false)
        .init();

    match cli.command {
        Commands::Status { package_root, json } => {
            commands::status::run(package_root.as_deref(), json).await
        },
        Commands::Clean {
            containers,
            volumes,
            all,
            package_root,
        } => commands::clean::run(containers || all, volumes || all, package_root.as_deref()),
    }
}
