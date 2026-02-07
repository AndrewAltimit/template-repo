use clap::{Parser, Subcommand};

mod commands;
mod shared;

#[derive(Parser)]
#[command(
    name = "automation-cli",
    about = "Unified CLI for CI/CD orchestration, service launching, and automation",
    version,
    propagate_version = true
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run CI/CD pipeline stages (format, lint, test, build)
    Ci {
        #[command(subcommand)]
        action: commands::ci::CiAction,
    },
    /// Run lint stages with error counting
    Lint {
        #[command(subcommand)]
        action: commands::ci::lint::LintAction,
    },
    /// Handle AI code reviews and CI failures
    Review {
        #[command(subcommand)]
        action: commands::review::ReviewAction,
    },
    /// Wait for a service to become available
    Wait(commands::wait::WaitArgs),
    /// Launch Docker services with health checking
    Launch(commands::launch::LaunchArgs),
    /// Manage remote AI services
    Service {
        #[command(subcommand)]
        action: commands::service::ServiceAction,
    },
    /// Setup runner, permissions, and prerequisites
    Setup {
        #[command(subcommand)]
        action: commands::setup::SetupAction,
    },
    /// Run corporate proxy tests
    Proxy {
        #[command(subcommand)]
        action: commands::proxy::ProxyAction,
    },
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Ci { action } => commands::ci::run(action),
        Commands::Lint { action } => commands::ci::lint::run(action),
        Commands::Review { action } => commands::review::run(action),
        Commands::Wait(args) => commands::wait::run(args),
        Commands::Launch(args) => commands::launch::run(args),
        Commands::Service { action } => commands::service::run(action),
        Commands::Setup { action } => commands::setup::run(action),
        Commands::Proxy { action } => commands::proxy::run(action),
    }
}
