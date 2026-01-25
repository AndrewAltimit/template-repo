//! Economic Agents CLI.

use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use clap::{Parser, Subcommand};
use tracing::info;

use economic_agents_cli::{run_agent, run_scenario, AgentFileConfig, Scenario};
use economic_agents_dashboard::{DashboardConfig, DashboardService, DashboardState};

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
        /// Configuration file path (YAML)
        #[arg(short, long)]
        config: Option<PathBuf>,

        /// Maximum number of cycles
        #[arg(short = 'n', long)]
        max_cycles: Option<u32>,

        /// Use mock backends (always true for now)
        #[arg(long, default_value = "true")]
        mock: bool,

        /// Keep cycle history in output
        #[arg(long)]
        keep_cycles: bool,

        /// Output format (text, json)
        #[arg(short, long, default_value = "text")]
        output: String,
    },

    /// Start the dashboard server
    Dashboard {
        /// Port to listen on
        #[arg(short, long, default_value = "8000")]
        port: u16,

        /// Host to bind to
        #[arg(long, default_value = "0.0.0.0")]
        host: String,

        /// Disable CORS
        #[arg(long)]
        no_cors: bool,

        /// Disable request tracing
        #[arg(long)]
        no_tracing: bool,
    },

    /// Run a predefined scenario
    Scenario {
        /// Scenario name
        name: String,

        /// Keep cycle history in output
        #[arg(long)]
        keep_cycles: bool,

        /// Output format (text, json)
        #[arg(short, long, default_value = "text")]
        output: String,
    },

    /// List available scenarios
    ListScenarios,

    /// Show agent status (placeholder)
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
            mock: _,
            keep_cycles,
            output,
        } => {
            // Load config from file or use defaults
            let mut agent_config = if let Some(path) = config {
                AgentFileConfig::from_file(&path)?
            } else {
                AgentFileConfig::default()
            };

            // Override max_cycles if specified
            if let Some(cycles) = max_cycles {
                agent_config.max_cycles = Some(cycles);
            }

            info!(
                agent_id = ?agent_config.agent_id,
                max_cycles = ?agent_config.max_cycles,
                mode = ?agent_config.mode,
                "Starting agent"
            );

            let result = run_agent(agent_config, None, keep_cycles).await?;

            match output.as_str() {
                "json" => {
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&serde_json::json!({
                            "agent_id": result.agent_id,
                            "cycles_executed": result.cycles_executed,
                            "tasks_completed": result.tasks_completed,
                            "tasks_failed": result.tasks_failed,
                            "success_rate": result.success_rate(),
                            "final_balance": result.final_balance,
                            "total_earnings": result.total_earnings,
                            "total_expenses": result.total_expenses,
                            "net_profit": result.net_profit(),
                            "has_company": result.has_company,
                            "duration_ms": result.duration_ms,
                        }))?
                    );
                }
                _ => {
                    println!("\n=== Agent Run Complete ===");
                    println!("Agent: {}", result.agent_id);
                    println!("Cycles: {}", result.cycles_executed);
                    println!(
                        "Tasks: {} completed, {} failed ({:.1}% success)",
                        result.tasks_completed,
                        result.tasks_failed,
                        result.success_rate() * 100.0
                    );
                    println!("Final balance: ${:.2}", result.final_balance);
                    println!("Net profit: ${:.2}", result.net_profit());
                    println!("Has company: {}", result.has_company);
                    println!("Duration: {}ms", result.duration_ms);
                }
            }
        }

        Commands::Dashboard {
            port,
            host,
            no_cors,
            no_tracing,
        } => {
            let config = DashboardConfig {
                port,
                host: host.clone(),
                enable_cors: !no_cors,
                enable_tracing: !no_tracing,
            };

            let state = Arc::new(DashboardState::new());
            let service = DashboardService::new(config.clone(), Arc::clone(&state));
            let router = service.build_router();

            let addr: SocketAddr = format!("{}:{}", host, port).parse()?;
            info!(address = %addr, "Starting dashboard server");
            println!("Dashboard running at http://{}", addr);

            let listener = tokio::net::TcpListener::bind(addr).await?;
            axum::serve(listener, router).await?;
        }

        Commands::Scenario {
            name,
            keep_cycles,
            output,
        } => {
            let scenario = Scenario::by_name(&name).ok_or_else(|| {
                anyhow::anyhow!(
                    "Unknown scenario: '{}'. Use 'list-scenarios' to see available scenarios.",
                    name
                )
            })?;

            info!(
                name = %scenario.name,
                agents = %scenario.agents.len(),
                parallel = %scenario.parallel,
                "Running scenario"
            );

            let result = run_scenario(scenario, keep_cycles).await?;

            match output.as_str() {
                "json" => {
                    let agents_json: Vec<_> = result
                        .agent_results
                        .iter()
                        .map(|r| {
                            serde_json::json!({
                                "agent_id": r.agent_id,
                                "cycles_executed": r.cycles_executed,
                                "tasks_completed": r.tasks_completed,
                                "tasks_failed": r.tasks_failed,
                                "success_rate": r.success_rate(),
                                "final_balance": r.final_balance,
                                "net_profit": r.net_profit(),
                                "has_company": r.has_company,
                                "duration_ms": r.duration_ms,
                            })
                        })
                        .collect();

                    println!(
                        "{}",
                        serde_json::to_string_pretty(&serde_json::json!({
                            "scenario": result.name,
                            "duration_ms": result.duration_ms,
                            "agents": agents_json,
                            "best_performer": result.best_performer().map(|b| &b.agent_id),
                        }))?
                    );
                }
                _ => {
                    result.print_summary();
                }
            }
        }

        Commands::ListScenarios => {
            println!("\nAvailable Scenarios:");
            println!("====================\n");
            for (name, description) in Scenario::list_all() {
                println!("  {:<20} - {}", name, description);
            }
            println!(
                "\nUsage: economic-agents scenario <name>\n"
            );
        }

        Commands::Status => {
            println!("Status display not yet implemented");
            println!("Use 'dashboard' command to start the web interface");
        }
    }

    Ok(())
}
