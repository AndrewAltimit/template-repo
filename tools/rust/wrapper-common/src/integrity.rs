//! Compile-time integrity verification
//!
//! Each wrapper binary embeds a SHA-256 hash of its source files via build.rs.
//! This module provides utilities for working with that hash:
//! - Printing it for external verification (--wrapper-integrity flag)
//! - Including it in audit log entries

/// Check if the first argument is the integrity check flag.
///
/// If so, print the source hash and return `true` (caller should exit 0).
/// Otherwise return `false` (normal execution continues).
///
/// # Arguments
/// * `args` - Command-line arguments (after skipping argv[0])
/// * `wrapper_name` - Name of the wrapper (e.g., "git-guard")
/// * `source_hash` - The compile-time embedded source hash
pub fn check_integrity_flag(args: &[String], wrapper_name: &str, source_hash: &str) -> bool {
    if args.first().map(|s| s.as_str()) == Some("--wrapper-integrity") {
        println!("wrapper={}", wrapper_name);
        println!("source_hash={}", source_hash);
        println!(
            "binary={}",
            std::env::current_exe()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_else(|_| "unknown".to_string())
        );
        true
    } else {
        false
    }
}

/// Validate that a source hash looks valid (64 hex chars for SHA-256)
pub fn is_valid_hash(hash: &str) -> bool {
    hash.len() == 64 && hash.chars().all(|c| c.is_ascii_hexdigit())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_check_integrity_flag_matches() {
        let args = vec!["--wrapper-integrity".to_string()];
        assert!(check_integrity_flag(&args, "test", "abc123"));
    }

    #[test]
    fn test_check_integrity_flag_no_match() {
        let args = vec!["status".to_string()];
        assert!(!check_integrity_flag(&args, "test", "abc123"));
    }

    #[test]
    fn test_check_integrity_flag_empty_args() {
        let args: Vec<String> = vec![];
        assert!(!check_integrity_flag(&args, "test", "abc123"));
    }

    #[test]
    fn test_is_valid_hash() {
        assert!(is_valid_hash(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ));
        assert!(!is_valid_hash("too_short"));
        assert!(!is_valid_hash(
            "g3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )); // 'g' is not hex
    }
}
