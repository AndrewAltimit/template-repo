//! Economic Agents CLI.

use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "economic-agents")]
#[command(about = "Autonomous economic agent simulation framework")]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run an agent simulation
    Run {
        /// Configuration file path
        #[arg(short, long)]
        config: Option<String>,

        /// Maximum number of cycles
        #[arg(short = 'n', long)]
        max_cycles: Option<u32>,

        /// Use mock backends
        #[arg(long, default_value = "true")]
        mock: bool,
    },

    /// Start the dashboard server
    Dashboard {
        /// Port to listen on
        #[arg(short, long, default_value = "8000")]
        port: u16,
    },

    /// Run a predefined scenario
    Scenario {
        /// Scenario name
        name: String,
    },

    /// Show agent status
    Status,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Run {
            config,
            max_cycles,
            mock,
        } => {
            tracing::info!(
                config = ?config,
                max_cycles = ?max_cycles,
                mock = mock,
                "Starting agent"
            );
            // TODO: Implement agent run
            println!("Agent simulation not yet implemented");
        }

        Commands::Dashboard { port } => {
            tracing::info!(port, "Starting dashboard");
            // TODO: Implement dashboard server
            println!("Dashboard server not yet implemented (port {})", port);
        }

        Commands::Scenario { name } => {
            tracing::info!(name = %name, "Running scenario");
            // TODO: Implement scenario runner
            println!("Scenario runner not yet implemented: {}", name);
        }

        Commands::Status => {
            // TODO: Implement status display
            println!("Status display not yet implemented");
        }
    }

    Ok(())
}
