//! Comment validation for Unicode emojis and formatting violations
//!
//! Validates GitHub comments to prevent:
//! 1. Unicode emojis that may display as corrupted characters
//! 2. Direct --body/-b usage with reaction images (should use --body-file)
//!
//! This module operates directly on argument vectors for robust validation,
//! avoiding fragile command string reconstruction.

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

/// Patterns to detect reaction images in content
static REACTION_IMAGE_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"(?i)\\?!\[.*\]\(.*reaction.*\)").unwrap(),
        Regex::new(r"(?i)\\?!\[.*\]\(.*githubusercontent.com/AndrewAltimit/Media.*\)").unwrap(),
        Regex::new(r"(?i)\\?!\[Reaction\]").unwrap(),
    ]
});

/// Flags that directly embed body content (not file-based)
const DIRECT_BODY_FLAGS: &[&str] = &["--body", "-b"];

/// Flags that indicate content posting (for emoji checks)
const CONTENT_FLAGS: &[&str] = &[
    "--body",
    "-b",
    "--body-file",
    "-F",
    "--message",
    "-m",
    "--title",
    "-t",
    "--notes",
    "-n",
];

/// Comment validator - operates on argument vectors directly
pub struct CommentValidator;

impl CommentValidator {
    /// Check for Unicode emojis in argument values
    ///
    /// Scans all arguments for emoji characters. Returns the first emoji found.
    pub fn check_unicode_emoji_in_args(args: &[String]) -> Option<char> {
        for arg in args {
            if let Some(emoji) = Self::check_unicode_emoji(arg) {
                return Some(emoji);
            }
        }
        None
    }

    /// Check for Unicode emojis in a single string
    fn check_unicode_emoji(text: &str) -> Option<char> {
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

    /// Check for formatting violations by inspecting args directly
    ///
    /// Returns a violation description if --body or -b is used with reaction images.
    /// The correct approach is to use --body-file with reaction images.
    pub fn check_formatting_violations_in_args(args: &[String]) -> Option<&'static str> {
        let mut iter = args.iter().peekable();

        while let Some(arg) = iter.next() {
            // Check --body=value or -b=value (equals syntax)
            for flag in DIRECT_BODY_FLAGS {
                if let Some(value) = arg.strip_prefix(&format!("{}=", flag)) {
                    if Self::content_has_reaction_image(value) {
                        return Some(
                            "Direct body flag with reaction images (use --body-file instead)",
                        );
                    }
                }
            }

            // Check --body value or -b value (space-separated)
            if DIRECT_BODY_FLAGS.contains(&arg.as_str()) {
                if let Some(value) = iter.next() {
                    if Self::content_has_reaction_image(value) {
                        return Some(
                            "Direct body flag with reaction images (use --body-file instead)",
                        );
                    }
                }
            }
        }

        None
    }

    /// Check if content contains a reaction image
    fn content_has_reaction_image(content: &str) -> bool {
        REACTION_IMAGE_PATTERNS.iter().any(|r| r.is_match(content))
    }

    /// Check if args indicate content posting (for determining if emoji check needed)
    pub fn args_post_content(args: &[String]) -> bool {
        args.iter().any(|arg| {
            // Check exact match
            if CONTENT_FLAGS.contains(&arg.as_str()) {
                return true;
            }
            // Check --flag=value syntax
            for flag in CONTENT_FLAGS {
                if arg.starts_with(&format!("{}=", flag)) {
                    return true;
                }
            }
            // Check for comment/create subcommands
            arg == "comment" || arg == "create"
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn to_args(strs: &[&str]) -> Vec<String> {
        strs.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn test_detect_emoji_in_args() {
        // Emoji in body content
        let args = to_args(&["pr", "comment", "--body", "Hello \u{1F600}"]);
        assert!(CommentValidator::check_unicode_emoji_in_args(&args).is_some());

        // Emoji in title
        let args = to_args(&["pr", "create", "--title", "\u{1F680} Launch"]);
        assert!(CommentValidator::check_unicode_emoji_in_args(&args).is_some());

        // No emoji
        let args = to_args(&["pr", "comment", "--body", "Plain text"]);
        assert!(CommentValidator::check_unicode_emoji_in_args(&args).is_none());

        // GitHub emoji shortcodes are fine
        let args = to_args(&["pr", "comment", "--body", "Check :white_check_mark:"]);
        assert!(CommentValidator::check_unicode_emoji_in_args(&args).is_none());
    }

    #[test]
    fn test_emoji_ranges() {
        assert!(CommentValidator::check_unicode_emoji("\u{1F600}").is_some()); // Emoticons
        assert!(CommentValidator::check_unicode_emoji("\u{1F300}").is_some()); // Misc Symbols
        assert!(CommentValidator::check_unicode_emoji("\u{1F680}").is_some()); // Transport
        assert!(CommentValidator::check_unicode_emoji("\u{2600}").is_some()); // Misc
        assert!(CommentValidator::check_unicode_emoji("\u{2700}").is_some()); // Dingbats
    }

    #[test]
    fn test_formatting_violations_direct_body_space_separated() {
        // --body with reaction image should be flagged
        let args = to_args(&[
            "pr",
            "comment",
            "1",
            "--body",
            "![Reaction](https://example.com/reaction/img.png)",
        ]);
        assert!(CommentValidator::check_formatting_violations_in_args(&args).is_some());
    }

    #[test]
    fn test_formatting_violations_direct_body_equals() {
        // --body= with reaction image should be flagged
        let args = to_args(&[
            "pr",
            "comment",
            "1",
            "--body=![Reaction](https://example.com/reaction/img.png)",
        ]);
        assert!(CommentValidator::check_formatting_violations_in_args(&args).is_some());
    }

    #[test]
    fn test_formatting_violations_short_flag_space_separated() {
        // -b with reaction image should be flagged
        let args = to_args(&[
            "pr",
            "comment",
            "1",
            "-b",
            "![Reaction](https://example.com/reaction/img.png)",
        ]);
        assert!(CommentValidator::check_formatting_violations_in_args(&args).is_some());
    }

    #[test]
    fn test_formatting_violations_short_flag_equals() {
        // -b= with reaction image should be flagged
        let args = to_args(&[
            "pr",
            "comment",
            "1",
            "-b=![Reaction](https://example.com/reaction/img.png)",
        ]);
        assert!(CommentValidator::check_formatting_violations_in_args(&args).is_some());
    }

    #[test]
    fn test_no_formatting_violations_body_file() {
        // --body-file is the correct approach - no violation
        let args = to_args(&["pr", "comment", "1", "--body-file", "/tmp/comment.md"]);
        assert!(CommentValidator::check_formatting_violations_in_args(&args).is_none());
    }

    #[test]
    fn test_no_formatting_violations_plain_text() {
        // Plain text without reaction images is fine
        let args = to_args(&["pr", "comment", "1", "--body", "Just some text"]);
        assert!(CommentValidator::check_formatting_violations_in_args(&args).is_none());
    }

    #[test]
    fn test_args_post_content() {
        // Various content flags
        assert!(CommentValidator::args_post_content(&to_args(&[
            "pr", "comment", "--body", "test"
        ])));
        assert!(CommentValidator::args_post_content(&to_args(&[
            "pr", "comment", "-b", "test"
        ])));
        assert!(CommentValidator::args_post_content(&to_args(&[
            "pr",
            "create",
            "--body-file",
            "/tmp/pr.md"
        ])));
        assert!(CommentValidator::args_post_content(&to_args(&[
            "issue", "comment", "1"
        ])));

        // No content flags
        assert!(!CommentValidator::args_post_content(&to_args(&[
            "pr", "list"
        ])));
        assert!(!CommentValidator::args_post_content(&to_args(&[
            "pr", "view", "1"
        ])));
    }

    #[test]
    fn test_args_post_content_equals_syntax() {
        assert!(CommentValidator::args_post_content(&to_args(&[
            "pr",
            "comment",
            "--body=test"
        ])));
        assert!(CommentValidator::args_post_content(&to_args(&[
            "pr", "comment", "-b=test"
        ])));
    }
}
