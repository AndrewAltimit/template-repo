//! Content checks for text posted to GitHub.
//!
//! - **Unicode emoji** are rejected: repository policy is ASCII-only
//!   comments (GitHub `:shortcodes:` are fine). Detection covers the emoji
//!   blocks, emoji-presentation selectors, keycaps, and Unicode *tag*
//!   characters (also used for invisible "ASCII smuggling" of instructions).
//! - **Escaped emoji** (`\ud83d\ude00`, `\u{1F600}`) are rejected in raw
//!   API payloads, where JSON/GraphQL would decode them server-side.
//! - **Reaction images passed inline** (`--body '![Reaction](...)'`) are
//!   rejected: shells mangle `!` so these must go through `--body-file`.
//! - **@mentions** of anyone but the allow-listed maintainer are neutralized
//!   by wrapping them in backticks (no notification is sent). Code spans,
//!   fenced code blocks, e-mail addresses, and URLs are left alone.

use regex::Regex;
use std::sync::LazyLock;

/// Code points (inclusive ranges) treated as emoji.
const EMOJI_RANGES: &[(u32, u32)] = &[
    (0x1F000, 0x1FAFF), // Mahjong .. Symbols and Pictographs Extended-A
    (0x2600, 0x27BF),   // Misc Symbols, Dingbats (includes check marks)
    (0x2B05, 0x2B07),   // arrows
    (0x2B1B, 0x2B1C),   // large squares
    (0x2B50, 0x2B50),   // star
    (0x2B55, 0x2B55),   // circle
    (0x231A, 0x231B),   // watch, hourglass
    (0x2328, 0x2328),   // keyboard
    (0x23CF, 0x23CF),   // eject
    (0x23E9, 0x23F3),   // media controls, clocks
    (0x23F8, 0x23FA),   // media controls
    (0x25AA, 0x25AB),   // small squares
    (0x25B6, 0x25B6),   // play
    (0x25C0, 0x25C0),   // reverse
    (0x25FB, 0x25FE),   // medium squares
    (0x2934, 0x2935),   // curved arrows
    (0x3030, 0x3030),   // wavy dash
    (0x303D, 0x303D),   // part alternation mark
    (0x3297, 0x3297),   // circled ideograph congratulation
    (0x3299, 0x3299),   // circled ideograph secret
    (0x20E3, 0x20E3),   // combining enclosing keycap
    (0xFE0F, 0xFE0F),   // emoji presentation selector
    (0xE0000, 0xE007F), // tag characters (flag sequences, ASCII smuggling)
];

/// Handles that may be @mentioned when no config overrides the list.
pub const DEFAULT_ALLOWED_MENTIONS: &[&str] = &["AndrewAltimit"];

static REACTION_IMAGE_PATTERNS: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    [
        r"(?i)\\?!\[[^\]]*\]\([^)]*reaction[^)]*\)",
        r"(?i)\\?!\[[^\]]*\]\([^)]*githubusercontent\.com/AndrewAltimit/Media[^)]*\)",
        r"(?i)\\?!\[Reaction\]",
    ]
    .iter()
    .map(|p| Regex::new(p).expect("static regex"))
    .collect()
});

/// Whether a code point is treated as an emoji.
pub fn is_emoji(c: char) -> bool {
    let cp = c as u32;
    EMOJI_RANGES.iter().any(|&(lo, hi)| (lo..=hi).contains(&cp))
}

/// First emoji in `text`, if any.
pub fn find_emoji(text: &str) -> Option<char> {
    text.chars().find(|&c| is_emoji(c))
}

/// First emoji in any argument.
pub fn find_emoji_in_args(args: &[String]) -> Option<char> {
    args.iter().find_map(|a| find_emoji(a))
}

/// First emoji written as an escape sequence: `\uXXXX` (with UTF-16
/// surrogate pairs, as in JSON) or `\u{XXXXX}` (GraphQL / JS style).
pub fn find_escaped_emoji(text: &str) -> Option<char> {
    let bytes = text.as_bytes();
    let mut i = 0;
    let mut pending_high: Option<u32> = None;
    while i + 1 < bytes.len() {
        if bytes[i] != b'\\' || bytes[i + 1] != b'u' {
            i += 1;
            pending_high = None;
            continue;
        }
        let start = i + 2;
        let (cp, next) = if bytes.get(start) == Some(&b'{') {
            let Some(end) = text[start + 1..].find('}') else {
                break;
            };
            let hex = &text[start + 1..start + 1 + end];
            (u32::from_str_radix(hex, 16).ok(), start + 2 + end)
        } else {
            let hex = text.get(start..start + 4).unwrap_or("");
            (
                (hex.len() == 4)
                    .then(|| u32::from_str_radix(hex, 16).ok())
                    .flatten(),
                start + 4,
            )
        };
        i = next.max(i + 2);
        let Some(cp) = cp else {
            pending_high = None;
            continue;
        };
        let cp = match (pending_high.take(), cp) {
            (_, 0xD800..=0xDBFF) => {
                pending_high = Some(cp);
                continue;
            },
            (Some(hi), 0xDC00..=0xDFFF) => 0x10000 + ((hi - 0xD800) << 10) + (cp - 0xDC00),
            (_, cp) => cp,
        };
        if let Some(c) = char::from_u32(cp)
            && is_emoji(c)
        {
            return Some(c);
        }
    }
    None
}

/// Whether text contains a markdown reaction image.
pub fn has_reaction_image(text: &str) -> bool {
    REACTION_IMAGE_PATTERNS.iter().any(|r| r.is_match(text))
}

/// Wrap @mentions of non-allowed handles in backticks so GitHub renders
/// them as code and sends no notification.
///
/// Returns the new text and the neutralized mentions (empty if unchanged).
pub fn neutralize_mentions(text: &str, allowed: &[String]) -> (String, Vec<String>) {
    let mut out = String::with_capacity(text.len());
    let mut found = Vec::new();
    let mut in_fence: Option<String> = None;

    for line in text.split_inclusive('\n') {
        let trimmed = line.trim_start();
        let fence = fence_marker(trimmed);
        if let Some(open) = &in_fence {
            if fence
                .as_deref()
                .is_some_and(|f| f.starts_with(open.as_str()))
            {
                in_fence = None;
            }
            out.push_str(line);
            continue;
        }
        if let Some(f) = fence {
            in_fence = Some(f);
            out.push_str(line);
            continue;
        }
        neutralize_line(line, allowed, &mut out, &mut found);
    }
    (out, found)
}

/// Opening/closing code fence marker (``` or ~~~, 3+ chars).
fn fence_marker(line: &str) -> Option<String> {
    for ch in ['`', '~'] {
        let n = line.chars().take_while(|&c| c == ch).count();
        if n >= 3 {
            return Some(std::iter::repeat_n(ch, n).collect());
        }
    }
    None
}

fn neutralize_line(line: &str, allowed: &[String], out: &mut String, found: &mut Vec<String>) {
    let chars: Vec<(usize, char)> = line.char_indices().collect();
    let mut k = 0;
    let mut copied_to = 0;
    while k < chars.len() {
        let (pos, c) = chars[k];
        // Skip inline code spans: a run of N backticks up to the next run
        // of exactly N backticks.
        if c == '`' {
            let run = chars[k..].iter().take_while(|(_, ch)| *ch == '`').count();
            let mut j = k + run;
            let mut closed = None;
            while j < chars.len() {
                if chars[j].1 == '`' {
                    let r = chars[j..].iter().take_while(|(_, ch)| *ch == '`').count();
                    if r == run {
                        closed = Some(j + r);
                        break;
                    }
                    j += r;
                } else {
                    j += 1;
                }
            }
            k = closed.unwrap_or(k + run);
            continue;
        }
        if c == '@' && mention_boundary(k.checked_sub(1).map(|p| chars[p].1)) {
            let end = mention_end(&chars, k + 1);
            if end > k + 1 {
                let handle_end = chars.get(end).map_or(line.len(), |(p, _)| *p);
                let mention = &line[pos..handle_end];
                let user = mention[1..].split('/').next().unwrap_or("");
                if !allowed.iter().any(|a| a.eq_ignore_ascii_case(user)) {
                    out.push_str(&line[copied_to..pos]);
                    out.push('`');
                    out.push_str(mention);
                    out.push('`');
                    copied_to = handle_end;
                    found.push(mention.to_string());
                }
                k = end;
                continue;
            }
        }
        k += 1;
    }
    out.push_str(&line[copied_to..]);
}

/// GitHub only links a mention not preceded by a word character, and we
/// also skip `/`, `.`, `-`, `+`, `=` so URLs, paths, and e-mails stay intact.
fn mention_boundary(prev: Option<char>) -> bool {
    match prev {
        None => true,
        Some(c) => !(c.is_alphanumeric() || "_@/.-+=`".contains(c)),
    }
}

/// End (exclusive char index) of `user` or `org/team` starting at `start`.
fn mention_end(chars: &[(usize, char)], start: usize) -> usize {
    let is_handle = |c: char| c.is_ascii_alphanumeric() || c == '-';
    let mut j = start;
    if !chars.get(j).is_some_and(|(_, c)| c.is_ascii_alphanumeric()) {
        return start;
    }
    while j < chars.len() && is_handle(chars[j].1) && j - start < 39 {
        j += 1;
    }
    // Trailing hyphens are not part of a handle.
    while j > start && chars[j - 1].1 == '-' {
        j -= 1;
    }
    // Team mention: @org/team
    if chars.get(j).is_some_and(|(_, c)| *c == '/') {
        let mut t = j + 1;
        while t < chars.len()
            && (chars[t].1.is_ascii_alphanumeric() || matches!(chars[t].1, '-' | '_' | '.'))
        {
            t += 1;
        }
        if t > j + 1 {
            j = t;
        }
    }
    j
}

#[cfg(test)]
mod tests {
    use super::*;

    fn allowed() -> Vec<String> {
        DEFAULT_ALLOWED_MENTIONS
            .iter()
            .map(|s| s.to_string())
            .collect()
    }

    #[test]
    fn emoji_ranges() {
        for c in [
            '\u{1F600}',
            '\u{1F300}',
            '\u{1F680}',
            '\u{1F916}',
            '\u{2600}',
            '\u{2705}',
            '\u{2714}',
            '\u{2B50}',
            '\u{23F3}',
            '\u{1F7E2}',
            '\u{1FA77}',
            '\u{1F1FA}',
            '\u{FE0F}',
            '\u{E0041}',
            '\u{1F004}',
        ] {
            assert!(is_emoji(c), "U+{:04X}", c as u32);
        }
        for c in [
            'a', '-', '>', '\u{2192}', '\u{00E9}', '\u{4E2D}', '\u{2014}', '\u{00A9}',
        ] {
            assert!(!is_emoji(c), "U+{:04X}", c as u32);
        }
    }

    #[test]
    fn emoji_in_args_and_text() {
        let args: Vec<String> = ["pr", "comment", "--body", "Hello \u{1F600}"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        assert_eq!(find_emoji_in_args(&args), Some('\u{1F600}'));
        assert!(find_emoji("Check :white_check_mark: -> done").is_none());
        assert!(find_emoji("## Summary\n\n\u{1F916} Generated with Claude Code\n").is_some());
    }

    #[test]
    fn escaped_emoji() {
        assert_eq!(
            find_escaped_emoji(r#"{"body":"hi \ud83d\ude00"}"#),
            Some('\u{1F600}')
        );
        assert_eq!(
            find_escaped_emoji(r#"{"body":"\ud83e\udd16"}"#),
            Some('\u{1F916}')
        );
        assert_eq!(find_escaped_emoji(r"body: \u{2705}"), Some('\u{2705}'));
        assert_eq!(find_escaped_emoji(r#"{"a":"\u00e9\u2192\n"}"#), None);
        assert_eq!(find_escaped_emoji(r"\u12"), None);
        assert_eq!(find_escaped_emoji(r"\u{zz} \u"), None);
        assert_eq!(find_escaped_emoji("\\u{1F600"), None);
    }

    #[test]
    fn reaction_images() {
        assert!(has_reaction_image(
            "![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/x.webp)"
        ));
        assert!(has_reaction_image(
            r"\![Reaction](https://example.com/a.png)"
        ));
        assert!(!has_reaction_image("![diagram](https://example.com/a.png)"));
        assert!(!has_reaction_image("plain text"));
    }

    fn neutral(text: &str) -> (String, Vec<String>) {
        neutralize_mentions(text, &allowed())
    }

    #[test]
    fn mentions_are_neutralized() {
        let (t, f) = neutral("Thanks @octocat and @some-org/team!");
        assert_eq!(t, "Thanks `@octocat` and `@some-org/team`!");
        assert_eq!(f, vec!["@octocat", "@some-org/team"]);

        let (t, _) = neutral("@octocat: see (cc @hubot)");
        assert_eq!(t, "`@octocat`: see (cc `@hubot`)");
    }

    #[test]
    fn allowed_mentions_kept() {
        let (t, f) = neutral("cc @AndrewAltimit and @andrewaltimit");
        assert_eq!(t, "cc @AndrewAltimit and @andrewaltimit");
        assert!(f.is_empty());
    }

    #[test]
    fn non_mentions_untouched() {
        for text in [
            "mail me at user@example.com",
            "see https://medium.com/@author/post",
            "npm i some/@scope",
            "already `@octocat` quoted",
            "``code with `@x` inside``",
            "a lone @ sign",
            "@-dash",
        ] {
            let (t, f) = neutral(text);
            assert_eq!(t, text);
            assert!(f.is_empty(), "{text}");
        }
    }

    #[test]
    fn fenced_code_is_untouched() {
        let text =
            "Before @one\n```python\n@decorator\ndef f(): pass\n```\nAfter @two\n~~~\n@x\n~~~\n";
        let (t, f) = neutral(text);
        assert_eq!(
            t,
            "Before `@one`\n```python\n@decorator\ndef f(): pass\n```\nAfter `@two`\n~~~\n@x\n~~~\n"
        );
        assert_eq!(f, vec!["@one", "@two"]);
    }

    #[test]
    fn mention_handles_unicode_neighbours() {
        let (t, _) = neutral("\u{00E9}t\u{00E9} @octocat \u{2192} ok");
        assert_eq!(t, "\u{00E9}t\u{00E9} `@octocat` \u{2192} ok");
    }
}
