//! GitHub-compatible heading anchor generation.
//!
//! Mirrors the [`github-slugger`](https://github.com/Flet/github-slugger)
//! algorithm GitHub uses when rendering markdown.

use std::collections::HashMap;

/// Convert heading text to a GitHub anchor ID (without duplicate suffixes).
///
/// 1. Lowercase.
/// 2. Drop everything except letters, numbers, combining marks, `-` and `_`.
/// 3. Turn each space into a hyphen.
///
/// Consecutive hyphens are NOT collapsed: `"Audio & Animation"` becomes
/// `"audio--animation"` because removing `&` leaves two spaces.
pub fn github_slugify(heading: &str) -> String {
    let mut slug = String::with_capacity(heading.len());
    for ch in heading.trim().to_lowercase().chars() {
        if ch.is_alphanumeric() || ch == '-' || ch == '_' || is_combining_mark(ch) {
            slug.push(ch);
        } else if ch == ' ' {
            slug.push('-');
        }
    }
    slug
}

/// Combining diacritical marks survive slugging on GitHub (Unicode category M).
fn is_combining_mark(ch: char) -> bool {
    matches!(
        ch,
        '\u{0300}'..='\u{036F}'
            | '\u{1AB0}'..='\u{1AFF}'
            | '\u{1DC0}'..='\u{1DFF}'
            | '\u{20D0}'..='\u{20FF}'
            | '\u{FE20}'..='\u{FE2F}'
    )
}

/// Stateful slugger that disambiguates duplicate headings in one document.
///
/// Matches github-slugger: the first `Foo` is `foo`, the second `foo-1`, and
/// a later natural `Foo 1` heading (which would also be `foo-1`) becomes
/// `foo-1-1`.
#[derive(Debug, Default)]
pub struct Slugger {
    occurrences: HashMap<String, usize>,
}

impl Slugger {
    /// Create an empty slugger.
    pub fn new() -> Self {
        Self::default()
    }

    /// Return the unique anchor for the next heading with the given text.
    pub fn slug(&mut self, heading: &str) -> String {
        let base = github_slugify(heading);
        let mut slug = base.clone();
        while self.occurrences.contains_key(&slug) {
            let count = self.occurrences.entry(base.clone()).or_insert(0);
            *count += 1;
            slug = format!("{base}-{count}");
        }
        self.occurrences.insert(slug.clone(), 0);
        slug
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slugify_matches_github() {
        let cases = [
            ("Introduction", "introduction"),
            (
                "1. Introduction and Methodology",
                "1-introduction-and-methodology",
            ),
            (
                "The Current Technological Landscape (2025)",
                "the-current-technological-landscape-2025",
            ),
            ("Second-Order Effects", "second-order-effects"),
            (
                "What Would Change This Assessment?",
                "what-would-change-this-assessment",
            ),
            (
                "The Insider Threat 2.0: Stasi-in-a-Box",
                "the-insider-threat-20-stasi-in-a-box",
            ),
            ("Audio & Animation Pipeline", "audio--animation-pipeline"),
            ("Monitoring & Alerts", "monitoring--alerts"),
            (
                "Phase 2: First Backend - VRChat OSC",
                "phase-2-first-backend---vrchat-osc",
            ),
            ("snake_case_name", "snake_case_name"),
            ("Caf\u{e9} Men\u{fc}", "caf\u{e9}-men\u{fc}"),
            ("\u{1F680} Launch", "-launch"),
            ("C++ / Rust", "c--rust"),
        ];
        for (input, expected) in cases {
            assert_eq!(github_slugify(input), expected, "input: {input}");
        }
    }

    #[test]
    fn slugger_suffixes_duplicates() {
        let mut s = Slugger::new();
        assert_eq!(s.slug("Details"), "details");
        assert_eq!(s.slug("Details"), "details-1");
        assert_eq!(s.slug("Details"), "details-2");
    }

    #[test]
    fn slugger_resolves_natural_collisions() {
        let mut s = Slugger::new();
        assert_eq!(s.slug("Foo"), "foo");
        assert_eq!(s.slug("Foo"), "foo-1");
        assert_eq!(s.slug("Foo 1"), "foo-1-1");
        // And the other order.
        let mut s = Slugger::new();
        assert_eq!(s.slug("Foo 1"), "foo-1");
        assert_eq!(s.slug("Foo"), "foo");
        assert_eq!(s.slug("Foo"), "foo-2");
    }
}
