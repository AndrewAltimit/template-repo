//! `md-link-checker`: fast concurrent markdown link validator.
//!
//! ```bash
//! md-link-checker .                          # Check all markdown files
//! md-link-checker docs/ --internal-only      # Only check internal links
//! md-link-checker README.md --json           # JSON output
//! md-link-checker . --ignore "localhost"     # Custom ignore pattern
//! md-link-checker . --skip-anchors           # Skip anchor validation
//! ```
//!
//! Exit codes: 0 all links valid, 1 broken links or unreadable files,
//! 2 usage or fatal error (bad arguments, invalid pattern, missing path).

use std::io::IsTerminal;
use std::path::PathBuf;
use std::process::ExitCode;
use std::time::Duration;

use anyhow::Result;
use clap::Parser;
use markdown_link_checker::discover::{DiscoverOptions, find_repo_root};
use markdown_link_checker::filters::{IgnoreRules, read_pattern_file};
use markdown_link_checker::http::HttpOptions;
use markdown_link_checker::{CheckOptions, check_paths};
use tracing::{Level, error, info};

/// Fast concurrent markdown link validator
#[derive(Parser, Debug)]
#[command(name = "md-link-checker")]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Markdown files or directories to check
    #[arg(default_value = ".")]
    paths: Vec<PathBuf>,

    /// Only check internal/local links (skip HTTP/HTTPS)
    #[arg(long)]
    internal_only: bool,

    /// Skip anchor/heading validation (same-page and cross-file)
    #[arg(long)]
    skip_anchors: bool,

    /// Patterns to ignore (regex, matched against the link as written)
    #[arg(long, short = 'i')]
    ignore: Vec<String>,

    /// File of ignore regexes, one per line ('#' comments allowed)
    #[arg(long, value_name = "FILE")]
    ignore_file: Vec<PathBuf>,

    /// Do not apply the built-in ignore patterns (localhost, private IPs, ...)
    #[arg(long)]
    no_default_ignores: bool,

    /// Skip files/directories matching this gitignore-style glob (repeatable)
    #[arg(long, short = 'e', value_name = "GLOB")]
    exclude: Vec<String>,

    /// Do not honor .gitignore / .mdlinkignore files when walking directories
    #[arg(long)]
    no_ignore_files: bool,

    /// Directory that '/absolute' links resolve against [default: git root]
    #[arg(long, value_name = "DIR")]
    root: Option<PathBuf>,

    /// Also report [text][label] references whose label is never defined
    /// (GitHub renders them as literal text)
    #[arg(long)]
    check_undefined_refs: bool,

    /// Timeout for HTTP requests in seconds
    #[arg(long, default_value = "10", value_parser = clap::value_parser!(u64).range(1..))]
    timeout: u64,

    /// Maximum concurrent HTTP checks
    #[arg(long, default_value = "10", value_parser = clap::value_parser!(u64).range(1..))]
    concurrent: u64,

    /// Maximum concurrent HTTP checks against a single host
    #[arg(long, default_value = "4", value_parser = clap::value_parser!(u64).range(1..))]
    per_host: u64,

    /// Retries for transient HTTP failures (timeouts, 429, 5xx)
    #[arg(long, default_value = "2")]
    max_retries: u32,

    /// Extra HTTP status codes to accept as valid (comma-separated, e.g. 403,429)
    #[arg(long, value_delimiter = ',', value_name = "CODES")]
    accept: Vec<u16>,

    /// Output results as JSON
    #[arg(long)]
    json: bool,

    /// Enable verbose logging
    #[arg(short, long)]
    verbose: bool,
}

impl Args {
    fn check_options(&self) -> Result<CheckOptions> {
        let mut patterns = self.ignore.clone();
        for file in &self.ignore_file {
            patterns.extend(read_pattern_file(file)?);
        }
        let root = match &self.root {
            Some(root) => root.clone(),
            None => find_repo_root(self.paths.first().map_or(".".as_ref(), |p| p.as_path())),
        };
        Ok(CheckOptions {
            check_external: !self.internal_only,
            validate_anchors: !self.skip_anchors,
            check_undefined_refs: self.check_undefined_refs,
            root,
            ignore: IgnoreRules::new(&patterns, !self.no_default_ignores)?,
            http: HttpOptions {
                timeout: Duration::from_secs(self.timeout),
                concurrency: usize::try_from(self.concurrent).unwrap_or(usize::MAX),
                per_host: usize::try_from(self.per_host).unwrap_or(usize::MAX),
                max_retries: self.max_retries,
                accept: self.accept.clone(),
                ..HttpOptions::default()
            },
            discover: DiscoverOptions {
                respect_ignore_files: !self.no_ignore_files,
                excludes: self.exclude.clone(),
            },
        })
    }
}

fn setup_logging(verbose: bool) {
    let level = if verbose { Level::DEBUG } else { Level::INFO };
    let subscriber = tracing_subscriber::fmt()
        .with_max_level(level)
        .with_target(false)
        .with_ansi(std::io::stderr().is_terminal())
        .with_writer(std::io::stderr)
        .finish();
    tracing::subscriber::set_global_default(subscriber).ok();
}

async fn run(args: &Args) -> Result<bool> {
    let options = args.check_options()?;
    let results = check_paths(&args.paths, &options).await?;

    if args.json {
        println!("{}", serde_json::to_string_pretty(&results)?);
    } else {
        results.write_human(&mut std::io::stdout().lock())?;
        if results.all_valid {
            info!("All links valid!");
        } else {
            error!(
                "Link check failed with {} broken link(s)",
                results.broken_links
            );
        }
    }
    Ok(results.all_valid)
}

#[tokio::main]
async fn main() -> ExitCode {
    let args = Args::parse();

    // Keep stdout clean for machine consumers in JSON mode.
    if !args.json {
        setup_logging(args.verbose);
    }

    match run(&args).await {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(1),
        Err(e) => {
            eprintln!("md-link-checker: error: {e:#}");
            ExitCode::from(2)
        },
    }
}
