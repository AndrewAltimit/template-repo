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
//!
//! # Architecture
//!
//! All validation operates directly on the argument vector rather than
//! reconstructing command strings. This provides robust validation that
//! cannot be bypassed through shell escaping tricks.
//!
//! # Special Flags
//!
//! - `--gh-validator-strip-invalid-images`: Instead of failing on invalid image
//!   URLs, strip them from the content and continue. Useful for CI pipelines.

use std::env;
use std::process::{exit, Command};

/// gh-validator specific flag for stripping invalid images instead of failing
const STRIP_INVALID_IMAGES_FLAG: &str = "--gh-validator-strip-invalid-images";

mod config;
mod error;
mod gh_finder;
mod validation;

use config::load_config;
use error::Error;
use validation::{CommentValidator, SecretMasker, UrlValidator};

/// Arguments that indicate we need to validate content
/// Includes both long and short flags from gh CLI
const CONTENT_ARGS: &[&str] = &[
    "--body",
    "-b", // short for --body
    "--body-file",
    "-F", // short for --body-file
    "--notes",
    "-n", // short for --notes
    "--notes-file",
    "--title",
    "-t", // short for --title
    "--message",
    "-m", // short for --message
];

/// Check if args contain any content-posting flags
fn needs_validation(args: &[String]) -> bool {
    args.iter().any(|arg| {
        CONTENT_ARGS.iter().any(|ca| {
            // Exact match (e.g., "--body")
            arg == *ca
                // Match with = value (e.g., "--body=content")
                || arg.starts_with(&format!("{}=", ca))
        })
    })
}

/// Extract --body-file/-F path from arguments
fn extract_body_file(args: &[String]) -> Option<String> {
    let mut iter = args.iter().peekable();
    while let Some(arg) = iter.next() {
        // Handle --body-file and -F (short form)
        if arg == "--body-file" || arg == "-F" {
            return iter.next().cloned();
        }
        if let Some(path) = arg.strip_prefix("--body-file=") {
            return Some(path.to_string());
        }
        // Handle -F=path form (rare but possible)
        if let Some(path) = arg.strip_prefix("-F=") {
            return Some(path.to_string());
        }
    }
    None
}

/// Check if --body-file/-F is reading from stdin (blocked for security)
fn is_stdin_body_file(args: &[String]) -> bool {
    let mut iter = args.iter().peekable();
    while let Some(arg) = iter.next() {
        // Handle --body-file and -F (short form)
        if arg == "--body-file" || arg == "-F" {
            if let Some(next) = iter.next() {
                if next == "-" {
                    return true;
                }
            }
        }
        // Handle combined forms
        if arg == "--body-file=-" || arg == "-F=-" || arg == "-F-" {
            return true;
        }
    }
    false
}

/// Check if strip-invalid-images flag is present and remove it from args
fn extract_strip_flag(args: &[String]) -> (Vec<String>, bool) {
    let has_flag = args.iter().any(|a| a == STRIP_INVALID_IMAGES_FLAG);
    let filtered: Vec<String> = args
        .iter()
        .filter(|a| *a != STRIP_INVALID_IMAGES_FLAG)
        .cloned()
        .collect();
    (filtered, has_flag)
}

/// Run validation and execute the real gh binary
fn run() -> Result<(), Error> {
    let raw_args: Vec<String> = env::args().skip(1).collect();

    // Extract gh-validator specific flags (not passed to real gh)
    let (args, strip_invalid_images) = extract_strip_flag(&raw_args);

    // Find real gh binary (skip ourselves)
    let real_gh = gh_finder::find_real_gh()?;

    // Fast path: if no content args (--body, --body-file, etc.), exec immediately
    // Note: We validate ANY command with content args, not just "pr comment"
    // This prevents bypasses like "gh pr --repo x comment --body secret"
    if !needs_validation(&args) {
        exec_gh(&real_gh, &args)?;
        unreachable!("exec should not return");
    }

    // Load config (fail-closed if missing)
    let config = load_config()?;

    // Initialize validators
    let masker = SecretMasker::new(&config);
    let url_validator = UrlValidator::default();

    // 1. Check for stdin usage (blocked for security) - check args directly
    if is_stdin_body_file(&args) {
        return Err(Error::StdinBlocked);
    }

    // 2. Mask secrets in individual arguments (avoids shell escaping issues)
    let (masked_args, was_masked) = masker.mask_args(&args);

    // 3. Check Unicode emojis in args (operates directly on arg vector)
    if CommentValidator::args_post_content(&masked_args) {
        if let Some(emoji) = CommentValidator::check_unicode_emoji_in_args(&masked_args) {
            return Err(Error::UnicodeEmoji {
                char: emoji,
                codepoint: emoji as u32,
            });
        }
    }

    // 4. Check formatting violations (operates directly on arg vector)
    // This catches --body/-b with reaction images (should use --body-file instead)
    if let Some(violation) = CommentValidator::check_formatting_violations_in_args(&masked_args) {
        return Err(Error::FormattingViolation {
            description: violation.to_string(),
        });
    }

    // 5. Validate URLs in --body-file (use original args for file path)
    if let Some(file_path) = extract_body_file(&args) {
        match std::fs::read_to_string(&file_path) {
            Ok(content) => {
                if strip_invalid_images {
                    // Strip mode: remove invalid images and continue
                    let (new_content, stripped) = url_validator.strip_invalid_images(&content);
                    if !stripped.is_empty() {
                        for (url, reason) in &stripped {
                            eprintln!(
                                "[gh-validator] WARNING: Stripped invalid image: {} ({})",
                                url, reason
                            );
                        }
                        // Write modified content back to the file
                        if let Err(e) = std::fs::write(&file_path, &new_content) {
                            return Err(Error::BodyFileRead {
                                path: file_path,
                                reason: format!("Failed to write modified content: {}", e),
                            });
                        }
                        eprintln!(
                            "[gh-validator] Removed {} invalid image(s), continuing with comment",
                            stripped.len()
                        );
                    }
                } else {
                    // Strict mode: fail on any invalid URL
                    let urls = UrlValidator::extract_reaction_urls(&content);
                    for url in urls {
                        url_validator.validate_exists(&url)?;
                    }
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

    // 6. Execute gh with masked arguments
    if was_masked {
        eprintln!("[gh-validator] Secrets were masked in command");
    }
    exec_gh(&real_gh, &masked_args)?;

    unreachable!("exec should not return");
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
