//! Small, dependency-free helpers.
//!
//! NOTE: this file is intentionally kept byte-for-byte identical between
//! `mcp_opencode/src/util.rs` and `mcp_crush/src/util.rs`. The two crates are
//! self-contained (no cross-crate dependency), so shared logic lives in an
//! aligned copy instead. Change both copies together.

use std::str::FromStr;

/// Marker appended to text that was shortened by [`truncate_chars`].
pub const TRUNCATION_MARKER: &str = "\n... [truncated]";

/// Replacement text for redacted secrets.
pub const REDACTED: &str = "[REDACTED]";

/// Truncate `text` to at most `max_chars` Unicode scalar values.
///
/// Never splits a UTF-8 code point (slicing a `&str` at an arbitrary byte
/// offset panics, and the release profile uses `panic = "abort"`). When the
/// text is shortened, [`TRUNCATION_MARKER`] is appended and the returned flag
/// is `true`.
pub fn truncate_chars(text: &str, max_chars: usize) -> (String, bool) {
    match text.char_indices().nth(max_chars) {
        None => (text.to_string(), false),
        Some((byte_idx, _)) => (format!("{}{}", &text[..byte_idx], TRUNCATION_MARKER), true),
    }
}

/// Remove secrets from text that may be surfaced to a client or a log.
///
/// Redacts every literal occurrence of `secret` (when it is long enough to be
/// a real credential) plus anything that looks like an OpenRouter key
/// (`sk-or-...`), which upstream error bodies sometimes echo back.
pub fn redact_secrets(text: &str, secret: &str) -> String {
    let literal_redacted = if secret.len() >= 8 {
        text.replace(secret, REDACTED)
    } else {
        text.to_string()
    };

    const PREFIX: &str = "sk-or-";
    let mut result = String::with_capacity(literal_redacted.len());
    let mut rest = literal_redacted.as_str();
    while let Some(pos) = rest.find(PREFIX) {
        result.push_str(&rest[..pos]);
        let tail = &rest[pos..];
        let key_len = tail
            .find(|c: char| !(c.is_ascii_alphanumeric() || c == '-' || c == '_'))
            .unwrap_or(tail.len());
        result.push_str(REDACTED);
        rest = &tail[key_len..];
    }
    result.push_str(rest);
    result
}

/// Parse a boolean flag leniently: `true/1/yes/on` and `false/0/no/off`
/// (case-insensitive, surrounding whitespace ignored). Anything else is `None`.
pub fn parse_bool(value: &str) -> Option<bool> {
    match value.trim().to_ascii_lowercase().as_str() {
        "true" | "1" | "yes" | "on" => Some(true),
        "false" | "0" | "no" | "off" => Some(false),
        _ => None,
    }
}

/// Read a boolean setting via `lookup`, falling back to `default` (with a
/// warning) when the value is missing or unparseable.
pub fn env_bool(lookup: &dyn Fn(&str) -> Option<String>, key: &str, default: bool) -> bool {
    match lookup(key) {
        None => default,
        Some(raw) => parse_bool(&raw).unwrap_or_else(|| {
            tracing::warn!(
                "{key}={raw:?} is not a boolean (expected true/false/1/0/yes/no/on/off); using default {default}"
            );
            default
        }),
    }
}

/// Read a numeric setting via `lookup`, clamped to `min..=max`. Missing or
/// unparseable values fall back to `default` (with a warning).
pub fn env_num<T>(
    lookup: &dyn Fn(&str) -> Option<String>,
    key: &str,
    default: T,
    min: T,
    max: T,
) -> T
where
    T: FromStr + PartialOrd + Copy + std::fmt::Display,
{
    let value = match lookup(key) {
        None => return default,
        Some(raw) => match raw.trim().parse::<T>() {
            Ok(v) => v,
            Err(_) => {
                tracing::warn!("{key}={raw:?} is not a valid number; using default {default}");
                return default;
            },
        },
    };
    if value < min {
        tracing::warn!("{key}={value} is below the minimum {min}; clamping");
        min
    } else if value > max {
        tracing::warn!("{key}={value} is above the maximum {max}; clamping");
        max
    } else {
        value
    }
}

/// Read a string setting via `lookup`; empty/whitespace values count as unset.
pub fn env_string(lookup: &dyn Fn(&str) -> Option<String>, key: &str) -> Option<String> {
    lookup(key)
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
}

/// Validate an OpenRouter-style model identifier (e.g. `qwen/qwen3.7-max`,
/// `anthropic/claude-sonnet-4.6:beta`). Restricting the charset keeps model
/// ids safe to embed in JSON, file names and log lines.
pub fn is_valid_model_id(model: &str) -> bool {
    !model.is_empty()
        && model.len() <= 200
        && model
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '/' | '-' | '_' | '.' | ':' | '@'))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn lookup_from(pairs: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
        let map: HashMap<String, String> = pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        move |k: &str| map.get(k).cloned()
    }

    #[test]
    fn truncate_is_utf8_safe() {
        // Multi-byte characters would panic with naive byte slicing.
        let text = "héllo wörld 日本語";
        let (out, truncated) = truncate_chars(text, 3);
        assert!(truncated);
        assert!(out.starts_with("hél"));
        assert!(out.ends_with(TRUNCATION_MARKER));

        let (out, truncated) = truncate_chars(text, 100);
        assert!(!truncated);
        assert_eq!(out, text);

        let (out, truncated) = truncate_chars("abc", 3);
        assert!(!truncated);
        assert_eq!(out, "abc");
    }

    #[test]
    fn redacts_literal_and_pattern_keys() {
        let secret = "sk-or-v1-abcdef0123456789";
        let text = format!("bad key {secret} and sk-or-other_KEY-99, done");
        let out = redact_secrets(&text, secret);
        assert!(!out.contains("abcdef"));
        assert!(!out.contains("other_KEY"));
        assert_eq!(out, "bad key [REDACTED] and [REDACTED], done");

        // Short "secrets" are not blanket-replaced.
        assert_eq!(redact_secrets("a b c", "b"), "a b c");
    }

    #[test]
    fn parses_booleans() {
        for v in ["true", "TRUE", " 1 ", "yes", "On"] {
            assert_eq!(parse_bool(v), Some(true), "{v}");
        }
        for v in ["false", "0", "No", "off"] {
            assert_eq!(parse_bool(v), Some(false), "{v}");
        }
        assert_eq!(parse_bool("maybe"), None);
    }

    #[test]
    fn env_helpers_fall_back_and_clamp() {
        let lookup = lookup_from(&[
            ("B_BAD", "maybe"),
            ("B_OK", "0"),
            ("N_OK", "42"),
            ("N_BAD", "x"),
            ("N_HIGH", "999999"),
            ("N_LOW", "0"),
            ("S_EMPTY", "   "),
            ("S_OK", " value "),
        ]);
        assert!(env_bool(&lookup, "B_BAD", true));
        assert!(!env_bool(&lookup, "B_OK", true));
        assert!(env_bool(&lookup, "MISSING", true));

        assert_eq!(env_num(&lookup, "N_OK", 1u64, 1, 100), 42);
        assert_eq!(env_num(&lookup, "N_BAD", 7u64, 1, 100), 7);
        assert_eq!(env_num(&lookup, "N_HIGH", 7u64, 1, 100), 100);
        assert_eq!(env_num(&lookup, "N_LOW", 7u64, 1, 100), 1);

        assert_eq!(env_string(&lookup, "S_EMPTY"), None);
        assert_eq!(env_string(&lookup, "S_OK").as_deref(), Some("value"));
    }

    #[test]
    fn validates_model_ids() {
        assert!(is_valid_model_id("qwen/qwen3.7-max"));
        assert!(is_valid_model_id("anthropic/claude-sonnet-4.6:beta"));
        assert!(!is_valid_model_id(""));
        assert!(!is_valid_model_id("model; rm -rf /"));
        assert!(!is_valid_model_id("a\"b"));
        assert!(!is_valid_model_id(&"x".repeat(201)));
    }
}
