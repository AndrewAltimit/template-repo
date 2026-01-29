//! Content sanitization to prevent secrets from being stored in memory

use regex::Regex;
use std::collections::HashMap;
use std::sync::LazyLock;

/// Blocked patterns for known secret formats
static BLOCKED_PATTERNS: LazyLock<Vec<(&'static str, Regex)>> = LazyLock::new(|| {
    vec![
        // Generic secrets with common labels
        (
            "generic_secret",
            Regex::new(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+").unwrap(),
        ),
        // Private keys
        (
            "private_key",
            Regex::new(r"-----BEGIN.*PRIVATE KEY-----").unwrap(),
        ),
        // API keys with vendor-specific prefixes (OpenAI, Stripe)
        (
            "openai_stripe",
            Regex::new(r"(sk-|pk_|rk_)[a-zA-Z0-9]{20,}").unwrap(),
        ),
        // AWS credentials
        ("aws_access_key", Regex::new(r"AKIA[0-9A-Z]{16}").unwrap()),
        // AWS secret keys - simplified pattern (no look-around in Rust regex)
        // Uses word boundaries to reduce false positives on arbitrary 40-char strings
        (
            "aws_secret_key",
            Regex::new(r"\b[A-Za-z0-9/+=]{40}\b").unwrap(),
        ),
        // GitHub tokens
        (
            "github_pat_new",
            Regex::new(r"gh[pousr]_[A-Za-z0-9_]{36,}").unwrap(),
        ),
        (
            "github_pat_fine",
            Regex::new(r"github_pat_[A-Za-z0-9_]{22,}").unwrap(),
        ),
        // Slack tokens
        (
            "slack_token",
            Regex::new(r"xox[baprs]-[0-9a-zA-Z-]+").unwrap(),
        ),
        // Google OAuth tokens
        ("google_oauth", Regex::new(r"ya29\.[0-9A-Za-z_-]+").unwrap()),
        // Anthropic API keys
        (
            "anthropic_key",
            Regex::new(r"sk-ant-[a-zA-Z0-9-]+").unwrap(),
        ),
        // OpenRouter API keys
        (
            "openrouter_key",
            Regex::new(r"sk-or-[a-zA-Z0-9-]+").unwrap(),
        ),
        // Generic bearer tokens
        (
            "bearer_token",
            Regex::new(r"Bearer\s+[A-Za-z0-9_-]{20,}").unwrap(),
        ),
        // Base64 encoded credentials
        (
            "basic_auth",
            Regex::new(r"Basic\s+[A-Za-z0-9+/=]{20,}").unwrap(),
        ),
        // Connection strings with passwords
        (
            "connection_string",
            Regex::new(r"(?i)(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@").unwrap(),
        ),
    ]
});

/// Regex for potential secret tokens (alphanumeric with base64/url-safe chars)
static TOKEN_PATTERN: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[A-Za-z0-9+/=_-]{20,}").unwrap());

/// Calculate Shannon entropy of a string (bits per character)
fn calculate_entropy(s: &str) -> f64 {
    if s.is_empty() {
        return 0.0;
    }

    let mut counts: HashMap<char, usize> = HashMap::new();
    for c in s.chars() {
        *counts.entry(c).or_insert(0) += 1;
    }

    let length = s.len() as f64;
    counts
        .values()
        .map(|&count| {
            let p = count as f64 / length;
            -p * p.log2()
        })
        .sum()
}

/// Detect high-entropy strings that might be secrets
fn is_high_entropy_blob(s: &str, threshold: f64, min_length: usize) -> bool {
    if s.len() < min_length {
        return false;
    }

    // Only check strings that look like potential secrets (base64-like or hex-like)
    static BASE64_LIKE: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"^[A-Za-z0-9+/=_-]+$").unwrap());

    if !BASE64_LIKE.is_match(s) {
        return false;
    }

    calculate_entropy(s) > threshold
}

/// Remove potential secrets before storing
///
/// Applies multiple layers:
/// 1. Known secret patterns -> [REDACTED]
/// 2. High-entropy blobs -> [HIGH_ENTROPY_REDACTED]
pub fn sanitize_content(content: &str) -> String {
    let mut result = content.to_string();

    // Layer 1: Check known patterns
    for (_, pattern) in BLOCKED_PATTERNS.iter() {
        result = pattern.replace_all(&result, "[REDACTED]").to_string();
    }

    // Layer 2: Check for high-entropy blobs
    result = TOKEN_PATTERN
        .replace_all(&result, |caps: &regex::Captures| {
            let token = caps.get(0).map(|m| m.as_str()).unwrap_or("");
            if is_high_entropy_blob(token, 4.5, 20) {
                "[HIGH_ENTROPY_REDACTED]".to_string()
            } else {
                token.to_string()
            }
        })
        .to_string();

    result
}

/// Check if content contains potential secrets without modifying it
#[allow(dead_code)]
pub fn contains_secrets(content: &str) -> (bool, Vec<&'static str>) {
    let mut detected = Vec::new();

    // Check known patterns
    for (name, pattern) in BLOCKED_PATTERNS.iter() {
        if pattern.is_match(content) {
            detected.push(*name);
        }
    }

    // Check for high-entropy blobs
    for caps in TOKEN_PATTERN.captures_iter(content) {
        if let Some(m) = caps.get(0)
            && is_high_entropy_blob(m.as_str(), 4.5, 20)
        {
            detected.push("high_entropy_blob");
            break;
        }
    }

    (!detected.is_empty(), detected)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_api_key() {
        let content = "My API key is api_key: sk-1234567890abcdefghij";
        let sanitized = sanitize_content(content);
        assert!(sanitized.contains("[REDACTED]"));
        assert!(!sanitized.contains("sk-1234567890"));
    }

    #[test]
    fn test_sanitize_github_token() {
        let content = "Token: ghp_1234567890abcdefghij1234567890abcdef";
        let sanitized = sanitize_content(content);
        assert!(sanitized.contains("[REDACTED]"));
    }

    #[test]
    fn test_preserves_short_text() {
        // Short text without long token-like strings should be preserved
        let content = "Hello world.";
        let sanitized = sanitize_content(content);
        assert_eq!(content, sanitized);
    }

    #[test]
    fn test_sanitize_bearer_token() {
        let content = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9";
        let sanitized = sanitize_content(content);
        assert!(sanitized.contains("[REDACTED]"));
    }
}
