//! Editor pass for cleaning up PR reviews.
//!
//! This module provides an optional second pass to clean up reviews
//! that don't follow the expected format.

use crate::error::Result;
use crate::review::agents::ReviewAgent;

/// Prompt for the editor pass
const EDITOR_PROMPT: &str = "You are an editor cleaning up a PR review. Your job is to:

1. Remove ALL internal reasoning, chain-of-thought, or process narration such as:
   - \"I will begin by...\", \"Let me check...\", \"I'll read...\"
   - \"First I need to verify...\", \"Now I'll search for...\"
   - File reading narration, tool usage narration
   - Any text that describes your process rather than the review itself

2. Ensure the review follows this EXACT structure:

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

![Reaction](URL)

3. If a section has no items, write \"(none)\" under it.

4. Keep ONLY the final review sections. Start directly with the Issues or Previous Issues section.

5. Preserve all technical content, file references, line numbers, and the reaction image.

6. Maximum 500 words.

Here is the review to clean up:

---

";

/// Run an editor pass on a review to clean up formatting.
pub async fn edit_review(review: &str, editor_agent: &dyn ReviewAgent) -> Result<String> {
    let prompt = format!("{}{}", EDITOR_PROMPT, review);

    tracing::info!("Running editor pass with {}", editor_agent.name());
    let edited = editor_agent.review(&prompt).await?;

    // Basic validation: ensure we got something back
    if edited.trim().is_empty() {
        tracing::warn!("Editor returned empty review, using original");
        return Ok(review.to_string());
    }

    // Check if edit actually starts with expected content
    let trimmed = edited.trim();
    if !trimmed.starts_with("## ") && !trimmed.starts_with("# ") {
        tracing::warn!("Editor output doesn't start with section header, using original");
        return Ok(review.to_string());
    }

    Ok(edited)
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_editor_prompt_contains_structure() {
        assert!(super::EDITOR_PROMPT.contains("## Issues"));
        assert!(super::EDITOR_PROMPT.contains("## Suggestions"));
        assert!(super::EDITOR_PROMPT.contains("## Notes"));
    }
}
