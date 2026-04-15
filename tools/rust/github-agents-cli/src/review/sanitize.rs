//! Content sanitization for PR review comments.
//!
//! Strips Unicode emojis that gh-validator rejects, replacing them with
//! ASCII equivalents where possible so the review can still be posted.

/// Unicode emoji ranges that gh-validator rejects.
///
/// Must stay in sync with `gh-validator::validation::comments::EMOJI_RANGES`.
const EMOJI_RANGES: [(u32, u32); 8] = [
    (0x1F600, 0x1F64F), // Emoticons
    (0x1F300, 0x1F5FF), // Misc Symbols and Pictographs
    (0x1F680, 0x1F6FF), // Transport and Map
    (0x1F900, 0x1F9FF), // Supplemental Symbols and Pictographs
    (0x2600, 0x26FF),   // Misc symbols
    (0x2700, 0x27BF),   // Dingbats (includes checkmark U+2705)
    (0x1F1E0, 0x1F1FF), // Regional indicator symbols (flags)
    (0x1FA70, 0x1FAFF), // Symbols and Pictographs Extended-A
];

/// Invisible joiner/selector codepoints that glue emoji sequences together.
///
/// Not in `EMOJI_RANGES` (and not rejected by gh-validator) but if we strip
/// the visible parts of a ZWJ sequence like `\u{1F468}\u{200D}\u{1F4BB}`
/// (man technologist) we'd leave orphan invisible controls in the output.
/// Strip them alongside the visible emoji for clean output.
const ZERO_WIDTH_JOINER: char = '\u{200D}';
const VARIATION_SELECTOR_16: char = '\u{FE0F}';

fn is_emoji(ch: char) -> bool {
    if ch == ZERO_WIDTH_JOINER || ch == VARIATION_SELECTOR_16 {
        return true;
    }
    let cp = ch as u32;
    EMOJI_RANGES
        .iter()
        .any(|(start, end)| cp >= *start && cp <= *end)
}

/// Replace a single emoji with an ASCII approximation.
///
/// Returns a short ASCII replacement that preserves intent for common
/// review glyphs (check/cross/warning). Unknown emojis become an empty
/// string so they simply disappear from the body.
fn replace_emoji(ch: char) -> &'static str {
    match ch {
        '\u{2705}' | '\u{2714}' | '\u{2611}' => "[OK]", // check marks
        '\u{274C}' | '\u{2716}' | '\u{2718}' => "[FAIL]", // crosses
        '\u{26A0}' => "[WARN]",                         // warning sign
        '\u{1F6A8}' => "[ALERT]",                       // rotating light
        '\u{1F4DD}' | '\u{1F4C4}' => "[NOTE]",          // memo / page
        '\u{1F50D}' | '\u{1F50E}' => "[SEARCH]",        // magnifier
        '\u{1F41B}' | '\u{1F41E}' => "[BUG]",           // bug
        '\u{1F389}' | '\u{1F38A}' => "[DONE]",          // party
        '\u{1F4A1}' => "[IDEA]",                        // light bulb
        '\u{1F527}' | '\u{1F528}' => "[FIX]",           // wrench / hammer
        '\u{1F6E1}' => "[SECURITY]",                    // shield
        _ => "",
    }
}

/// Strip Unicode emojis from review text.
///
/// Returns the sanitized text and the number of emoji characters replaced.
/// A non-zero count means the caller should retry posting.
pub fn strip_emojis(text: &str) -> (String, usize) {
    let mut out = String::with_capacity(text.len());
    let mut replaced = 0usize;
    for ch in text.chars() {
        if is_emoji(ch) {
            out.push_str(replace_emoji(ch));
            replaced += 1;
        } else {
            out.push(ch);
        }
    }
    (out, replaced)
}

/// Best-effort detection of a gh-validator rejection in stderr.
///
/// Used to decide whether a failed `gh pr comment` invocation is worth
/// retrying after sanitization. Matches the exact validator error prefix
/// so unrelated errors that happen to mention "emoji" (e.g. a dependency
/// complaining about emoji font parsing) don't trigger a pointless retry.
pub fn is_sanitizable_failure(stderr: &str) -> bool {
    stderr
        .to_ascii_lowercase()
        .contains("unicode emoji detected")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_checkmark() {
        let (out, n) = strip_emojis("All good \u{2705} now");
        assert_eq!(n, 1);
        assert_eq!(out, "All good [OK] now");
    }

    #[test]
    fn strips_unknown_emoji_to_empty() {
        let (out, n) = strip_emojis("hello \u{1F600} world");
        assert_eq!(n, 1);
        assert_eq!(out, "hello  world");
    }

    #[test]
    fn leaves_plain_text_alone() {
        let (out, n) = strip_emojis("plain ASCII text");
        assert_eq!(n, 0);
        assert_eq!(out, "plain ASCII text");
    }

    #[test]
    fn detects_validator_failure() {
        assert!(is_sanitizable_failure(
            "ERROR: Unicode emoji detected: '\u{2705}' (U+2705)"
        ));
        assert!(!is_sanitizable_failure("network timeout"));
    }

    #[test]
    fn strips_zwj_sequence_cleanly() {
        // Man technologist: man + ZWJ + laptop. We don't have either visible
        // emoji mapped, so both become "" — but the ZWJ must also be stripped
        // so no invisible orphan is left behind.
        let input = "author \u{1F468}\u{200D}\u{1F4BB} shipped it";
        let (out, n) = strip_emojis(input);
        assert_eq!(n, 3);
        assert_eq!(out, "author  shipped it");
    }

    #[test]
    fn strips_variation_selector() {
        // Warning sign with VS16 emoji presentation: U+26A0 U+FE0F.
        // U+26A0 maps to "[WARN]"; VS16 must be stripped too.
        let input = "heads up \u{26A0}\u{FE0F} here";
        let (out, n) = strip_emojis(input);
        assert_eq!(n, 2);
        assert_eq!(out, "heads up [WARN] here");
    }

    #[test]
    fn ignores_unrelated_emoji_mentions() {
        // Must not false-positive on errors that merely mention "emoji"
        // but aren't the gh-validator rejection we know how to recover from.
        assert!(!is_sanitizable_failure("custom emoji font missing"));
        assert!(!is_sanitizable_failure(
            "emoji parsing failed in dependency"
        ));
    }
}
