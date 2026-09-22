//! UTF-8 safe text helpers.
//!
//! GitHub content (issue bodies, comments, agent output) is arbitrary UTF-8.
//! Slicing it with `&s[..n]` panics when `n` falls inside a multi-byte
//! character, so every truncation in this crate goes through these helpers.

/// Return the longest prefix of `s` that is at most `max_bytes` long and ends
/// on a character boundary.
pub fn truncate_str(s: &str, max_bytes: usize) -> &str {
    &s[..s.floor_char_boundary(max_bytes)]
}

/// Truncate `s` to at most `max_bytes` bytes, appending `suffix` when
/// anything was cut off.
pub fn truncate_with_suffix(s: &str, max_bytes: usize, suffix: &str) -> String {
    if s.len() <= max_bytes {
        s.to_string()
    } else {
        format!("{}{}", truncate_str(s, max_bytes), suffix)
    }
}

/// Truncate a `String` in place to at most `max_bytes` bytes on a character
/// boundary.
pub fn truncate_string(s: &mut String, max_bytes: usize) {
    let boundary = s.floor_char_boundary(max_bytes);
    s.truncate(boundary);
}

/// Truncate at the last newline before `max_bytes` (falling back to a plain
/// character-boundary cut when there is no newline).
pub fn truncate_at_line_boundary(text: &str, max_bytes: usize) -> &str {
    if text.len() <= max_bytes {
        return text;
    }
    let slice = truncate_str(text, max_bytes);
    match slice.rfind('\n') {
        Some(pos) => &text[..pos],
        None => slice,
    }
}

/// Uppercase the first character of `s`.
pub fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
        None => String::new(),
    }
}

/// Strip ANSI escape sequences (CSI `ESC [ ... letter` and bare `ESC x`)
/// from CLI output.
pub fn strip_ansi_codes(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();

    while let Some(c) = chars.next() {
        if c != '\x1b' {
            result.push(c);
            continue;
        }
        match chars.peek() {
            Some('[') => {
                chars.next();
                // CSI: parameters/intermediates end with a byte in 0x40..=0x7E
                for next in chars.by_ref() {
                    if ('\x40'..='\x7e').contains(&next) {
                        break;
                    }
                }
            },
            Some(']') => {
                chars.next();
                // OSC: terminated by BEL or ESC \
                while let Some(next) = chars.next() {
                    if next == '\x07' {
                        break;
                    }
                    if next == '\x1b' && chars.peek() == Some(&'\\') {
                        chars.next();
                        break;
                    }
                }
            },
            Some(_) => {
                // Two-character escape: drop the following char
                chars.next();
            },
            None => {},
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn truncate_str_respects_char_boundaries() {
        let s = "ab\u{00e9}cd"; // e-acute is 2 bytes (bytes 2..4)
        assert_eq!(truncate_str(s, 3), "ab");
        assert_eq!(truncate_str(s, 4), "ab\u{00e9}");
        assert_eq!(truncate_str(s, 100), s);
        assert_eq!(truncate_str("", 5), "");
    }

    #[test]
    fn truncate_with_suffix_only_when_cut() {
        assert_eq!(truncate_with_suffix("hello", 10, "..."), "hello");
        assert_eq!(truncate_with_suffix("hello", 3, "..."), "hel...");
        // 4-byte char must not be split
        assert_eq!(truncate_with_suffix("a\u{1F600}b", 3, "..."), "a...");
    }

    #[test]
    fn truncate_string_in_place() {
        let mut s = String::from("x\u{00e9}\u{00e9}");
        truncate_string(&mut s, 2);
        assert_eq!(s, "x");
    }

    #[test]
    fn line_boundary_truncation() {
        assert_eq!(
            truncate_at_line_boundary("hello\nworld", 100),
            "hello\nworld"
        );
        assert_eq!(
            truncate_at_line_boundary("line1\nline2\nline3", 10),
            "line1"
        );
        assert_eq!(truncate_at_line_boundary("noline", 3), "nol");
        assert_eq!(
            truncate_at_line_boundary("hello\n\u{1F389}world\nend", 8),
            "hello"
        );
    }

    #[test]
    fn capitalize_works() {
        assert_eq!(capitalize("claude"), "Claude");
        assert_eq!(capitalize(""), "");
    }

    #[test]
    fn strips_ansi() {
        assert_eq!(
            strip_ansi_codes("\x1b[32mGreen text\x1b[0m and normal"),
            "Green text and normal"
        );
        assert_eq!(strip_ansi_codes("\x1b[?25lhidden"), "hidden");
        assert_eq!(strip_ansi_codes("\x1b]0;title\x07body"), "body");
        assert_eq!(strip_ansi_codes("plain"), "plain");
    }
}
