//! Result types (the `--json` schema) and human-readable rendering.

use std::io::{self, Write};

use serde::Serialize;

/// Result of checking a single unique link in a file.
#[derive(Debug, Clone, Serialize)]
pub struct LinkResult {
    /// Destination as written in the markdown.
    pub url: String,
    /// Whether the link resolved.
    pub valid: bool,
    /// Reason for failure.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    /// 1-based line numbers where the link occurs.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub lines: Vec<usize>,
    /// True when the link was not validated (external link with
    /// `--internal-only`). Skipped links count as valid.
    #[serde(skip_serializing_if = "std::ops::Not::not")]
    pub skipped: bool,
}

impl LinkResult {
    /// A resolved link.
    pub fn ok(url: String, lines: Vec<usize>) -> Self {
        Self {
            url,
            valid: true,
            error: None,
            lines,
            skipped: false,
        }
    }

    /// A broken link.
    pub fn broken(url: String, lines: Vec<usize>, error: String) -> Self {
        Self {
            url,
            valid: false,
            error: Some(error),
            lines,
            skipped: false,
        }
    }

    /// Build from a check outcome.
    pub fn from_outcome(url: String, lines: Vec<usize>, outcome: Result<(), String>) -> Self {
        match outcome {
            Ok(()) => Self::ok(url, lines),
            Err(e) => Self::broken(url, lines, e),
        }
    }
}

/// Result of checking links in a single file.
#[derive(Debug, Clone, Serialize)]
pub struct FileResult {
    /// File path as discovered.
    pub file: String,
    /// One entry per unique link, in order of first appearance.
    pub links: Vec<LinkResult>,
    /// Number of invalid entries in `links`.
    pub broken_count: usize,
    /// Number of entries in `links`.
    pub total_count: usize,
    /// Set when the file could not be read; the run then fails.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl FileResult {
    /// Build from checked links, computing the counts.
    pub fn new(file: String, links: Vec<LinkResult>) -> Self {
        let broken_count = links.iter().filter(|l| !l.valid).count();
        Self {
            file,
            total_count: links.len(),
            broken_count,
            links,
            error: None,
        }
    }

    /// A file that could not be read.
    pub fn unreadable(file: String, error: String) -> Self {
        Self {
            file,
            links: Vec::new(),
            broken_count: 0,
            total_count: 0,
            error: Some(error),
        }
    }
}

/// Overall results (top-level `--json` object).
#[derive(Debug, Clone, Serialize)]
pub struct CheckResults {
    /// The checker ran to completion (fatal errors exit before output).
    pub success: bool,
    /// Markdown files examined.
    pub files_checked: usize,
    /// Sum of `total_count` over all files.
    pub total_links: usize,
    /// Sum of `broken_count` over all files.
    pub broken_links: usize,
    /// Files that could not be read.
    pub file_errors: usize,
    /// No broken links and no unreadable files.
    pub all_valid: bool,
    /// Per-file details, sorted by path.
    pub results: Vec<FileResult>,
}

impl CheckResults {
    /// Aggregate per-file results.
    pub fn from_files(results: Vec<FileResult>) -> Self {
        let total_links = results.iter().map(|r| r.total_count).sum();
        let broken_links = results.iter().map(|r| r.broken_count).sum();
        let file_errors = results.iter().filter(|r| r.error.is_some()).count();
        Self {
            success: true,
            files_checked: results.len(),
            total_links,
            broken_links,
            file_errors,
            all_valid: broken_links == 0 && file_errors == 0,
            results,
        }
    }

    /// Write the human-readable report.
    ///
    /// Each broken link is one line, `  <file>:<line> -> <url> (<error>)`,
    /// which the CI summary step greps for `-> `.
    pub fn write_human(&self, out: &mut impl Write) -> io::Result<()> {
        writeln!(out)?;
        writeln!(out, "=== Markdown Link Check Results ===")?;
        writeln!(out)?;
        writeln!(out, "Files checked: {}", self.files_checked)?;
        writeln!(out, "Total links:   {}", self.total_links)?;
        writeln!(out, "Broken links:  {}", self.broken_links)?;
        writeln!(out)?;

        if self.broken_links > 0 {
            writeln!(out, "Broken links:")?;
            writeln!(out)?;
            for file in &self.results {
                for link in file.links.iter().filter(|l| !l.valid) {
                    let location = match link.lines.first() {
                        Some(line) => format!("{}:{line}", file.file),
                        None => file.file.clone(),
                    };
                    writeln!(
                        out,
                        "  {location} -> {} ({})",
                        link.url,
                        link.error.as_deref().unwrap_or("unknown error")
                    )?;
                }
            }
            writeln!(out)?;
        }

        if self.file_errors > 0 {
            writeln!(out, "Unreadable files:")?;
            writeln!(out)?;
            for file in self.results.iter().filter(|r| r.error.is_some()) {
                writeln!(
                    out,
                    "  {} ({})",
                    file.file,
                    file.error.as_deref().unwrap_or_default()
                )?;
            }
            writeln!(out)?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn aggregates_and_renders() {
        let results = CheckResults::from_files(vec![
            FileResult::new(
                "docs/a.md".into(),
                vec![
                    LinkResult::ok("ok.md".into(), vec![1]),
                    LinkResult::broken("gone.md".into(), vec![7, 9], "File not found".into()),
                ],
            ),
            FileResult::unreadable("bad.md".into(), "invalid UTF-8".into()),
        ]);
        assert_eq!(results.total_links, 2);
        assert_eq!(results.broken_links, 1);
        assert_eq!(results.file_errors, 1);
        assert!(!results.all_valid);

        let mut out = Vec::new();
        results.write_human(&mut out).unwrap();
        let text = String::from_utf8(out).unwrap();
        assert!(
            text.contains("  docs/a.md:7 -> gone.md (File not found)"),
            "{text}"
        );
        assert!(text.contains("  bad.md (invalid UTF-8)"), "{text}");
    }

    #[test]
    fn json_omits_defaults() {
        let json = serde_json::to_value(LinkResult::ok("x".into(), vec![])).unwrap();
        assert_eq!(json, serde_json::json!({"url": "x", "valid": true}));
        let mut skipped = LinkResult::ok("https://x.test".into(), vec![3]);
        skipped.skipped = true;
        let json = serde_json::to_value(skipped).unwrap();
        assert_eq!(json["skipped"], true);
        assert_eq!(json["lines"], serde_json::json!([3]));
    }
}
