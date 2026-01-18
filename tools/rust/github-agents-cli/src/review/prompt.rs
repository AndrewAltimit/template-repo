//! Prompt construction for PR reviews.
//!
//! Builds comprehensive prompts with project context, diff, and comments.

use std::fs;
use std::path::Path;

use super::diff::{FileStats, PRMetadata};

/// Maximum characters for project context files
const MAX_CONTEXT_CHARS: usize = 3000;

/// Build the complete review prompt
pub fn build_review_prompt(
    metadata: &PRMetadata,
    stats: &FileStats,
    diff: &str,
    comment_context: &str,
    is_incremental: bool,
    previous_issues: Option<&str>,
) -> String {
    let mut prompt = String::with_capacity(diff.len() + 10000);

    // Output rules
    prompt.push_str(REVIEW_RULES);
    prompt.push('\n');

    // Project context
    if let Some(context) = get_project_context() {
        prompt.push_str("## Project Context\n\n");
        prompt.push_str(&context);
        prompt.push_str("\n\n");
    }

    // PR metadata
    prompt.push_str("## Pull Request Information\n\n");
    prompt.push_str(&format!(
        "- **PR #{}**: {}\n",
        metadata.number, metadata.title
    ));
    prompt.push_str(&format!("- **Author**: {}\n", metadata.author));
    prompt.push_str(&format!(
        "- **Branch**: {} -> {}\n",
        metadata.head_branch, metadata.base_branch
    ));
    prompt.push_str(&format!(
        "- **Files Changed**: {} (+{} -{})\n\n",
        stats.files_changed, stats.lines_added, stats.lines_deleted
    ));

    if !metadata.body.is_empty() {
        prompt.push_str("### PR Description\n\n");
        prompt.push_str(&metadata.body);
        prompt.push_str("\n\n");
    }

    // Incremental review context
    if is_incremental {
        prompt.push_str("## Incremental Review Mode\n\n");
        prompt.push_str(
            "This is an INCREMENTAL REVIEW. Files marked `[NEW SINCE LAST REVIEW]` contain new changes.\n\n",
        );
        prompt.push_str("**Review Strategy:**\n");
        prompt.push_str("- **TIER 1 (NEW files)**: Report ALL issues found\n");
        prompt.push_str(
            "- **TIER 2 (Previously reviewed)**: Only check if previous issues are fixed\n\n",
        );

        if let Some(issues) = previous_issues {
            prompt.push_str("### Previous Issues to Verify\n\n");
            prompt.push_str(issues);
            prompt.push_str("\n\n");
            prompt.push_str("For each previous issue, mark as:\n");
            prompt.push_str("- `[RESOLVED]` - Issue has been fixed\n");
            prompt.push_str("- `[STILL UNRESOLVED]` - Issue remains\n\n");
        }
    }

    // Comment context (3-tier bucketed)
    if !comment_context.is_empty() {
        prompt.push_str(&comment_context);
        prompt.push_str("\n\n");
    }

    // The diff
    prompt.push_str("## Code Diff\n\n");
    prompt.push_str("```diff\n");
    prompt.push_str(diff);
    prompt.push_str("\n```\n\n");

    // Verification instructions
    prompt.push_str(VERIFICATION_INSTRUCTIONS);

    prompt
}

/// Get project context from README and CONTRIBUTING files
fn get_project_context() -> Option<String> {
    let mut context = String::new();

    // Try to read README
    for readme_name in &["README.md", "README.rst", "README.txt", "README"] {
        if let Ok(content) = fs::read_to_string(readme_name) {
            let truncated = if content.len() > MAX_CONTEXT_CHARS {
                &content[..MAX_CONTEXT_CHARS]
            } else {
                &content
            };
            context.push_str("### README (excerpt)\n\n");
            context.push_str(truncated);
            if content.len() > MAX_CONTEXT_CHARS {
                context.push_str("\n\n[README truncated...]\n");
            }
            context.push_str("\n\n");
            break;
        }
    }

    // Try to read CONTRIBUTING
    if let Ok(content) = fs::read_to_string("CONTRIBUTING.md") {
        let truncated = if content.len() > MAX_CONTEXT_CHARS {
            &content[..MAX_CONTEXT_CHARS]
        } else {
            &content
        };
        context.push_str("### CONTRIBUTING Guidelines (excerpt)\n\n");
        context.push_str(truncated);
        context.push_str("\n\n");
    }

    // Try to read CLAUDE.md for AI-specific instructions
    if Path::new("CLAUDE.md").exists() {
        if let Ok(content) = fs::read_to_string("CLAUDE.md") {
            let truncated = if content.len() > MAX_CONTEXT_CHARS * 2 {
                &content[..MAX_CONTEXT_CHARS * 2]
            } else {
                &content
            };
            context.push_str("### AI Instructions (CLAUDE.md excerpt)\n\n");
            context.push_str(truncated);
            context.push_str("\n\n");
        }
    }

    if context.is_empty() {
        None
    } else {
        Some(context)
    }
}

/// Review output rules
const REVIEW_RULES: &str = r#"# Code Review Instructions

You are reviewing a pull request. Follow these rules strictly:

## Output Format Rules
- Maximum 500 words total
- Use bullet points, not paragraphs
- Only report ACTIONABLE issues (bugs, security vulnerabilities, required fixes)
- NO generic praise ("great work", "well done", etc.)
- NO filler text

## Required Section Structure

Your review MUST use exactly this structure:

```
## Issues (if any)

- [SEVERITY] `filename:line` - Brief description
  - What's wrong
  - How to fix (if obvious)

## Previous Issues (for incremental reviews)

- [RESOLVED] `filename:line` - Issue description
- [STILL UNRESOLVED] `filename:line` - Issue description

## Suggestions (if any)

- `filename:line` - Optional improvement suggestion

## Notes

- Any relevant observations about the changes
- Clarifications about why certain issues were/weren't raised

![Reaction](URL)
```

If a section has no items, write "(none)" under it.

## Issue Severity Levels
- `[CRITICAL]` - Must fix before merge (security, data loss, crashes)
- `[BUG]` - Likely bugs or incorrect behavior
- `[WARNING]` - Potential issues, edge cases

## What NOT to Report
- Style preferences already handled by formatters
- Minor naming suggestions
- "Consider adding tests" (unless critical path)
- Generic advice that doesn't apply to specific code

## Reaction Images
End your review with EXACTLY ONE reaction image from:
https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/

Choose based on review sentiment:
- Positive/clean: kurisu_thumbs_up.webp, aqua_happy.webp
- Minor issues: menhera_stare.webp, thinking_foxgirl.webp
- Significant issues: kagami_annoyed.webp, nervous_sweat.webp
"#;

/// Verification instructions for the AI
const VERIFICATION_INSTRUCTIONS: &str = r#"
## Verification Requirements

Before reporting an issue, you MUST verify it exists in the actual code:
1. Check that the file exists in the diff
2. Verify the line number corresponds to actual problematic code
3. Don't hallucinate issues - only report what you can see

If you're unsure about something:
- State your uncertainty clearly
- Don't make up code that doesn't exist
- Reference only what's shown in the diff
"#;

/// Count words in a string
pub fn count_words(text: &str) -> usize {
    text.split_whitespace().count()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_count_words() {
        assert_eq!(count_words("hello world"), 2);
        assert_eq!(count_words("  multiple   spaces  "), 2);
        assert_eq!(count_words(""), 0);
    }

    #[test]
    fn test_build_prompt() {
        let metadata = PRMetadata {
            number: 123,
            title: "Test PR".to_string(),
            body: "Description".to_string(),
            author: "user".to_string(),
            base_branch: "main".to_string(),
            head_branch: "feature".to_string(),
        };
        let stats = FileStats {
            files_changed: 2,
            lines_added: 10,
            lines_deleted: 5,
        };

        let prompt = build_review_prompt(&metadata, &stats, "diff content", "", false, None);

        assert!(prompt.contains("PR #123"));
        assert!(prompt.contains("Test PR"));
        assert!(prompt.contains("diff content"));
    }
}
