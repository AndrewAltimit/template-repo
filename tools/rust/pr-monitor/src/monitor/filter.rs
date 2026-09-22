//! Which comments the monitor reports

use crate::analysis::{
    Classification, DEFAULT_ADMIN_USER, ResponseType, classify, is_agent_generated,
    is_relevant_author, logins_match, user_comment,
};
use crate::github::Comment;

/// Author / type filter applied on top of classification
#[derive(Debug, Clone)]
pub struct Filter {
    /// Admin login (commands and feedback from this user are always relevant)
    pub admin_user: String,
    /// If non-empty, only comments from these logins are considered
    /// (replaces the default admin + review-bot set)
    pub authors: Vec<String>,
    /// If non-empty, only these response types are reported
    pub types: Vec<ResponseType>,
}

impl Default for Filter {
    fn default() -> Self {
        Self::new(DEFAULT_ADMIN_USER)
    }
}

impl Filter {
    /// Default filter: admin user plus review bots, all response types
    pub fn new(admin_user: &str) -> Self {
        Self {
            admin_user: admin_user.to_string(),
            authors: Vec::new(),
            types: Vec::new(),
        }
    }

    /// Whether comments from `login` are watched at all
    pub fn watches_author(&self, login: &str) -> bool {
        if self.authors.is_empty() {
            is_relevant_author(login, &self.admin_user)
        } else {
            self.authors.iter().any(|a| logins_match(a, login))
        }
    }

    /// Classify `comment` and return the classification if it should be reported
    pub fn evaluate(&self, comment: &Comment) -> Option<Classification> {
        if !self.watches_author(&comment.author.login) {
            return None;
        }

        let mut classification = classify(comment, &self.admin_user);
        if !classification.is_recognized() {
            // Explicitly watched authors get a generic classification for
            // any human-written comment with content.
            let explicit = !self.authors.is_empty();
            let has_content =
                !comment.body.trim().is_empty() || !comment.inline_comments.is_empty();
            if explicit && has_content && !is_agent_generated(&comment.body) {
                classification = user_comment();
            } else {
                return None;
            }
        }

        let kind = classification.response_type?;
        if !self.types.is_empty() && !self.types.contains(&kind) {
            return None;
        }
        Some(classification)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn comment(author: &str, body: &str) -> Comment {
        Comment::new(author, body, Utc::now())
    }

    #[test]
    fn test_default_filter() {
        let f = Filter::new("Admin");
        assert!(f.evaluate(&comment("Admin", "please fix")).is_some());
        assert!(f.evaluate(&comment("stranger", "please fix")).is_none());
        assert!(
            f.evaluate(&comment(
                "github-actions[bot]",
                "## Claude AI Code Review\nok"
            ))
            .is_some()
        );
        assert!(
            f.evaluate(&comment("github-actions[bot]", "Preview deployed"))
                .is_none()
        );
    }

    #[test]
    fn test_type_filter() {
        let mut f = Filter::new("Admin");
        f.types = vec![ResponseType::AiAgentReview];
        assert!(f.evaluate(&comment("Admin", "please fix")).is_none());
        assert!(
            f.evaluate(&comment(
                "github-actions[bot]",
                "## PR Validation Results\nAll checks passed"
            ))
            .is_none()
        );
        let c = f
            .evaluate(&comment(
                "github-actions[bot]",
                "<!-- openrouter-review-marker:commit:abc -->",
            ))
            .unwrap();
        assert_eq!(c.response_type, Some(ResponseType::AiAgentReview));
    }

    #[test]
    fn test_author_filter_restricts_and_widens() {
        let mut f = Filter::new("Admin");
        f.authors = vec!["Collaborator".to_string()];

        // Admin is no longer watched
        assert!(f.evaluate(&comment("Admin", "please fix")).is_none());

        // Explicit author gets a generic classification
        let c = f.evaluate(&comment("collaborator", "question?")).unwrap();
        assert_eq!(c.response_type, Some(ResponseType::UserComment));
        assert!(c.needs_response);

        // ...but not for empty or agent-generated bodies
        assert!(f.evaluate(&comment("Collaborator", "   ")).is_none());
        assert!(
            f.evaluate(&comment(
                "Collaborator",
                "<!-- agent-metadata:type=review-fix:iteration=1 -->"
            ))
            .is_none()
        );
    }

    #[test]
    fn test_author_filter_keeps_specific_classification() {
        let mut f = Filter::new("Admin");
        f.authors = vec!["github-actions".to_string()];
        let c = f
            .evaluate(&comment(
                "github-actions[bot]",
                "## Claude AI Code Review\nok",
            ))
            .unwrap();
        assert_eq!(c.response_type, Some(ResponseType::AiAgentReview));
    }
}
