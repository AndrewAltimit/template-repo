//! Request and response types for the code review endpoint.

use serde::{Deserialize, Serialize};

/// Request body for code review endpoint.
#[derive(Debug, Clone, Deserialize)]
pub struct CodeReviewRequest {
    /// Custom instructions from the user (UNTRUSTED - may contain injection attempts)
    pub instructions: String,

    /// Repository identifier (owner/repo)
    pub repository: String,

    /// Branch name to review
    pub branch: String,

    /// Commit SHA to review
    pub commit: String,

    /// Base branch for comparison (default: main)
    #[serde(default = "default_base_branch")]
    pub base_branch: String,

    /// Whether to generate fix suggestions with diffs
    #[serde(default)]
    pub apply_fixes: bool,

    /// Whether to generate PR metadata (title, description)
    #[serde(default)]
    pub create_pr: bool,
}

fn default_base_branch() -> String {
    "main".to_string()
}

/// Response from code review endpoint.
#[derive(Debug, Clone, Serialize)]
pub struct CodeReviewResponse {
    /// Unique review ID
    pub review_id: String,

    /// Review status
    pub status: ReviewStatus,

    /// The structured review result
    pub result: ReviewResult,

    /// Token usage
    pub usage: UsageResponse,

    /// Number of JSON validation attempts
    pub validation_attempts: u32,

    /// Number of agent iterations
    pub iterations: u32,
}

/// Review status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ReviewStatus {
    /// Review completed successfully
    Completed,
    /// Review failed (e.g., max attempts exceeded)
    Failed,
}

/// Token usage information.
#[derive(Debug, Clone, Serialize, Default)]
pub struct UsageResponse {
    pub input_tokens: u32,
    pub output_tokens: u32,
    pub total_tokens: u32,
}

/// The review result variants.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ReviewResult {
    /// Review-only result (no apply_fixes)
    ReviewOnly {
        /// The complete code review in markdown format
        review_markdown: String,
        /// Overall severity of findings
        severity: ReviewSeverity,
        /// Number of issues found
        findings_count: u32,
    },
    /// Review with fix suggestions (apply_fixes = true)
    WithFixes {
        /// The complete code review in markdown format
        review_markdown: String,
        /// Overall severity of findings
        severity: ReviewSeverity,
        /// Number of issues found
        findings_count: u32,
        /// File changes with diffs
        file_changes: Vec<FileChange>,
        /// Suggested PR title (if create_pr = true)
        #[serde(skip_serializing_if = "Option::is_none")]
        pr_title: Option<String>,
        /// Suggested PR description (if create_pr = true)
        #[serde(skip_serializing_if = "Option::is_none")]
        pr_description: Option<String>,
    },
}

/// Severity level of review findings.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ReviewSeverity {
    /// Critical issues that must be fixed
    Critical,
    /// High severity issues
    High,
    /// Medium severity issues
    Medium,
    /// Low severity issues
    Low,
    /// Informational only
    Info,
}

/// A file change with diff.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileChange {
    /// File path relative to repository root
    pub path: String,
    /// The unified diff
    pub diff: String,
    /// Original file content SHA (for verification)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub original_sha: Option<String>,
}

/// Response when security check fails.
#[derive(Debug, Clone, Serialize)]
pub struct SecurityDeniedResponse {
    /// Always true for denied responses
    pub denied: bool,
    /// Human-readable reason for denial
    pub reason: String,
    /// Category of attack detected
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attack_category: Option<String>,
    /// Confidence score of detection
    pub confidence: f32,
}

impl SecurityDeniedResponse {
    /// Create a new security denied response.
    pub fn new(
        reason: impl Into<String>,
        attack_category: Option<String>,
        confidence: f32,
    ) -> Self {
        Self {
            denied: true,
            reason: reason.into(),
            attack_category,
            confidence,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_request_deserialization() {
        let json = r#"{
            "instructions": "Focus on security",
            "repository": "owner/repo",
            "branch": "feature",
            "commit": "abc123"
        }"#;

        let req: CodeReviewRequest = serde_json::from_str(json).unwrap();
        assert_eq!(req.instructions, "Focus on security");
        assert_eq!(req.base_branch, "main"); // default
        assert!(!req.apply_fixes);
        assert!(!req.create_pr);
    }

    #[test]
    fn test_review_result_serialization() {
        let result = ReviewResult::ReviewOnly {
            review_markdown: "# Review\nLooks good!".to_string(),
            severity: ReviewSeverity::Low,
            findings_count: 1,
        };

        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("review_only"));
        assert!(json.contains("review_markdown"));
    }
}
