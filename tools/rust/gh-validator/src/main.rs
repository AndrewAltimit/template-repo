//! gh-validator: GitHub CLI wrapper for comment validation and secret masking
//!
//! This binary intercepts `gh` commands and performs validation before
//! delegating to the real `gh` binary.
//!
//! # Usage
//!
//! Install this binary as `gh` in a higher-priority PATH directory.
//! It will automatically find and call the real `gh` binary.
//!
//! # Validation
//!
//! - Secret masking: Detects and masks secrets in comment content
//! - Unicode emoji detection: Blocks emojis that may display incorrectly
//! - Formatting validation: Ensures proper use of --body-file for reaction images
//! - URL validation: Verifies reaction image URLs exist (with SSRF protection)

use std::env;
use std::process::{exit, Command};

mod config;
mod error;
mod gh_finder;
mod validation;

use config::load_config;
use error::Error;
use validation::{CommentValidator, SecretMasker, UrlValidator};

/// Arguments that indicate we need to validate content
const CONTENT_ARGS: &[&str] = &[
    "--body",
    "--body-file",
    "--notes",
    "--notes-file",
    "--title",
    "--message",
    "-m",
];

/// Check if args contain any content-posting flags
fn needs_validation(args: &[String]) -> bool {
    args.iter()
        .any(|arg| CONTENT_ARGS.iter().any(|ca| arg.starts_with(ca)))
}

/// Check if this is a gh comment/create command
fn is_comment_command(args: &[String]) -> bool {
    let joined = args.join(" ").to_lowercase();
    [
        "pr comment",
        "issue comment",
        "pr create",
        "issue create",
        "pr review",
    ]
    .iter()
    .any(|pattern| joined.contains(pattern))
}

/// Extract --body-file path from arguments
fn extract_body_file(args: &[String]) -> Option<String> {
    let mut iter = args.iter().peekable();
    while let Some(arg) = iter.next() {
        if arg == "--body-file" {
            return iter.next().cloned();
        }
        if let Some(path) = arg.strip_prefix("--body-file=") {
            return Some(path.to_string());
        }
    }
    None
}

/// Build command string for validation (for logging/display)
fn build_command_string(args: &[String]) -> String {
    format!("gh {}", args.join(" "))
}

/// Run validation and execute the real gh binary
fn run() -> Result<(), Error> {
    let args: Vec<String> = env::args().skip(1).collect();

    // Find real gh binary (skip ourselves)
    let real_gh = gh_finder::find_real_gh()?;

    // Fast path: if no validation needed, exec immediately
    if !needs_validation(&args) || !is_comment_command(&args) {
        exec_gh(&real_gh, &args)?;
        unreachable!("exec should not return");
    }

    // Load config (fail-closed if missing)
    let config = load_config()?;

    // Build command string for validation
    let command = build_command_string(&args);

    // Initialize validators
    let masker = SecretMasker::new(&config);
    let url_validator = UrlValidator::default();

    // 1. Check for stdin usage (blocked for security)
    if command.contains("--body-file -") || command.contains("--body-file=-") {
        return Err(Error::StdinBlocked);
    }

    // 2. Mask secrets in command
    let (masked_command, was_masked) = masker.mask(&command);

    // 3. Check Unicode emojis
    if CommentValidator::is_posting_content(&masked_command) {
        if let Some(emoji) = CommentValidator::check_unicode_emoji(&masked_command) {
            return Err(Error::UnicodeEmoji {
                char: emoji,
                codepoint: emoji as u32,
            });
        }
    }

    // 4. Check formatting violations (only if has reaction images)
    if CommentValidator::has_reaction_image(&masked_command) {
        let violations = CommentValidator::check_formatting_violations(&masked_command);
        if !violations.is_empty() {
            return Err(Error::FormattingViolation {
                description: violations.join(", "),
            });
        }
    }

    // 5. Validate URLs in --body-file
    if let Some(file_path) = extract_body_file(&args) {
        match std::fs::read_to_string(&file_path) {
            Ok(content) => {
                let urls = UrlValidator::extract_reaction_urls(&content);
                for url in urls {
                    url_validator.validate_exists(&url)?;
                }
            }
            Err(e) => {
                // Only error if the file is supposed to exist
                // (might be created by a previous command in a pipeline)
                if std::path::Path::new(&file_path).exists() {
                    return Err(Error::BodyFileRead {
                        path: file_path,
                        reason: e.to_string(),
                    });
                }
            }
        }
    }

    // 6. Execute gh with potentially masked arguments
    if was_masked {
        eprintln!("[gh-validator] Secrets were masked in command");

        // Parse masked command back to args
        let masked_args = parse_masked_command(&masked_command)?;
        exec_gh(&real_gh, &masked_args)?;
    } else {
        exec_gh(&real_gh, &args)?;
    }

    unreachable!("exec should not return");
}

/// Parse masked command string back to arguments
fn parse_masked_command(command: &str) -> Result<Vec<String>, Error> {
    // Strip the "gh " prefix
    let args_str = command.strip_prefix("gh ").unwrap_or(command);

    shell_words::split(args_str).map_err(|_| Error::ArgParse)
}

/// Execute the real gh binary (replaces current process on Unix)
#[cfg(unix)]
fn exec_gh(gh_path: &std::path::Path, args: &[String]) -> Result<(), Error> {
    use std::os::unix::process::CommandExt;

    let err = Command::new(gh_path).args(args).exec();

    // exec() only returns on error
    Err(Error::ExecFailed(err))
}

/// Execute the real gh binary (Windows doesn't have exec, use spawn)
#[cfg(windows)]
fn exec_gh(gh_path: &std::path::Path, args: &[String]) -> Result<(), Error> {
    let status = Command::new(gh_path)
        .args(args)
        .status()
        .map_err(Error::ExecFailed)?;

    std::process::exit(status.code().unwrap_or(1));
}

fn main() {
    if let Err(e) = run() {
        eprintln!("ERROR: {}", e);

        // Print help text if available
        if let Some(help) = e.help_text() {
            eprintln!();
            eprintln!("{}", help);
        }

        exit(1);
    }
}
