mod commands;
mod common;

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

    /// Detect backdoors in text using the loaded model
    Detect {
        /// Text to analyze for backdoor behavior
        text: String,

        /// Model to use for detection
        #[arg(long, short, default_value = "gpt2")]
        model: String,

        /// Use probe ensemble for detection
        #[arg(long)]
        ensemble: bool,

        /// Run causal interventions
        #[arg(long)]
        interventions: bool,

        /// Check attention patterns
        #[arg(long)]
        attention: bool,

        /// Force CPU mode
        #[arg(long)]
        cpu: bool,

        /// Output raw JSON
        #[arg(long)]
        json: bool,

        /// Path to the sleeper_agents package root
        #[arg(long, short)]
        package_root: Option<String>,
    },

    /// Evaluate a model with test suites
    Evaluate {
        /// Model name or HuggingFace model ID
        model: String,

        /// Test suites to run (default: all)
        #[arg(
            long,
            value_delimiter = ',',
            value_parser = ["basic", "code_vulnerability", "chain_of_thought", "robustness", "attention", "intervention"]
        )]
        suites: Vec<String>,

        /// Enable GPU mode
        #[arg(long)]
        gpu: bool,

        /// Override batch size
        #[arg(long)]
        batch_size: Option<u32>,

        /// Detection threshold (0.0-1.0)
        #[arg(long)]
        threshold: Option<f64>,

        /// Output directory for results
        #[arg(long, short)]
        output: Option<String>,

        /// Generate report after evaluation (html, pdf, json)
        #[arg(long)]
        report: Option<String>,

        /// Job timeout in seconds
        #[arg(long, default_value = "3600")]
        timeout: u64,

        /// Path to the sleeper_agents package root
        #[arg(long, short)]
        package_root: Option<String>,
    },

    /// Train models (backdoor, probes, safety)
    #[command(subcommand)]
    Train(commands::train::TrainAction),

    /// Manage orchestrator jobs
    #[command(subcommand)]
    Jobs(commands::jobs::JobsAction),

    /// Generate reports from evaluation results database
    Report {
        /// Filter by model name
        #[arg(long, short)]
        model: Option<String>,

        /// Output format: json or csv (default: human-readable)
        #[arg(long, short)]
        format: Option<String>,

        /// Output file or directory path
        #[arg(long, short)]
        output: Option<String>,

        /// Export a specific section: persistence, cot, honeypot, trigger, internal
        #[arg(long, short)]
        section: Option<String>,

        /// Path to the SQLite database file
        #[arg(long)]
        db_path: Option<String>,

        /// Path to the sleeper_agents package root
        #[arg(long)]
        package_root: Option<String>,
    },

    /// Submit multiple jobs from a JSON config file
    Batch {
        /// Path to the batch config JSON file
        config: String,

        /// Validate config without submitting jobs
        #[arg(long)]
        dry_run: bool,
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
        Commands::Detect {
            text,
            model,
            ensemble,
            interventions,
            attention,
            cpu,
            json,
            package_root,
        } => {
            commands::detect::run(commands::detect::DetectOpts {
                text: &text,
                model: &model,
                ensemble,
                interventions,
                attention,
                cpu,
                json_output: json,
                package_root: package_root.as_deref(),
            })
            .await
        },
        Commands::Evaluate {
            model,
            suites,
            gpu,
            batch_size,
            threshold,
            output,
            report,
            timeout,
            package_root,
        } => {
            commands::evaluate::run(commands::evaluate::EvalOpts {
                model: &model,
                suites: &suites,
                gpu,
                batch_size,
                threshold,
                output_dir: output.as_deref(),
                report_format: report.as_deref(),
                timeout_secs: timeout,
                package_root: package_root.as_deref(),
            })
            .await
        },
        Commands::Train(action) => commands::train::run(action).await,
        Commands::Jobs(action) => commands::jobs::run(action).await,
        Commands::Report {
            model,
            format,
            output,
            section,
            db_path,
            package_root,
        } => commands::report::run(commands::report::ReportOpts {
            model: model.as_deref(),
            format: format.as_deref(),
            output_path: output.as_deref(),
            section: section.as_deref(),
            db_path: db_path.as_deref(),
            package_root: package_root.as_deref(),
        }),
        Commands::Batch { config, dry_run } => commands::batch::run(&config, dry_run).await,
        Commands::Clean {
            containers,
            volumes,
            all,
            package_root,
        } => commands::clean::run(containers || all, volumes || all, package_root.as_deref()),
    }
}
