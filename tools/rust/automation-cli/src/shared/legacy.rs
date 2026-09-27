//! Gate for legacy agents (Gemini, Codex).
//!
//! Their code is kept for reference, but they are not allowed in this lab.
//! Paths that would build or run them refuse unless `ALLOW_LEGACY_AGENTS=1`
//! is set, the same override the shell scripts use. Their compose services
//! live under the `legacy` profile.

use anyhow::{Result, bail};

/// Environment variable that re-enables legacy agents.
pub const ALLOW_ENV: &str = "ALLOW_LEGACY_AGENTS";

/// Compose profile holding the legacy services.
pub const PROFILE: &str = "legacy";

/// Whether legacy agents are explicitly allowed for this run.
pub fn allowed() -> bool {
    allowed_from(std::env::var(ALLOW_ENV).ok().as_deref())
}

/// Exactly `1` enables the override, matching the shell scripts'
/// `[ "${ALLOW_LEGACY_AGENTS:-}" = "1" ]`.
fn allowed_from(value: Option<&str>) -> bool {
    value == Some("1")
}

/// Message used when refusing `what`.
pub fn refusal(what: &str) -> String {
    format!("{what} is legacy: not allowed in this lab (set {ALLOW_ENV}=1 to override)")
}

/// Fail with a clear error unless legacy agents are allowed.
pub fn ensure_allowed(what: &str) -> Result<()> {
    if allowed() {
        Ok(())
    } else {
        bail!(refusal(what))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_exact_one_allows() {
        assert!(allowed_from(Some("1")));
        for v in [
            None,
            Some(""),
            Some("0"),
            Some("true"),
            Some(" 1"),
            Some("yes"),
        ] {
            assert!(!allowed_from(v), "{v:?}");
        }
    }

    #[test]
    fn refusal_names_the_override() {
        let msg = refusal("gemini-proxy");
        assert!(msg.contains("gemini-proxy is legacy: not allowed in this lab"));
        assert!(msg.contains("ALLOW_LEGACY_AGENTS=1"));
    }
}
