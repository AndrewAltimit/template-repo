//! Claim verification for hallucination detection.
//!
//! Verifies that file paths and line numbers mentioned in reviews actually
//! exist. Only repository-relative paths are ever touched on disk: absolute
//! paths and `..` traversal are treated as unverifiable, so model output
//! cannot make the reviewer probe (and leak line counts of) arbitrary files.

use std::collections::HashSet;
use std::fs;
use std::path::{Component, Path};
use std::sync::LazyLock;

use regex::Regex;

/// Pattern to match file:line references like `src/main.rs:42`
static FILE_LINE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"`([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+):(\d+)`").expect("valid file:line regex")
});

/// Pattern to match file references like `src/main.rs`
static FILE_ONLY_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"`([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)`").expect("valid file regex"));

/// Result of claim verification
#[derive(Debug)]
pub struct VerificationResult {
    /// Review with invalid claims marked
    pub cleaned: String,
    /// List of invalid claims that were found (deduplicated)
    pub invalid_claims: Vec<InvalidClaim>,
    /// Whether any claims were invalid
    pub had_invalid_claims: bool,
}

/// An invalid claim found in the review
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InvalidClaim {
    /// The file path mentioned
    pub file_path: String,
    /// The line number mentioned (if any)
    pub line_number: Option<usize>,
    /// Why the claim is invalid
    pub reason: String,
}

/// Whether `path` is a safe repository-relative path.
fn is_repo_relative(path: &str) -> bool {
    let p = Path::new(path);
    !p.is_absolute()
        && p.components()
            .all(|c| matches!(c, Component::Normal(_) | Component::CurDir))
}

/// Whether `path` names a file changed in the PR (exact or path-suffix match).
fn in_changed_set(path: &str, changed: &HashSet<&str>) -> bool {
    let trimmed = path.trim_start_matches("./");
    changed.contains(trimmed)
        || changed
            .iter()
            .any(|f| f.ends_with(&format!("/{}", trimmed)))
}

/// Whether the file exists locally (repository-relative paths only).
fn exists_locally(path: &str) -> bool {
    is_repo_relative(path) && Path::new(path).is_file()
}

/// Verify claims in a review against actual files
pub fn verify_claims(review: &str, changed_files: &[String]) -> VerificationResult {
    let changed_set: HashSet<&str> = changed_files.iter().map(|s| s.as_str()).collect();
    let mut invalid_claims: Vec<InvalidClaim> = Vec::new();
    let mut checked_files: HashSet<String> = HashSet::new();

    fn push(claim: InvalidClaim, claims: &mut Vec<InvalidClaim>) {
        if !claims.contains(&claim) {
            claims.push(claim);
        }
    }

    for captures in FILE_LINE_RE.captures_iter(review) {
        let file_path = &captures[1];
        let line_num: usize = captures[2].parse().unwrap_or(0);
        checked_files.insert(file_path.to_string());

        if !in_changed_set(file_path, &changed_set) && !exists_locally(file_path) {
            push(
                InvalidClaim {
                    file_path: file_path.to_string(),
                    line_number: Some(line_num),
                    reason: "File does not exist and is not in PR".to_string(),
                },
                &mut invalid_claims,
            );
            continue;
        }

        if exists_locally(file_path)
            && let Ok(content) = fs::read_to_string(file_path)
        {
            let line_count = content.lines().count();
            if line_num == 0 || line_num > line_count {
                push(
                    InvalidClaim {
                        file_path: file_path.to_string(),
                        line_number: Some(line_num),
                        reason: format!("Line {} exceeds file length ({})", line_num, line_count),
                    },
                    &mut invalid_claims,
                );
            }
        }
    }

    for captures in FILE_ONLY_RE.captures_iter(review) {
        let file_path = &captures[1];
        if checked_files.contains(file_path) || is_common_filename(file_path) {
            continue;
        }
        if !in_changed_set(file_path, &changed_set) && !exists_locally(file_path) {
            push(
                InvalidClaim {
                    file_path: file_path.to_string(),
                    line_number: None,
                    reason: "File does not exist and is not in PR".to_string(),
                },
                &mut invalid_claims,
            );
        }
    }

    // Mark invalid claims in the review (each distinct claim exactly once)
    let mut cleaned = review.to_string();
    for claim in &invalid_claims {
        let pattern = match claim.line_number {
            Some(line) => format!("`{}:{}`", claim.file_path, line),
            None => format!("`{}`", claim.file_path),
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
        cleaned,
        invalid_claims,
        had_invalid_claims,
    }
}

/// Check if a filename is a common false positive (not a real file reference)
fn is_common_filename(path: &str) -> bool {
    const COMMON: &[&str] = &[
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

    // Very short names are likely code examples
    path.len() < 5 || COMMON.contains(&path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verify_valid_claims() {
        let result = verify_claims("Found issue in `Cargo.toml`", &["Cargo.toml".to_string()]);
        assert!(!result.had_invalid_claims);
    }

    #[test]
    fn test_verify_invalid_file() {
        let review = "Found issue in `nonexistent/file.rs:42`";
        let result = verify_claims(review, &["src/main.rs".to_string()]);
        assert!(result.had_invalid_claims);
        assert_eq!(result.invalid_claims.len(), 1);
        assert_eq!(result.invalid_claims[0].file_path, "nonexistent/file.rs");
    }

    #[test]
    fn test_duplicate_claims_marked_once() {
        let review = "`missing/a.rs:1` and again `missing/a.rs:1`";
        let result = verify_claims(review, &[]);
        assert_eq!(result.invalid_claims.len(), 1);
        assert_eq!(result.cleaned.matches("[UNVERIFIED").count(), 2);
        assert!(
            !result
                .cleaned
                .contains("[UNVERIFIED - File does not exist and is not in PR] [UNVERIFIED")
        );
    }

    #[test]
    fn test_changed_file_suffix_match_requires_path_boundary() {
        let changed = ["src/domain.rs".to_string()];
        let set: HashSet<&str> = changed.iter().map(|s| s.as_str()).collect();
        assert!(in_changed_set("domain.rs", &set));
        assert!(!in_changed_set("main.rs", &set));
        assert!(in_changed_set("./src/domain.rs", &set));
    }

    #[test]
    fn test_path_traversal_never_read() {
        assert!(!is_repo_relative("/etc/passwd"));
        assert!(!is_repo_relative("../../etc/passwd"));
        assert!(!is_repo_relative("src/../../x.rs"));
        assert!(is_repo_relative("src/main.rs"));
        assert!(is_repo_relative("./src/main.rs"));
        let result = verify_claims("see `/etc/passwd.txt:1`", &[]);
        assert!(result.had_invalid_claims);
    }

    #[test]
    fn test_common_filenames_ignored() {
        assert!(is_common_filename("example.js"));
        assert!(is_common_filename("a.rs"));
        assert!(!is_common_filename("src/main.rs"));
    }
}
