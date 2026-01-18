//! Review condensation for brevity enforcement.
//!
//! Ensures reviews stay within word limits using a fast model.

use super::agents::ReviewAgent;
use super::prompt::count_words;
use crate::error::Result;

/// Condense a review if it exceeds the threshold
pub async fn condense_if_needed(
    review: &str,
    max_words: usize,
    threshold: usize,
    agent: &dyn ReviewAgent,
) -> Result<String> {
    let word_count = count_words(review);

    if word_count <= threshold {
        tracing::debug!(
            "Review has {} words, under threshold of {}",
            word_count,
            threshold
        );
        return Ok(review.to_string());
    }

    tracing::info!(
        "Review has {} words, exceeds threshold of {}. Condensing...",
        word_count,
        threshold
    );

    let condensed = agent.condense(review, max_words).await?;
    let new_count = count_words(&condensed);

    tracing::info!(
        "Condensed review from {} to {} words",
        word_count,
        new_count
    );

    Ok(condensed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_count_words() {
        assert_eq!(count_words("one two three"), 3);
        assert_eq!(count_words(""), 0);
    }
}
