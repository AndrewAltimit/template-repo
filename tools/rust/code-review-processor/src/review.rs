//! Review model and lenient parsing of AgentCore code review responses.
//!
//! Three input shapes are accepted:
//!
//! 1. **Endpoint envelope** -- what `POST /code-review` actually returns:
//!    `{"review_id", "status", "result": {"type": ..., ...}, "usage", ...}`.
//! 2. **Flat schema** -- the object the agent commits via `validate_json`:
//!    `{"review_markdown", "severity", "findings_count", "file_changes"?, ...}`.
//! 3. **Legacy tagged** -- the flat schema plus a `"type"` discriminator
//!    (`review_only` / `with_fixes`).
//!
//! Parsing is deliberately forgiving about things a model commonly gets
//! slightly wrong (severity casing and synonyms, numeric strings, `null`
//! optional fields, JSON wrapped in a markdown code fence, a UTF-8 BOM) and
//! strict about things that would make acting on the review unsafe (missing
//! review text, malformed file change entries).

use std::fmt;

use anyhow::{Context, Result, bail};
use serde::Serialize;
use serde_json::{Map, Value};
use tracing::warn;

/// Overall severity of a review, ordered from least to most severe.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    /// Informational only.
    Info,
    /// Low severity issues.
    Low,
    /// Medium severity issues.
    Medium,
    /// High severity issues.
    High,
    /// Critical issues that must be fixed.
    Critical,
}

impl Severity {
    /// All severities in ascending order.
    pub const ALL: [Severity; 5] = [
        Severity::Info,
        Severity::Low,
        Severity::Medium,
        Severity::High,
        Severity::Critical,
    ];

    /// Canonical lowercase name.
    pub fn as_str(self) -> &'static str {
        match self {
            Severity::Info => "info",
            Severity::Low => "low",
            Severity::Medium => "medium",
            Severity::High => "high",
            Severity::Critical => "critical",
        }
    }

    /// Parse a severity label, accepting common synonyms and any casing.
    ///
    /// Returns `None` for labels that cannot be mapped.
    pub fn parse(label: &str) -> Option<Self> {
        let normalized = label.trim().to_ascii_lowercase();
        let severity = match normalized.as_str() {
            "critical" | "blocker" | "severe" | "fatal" => Severity::Critical,
            "high" | "major" | "error" | "important" => Severity::High,
            "medium" | "moderate" | "warning" | "warn" => Severity::Medium,
            "low" | "minor" | "trivial" | "nit" => Severity::Low,
            "info" | "informational" | "information" | "none" | "ok" | "pass" => Severity::Info,
            _ => return None,
        };
        Some(severity)
    }
}

impl fmt::Display for Severity {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// A proposed change to a single file, expressed as a unified diff.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct FileChange {
    /// File path relative to the repository root.
    pub path: String,
    /// Unified diff for this file.
    pub diff: String,
    /// Git blob SHA of the file the diff was generated against (optional).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub original_sha: Option<String>,
}

/// Status reported by the endpoint envelope.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReviewStatus {
    /// The agent committed a schema-valid result.
    Completed,
    /// The agent never committed a result; the markdown is its raw output.
    Failed,
}

/// Metadata that only exists when the input is the full endpoint envelope.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize)]
pub struct EnvelopeMeta {
    /// Unique review ID assigned by the endpoint.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_id: Option<String>,
    /// Completion status, if reported.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<ReviewStatus>,
    /// Total tokens consumed, if reported.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total_tokens: Option<u64>,
}

/// A parsed, normalized code review.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Review {
    /// Review body in markdown.
    pub review_markdown: String,
    /// Overall severity.
    pub severity: Severity,
    /// Number of findings reported by the agent.
    pub findings_count: u32,
    /// Proposed file changes (deduplicated, possibly empty).
    pub file_changes: Vec<FileChange>,
    /// Suggested PR title for `--create-pr`.
    pub pr_title: Option<String>,
    /// Suggested PR description for `--create-pr`.
    pub pr_description: Option<String>,
    /// Envelope metadata, present only for full endpoint responses.
    pub meta: Option<EnvelopeMeta>,
}

impl Review {
    /// Whether the review carries at least one file change.
    pub fn has_fixes(&self) -> bool {
        !self.file_changes.is_empty()
    }

    /// Proposed file changes.
    pub fn file_changes(&self) -> &[FileChange] {
        &self.file_changes
    }

    /// Whether the endpoint reported that the agent failed to commit a result.
    pub fn agent_failed(&self) -> bool {
        self.meta
            .as_ref()
            .is_some_and(|m| m.status == Some(ReviewStatus::Failed))
    }
}

/// Parse review JSON in any of the supported shapes (see module docs).
pub fn parse_review_json(input: &str) -> Result<Review> {
    let root = parse_json_value(input)?;
    let Value::Object(root) = root else {
        bail!("Review JSON must be an object, got {}", json_type(&root));
    };

    if root.get("denied").and_then(Value::as_bool) == Some(true) {
        let reason = root
            .get("reason")
            .and_then(Value::as_str)
            .unwrap_or("unknown reason");
        let category = root
            .get("attack_category")
            .and_then(Value::as_str)
            .unwrap_or("unknown");
        bail!(
            "Input is a security-denied response, not a review (reason: {reason}; \
             category: {category})"
        );
    }

    if let Some(error) = root.get("error").and_then(Value::as_str)
        && !root.contains_key("review_markdown")
        && !root.contains_key("result")
    {
        let code = root
            .get("code")
            .and_then(Value::as_str)
            .unwrap_or("unknown");
        bail!("Input is an endpoint error response (code: {code}): {error}");
    }

    match root.get("result") {
        Some(Value::Object(result)) if !root.contains_key("review_markdown") => {
            let meta = parse_envelope_meta(&root);
            let mut review = parse_payload(result).context("Invalid `result` in response")?;
            review.meta = Some(meta);
            Ok(review)
        },
        Some(other) if !root.contains_key("review_markdown") => {
            bail!("`result` must be an object, got {}", json_type(other))
        },
        _ => parse_payload(&root),
    }
}

/// Parse text into a JSON value, tolerating a BOM and markdown code fences.
fn parse_json_value(input: &str) -> Result<Value> {
    let text = input.trim_start_matches('\u{feff}').trim();
    if text.is_empty() {
        bail!("Review input is empty");
    }

    let direct_err = match serde_json::from_str::<Value>(text) {
        Ok(value) => return Ok(value),
        Err(e) => e,
    };

    // Models sometimes wrap the JSON in a ```json fence or add prose around it.
    if let Some(inner) = extract_embedded_object(text)
        && let Ok(value) = serde_json::from_str::<Value>(inner)
    {
        warn!("Review JSON was embedded in surrounding text; extracted the JSON object");
        return Ok(value);
    }

    Err(direct_err).context("Failed to parse review JSON")
}

/// Return the slice between the first `{` and the last `}`, if any.
fn extract_embedded_object(text: &str) -> Option<&str> {
    let start = text.find('{')?;
    let end = text.rfind('}')?;
    (end > start).then(|| &text[start..=end])
}

fn parse_envelope_meta(root: &Map<String, Value>) -> EnvelopeMeta {
    let status = root.get("status").and_then(Value::as_str).and_then(|s| {
        match s.trim().to_ascii_lowercase().as_str() {
            "completed" => Some(ReviewStatus::Completed),
            "failed" => Some(ReviewStatus::Failed),
            other => {
                warn!(status = other, "Unknown review status in envelope");
                None
            },
        }
    });
    EnvelopeMeta {
        review_id: non_empty_string(root.get("review_id")),
        status,
        total_tokens: root
            .get("usage")
            .and_then(|u| u.get("total_tokens"))
            .and_then(Value::as_u64),
    }
}

/// Parse the flat (or legacy tagged) review object.
fn parse_payload(obj: &Map<String, Value>) -> Result<Review> {
    if let Some(kind) = obj.get("type").and_then(Value::as_str)
        && kind != "review_only"
        && kind != "with_fixes"
    {
        warn!(
            r#type = kind,
            "Unknown review `type`; treating as a plain review"
        );
    }

    let review_markdown = match obj.get("review_markdown") {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Null) | None => bail!("Missing required field `review_markdown`"),
        Some(other) => bail!(
            "`review_markdown` must be a string, got {}",
            json_type(other)
        ),
    };

    let severity = match obj.get("severity") {
        Some(Value::String(label)) => Severity::parse(label).unwrap_or_else(|| {
            warn!(severity = %label, "Unrecognized severity; defaulting to info");
            Severity::Info
        }),
        Some(Value::Null) | None => {
            warn!("Missing `severity`; defaulting to info");
            Severity::Info
        },
        Some(other) => bail!("`severity` must be a string, got {}", json_type(other)),
    };

    let findings_count = parse_count(obj.get("findings_count"))?;
    let file_changes = parse_file_changes(obj.get("file_changes"))?;

    Ok(Review {
        review_markdown,
        severity,
        findings_count,
        file_changes,
        pr_title: non_empty_string(obj.get("pr_title")),
        pr_description: non_empty_string(obj.get("pr_description")),
        meta: None,
    })
}

/// Parse `findings_count`, accepting integers, integral floats and numeric strings.
fn parse_count(value: Option<&Value>) -> Result<u32> {
    let clamp = |n: u64| u32::try_from(n).unwrap_or(u32::MAX);
    match value {
        None | Some(Value::Null) => Ok(0),
        Some(Value::Number(n)) => {
            if let Some(u) = n.as_u64() {
                Ok(clamp(u))
            } else if n.as_i64().is_some() {
                bail!("`findings_count` must not be negative, got {n}")
            } else {
                match n.as_f64() {
                    Some(f) if f >= 0.0 && f.fract() == 0.0 => Ok(clamp(f as u64)),
                    _ => bail!("`findings_count` must be a non-negative integer, got {n}"),
                }
            }
        },
        Some(Value::String(s)) => s
            .trim()
            .parse::<u64>()
            .map(clamp)
            .with_context(|| format!("`findings_count` is not a non-negative integer: {s:?}")),
        Some(other) => bail!(
            "`findings_count` must be an integer, got {}",
            json_type(other)
        ),
    }
}

/// Parse `file_changes`, rejecting malformed entries and dropping exact duplicates.
fn parse_file_changes(value: Option<&Value>) -> Result<Vec<FileChange>> {
    let items = match value {
        None | Some(Value::Null) => return Ok(Vec::new()),
        Some(Value::Array(items)) => items,
        Some(other) => bail!("`file_changes` must be an array, got {}", json_type(other)),
    };

    let mut changes: Vec<FileChange> = Vec::with_capacity(items.len());
    for (index, item) in items.iter().enumerate() {
        let Value::Object(entry) = item else {
            bail!(
                "file_changes[{index}] must be an object, got {}",
                json_type(item)
            );
        };
        let path = match entry.get("path") {
            Some(Value::String(p)) if !p.trim().is_empty() => p.trim().to_string(),
            _ => bail!("file_changes[{index}] is missing a non-empty string `path`"),
        };
        let diff = match entry.get("diff") {
            Some(Value::String(d)) if !d.trim().is_empty() => d.clone(),
            _ => bail!("file_changes[{index}] ({path}) is missing a non-empty string `diff`"),
        };
        let change = FileChange {
            path,
            diff,
            original_sha: non_empty_string(entry.get("original_sha")),
        };
        if changes.contains(&change) {
            warn!(path = %change.path, "Dropping duplicate file change");
            continue;
        }
        changes.push(change);
    }
    Ok(changes)
}

/// Extract a trimmed, non-empty string; anything else becomes `None`.
fn non_empty_string(value: Option<&Value>) -> Option<String> {
    value
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

fn json_type(value: &Value) -> &'static str {
    match value {
        Value::Null => "null",
        Value::Bool(_) => "a boolean",
        Value::Number(_) => "a number",
        Value::String(_) => "a string",
        Value::Array(_) => "an array",
        Value::Object(_) => "an object",
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn parse(value: serde_json::Value) -> Result<Review> {
        parse_review_json(&value.to_string())
    }

    #[test]
    fn flat_review_only() {
        let review = parse(json!({
            "review_markdown": "Code Review - Looks good!",
            "severity": "low",
            "findings_count": 1
        }))
        .unwrap();
        assert!(review.review_markdown.contains("Looks good"));
        assert_eq!(review.severity, Severity::Low);
        assert_eq!(review.findings_count, 1);
        assert!(!review.has_fixes());
        assert!(review.meta.is_none());
    }

    #[test]
    fn flat_with_fixes() {
        let review = parse(json!({
            "review_markdown": "Security Issue Found",
            "severity": "critical",
            "findings_count": 1,
            "file_changes": [{"path": "src/db.rs", "diff": "--- a/src/db.rs\n+++ b/src/db.rs"}],
            "pr_title": "fix(security): patch vulnerability",
            "pr_description": "This PR fixes the security issue."
        }))
        .unwrap();
        assert!(review.has_fixes());
        assert_eq!(review.file_changes()[0].path, "src/db.rs");
        assert_eq!(
            review.pr_title.as_deref(),
            Some("fix(security): patch vulnerability")
        );
    }

    #[test]
    fn legacy_tagged_formats() {
        let only = parse(json!({
            "type": "review_only",
            "review_markdown": "Looks good!",
            "severity": "low",
            "findings_count": 1
        }))
        .unwrap();
        assert!(!only.has_fixes());

        let fixes = parse(json!({
            "type": "with_fixes",
            "review_markdown": "Review",
            "severity": "medium",
            "findings_count": 2,
            "file_changes": [{"path": "src/main.rs", "diff": "diff content"}],
            "pr_title": "Fix issues"
        }))
        .unwrap();
        assert_eq!(fixes.file_changes().len(), 1);
        assert_eq!(fixes.pr_title.as_deref(), Some("Fix issues"));
    }

    #[test]
    fn endpoint_envelope_is_unwrapped() {
        let review = parse(json!({
            "review_id": "rev-123",
            "status": "completed",
            "result": {
                "type": "with_fixes",
                "review_markdown": "## Review",
                "severity": "high",
                "findings_count": 2,
                "file_changes": [{"path": "a.rs", "diff": "@@ -1 +1 @@\n-a\n+b\n"}]
            },
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "validation_attempts": 1,
            "iterations": 3
        }))
        .unwrap();
        assert_eq!(review.severity, Severity::High);
        assert!(review.has_fixes());
        let meta = review.meta.as_ref().unwrap();
        assert_eq!(meta.review_id.as_deref(), Some("rev-123"));
        assert_eq!(meta.status, Some(ReviewStatus::Completed));
        assert_eq!(meta.total_tokens, Some(15));
        assert!(!review.agent_failed());
    }

    #[test]
    fn failed_envelope_is_flagged() {
        let review = parse(json!({
            "review_id": "rev-9",
            "status": "failed",
            "result": {"type": "review_only", "review_markdown": "raw text",
                       "severity": "info", "findings_count": 0}
        }))
        .unwrap();
        assert!(review.agent_failed());
    }

    #[test]
    fn severity_is_lenient() {
        for (label, expected) in [
            ("CRITICAL", Severity::Critical),
            (" High ", Severity::High),
            ("warning", Severity::Medium),
            ("minor", Severity::Low),
            ("none", Severity::Info),
            ("banana", Severity::Info),
        ] {
            let review = parse(json!({
                "review_markdown": "x", "severity": label, "findings_count": 0
            }))
            .unwrap();
            assert_eq!(review.severity, expected, "label {label:?}");
        }
        let missing = parse(json!({"review_markdown": "x"})).unwrap();
        assert_eq!(missing.severity, Severity::Info);
        assert_eq!(missing.findings_count, 0);
    }

    #[test]
    fn severity_ordering() {
        assert!(Severity::Critical > Severity::High);
        assert!(Severity::Low > Severity::Info);
        let mut sorted = Severity::ALL;
        sorted.sort();
        assert_eq!(sorted, Severity::ALL);
    }

    #[test]
    fn findings_count_variants() {
        let count = |v: serde_json::Value| {
            parse(json!({"review_markdown": "x", "severity": "low", "findings_count": v}))
        };
        assert_eq!(count(json!(3)).unwrap().findings_count, 3);
        assert_eq!(count(json!(3.0)).unwrap().findings_count, 3);
        assert_eq!(count(json!(" 7 ")).unwrap().findings_count, 7);
        assert_eq!(count(json!(null)).unwrap().findings_count, 0);
        assert_eq!(count(json!(u64::MAX)).unwrap().findings_count, u32::MAX);
        assert!(count(json!(-1)).is_err());
        assert!(count(json!(1.5)).is_err());
        assert!(count(json!("five")).is_err());
        assert!(count(json!([1])).is_err());
    }

    #[test]
    fn optional_fields_accept_null_and_blank() {
        let review = parse(json!({
            "review_markdown": "x", "severity": "low", "findings_count": 0,
            "file_changes": null, "pr_title": "   ", "pr_description": null
        }))
        .unwrap();
        assert!(!review.has_fixes());
        assert!(review.pr_title.is_none());
        assert!(review.pr_description.is_none());
    }

    #[test]
    fn empty_file_changes_means_no_fixes() {
        let review = parse(json!({
            "review_markdown": "No issues", "severity": "info", "findings_count": 0,
            "file_changes": []
        }))
        .unwrap();
        assert!(!review.has_fixes());
    }

    #[test]
    fn duplicate_file_changes_are_dropped() {
        let change = json!({"path": "a.rs", "diff": "@@ -1 +1 @@\n-a\n+b\n"});
        let review = parse(json!({
            "review_markdown": "x", "severity": "low", "findings_count": 1,
            "file_changes": [change.clone(), change, {"path": "b.rs", "diff": "d"}]
        }))
        .unwrap();
        assert_eq!(review.file_changes().len(), 2);
    }

    #[test]
    fn malformed_file_changes_are_rejected() {
        for bad in [
            json!("not an array"),
            json!([42]),
            json!([{"path": "a.rs"}]),
            json!([{"diff": "d"}]),
            json!([{"path": "", "diff": "d"}]),
            json!([{"path": "a.rs", "diff": "   "}]),
        ] {
            let result = parse(json!({
                "review_markdown": "x", "severity": "low", "findings_count": 1,
                "file_changes": bad
            }));
            assert!(result.is_err(), "should reject {bad}");
        }
    }

    #[test]
    fn missing_or_invalid_markdown_is_rejected() {
        assert!(parse(json!({"severity": "low", "findings_count": 0})).is_err());
        assert!(parse(json!({"review_markdown": 5})).is_err());
        assert!(parse(json!({"review_markdown": null})).is_err());
    }

    #[test]
    fn non_object_and_garbage_inputs_fail_cleanly() {
        for input in [
            "",
            "   \n",
            "{ invalid json }",
            "[1,2,3]",
            "\"text\"",
            "null",
            "{",
        ] {
            assert!(parse_review_json(input).is_err(), "input {input:?}");
        }
    }

    #[test]
    fn bom_and_code_fence_are_tolerated() {
        let body = r#"{"review_markdown": "ok", "severity": "low", "findings_count": 0}"#;
        assert!(parse_review_json(&format!("\u{feff}{body}")).is_ok());
        let fenced = format!("Here is the review:\n```json\r\n{body}\r\n```\n");
        assert_eq!(parse_review_json(&fenced).unwrap().review_markdown, "ok");
    }

    #[test]
    fn denied_and_error_responses_are_reported() {
        let denied = parse(json!({
            "denied": true, "reason": "Prompt injection", "attack_category": "jailbreak",
            "confidence": 0.9
        }))
        .unwrap_err();
        assert!(format!("{denied:#}").contains("security-denied"));

        let error = parse(
            json!({"error": "Agent execution failed", "code": "AGENT_ERROR",
                                 "retryable": false}),
        )
        .unwrap_err();
        assert!(format!("{error:#}").contains("AGENT_ERROR"));
    }

    #[test]
    fn envelope_with_non_object_result_fails() {
        assert!(parse(json!({"review_id": "x", "result": "oops"})).is_err());
    }

    #[test]
    fn multiline_and_special_characters_survive() {
        let review = parse(json!({
            "review_markdown": "Line 1\r\nLine 2\n\n## Header \u{2014} done",
            "severity": "low",
            "findings_count": 0,
            "file_changes": [{"path": "t.rs", "diff": "-let x = \"hello\";\n+let x = \"world\";"}]
        }))
        .unwrap();
        assert!(review.review_markdown.contains("## Header"));
        assert!(review.file_changes()[0].diff.contains("\"world\""));
    }
}
