//! Claim verification for hallucination detection.
//!
//! Verifies that file paths and line numbers mentioned in reviews actually exist.

use regex::Regex;
use std::collections::HashSet;
use std::fs;
use std::path::Path;

/// Result of claim verification
#[derive(Debug)]
pub struct VerificationResult {
    /// Original review text
    pub original: String,
    /// Review with invalid claims removed or marked
    pub cleaned: String,
    /// List of invalid claims that were found
    pub invalid_claims: Vec<InvalidClaim>,
    /// Whether any claims were invalid
    pub had_invalid_claims: bool,
}

/// An invalid claim found in the review
#[derive(Debug, Clone)]
pub struct InvalidClaim {
    /// The file path mentioned
    pub file_path: String,
    /// The line number mentioned (if any)
    pub line_number: Option<usize>,
    /// Why the claim is invalid
    pub reason: String,
}

/// Verify claims in a review against actual files
pub fn verify_claims(review: &str, changed_files: &[String]) -> VerificationResult {
    let changed_set: HashSet<&str> = changed_files.iter().map(|s| s.as_str()).collect();
    let mut invalid_claims = Vec::new();
    let mut cleaned = review.to_string();

    // Pattern to match file:line references like `src/main.rs:42`
    let file_line_re = Regex::new(r"`([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+):(\d+)`").unwrap();

    // Pattern to match file references like `src/main.rs`
    let file_only_re = Regex::new(r"`([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)`").unwrap();

    // Collect all file:line claims
    for captures in file_line_re.captures_iter(review) {
        let file_path = captures.get(1).map(|m| m.as_str()).unwrap_or("");
        let line_num: usize = captures
            .get(2)
            .and_then(|m| m.as_str().parse().ok())
            .unwrap_or(0);

        // Check if file is in changed files
        if !changed_set.contains(file_path) && !changed_set.iter().any(|f| f.ends_with(file_path)) {
            // File not in PR - might be hallucinated
            if !Path::new(file_path).exists() {
                invalid_claims.push(InvalidClaim {
                    file_path: file_path.to_string(),
                    line_number: Some(line_num),
                    reason: "File does not exist and is not in PR".to_string(),
                });
                continue;
            }
        }

        // Verify line number if file exists
        if Path::new(file_path).exists() {
            if let Ok(content) = fs::read_to_string(file_path) {
                let line_count = content.lines().count();
                if line_num > line_count {
                    invalid_claims.push(InvalidClaim {
                        file_path: file_path.to_string(),
                        line_number: Some(line_num),
                        reason: format!("Line {} exceeds file length ({})", line_num, line_count),
                    });
                }
            }
        }
    }

    // Collect file-only claims (without line numbers)
    for captures in file_only_re.captures_iter(review) {
        let file_path = captures.get(1).map(|m| m.as_str()).unwrap_or("");

        // Skip if we already checked this file with a line number
        if invalid_claims.iter().any(|c| c.file_path == file_path) {
            continue;
        }

        // Skip common false positives
        if is_common_filename(file_path) {
            continue;
        }

        // Check if file is in changed files or exists
        if !changed_set.contains(file_path)
            && !changed_set.iter().any(|f| f.ends_with(file_path))
            && !Path::new(file_path).exists()
        {
            invalid_claims.push(InvalidClaim {
                file_path: file_path.to_string(),
                line_number: None,
                reason: "File does not exist and is not in PR".to_string(),
            });
        }
    }

    // Mark invalid claims in the review
    for claim in &invalid_claims {
        let pattern = if let Some(line) = claim.line_number {
            format!("`{}:{}`", claim.file_path, line)
        } else {
            format!("`{}`", claim.file_path)
        };

        let replacement = format!("{} [UNVERIFIED - {}]", pattern, claim.reason);
        cleaned = cleaned.replace(&pattern, &replacement);
    }

    let had_invalid_claims = !invalid_claims.is_empty();

    if had_invalid_claims {
        tracing::warn!("Found {} invalid claims in review", invalid_claims.len());
        for claim in &invalid_claims {
            tracing::debug!(
                "Invalid claim: {}:{:?} - {}",
                claim.file_path,
                claim.line_number,
                claim.reason
            );
        }
    }

    VerificationResult {
        original: review.to_string(),
        cleaned,
        invalid_claims,
        had_invalid_claims,
    }
}

/// Check if a filename is a common false positive (not a real file reference)
fn is_common_filename(path: &str) -> bool {
    let common = [
        "example.js",
        "example.ts",
        "example.py",
        "example.rs",
        "file.txt",
        "config.json",
        "package.json",
        "Cargo.toml",
        "README.md",
        ".env",
        ".gitignore",
    ];

    // Skip very short names that are likely code examples
    if path.len() < 5 {
        return true;
    }

    common.iter().any(|&c| path == c)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verify_valid_claims() {
        let review = "Found issue in `Cargo.toml`";
        let changed_files = vec!["Cargo.toml".to_string()];

        let result = verify_claims(review, &changed_files);
        assert!(!result.had_invalid_claims);
    }

    #[test]
    fn test_verify_invalid_file() {
        let review = "Found issue in `nonexistent/file.rs:42`";
        let changed_files = vec!["src/main.rs".to_string()];

        let result = verify_claims(review, &changed_files);
        assert!(result.had_invalid_claims);
        assert_eq!(result.invalid_claims.len(), 1);
        assert_eq!(result.invalid_claims[0].file_path, "nonexistent/file.rs");
    }

    #[test]
    fn test_common_filenames_ignored() {
        assert!(is_common_filename("example.js"));
        assert!(is_common_filename("a.rs"));
        assert!(!is_common_filename("src/main.rs"));
    }
}
