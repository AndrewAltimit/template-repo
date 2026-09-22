//! Commit-level validation for PR approvals.
//!
//! Threat model: an attacker opens an innocent PR, waits for an admin to post
//! `[Approved][Agent]`, then pushes malicious commits before (or while) the
//! agent works on the branch. Defenses implemented here:
//!
//! 1. **Approval freshness**: the head commit must not be newer than the
//!    approval comment. Commit dates are client-supplied, so this catches
//!    ordinary pushes but not deliberately back-dated commits; stages 2 and 3
//!    are server-authoritative.
//! 2. **Pre-execution pin**: the head SHA observed when the trigger was
//!    discovered must still be the head SHA right before the agent starts.
//! 3. **Pre-publish pin**: the head SHA must be unchanged after the agent
//!    finishes; otherwise all agent output is discarded.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tracing::debug;

use crate::error::Error;
use crate::utils::run_gh_command;

/// Minimum length accepted for an abbreviated SHA.
pub const MIN_SHA_LEN: usize = 7;

/// Whether `s` is a plausible (abbreviated or full) git SHA: 7-64 hex chars.
///
/// Also used to reject option-like values (`--output=...`) before they are
/// passed to git.
pub fn is_valid_sha(s: &str) -> bool {
    (MIN_SHA_LEN..=64).contains(&s.len()) && s.chars().all(|c| c.is_ascii_hexdigit())
}

/// Whether `expected` (possibly abbreviated) identifies `actual`.
///
/// Both must be valid SHAs; comparison is case-insensitive prefix matching.
pub fn sha_matches(expected: &str, actual: &str) -> bool {
    if !is_valid_sha(expected) || !is_valid_sha(actual) {
        return false;
    }
    let expected = expected.to_ascii_lowercase();
    let actual = actual.to_ascii_lowercase();
    if expected.len() <= actual.len() {
        actual.starts_with(&expected)
    } else {
        expected.starts_with(&actual)
    }
}

/// Current head state of a pull request.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrHead {
    /// Full SHA of the head commit
    pub sha: String,
    /// Committer date of the head commit (client-supplied, informational)
    pub committed_at: Option<DateTime<Utc>>,
}

/// Fetch the current head SHA (and head commit date) of a PR.
pub async fn fetch_pr_head(repo: &str, pr_number: u64) -> Result<PrHead, Error> {
    let output = run_gh_command(
        &[
            "pr",
            "view",
            &pr_number.to_string(),
            "--repo",
            repo,
            "--json",
            "headRefOid,commits",
            "--jq",
            "{sha: .headRefOid, date: ((.commits | last | .committedDate) // null)}",
        ],
        true,
    )
    .await?
    .unwrap_or_default();

    parse_pr_head(&output)
}

/// Parse the `--jq` projection emitted by [`fetch_pr_head`].
fn parse_pr_head(json: &str) -> Result<PrHead, Error> {
    #[derive(Deserialize)]
    struct Raw {
        sha: Option<String>,
        date: Option<String>,
    }
    let raw: Raw = serde_json::from_str(json.trim())?;
    let sha = raw
        .sha
        .filter(|s| is_valid_sha(s))
        .ok_or_else(|| Error::SecurityCheck("PR head SHA missing or malformed".to_string()))?;
    let committed_at = raw.date.and_then(|d| d.parse().ok());
    debug!("PR head: {} (committed {:?})", sha, committed_at);
    Ok(PrHead { sha, committed_at })
}

/// Stage 1: ensure the head commit is not newer than the approval.
///
/// Returns a human-readable rejection reason on failure. When either
/// timestamp is unknown the check passes (stages 2/3 still apply).
pub fn check_approval_freshness(
    head: &PrHead,
    approved_at: Option<DateTime<Utc>>,
) -> Result<(), String> {
    match (head.committed_at, approved_at) {
        (Some(committed), Some(approved)) if committed > approved => Err(format!(
            "The PR head commit {} ({}) is newer than the approval ({}). \
             New commits must be reviewed and re-approved.",
            short_sha(&head.sha),
            committed.to_rfc3339(),
            approved.to_rfc3339()
        )),
        _ => Ok(()),
    }
}

/// Stages 2/3: ensure the head has not moved from the pinned SHA.
pub fn check_head_unchanged(pinned_sha: &str, current: &PrHead) -> Result<(), String> {
    if sha_matches(pinned_sha, &current.sha) {
        Ok(())
    } else {
        Err(format!(
            "The PR head changed from {} to {} while the request was being processed.",
            short_sha(pinned_sha),
            short_sha(&current.sha)
        ))
    }
}

/// First 12 characters of a SHA for display.
pub fn short_sha(sha: &str) -> &str {
    crate::utils::truncate_str(sha, 12)
}

#[cfg(test)]
mod tests {
    use super::*;

    const FULL: &str = "0123456789abcdef0123456789abcdef01234567";

    #[test]
    fn sha_validation() {
        assert!(is_valid_sha("abc1234"));
        assert!(is_valid_sha(FULL));
        assert!(is_valid_sha("ABCDEF0"));
        assert!(!is_valid_sha("abc123")); // too short
        assert!(!is_valid_sha("--output=/tmp/x"));
        assert!(!is_valid_sha("abc123g"));
        assert!(!is_valid_sha(""));
        assert!(!is_valid_sha(&"a".repeat(65)));
    }

    #[test]
    fn sha_prefix_matching() {
        assert!(sha_matches("0123456", FULL));
        assert!(sha_matches(FULL, FULL));
        assert!(sha_matches("0123456789ABCDEF", FULL));
        assert!(!sha_matches("1123456", FULL));
        assert!(!sha_matches("012345", FULL)); // too short to trust
        assert!(!sha_matches("", FULL));
        assert!(!sha_matches("0123456", "not-a-sha"));
    }

    #[test]
    fn parses_pr_head() {
        let head = parse_pr_head(&format!(
            r#"{{"sha":"{FULL}","date":"2026-01-02T03:04:05Z"}}"#
        ))
        .unwrap();
        assert_eq!(head.sha, FULL);
        assert!(head.committed_at.is_some());

        let head = parse_pr_head(&format!(r#"{{"sha":"{FULL}","date":null}}"#)).unwrap();
        assert!(head.committed_at.is_none());

        assert!(parse_pr_head(r#"{"sha":"--evil","date":null}"#).is_err());
        assert!(parse_pr_head(r#"{"sha":null,"date":null}"#).is_err());
        assert!(parse_pr_head("not json").is_err());
    }

    #[test]
    fn freshness_check() {
        let approved: DateTime<Utc> = "2026-01-02T00:00:00Z".parse().unwrap();
        let older = PrHead {
            sha: FULL.to_string(),
            committed_at: Some("2026-01-01T00:00:00Z".parse().unwrap()),
        };
        let newer = PrHead {
            sha: FULL.to_string(),
            committed_at: Some("2026-01-03T00:00:00Z".parse().unwrap()),
        };
        assert!(check_approval_freshness(&older, Some(approved)).is_ok());
        assert!(check_approval_freshness(&newer, Some(approved)).is_err());
        assert!(check_approval_freshness(&newer, None).is_ok());
    }

    #[test]
    fn head_unchanged_check() {
        let head = PrHead {
            sha: FULL.to_string(),
            committed_at: None,
        };
        assert!(check_head_unchanged("0123456789", &head).is_ok());
        let err = check_head_unchanged("fedcba9876", &head).unwrap_err();
        assert!(err.contains("fedcba9876"));
    }
}
