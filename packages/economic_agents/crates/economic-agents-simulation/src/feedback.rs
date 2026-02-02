//! Feedback generation for task submissions.

/// Generates realistic feedback for task submissions.
pub struct FeedbackGenerator;

impl FeedbackGenerator {
    /// Generate feedback for a submission.
    pub fn generate(quality_score: f64) -> FeedbackResult {
        use rand::seq::SliceRandom;
        let mut rng = rand::thread_rng();

        let (status, feedback) = if quality_score >= 0.9 {
            let options = [
                "Exceptional work! Exceeded expectations.",
                "Outstanding quality. Highly recommended.",
                "Perfect execution. No revisions needed.",
            ];
            (
                FeedbackStatus::Excellent,
                options
                    .choose(&mut rng)
                    .expect("feedback options array is non-empty")
                    .to_string(),
            )
        } else if quality_score >= 0.7 {
            let options = [
                "Good work overall. Minor improvements possible.",
                "Solid submission. Meets requirements well.",
                "Quality work with attention to detail.",
            ];
            (
                FeedbackStatus::Good,
                options
                    .choose(&mut rng)
                    .expect("feedback options array is non-empty")
                    .to_string(),
            )
        } else if quality_score >= 0.5 {
            let options = [
                "Acceptable work. Some areas need improvement.",
                "Meets basic requirements. Room for growth.",
                "Passable but could use more polish.",
            ];
            (
                FeedbackStatus::Acceptable,
                options
                    .choose(&mut rng)
                    .expect("feedback options array is non-empty")
                    .to_string(),
            )
        } else {
            let options = [
                "Does not meet requirements. Please revise.",
                "Significant issues found. Needs rework.",
                "Quality below expectations. Review guidelines.",
            ];
            (
                FeedbackStatus::NeedsImprovement,
                options
                    .choose(&mut rng)
                    .expect("feedback options array is non-empty")
                    .to_string(),
            )
        };

        FeedbackResult {
            status,
            feedback,
            quality_score,
            reward_multiplier: quality_score.max(0.5), // Minimum 50% reward
        }
    }
}

/// Feedback status categories.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FeedbackStatus {
    Excellent,
    Good,
    Acceptable,
    NeedsImprovement,
}

/// Result of feedback generation.
#[derive(Debug, Clone)]
pub struct FeedbackResult {
    pub status: FeedbackStatus,
    pub feedback: String,
    pub quality_score: f64,
    pub reward_multiplier: f64,
}
