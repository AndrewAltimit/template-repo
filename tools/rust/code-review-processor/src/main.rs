//! Code Review Processor CLI entry point.
//!
//! stdout carries only the result (the PR URL in text mode, a JSON summary in
//! JSON mode); all logs go to stderr. See [`code_review_processor::exit_code`].

use std::io::{IsTerminal, Read};
use std::process::ExitCode;

use anyhow::{Context, Result, bail};
use clap::Parser;
use tracing::{error, info, warn};
use tracing_subscriber::EnvFilter;

use code_review_processor::cli::{Args, OutputFormat};
use code_review_processor::exit_code;
use code_review_processor::processor::{ReviewProcessor, Summary};
use code_review_processor::review;

/// Refuse inputs larger than this; real responses are a few hundred KiB.
const MAX_INPUT_BYTES: u64 = 64 * 1024 * 1024;

fn main() -> ExitCode {
    init_logging();
    let args = Args::parse();

    match run(&args) {
        Ok(summary) if summary.threshold_exceeded => {
            warn!(
                severity = %summary.severity,
                threshold = ?summary.severity_threshold,
                "Review severity meets --fail-on-severity threshold"
            );
            ExitCode::from(exit_code::SEVERITY_THRESHOLD)
        },
        Ok(_) => ExitCode::from(exit_code::SUCCESS),
        Err(e) => {
            error!("{e:#}");
            ExitCode::from(exit_code::ERROR)
        },
    }
}

fn init_logging() {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("code_review_processor=info"));
    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_writer(std::io::stderr)
        .with_ansi(std::io::stderr().is_terminal())
        .init();
}

fn run(args: &Args) -> Result<Summary> {
    info!(
        input = %args.input,
        post_comment = args.post_comment,
        commit_changes = args.commit_changes,
        create_pr = args.create_pr,
        dry_run = args.dry_run,
        "Starting code review processor"
    );

    let content = read_input(&args.input)?;
    let review = review::parse_review_json(&content)?;
    info!(
        severity = %review.severity,
        findings = review.findings_count,
        file_changes = review.file_changes.len(),
        "Parsed review"
    );

    let summary = ReviewProcessor::new(args.dry_run).process(&review, args)?;
    write_output(args.output_format, &summary)?;
    Ok(summary)
}

fn read_input(input: &str) -> Result<String> {
    let mut bytes = Vec::new();
    if input == "-" {
        let stdin = std::io::stdin();
        if stdin.is_terminal() {
            bail!("No input: pass --input <FILE> or pipe the review JSON on stdin");
        }
        stdin
            .lock()
            .take(MAX_INPUT_BYTES + 1)
            .read_to_end(&mut bytes)
            .context("Failed to read review JSON from stdin")?;
    } else {
        std::fs::File::open(input)
            .and_then(|f| f.take(MAX_INPUT_BYTES + 1).read_to_end(&mut bytes))
            .with_context(|| format!("Failed to read review JSON from {input}"))?;
    }
    if bytes.len() as u64 > MAX_INPUT_BYTES {
        bail!("Input exceeds {} MiB", MAX_INPUT_BYTES / (1024 * 1024));
    }
    String::from_utf8(bytes).context("Review JSON is not valid UTF-8")
}

fn write_output(format: OutputFormat, summary: &Summary) -> Result<()> {
    match format {
        OutputFormat::Text => {
            if let Some(url) = &summary.pr_url {
                println!("{url}");
            }
        },
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(summary)?);
        },
    }
    Ok(())
}
