//! Unified diff parsing and in-memory application.
//!
//! The parser is deliberately lenient because AI-written diffs are often slightly
//! wrong: hunk line counts may be off or missing (`@@ ... @@`), blank context lines
//! may have lost their leading space, and line numbers may drift. Hunks are located
//! by content, preferring the position closest to the stated line number.

use std::sync::LazyLock;

use regex::Regex;

use crate::error::{CodeParserError, Result};
use crate::text::split_lines;

/// One line of a hunk body.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HunkLine {
    /// Unchanged line (` ` prefix).
    Context(String),
    /// Line removed from the old file (`-` prefix).
    Removed(String),
    /// Line added in the new file (`+` prefix).
    Added(String),
}

/// A single `@@` hunk.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Hunk {
    /// 1-based start line in the old file (0 if the header had no numbers).
    pub old_start: usize,
    /// Old line count from the header, if present.
    pub old_count: Option<usize>,
    /// 1-based start line in the new file (0 if the header had no numbers).
    pub new_start: usize,
    /// New line count from the header, if present.
    pub new_count: Option<usize>,
    /// Hunk body.
    pub lines: Vec<HunkLine>,
}

impl Hunk {
    /// Lines the hunk expects in the old file (context + removed).
    pub fn old_lines(&self) -> impl Iterator<Item = &str> {
        self.lines.iter().filter_map(|l| match l {
            HunkLine::Context(s) | HunkLine::Removed(s) => Some(s.as_str()),
            HunkLine::Added(_) => None,
        })
    }

    /// Lines the hunk produces in the new file (context + added).
    pub fn new_lines(&self) -> impl Iterator<Item = &str> {
        self.lines.iter().filter_map(|l| match l {
            HunkLine::Context(s) | HunkLine::Added(s) => Some(s.as_str()),
            HunkLine::Removed(_) => None,
        })
    }
}

/// All hunks for one file in a unified diff.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FilePatch {
    /// Old path with any `a/` prefix removed; `None` for `/dev/null` (file creation).
    pub old_path: Option<String>,
    /// New path with any `b/` prefix removed; `None` for `/dev/null` (file deletion).
    pub new_path: Option<String>,
    /// Hunks in file order.
    pub hunks: Vec<Hunk>,
    /// The old file's last line had `\ No newline at end of file`.
    pub old_no_newline: bool,
    /// The new file's last line had `\ No newline at end of file`.
    pub new_no_newline: bool,
}

impl FilePatch {
    /// The path this patch writes to (the new path, or the old path for deletions).
    pub fn path(&self) -> Option<&str> {
        self.new_path.as_deref().or(self.old_path.as_deref())
    }

    /// The patch creates a file (`--- /dev/null`).
    pub fn is_new_file(&self) -> bool {
        self.old_path.is_none()
    }

    /// The patch deletes a file (`+++ /dev/null`).
    pub fn is_deletion(&self) -> bool {
        self.new_path.is_none()
    }

    /// The patch renames a file (old and new paths differ).
    pub fn is_rename(&self) -> bool {
        matches!((&self.old_path, &self.new_path), (Some(a), Some(b)) if a != b)
    }

    /// Apply this patch to `original` and return the new content.
    ///
    /// Each hunk is matched exactly, then with trailing whitespace ignored; the match
    /// closest to the hunk's stated position wins. CRLF line endings are preserved.
    pub fn apply(&self, original: &str) -> Result<String> {
        let crlf = original.contains("\r\n");
        let src: Vec<&str> = original.lines().collect();
        let mut out: Vec<&str> = Vec::with_capacity(src.len() + 16);
        let mut cursor = 0usize;

        for (idx, hunk) in self.hunks.iter().enumerate() {
            let old: Vec<&str> = hunk.old_lines().collect();
            let pos = if old.is_empty() {
                // Pure insertion: `-N,0` means "after line N".
                let want = if hunk.old_start == 0 && idx > 0 {
                    cursor
                } else {
                    hunk.old_start
                };
                want.clamp(cursor, src.len())
            } else {
                let expected = if hunk.old_start == 0 {
                    cursor
                } else {
                    hunk.old_start - 1
                };
                find_nearest(&src, &old, cursor, expected, |a, b| a == b)
                    .or_else(|| {
                        find_nearest(&src, &old, cursor, expected, |a, b| {
                            a.trim_end() == b.trim_end()
                        })
                    })
                    .ok_or_else(|| CodeParserError::PatchConflict {
                        file: self.path().unwrap_or("<unknown>").to_string(),
                        hunk: idx + 1,
                    })?
            };
            out.extend_from_slice(&src[cursor..pos]);
            out.extend(hunk.new_lines());
            cursor = pos + old.len();
        }
        out.extend_from_slice(&src[cursor..]);

        if out.is_empty() {
            return Ok(String::new());
        }
        let nl = if crlf { "\r\n" } else { "\n" };
        let mut result = out.join(nl);
        let trailing = if self.new_no_newline {
            false
        } else {
            self.old_no_newline || original.is_empty() || original.ends_with('\n')
        };
        if trailing {
            result.push_str(nl);
        }
        Ok(result)
    }
}

/// Find `needle` in `hay[from..]`, preferring the start position nearest `expected`.
fn find_nearest(
    hay: &[&str],
    needle: &[&str],
    from: usize,
    expected: usize,
    eq: impl Fn(&str, &str) -> bool,
) -> Option<usize> {
    if needle.len() > hay.len() {
        return None;
    }
    let last = hay.len() - needle.len();
    if from > last {
        return None;
    }
    let expected = expected.clamp(from, last);
    let matches_at = |p: usize| {
        hay[p..p + needle.len()]
            .iter()
            .zip(needle)
            .all(|(a, b)| eq(a, b))
    };
    for d in 0..=(last - from) {
        if let Some(p) = expected.checked_add(d)
            && p <= last
            && matches_at(p)
        {
            return Some(p);
        }
        if d > 0
            && let Some(p) = expected.checked_sub(d)
            && p >= from
            && matches_at(p)
        {
            return Some(p);
        }
    }
    None
}

static HUNK_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^@@+ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@+").expect("valid regex")
});

/// Parse every file section of a unified diff found in `text`.
///
/// Surrounding prose is ignored. Returns [`CodeParserError::InvalidPatch`] if no
/// `--- ` / `+++ ` header pair with at least one hunk is found.
pub(crate) fn parse(text: &str) -> Result<Vec<FilePatch>> {
    let lines = split_lines(text);
    let mut patches = Vec::new();
    let mut i = 0;

    while i + 1 < lines.len() {
        let (Some(old_raw), Some(new_raw)) = (
            lines[i].strip_prefix("--- "),
            lines[i + 1].strip_prefix("+++ "),
        ) else {
            i += 1;
            continue;
        };
        let (old_path, new_path) = header_paths(old_raw, new_raw);
        i += 2;

        if old_path.is_none() && new_path.is_none() {
            return Err(CodeParserError::InvalidPatch(
                "both sides of the diff are /dev/null".to_string(),
            ));
        }

        let mut patch = FilePatch {
            old_path,
            new_path,
            hunks: Vec::new(),
            old_no_newline: false,
            new_no_newline: false,
        };
        while i < lines.len() && lines[i].starts_with("@@") {
            let (hunk, next) = parse_hunk(&lines, i, &mut patch);
            i = next;
            if !hunk.lines.is_empty() {
                patch.hunks.push(hunk);
            }
        }

        if patch.hunks.is_empty() {
            return Err(CodeParserError::InvalidPatch(format!(
                "no hunks for {}",
                patch.path().unwrap_or("<unknown>")
            )));
        }
        patches.push(patch);
    }

    if patches.is_empty() {
        return Err(CodeParserError::InvalidPatch(
            "no '--- ' / '+++ ' file headers found".to_string(),
        ));
    }
    Ok(patches)
}

/// Parse the hunk whose header is at `lines[start]`. Returns the hunk and the next index.
fn parse_hunk(lines: &[&str], start: usize, patch: &mut FilePatch) -> (Hunk, usize) {
    let caps = HUNK_RE.captures(lines[start]);
    let num = |n: usize| {
        caps.as_ref()
            .and_then(|c| c.get(n))
            .and_then(|m| m.as_str().parse::<usize>().ok())
    };
    let old_start = num(1).unwrap_or(0);
    let new_start = num(3).unwrap_or(0);
    // A missing count means 1 when the header itself parsed.
    let (old_count, new_count) = if caps.is_some() {
        (Some(num(2).unwrap_or(1)), Some(num(4).unwrap_or(1)))
    } else {
        (None, None)
    };
    let counted = old_count.zip(new_count);

    let mut hunk = Hunk {
        old_start,
        old_count,
        new_start,
        new_count,
        lines: Vec::new(),
    };
    // Tracks which lines came from completely empty input lines (lost ' ' prefix).
    let mut from_empty: Vec<bool> = Vec::new();
    let (mut old_seen, mut new_seen) = (0usize, 0usize);
    let mut i = start + 1;

    while i < lines.len() {
        let line = lines[i];
        if let Some((oc, nc)) = counted
            && old_seen >= oc
            && new_seen >= nc
        {
            // Counts satisfied; only a trailing "\ No newline" marker may follow.
            if line.starts_with('\\') {
                mark_no_newline(&hunk, patch);
                i += 1;
            }
            break;
        }
        if line.starts_with("@@") || line.starts_with("diff ") {
            break;
        }
        if counted.is_none()
            && line.starts_with("--- ")
            && lines.get(i + 1).is_some_and(|n| n.starts_with("+++ "))
        {
            break;
        }
        let parsed = match line.as_bytes().first() {
            None => Some((HunkLine::Context(String::new()), true)),
            Some(b' ') => Some((HunkLine::Context(line[1..].to_string()), false)),
            Some(b'-') => Some((HunkLine::Removed(line[1..].to_string()), false)),
            Some(b'+') => Some((HunkLine::Added(line[1..].to_string()), false)),
            Some(b'\\') => {
                mark_no_newline(&hunk, patch);
                i += 1;
                continue;
            },
            Some(_) => None,
        };
        let Some((hl, empty)) = parsed else {
            break;
        };
        match hl {
            HunkLine::Context(_) => {
                old_seen += 1;
                new_seen += 1;
            },
            HunkLine::Removed(_) => old_seen += 1,
            HunkLine::Added(_) => new_seen += 1,
        }
        hunk.lines.push(hl);
        from_empty.push(empty);
        i += 1;
    }

    // Blank lines that trail a hunk are usually prose separators, not context,
    // unless the header's counts (exactly satisfied) say they belong to the hunk.
    let counts_exact = counted.is_some_and(|(oc, nc)| old_seen == oc && new_seen == nc);
    if !counts_exact {
        while from_empty.last() == Some(&true) {
            from_empty.pop();
            hunk.lines.pop();
        }
    }
    (hunk, i)
}

fn mark_no_newline(hunk: &Hunk, patch: &mut FilePatch) {
    match hunk.lines.last() {
        Some(HunkLine::Removed(_)) => patch.old_no_newline = true,
        Some(HunkLine::Added(_)) => patch.new_no_newline = true,
        Some(HunkLine::Context(_)) => {
            patch.old_no_newline = true;
            patch.new_no_newline = true;
        },
        None => {},
    }
}

/// Extract the path from a `---`/`+++` header value (drops timestamps and quotes).
fn header_path(raw: &str) -> Option<String> {
    let raw = raw.trim();
    let path = if let Some(rest) = raw.strip_prefix('"') {
        rest.split('"').next().unwrap_or("")
    } else {
        raw.split(['\t', ' ']).next().unwrap_or("")
    };
    if path.is_empty() || path == "/dev/null" {
        None
    } else {
        Some(path.to_string())
    }
}

/// Resolve both header paths, stripping git's `a/` and `b/` prefixes.
fn header_paths(old_raw: &str, new_raw: &str) -> (Option<String>, Option<String>) {
    let old = header_path(old_raw);
    let new = header_path(new_raw);
    let old_git = old.as_deref().is_none_or(|p| p.starts_with("a/"));
    let new_git = new.as_deref().is_none_or(|p| p.starts_with("b/"));
    if old_git && new_git {
        let strip = |p: Option<String>| p.map(|p| p[2..].to_string());
        (strip(old), strip(new))
    } else {
        (old, new)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SIMPLE: &str = "\
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,3 +1,3 @@
 fn a() {}
-fn b() {}
+fn b() -> u8 { 1 }
 fn c() {}
";

    #[test]
    fn parses_git_style() {
        let p = parse(SIMPLE).unwrap();
        assert_eq!(p.len(), 1);
        assert_eq!(p[0].old_path.as_deref(), Some("src/lib.rs"));
        assert_eq!(p[0].new_path.as_deref(), Some("src/lib.rs"));
        assert_eq!(p[0].hunks[0].lines.len(), 4);
    }

    #[test]
    fn applies_with_drift() {
        let p = &parse(SIMPLE).unwrap()[0];
        let src = "// header\n// more\nfn a() {}\nfn b() {}\nfn c() {}\n";
        assert_eq!(
            p.apply(src).unwrap(),
            "// header\n// more\nfn a() {}\nfn b() -> u8 { 1 }\nfn c() {}\n"
        );
    }

    #[test]
    fn conflict_is_reported() {
        let p = &parse(SIMPLE).unwrap()[0];
        assert!(matches!(
            p.apply("nothing here\n"),
            Err(CodeParserError::PatchConflict { hunk: 1, .. })
        ));
    }

    #[test]
    fn counted_hunk_keeps_sql_comment_removal() {
        let d = "--- q.sql\n+++ q.sql\n@@ -1,2 +1,1 @@\n--- old comment\n SELECT 1;\n";
        let p = &parse(d).unwrap()[0];
        assert_eq!(
            p.apply("-- old comment\nSELECT 1;\n").unwrap(),
            "SELECT 1;\n"
        );
    }

    #[test]
    fn bare_hunk_headers_and_new_file() {
        let d = "--- /dev/null\n+++ b/new.txt\n@@\n+hello\n+world\n\nSome prose after.";
        let p = &parse(d).unwrap()[0];
        assert!(p.is_new_file());
        assert_eq!(p.path(), Some("new.txt"));
        assert_eq!(p.apply("").unwrap(), "hello\nworld\n");
    }

    #[test]
    fn no_newline_marker() {
        let d = "--- a\n+++ a\n@@ -1 +1 @@\n-x\n+y\n\\ No newline at end of file\n";
        let p = &parse(d).unwrap()[0];
        assert_eq!(p.apply("x\n").unwrap(), "y");
    }

    #[test]
    fn crlf_is_preserved() {
        let p = &parse(SIMPLE).unwrap()[0];
        let src = "fn a() {}\r\nfn b() {}\r\nfn c() {}\r\n";
        assert_eq!(
            p.apply(src).unwrap(),
            "fn a() {}\r\nfn b() -> u8 { 1 }\r\nfn c() {}\r\n"
        );
    }

    #[test]
    fn rejects_garbage() {
        assert!(parse("hello").is_err());
        assert!(parse("--- a\n+++ b\nno hunks").is_err());
        assert!(parse("--- /dev/null\n+++ /dev/null\n@@\n+x").is_err());
    }
}
