//! Code Review Processor
//!
//! CLI tool to process code review JSON output from AgentCore.
//! Supports posting comments, committing changes, and creating PRs.

mod cli;
mod git;
mod github;
mod processor;

use anyhow::Result;
use clap::Parser;
use tracing::{error, info};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

use cli::Args;
use processor::ReviewProcessor;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::registry()
        .with(fmt::layer())
        .with(EnvFilter::from_default_env().add_directive("code_review_processor=info".parse()?))
        .init();

    let args = Args::parse();

    info!(
        input = %args.input,
        post_comment = args.post_comment,
        commit_changes = args.commit_changes,
        create_pr = args.create_pr,
        dry_run = args.dry_run,
        "Starting code review processor"
    );

    // Read input JSON
    let json_content = if args.input == "-" {
        use std::io::Read;
        let mut buffer = String::new();
        std::io::stdin().read_to_string(&mut buffer)?;
        buffer
    } else {
        std::fs::read_to_string(&args.input)?
    };

    // Parse JSON (supports both new schema format and legacy tagged format)
    let review = processor::parse_review_json(&json_content).map_err(|e| {
        error!(error = %e, "Failed to parse review JSON");
        e
    })?;

    // Create processor
    let processor = ReviewProcessor::new(args.repository.clone(), args.dry_run);

    // Process the review
    let result = processor.process(&review, &args).await?;

    // Output result
    match result {
        processor::ProcessingResult::ReviewPosted => {
            info!("Review posted as comment");
        },
        processor::ProcessingResult::ChangesCommitted => {
            info!("Changes committed successfully");
        },
        processor::ProcessingResult::PrCreated { pr_number, pr_url } => {
            info!(pr_number, pr_url = %pr_url, "Pull request created");
            println!("{}", pr_url);
        },
        processor::ProcessingResult::NoAction => {
            info!("No action taken (no flags specified)");
        },
    }

    Ok(())
}
