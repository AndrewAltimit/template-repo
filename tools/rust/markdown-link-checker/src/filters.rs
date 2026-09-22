//! URL ignore rules.

use std::path::Path;

use anyhow::{Context, Result};
use regex::Regex;

/// Built-in ignore patterns: loopback and private-network hosts that CI
/// cannot reach, plus non-HTTP schemes (listed for documentation; any
/// non-HTTP scheme is skipped anyway).
pub const DEFAULT_IGNORE_PATTERNS: &[&str] = &[
    r"^https?://localhost",
    r"^https?://127\.",
    r"^https?://0\.0\.0\.0",
    r"^https?://\[::1?\]",
    r"^https?://10\.",
    r"^https?://172\.(1[6-9]|2[0-9]|3[01])\.",
    r"^https?://192\.168\.",
    r"^mailto:",
    r"^chrome://",
    r"^file://",
    r"^ftp://",
    r"^tel:",
    r"^javascript:",
];

/// Compiled set of regexes; a link matching any of them is skipped entirely
/// (not validated and not counted).
#[derive(Debug, Clone, Default)]
pub struct IgnoreRules {
    patterns: Vec<Regex>,
}

impl IgnoreRules {
    /// Compile `patterns`, optionally preceded by [`DEFAULT_IGNORE_PATTERNS`].
    pub fn new<S: AsRef<str>>(patterns: &[S], include_defaults: bool) -> Result<Self> {
        let defaults: &[&str] = if include_defaults {
            DEFAULT_IGNORE_PATTERNS
        } else {
            &[]
        };
        let compiled = defaults
            .iter()
            .copied()
            .chain(patterns.iter().map(AsRef::as_ref))
            .map(|p| Regex::new(p).with_context(|| format!("invalid ignore pattern '{p}'")))
            .collect::<Result<_>>()?;
        Ok(Self { patterns: compiled })
    }

    /// Whether `link` matches any pattern.
    pub fn is_ignored(&self, link: &str) -> bool {
        self.patterns.iter().any(|p| p.is_match(link))
    }
}

/// Read ignore patterns from a file: one regex per line; blank lines and
/// lines starting with `#` are skipped.
pub fn read_pattern_file(path: &Path) -> Result<Vec<String>> {
    let content = std::fs::read_to_string(path)
        .with_context(|| format!("cannot read ignore file {}", path.display()))?;
    Ok(content
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .map(String::from)
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults() {
        let rules = IgnoreRules::new::<&str>(&[], true).unwrap();
        for link in [
            "http://localhost:8080",
            "https://localhost/x",
            "http://127.0.0.1:3000",
            "http://192.168.0.152:8007",
            "http://10.0.0.1",
            "http://172.20.1.1",
            "mailto:test@example.com",
        ] {
            assert!(rules.is_ignored(link), "{link}");
        }
        for link in [
            "#anchor",
            "https://example.com",
            "http://172.32.0.1",
            "docs/a.md",
        ] {
            assert!(!rules.is_ignored(link), "{link}");
        }
    }

    #[test]
    fn custom_without_defaults() {
        let rules = IgnoreRules::new(&["example\\.com"], false).unwrap();
        assert!(rules.is_ignored("https://example.com/x"));
        assert!(!rules.is_ignored("http://localhost"));
    }

    #[test]
    fn invalid_pattern_errors() {
        let err = IgnoreRules::new(&["("], true).unwrap_err();
        assert!(err.to_string().contains("invalid ignore pattern"));
    }

    #[test]
    fn pattern_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("ignore.txt");
        std::fs::write(
            &path,
            "# comment\n\n^https://flaky\\.test\n  internal\\.corp  \n",
        )
        .unwrap();
        assert_eq!(
            read_pattern_file(&path).unwrap(),
            ["^https://flaky\\.test", "internal\\.corp"]
        );
    }
}
