//! Comment validation for Unicode emojis and formatting violations
//!
//! Validates GitHub comments to prevent:
//! 1. Unicode emojis that may display as corrupted characters
//! 2. Formatting patterns that would escape markdown (heredocs, echo piping, etc.)

use once_cell::sync::Lazy;
use regex::Regex;

/// Unicode emoji ranges that may display incorrectly in GitHub
const EMOJI_RANGES: [(u32, u32); 8] = [
    (0x1F600, 0x1F64F), // Emoticons
    (0x1F300, 0x1F5FF), // Misc Symbols and Pictographs
    (0x1F680, 0x1F6FF), // Transport and Map
    (0x1F900, 0x1F9FF), // Supplemental Symbols and Pictographs
    (0x2600, 0x26FF),   // Misc symbols
    (0x2700, 0x27BF),   // Dingbats (includes checkmark)
    (0x1F1E0, 0x1F1FF), // Regional indicator symbols (flags)
    (0x1FA70, 0x1FAFF), // Symbols and Pictographs Extended-A
];

/// Problematic formatting patterns with descriptions
///
/// Note: Only patterns that match argument content are effective here.
/// Shell operators (pipes, heredocs, command substitution) are expanded
/// before the binary receives arguments, so we cannot detect them.
/// The --body patterns below catch direct usage which bypasses --body-file.
static FORMATTING_VIOLATIONS: Lazy<Vec<(Regex, &'static str)>> = Lazy::new(|| {
    vec![
        // Direct --body with reaction images (these work - checks arg content)
        (
            Regex::new(r#"--body\s+["'].*!\[.*\]"#).unwrap(),
            "Direct --body flag with reaction images (use --body-file instead)",
        ),
        (
            Regex::new(r"--body\s+\S*.*!\[.*\]").unwrap(),
            "Direct --body flag with reaction images (use --body-file instead)",
        ),
    ]
});

/// Patterns to detect reaction images in commands
static REACTION_IMAGE_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"(?i)\\?!\[.*\]\(.*reaction.*\)").unwrap(),
        Regex::new(r"(?i)\\?!\[.*\]\(.*githubusercontent.com/AndrewAltimit/Media.*\)").unwrap(),
        Regex::new(r"(?i)\\?!\[Reaction\]").unwrap(),
    ]
});

/// Comment validator
pub struct CommentValidator;

impl CommentValidator {
    /// Check for Unicode emojis in text
    ///
    /// Returns `Some(char)` if an emoji is found, `None` otherwise.
    pub fn check_unicode_emoji(text: &str) -> Option<char> {
        for ch in text.chars() {
            let cp = ch as u32;
            for (start, end) in EMOJI_RANGES.iter() {
                if cp >= *start && cp <= *end {
                    return Some(ch);
                }
            }
        }
        None
    }

    /// Check for problematic formatting patterns
    ///
    /// Returns a list of violation descriptions.
    pub fn check_formatting_violations(command: &str) -> Vec<&'static str> {
        FORMATTING_VIOLATIONS
            .iter()
            .filter(|(regex, _)| regex.is_match(command))
            .map(|(_, desc)| *desc)
            .collect()
    }

    /// Check if command contains reaction images
    pub fn has_reaction_image(command: &str) -> bool {
        REACTION_IMAGE_PATTERNS.iter().any(|r| r.is_match(command))
    }

    /// Check if this is a command that posts content
    pub fn is_posting_content(command: &str) -> bool {
        let posting_indicators = ["--body", "--body-file", "comment", "create"];
        posting_indicators.iter().any(|ind| command.contains(ind))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_emoji() {
        // Common emojis
        assert!(CommentValidator::check_unicode_emoji("Hello \u{1F600}").is_some());
        assert!(CommentValidator::check_unicode_emoji("Check \u{2705}").is_some());
        assert!(CommentValidator::check_unicode_emoji("\u{1F680} Launch").is_some());

        // No emoji
        assert!(CommentValidator::check_unicode_emoji("Plain text").is_none());
        assert!(CommentValidator::check_unicode_emoji("With :emoji: colons").is_none());
    }

    #[test]
    fn test_emoji_ranges() {
        // Test specific ranges
        assert!(CommentValidator::check_unicode_emoji("\u{1F600}").is_some()); // Emoticons
        assert!(CommentValidator::check_unicode_emoji("\u{1F300}").is_some()); // Misc Symbols
        assert!(CommentValidator::check_unicode_emoji("\u{1F680}").is_some()); // Transport
        assert!(CommentValidator::check_unicode_emoji("\u{2600}").is_some()); // Misc
        assert!(CommentValidator::check_unicode_emoji("\u{2700}").is_some()); // Dingbats
    }

    #[test]
    fn test_formatting_violations_direct_body() {
        // Direct --body with reaction images should be flagged
        let violations = CommentValidator::check_formatting_violations(
            "gh pr comment 1 --body '![Reaction](url)'",
        );
        assert!(!violations.is_empty());
        assert!(violations.iter().any(|v| v.contains("--body-file instead")));
    }

    #[test]
    fn test_no_formatting_violations() {
        // Correct method: --body-file
        let violations = CommentValidator::check_formatting_violations(
            "gh pr comment 1 --body-file /tmp/comment.md",
        );
        assert!(violations.is_empty());
    }

    #[test]
    fn test_has_reaction_image() {
        assert!(CommentValidator::has_reaction_image(
            "![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/main/reaction/miku.png)"
        ));
        assert!(CommentValidator::has_reaction_image(
            "![alt](https://example.com/reaction/image.gif)"
        ));
        assert!(CommentValidator::has_reaction_image("![Reaction]"));

        assert!(!CommentValidator::has_reaction_image("Regular text"));
        assert!(!CommentValidator::has_reaction_image(
            "![Image](https://example.com/other.png)"
        ));
    }

    #[test]
    fn test_is_posting_content() {
        assert!(CommentValidator::is_posting_content(
            "gh pr comment 1 --body test"
        ));
        assert!(CommentValidator::is_posting_content(
            "gh pr create --body-file /tmp/pr.md"
        ));
        assert!(CommentValidator::is_posting_content("gh issue comment 1"));

        assert!(!CommentValidator::is_posting_content("gh pr list"));
        assert!(!CommentValidator::is_posting_content("gh pr view 1"));
    }
}
