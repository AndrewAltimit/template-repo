//! Content sanitization so that secrets never reach the memory store.
//!
//! Two layers run over every piece of text (memory content and string
//! metadata values) before it is embedded or stored:
//!
//! 1. **Known secret formats** (vendor key prefixes, `password=...` style
//!    assignments, PEM private-key blocks, connection strings with inline
//!    passwords, JWTs, ...) are replaced with `[REDACTED]`.
//! 2. **High-entropy blobs**: base64/url-safe tokens of 20+ chars whose Shannon
//!    entropy exceeds 4.5 bits/char and that contain both letters and digits
//!    are replaced with `[HIGH_ENTROPY_REDACTED]`. Requiring a digit keeps long
//!    identifiers and paths (`tools/mcp/mcp_agentcore_memory/src`) intact.
//!
//! This is a best-effort safety net, not a guarantee: callers should still
//! avoid sending credentials to memory tools.

use regex::Regex;
use std::collections::{BTreeSet, HashMap};
use std::sync::LazyLock;

/// Replacement for a known-pattern match.
pub const REDACTED: &str = "[REDACTED]";
/// Replacement for a high-entropy token.
pub const HIGH_ENTROPY_REDACTED: &str = "[HIGH_ENTROPY_REDACTED]";

const ENTROPY_THRESHOLD: f64 = 4.5;
const ENTROPY_MIN_LEN: usize = 20;

/// Build a regex from a pattern that is a compile-time constant in this file.
///
/// Every pattern below is covered by `all_patterns_compile`; if one were ever
/// broken the pattern is skipped (with an error log) instead of panicking.
fn compile(name: &'static str, pattern: &str) -> Option<(&'static str, Regex)> {
    match Regex::new(pattern) {
        Ok(re) => Some((name, re)),
        Err(e) => {
            tracing::error!("sanitizer pattern '{name}' failed to compile: {e}");
            None
        },
    }
}

/// `(name, pattern)` pairs for known secret formats. Order matters: more
/// specific patterns (whole PEM blocks) run before generic ones.
const PATTERN_SOURCES: &[(&str, &str)] = &[
    // Whole PEM private-key blocks (header, base64 body, footer).
    (
        "private_key",
        r"(?s)-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\z)",
    ),
    // Connection strings with inline credentials.
    (
        "connection_string",
        r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqps?)://[^:/\s@]+:[^@\s]+@",
    ),
    // Vendor-prefixed API keys.
    ("anthropic_key", r"sk-ant-[A-Za-z0-9_-]{10,}"),
    ("openrouter_key", r"sk-or-[A-Za-z0-9_-]{10,}"),
    (
        "openai_stripe",
        r"\b(?:sk|pk|rk)[-_](?:live_|test_|proj-)?[A-Za-z0-9]{20,}",
    ),
    ("aws_access_key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    (
        "aws_secret_key",
        r"(?i)(?:aws_secret|secret_?key|secret_?access)\S*\s*[:=]\s*[A-Za-z0-9/+=]{40}",
    ),
    ("github_token", r"\bgh[pousr]_[A-Za-z0-9_]{36,}"),
    ("github_pat_fine", r"\bgithub_pat_[A-Za-z0-9_]{22,}"),
    ("slack_token", r"\bxox[abposr]-[0-9A-Za-z-]{10,}"),
    ("google_oauth", r"\bya29\.[0-9A-Za-z_-]+"),
    ("google_api_key", r"\bAIza[0-9A-Za-z_-]{35}"),
    ("huggingface_token", r"\bhf_[A-Za-z0-9]{30,}"),
    (
        "jwt",
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*",
    ),
    ("bearer_token", r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    ("basic_auth", r"(?i)\bBasic\s+[A-Za-z0-9+/=]{20,}"),
    // Labelled assignments: `api_key: ...`, `password=...`, `token = ...`.
    (
        "generic_secret",
        r#"(?i)\b(?:api[_-]?key|secret|passwd|password|token|access[_-]?key|private[_-]?key)["']?\s*[:=]\s*["']?[^\s"',;]+"#,
    ),
];

static BLOCKED_PATTERNS: LazyLock<Vec<(&'static str, Regex)>> = LazyLock::new(|| {
    PATTERN_SOURCES
        .iter()
        .filter_map(|(name, pat)| compile(name, pat))
        .collect()
});

/// Candidate tokens for the entropy check (base64 / url-safe alphabet).
static TOKEN_PATTERN: LazyLock<Option<Regex>> =
    LazyLock::new(|| compile("token", r"[A-Za-z0-9+/=_-]{20,}").map(|(_, re)| re));

/// Shannon entropy of `s` in bits per character.
fn calculate_entropy(s: &str) -> f64 {
    let len = s.chars().count();
    if len == 0 {
        return 0.0;
    }
    let mut counts: HashMap<char, usize> = HashMap::new();
    for c in s.chars() {
        *counts.entry(c).or_insert(0) += 1;
    }
    let len = len as f64;
    counts
        .values()
        .map(|&count| {
            let p = count as f64 / len;
            -p * p.log2()
        })
        .sum()
}

/// Heuristic: does this token look like a random secret?
fn is_high_entropy_blob(s: &str) -> bool {
    s.len() >= ENTROPY_MIN_LEN
        && s.bytes().any(|b| b.is_ascii_digit())
        && s.bytes().any(|b| b.is_ascii_alphabetic())
        && calculate_entropy(s) > ENTROPY_THRESHOLD
}

/// Result of sanitizing one string.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Sanitized {
    /// The text with secrets replaced.
    pub text: String,
    /// Names of the detectors that fired (sorted, deduplicated).
    pub detections: BTreeSet<&'static str>,
}

impl Sanitized {
    /// True if anything was redacted.
    pub fn redacted(&self) -> bool {
        !self.detections.is_empty()
    }
}

/// Redact secrets from `content`, reporting which detectors fired.
pub fn sanitize(content: &str) -> Sanitized {
    let mut detections = BTreeSet::new();
    let mut text = content.to_string();

    for (name, pattern) in BLOCKED_PATTERNS.iter() {
        if pattern.is_match(&text) {
            detections.insert(*name);
            text = pattern.replace_all(&text, REDACTED).into_owned();
        }
    }

    if let Some(token_re) = TOKEN_PATTERN.as_ref() {
        let mut hit = false;
        let replaced = token_re.replace_all(&text, |caps: &regex::Captures| {
            let token = caps.get(0).map_or("", |m| m.as_str());
            if is_high_entropy_blob(token) {
                hit = true;
                HIGH_ENTROPY_REDACTED.to_string()
            } else {
                token.to_string()
            }
        });
        if hit {
            text = replaced.into_owned();
            detections.insert("high_entropy_blob");
        }
    }

    Sanitized { text, detections }
}

/// Convenience wrapper returning only the sanitized text.
#[cfg(test)]
pub fn sanitize_content(content: &str) -> String {
    sanitize(content).text
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_patterns_compile() {
        assert_eq!(BLOCKED_PATTERNS.len(), PATTERN_SOURCES.len());
        assert!(TOKEN_PATTERN.is_some());
    }

    #[test]
    fn api_key_assignment() {
        let s = sanitize("My API key is api_key: sk-1234567890abcdefghij");
        assert!(s.text.contains(REDACTED));
        assert!(!s.text.contains("sk-1234567890"));
        assert!(s.redacted());
    }

    #[test]
    fn github_token() {
        let s = sanitize_content("Token ghp_1234567890abcdefghij1234567890abcdef here");
        assert!(s.contains(REDACTED));
        assert!(!s.contains("ghp_"));
    }

    #[test]
    fn bearer_jwt_fully_removed() {
        let jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U";
        let s = sanitize_content(&format!("Authorization: Bearer {jwt}"));
        assert!(s.contains(REDACTED));
        assert!(!s.contains("dozjgNryP4J3"), "JWT signature leaked: {s}");
        let s = sanitize_content(&format!("raw jwt {jwt}"));
        assert!(!s.contains("eyJzdWIi"), "bare JWT leaked: {s}");
    }

    #[test]
    fn private_key_block_fully_removed() {
        let pem = "before\n-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAx1x2\nabcDEF\n-----END RSA PRIVATE KEY-----\nafter";
        let s = sanitize_content(pem);
        assert!(s.starts_with("before\n"));
        assert!(s.ends_with("\nafter"));
        assert!(!s.contains("MIIEow"));
        assert!(!s.contains("abcDEF"));
    }

    #[test]
    fn connection_string_password() {
        let s = sanitize_content("db at postgres://admin:hunter2@db.internal:5432/app");
        assert!(!s.contains("hunter2"));
        assert!(s.contains("db.internal"));
    }

    #[test]
    fn vendor_keys() {
        for secret in [
            "sk-ant-api03-abcdefghijklmnopqrstuvwxyz",
            "sk-or-v1-abcdefghijklmnopqrstuvwxyz",
            "AKIAIOSFODNN7EXAMPLE",
            "xoxb-1234567890-abcdefghij",
            "AIzaSyA1234567890abcdefghijklmnopqrstuv",
            "hf_abcdefghijklmnopqrstuvwxyz0123456789",
        ] {
            let s = sanitize(&format!("value {secret} end"));
            assert!(!s.text.contains(secret), "leaked {secret}: {}", s.text);
            assert!(s.text.starts_with("value ") && s.text.ends_with(" end"));
        }
    }

    #[test]
    fn high_entropy_blob_redacted() {
        let s = sanitize("blob: Zx8Qp2Lm9Vt4Rw7Ky1Hs6Nd3Jb5Fg0Ac");
        assert!(s.text.contains(HIGH_ENTROPY_REDACTED), "{}", s.text);
        assert!(s.detections.contains("high_entropy_blob"));
    }

    #[test]
    fn ordinary_text_preserved() {
        for text in [
            "Hello world.",
            "All MCP servers use the mcp-core crate for transport",
            "See tools/mcp/mcp_agentcore_memory/src/server for the tool definitions",
            "commit 5109927a3f0c9b1e2d4f6a8b0c2d4e6f8a0b2c4d fixed it",
            "uuid 550e8400-e29b-41d4-a716-446655440000",
            "max_tokens: 4096 was used",
            "the token budget matters",
        ] {
            let s = sanitize(text);
            assert_eq!(s.text, text, "altered: {text}");
            assert!(!s.redacted());
        }
    }

    #[test]
    fn entropy_math() {
        assert_eq!(calculate_entropy(""), 0.0);
        assert_eq!(calculate_entropy("aaaa"), 0.0);
        assert!((calculate_entropy("ab") - 1.0).abs() < 1e-9);
    }

    #[test]
    fn non_ascii_does_not_panic() {
        let s = sanitize("password: \u{00e9}\u{00e8}\u{4e2d}\u{6587} and more \u{4e2d}");
        assert!(s.text.contains(REDACTED));
    }
}
