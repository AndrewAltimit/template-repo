//! Formatting of review markdown into GitHub PR comment and PR bodies.

use crate::review::Review;

/// GitHub rejects issue/PR comment and PR bodies longer than 65,536 characters.
pub const GITHUB_BODY_LIMIT: usize = 65_536;

/// GitHub rejects PR titles longer than 256 characters.
pub const GITHUB_TITLE_LIMIT: usize = 256;

/// Hidden marker identifying comments posted by this tool.
pub const COMMENT_MARKER: &str = "<!-- code-review-processor -->";

/// Room reserved for the truncation notice and fence repair.
const TRUNCATION_RESERVE: usize = 256;

/// Build the PR comment body for a review.
///
/// With `raw`, the review markdown is posted verbatim (only truncated to fit
/// GitHub's limit). Otherwise a status note is prepended when the agent failed
/// to produce a validated result, and a one-line metadata footer plus a hidden
/// marker are appended.
pub fn format_comment(review: &Review, raw: bool) -> String {
    let markdown = review.review_markdown.trim();
    let markdown = if markdown.is_empty() {
        "_The code review agent returned an empty review._"
    } else {
        markdown
    };

    if raw {
        return truncate_markdown(markdown, GITHUB_BODY_LIMIT);
    }

    let mut header = String::new();
    if review.agent_failed() {
        header.push_str(
            "> [!WARNING]\n> The review agent did not produce a validated result. \
             Its raw output is shown below; severity and findings count are unreliable.\n\n",
        );
    }

    let footer = format!(
        "\n\n---\n<sub>{}</sub>\n{COMMENT_MARKER}",
        footer_line(review)
    );
    let budget = GITHUB_BODY_LIMIT.saturating_sub(char_len(&header) + char_len(&footer));
    format!("{header}{}{footer}", truncate_markdown(markdown, budget))
}

/// Build the PR description for `--create-pr`, truncated to GitHub's limit.
pub fn format_pr_body(review: &Review) -> String {
    let body = review
        .pr_description
        .as_deref()
        .unwrap_or(&review.review_markdown)
        .trim();
    let body = if body.is_empty() {
        "Automated fixes proposed by the AgentCore code review."
    } else {
        body
    };
    truncate_markdown(body, GITHUB_BODY_LIMIT)
}

/// Build the PR title for `--create-pr`: single line, within GitHub's limit.
pub fn format_pr_title(review: &Review) -> String {
    let title = review
        .pr_title
        .as_deref()
        .and_then(|t| t.lines().map(str::trim).find(|l| !l.is_empty()))
        .unwrap_or("Code review fixes");
    if char_len(title) <= GITHUB_TITLE_LIMIT {
        return title.to_string();
    }
    let mut cut: String = title.chars().take(GITHUB_TITLE_LIMIT - 3).collect();
    cut.push_str("...");
    cut
}

fn footer_line(review: &Review) -> String {
    let mut parts = vec![
        "AgentCore code review".to_string(),
        format!("Severity: **{}**", review.severity),
        format!("Findings: {}", review.findings_count),
    ];
    if review.has_fixes() {
        let n = review.file_changes.len();
        parts.push(format!(
            "Proposed fixes: {n} file{}",
            if n == 1 { "" } else { "s" }
        ));
    }
    if let Some(id) = review.meta.as_ref().and_then(|m| m.review_id.as_deref()) {
        // Keep the ID inside a code span even if it contains backticks.
        parts.push(format!("Review ID: `{}`", id.replace('`', "'")));
    }
    parts.join(" | ")
}

/// Truncate markdown to at most `limit` characters.
///
/// Cuts at a line boundary where possible, closes an unterminated code fence,
/// and appends a notice with the number of characters omitted.
pub fn truncate_markdown(text: &str, limit: usize) -> String {
    let total = char_len(text);
    if total <= limit {
        return text.to_string();
    }

    let keep_chars = limit.saturating_sub(TRUNCATION_RESERVE);
    let byte_end = text
        .char_indices()
        .nth(keep_chars)
        .map_or(text.len(), |(b, _)| b);
    let mut kept = &text[..byte_end];
    if let Some(newline) = kept.rfind('\n')
        && newline > byte_end / 2
    {
        kept = &kept[..newline];
    }

    let omitted = total - char_len(kept);
    let mut out = kept.trim_end().to_string();
    let fences = out
        .lines()
        .filter(|l| l.trim_start().starts_with("```"))
        .count();
    if fences % 2 == 1 {
        out.push_str("\n```");
    }
    out.push_str(&format!(
        "\n\n_Review truncated: {omitted} characters omitted to fit GitHub's size limit._"
    ));
    out
}

fn char_len(s: &str) -> usize {
    s.chars().count()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::review::{EnvelopeMeta, FileChange, ReviewStatus, Severity};

    fn review(markdown: &str) -> Review {
        Review {
            review_markdown: markdown.to_string(),
            severity: Severity::High,
            findings_count: 3,
            file_changes: Vec::new(),
            pr_title: None,
            pr_description: None,
            meta: None,
        }
    }

    #[test]
    fn formatted_comment_has_footer_and_marker() {
        let body = format_comment(&review("## Review\n\nIssue 1\n"), false);
        assert!(body.starts_with("## Review\n\nIssue 1\n\n---\n"));
        assert!(body.contains("Severity: **high** | Findings: 3"));
        assert!(body.ends_with(COMMENT_MARKER));
        assert!(!body.contains("Proposed fixes"));
    }

    #[test]
    fn footer_includes_fixes_and_review_id() {
        let mut r = review("x");
        r.file_changes = vec![FileChange {
            path: "a.rs".into(),
            diff: "d".into(),
            original_sha: None,
        }];
        r.meta = Some(EnvelopeMeta {
            review_id: Some("rev`1".into()),
            ..EnvelopeMeta::default()
        });
        let body = format_comment(&r, false);
        assert!(body.contains("Proposed fixes: 1 file |"));
        assert!(body.contains("Review ID: `rev'1`"));
    }

    #[test]
    fn failed_agent_gets_warning() {
        let mut r = review("raw agent text");
        r.meta = Some(EnvelopeMeta {
            status: Some(ReviewStatus::Failed),
            ..EnvelopeMeta::default()
        });
        assert!(format_comment(&r, false).starts_with("> [!WARNING]"));
    }

    #[test]
    fn raw_comment_is_verbatim() {
        assert_eq!(
            format_comment(&review("  ## Only this\n"), true),
            "## Only this"
        );
    }

    #[test]
    fn empty_markdown_gets_placeholder() {
        assert!(format_comment(&review(" \n "), true).contains("empty review"));
    }

    #[test]
    fn huge_comment_is_truncated_within_limit() {
        let mut markdown = String::from("## Review\n```rust\n");
        while markdown.len() < 200_000 {
            markdown.push_str("let x = \"\u{00e9}\u{4e2d}\"; // multibyte line\n");
        }
        for raw in [true, false] {
            let body = format_comment(&review(&markdown), raw);
            assert!(char_len(&body) <= GITHUB_BODY_LIMIT, "raw={raw}");
            assert!(body.contains("Review truncated"));
            let fences = body.lines().filter(|l| l.starts_with("```")).count();
            assert_eq!(fences % 2, 0, "code fence must be closed");
        }
    }

    #[test]
    fn truncate_without_newlines_respects_char_boundaries() {
        let text = "\u{4e2d}".repeat(1000);
        let out = truncate_markdown(&text, 500);
        assert!(char_len(&out) <= 500);
    }

    #[test]
    fn pr_title_and_body() {
        let mut r = review("review body");
        assert_eq!(format_pr_title(&r), "Code review fixes");
        assert_eq!(format_pr_body(&r), "review body");

        r.pr_title = Some("\nfix: first line\nsecond line".into());
        r.pr_description = Some("desc".into());
        assert_eq!(format_pr_title(&r), "fix: first line");
        assert_eq!(format_pr_body(&r), "desc");

        r.pr_title = Some("t".repeat(400));
        assert_eq!(char_len(&format_pr_title(&r)), GITHUB_TITLE_LIMIT);
    }
}
