//! Validation and normalization of model-generated unified diffs.
//!
//! Diffs written by a language model are frequently *almost* valid: CRLF line
//! endings, a surrounding ```` ```diff ```` fence, missing `---`/`+++` headers,
//! headers without the `a/`/`b/` prefixes, `diff --git`/`index` lines that do
//! not match the content, or no trailing newline. This module turns each
//! [`FileChange`] into a canonical traditional unified diff with
//! `--- a/<path>` / `+++ b/<path>` headers suitable for `git apply` (or
//! `patch -p1`).
//!
//! It also enforces that a change only touches the path it declares, and that
//! the path is a safe, repository-relative location.

use anyhow::{Result, bail};

use crate::review::FileChange;

/// A file change whose path has been validated and whose diff is canonical.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PreparedChange {
    /// Normalized repository-relative path (forward slashes, no `./`).
    pub path: String,
    /// Canonical unified diff for `path`, ending in a newline.
    pub diff: String,
    /// Optional blob SHA the diff was generated against.
    pub original_sha: Option<String>,
}

/// Validate a repository-relative path and return its normalized form.
///
/// Rejects empty paths, absolute paths (Unix, UNC, or drive-letter), `..`
/// components, anything inside a `.git` directory, and control characters.
pub fn normalize_path(raw: &str) -> Result<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        bail!("File path is empty");
    }
    if trimmed.chars().any(char::is_control) {
        bail!("File path {raw:?} contains control characters");
    }
    let unified = trimmed.replace('\\', "/");
    let bytes = unified.as_bytes();
    if unified.starts_with('/') || (bytes.len() >= 2 && bytes[1] == b':') {
        bail!("File path {raw:?} must be relative to the repository root");
    }

    let mut parts = Vec::new();
    for component in unified.split('/') {
        match component {
            "" | "." => continue,
            ".." => bail!("File path {raw:?} must not contain `..`"),
            c if c.eq_ignore_ascii_case(".git") => {
                bail!("File path {raw:?} must not point inside .git")
            },
            c => parts.push(c),
        }
    }
    if parts.is_empty() {
        bail!("File path {raw:?} does not name a file");
    }
    Ok(parts.join("/"))
}

/// Validate and canonicalize a single file change.
pub fn prepare_change(change: &FileChange) -> Result<PreparedChange> {
    let path = normalize_path(&change.path)?;
    let diff = normalize_diff(&path, &change.diff)?;
    Ok(PreparedChange {
        path,
        diff,
        original_sha: change.original_sha.clone(),
    })
}

/// Validate and canonicalize a set of file changes.
///
/// Fails on the first invalid change, naming it, so nothing is applied when any
/// change is unusable.
pub fn prepare_changes(changes: &[FileChange]) -> Result<Vec<PreparedChange>> {
    changes
        .iter()
        .enumerate()
        .map(|(i, change)| {
            prepare_change(change).map_err(|e| e.context(format!("file_changes[{i}]")))
        })
        .collect()
}

/// Concatenate prepared diffs into one patch, so it can be applied atomically.
pub fn combine(changes: &[PreparedChange]) -> String {
    changes.iter().map(|c| c.diff.as_str()).collect()
}

/// Rewrite a model-generated diff for `path` into canonical form.
fn normalize_diff(path: &str, raw: &str) -> Result<String> {
    let unix = raw.replace("\r\n", "\n").replace('\r', "\n");
    let lines: Vec<&str> = strip_code_fence(unix.lines().collect());

    let mut out = String::with_capacity(unix.len() + 2 * path.len() + 32);
    let mut hunk: Option<Hunk> = None;
    let mut saw_hunk = false;
    let mut pending_header = false;
    let mut i = 0;

    while i < lines.len() {
        let line = lines[i];
        let in_hunk = hunk.is_some();

        // A `---`/`+++` pair followed by a hunk header is a file header, even
        // inside a previous hunk (a removed line starting with "-- " would not
        // be followed by "+++ " and "@@").
        if is_file_header(&lines, i, in_hunk)
            && let Some(old) = line.strip_prefix("--- ")
            && let Some(new) = lines[i + 1].strip_prefix("+++ ")
        {
            flush_hunk(&mut out, hunk.take(), path)?;
            let old = header_path(old);
            let new = header_path(new);
            check_header_path(path, old)?;
            check_header_path(path, new)?;
            if old.is_none() && new.is_none() {
                bail!("Diff for {path} has /dev/null on both sides");
            }
            let old = old.map_or_else(|| "/dev/null".to_string(), |_| format!("a/{path}"));
            let new = new.map_or_else(|| "/dev/null".to_string(), |_| format!("b/{path}"));
            out.push_str(&format!("--- {old}\n+++ {new}\n"));
            pending_header = false;
            i += 2;
            continue;
        }

        if line.starts_with("@@") {
            flush_hunk(&mut out, hunk.take(), path)?;
            if !saw_hunk && out.is_empty() {
                // Hunks without file headers: synthesize them.
                out.push_str(&format!("--- a/{path}\n+++ b/{path}\n"));
            } else if pending_header {
                bail!("Diff for {path} has a hunk after an incomplete file header");
            }
            hunk = Some(Hunk::parse(line).ok_or_else(|| {
                anyhow::anyhow!("Diff for {path} has a malformed hunk header: {line:?}")
            })?);
            saw_hunk = true;
            i += 1;
            continue;
        }

        if let Some(current) = hunk.as_mut() {
            match line.chars().next() {
                Some(' ' | '+' | '-' | '\\') => current.push(line),
                // Blank context line whose leading space was stripped -- unless
                // it merely separates this hunk from whatever follows.
                None if continues_hunk(&lines, i, true) => current.push(" "),
                None => {},
                // Trailing prose after the hunk ends it.
                Some(_) => flush_hunk(&mut out, hunk.take(), path)?,
            }
        } else if let Some(rest) = line.strip_prefix("diff --git ") {
            // Extended git header: validate, then drop (we emit a traditional diff).
            let rest = rest.trim();
            let accepted = [
                format!("a/{path} b/{path}"),
                format!("\"a/{path}\" \"b/{path}\""),
                format!("{path} {path}"),
            ];
            if !accepted.iter().any(|a| a == rest) {
                bail!("Diff declared for {path} has a git header for a different file: {line:?}");
            }
            pending_header = true;
        } else if line.starts_with("--- ") || line.starts_with("+++ ") {
            bail!("Diff for {path} has an incomplete file header: {line:?}");
        }
        // Anything else outside a hunk (index/mode lines, prose) is dropped.
        i += 1;
    }
    flush_hunk(&mut out, hunk.take(), path)?;

    if !saw_hunk {
        bail!("Diff for {path} contains no hunks (expected lines starting with \"@@ -\")");
    }
    Ok(out)
}

/// A hunk being collected, so its header can be rewritten with correct counts.
///
/// Models routinely get the `@@ -a,b +c,d @@` line counts wrong; `git apply`
/// would then reject the hunk or misread the next file's `---` header as a
/// removed line. Start positions are kept, since `git apply` tolerates offsets.
struct Hunk {
    old_start: u64,
    new_start: u64,
    /// Section text after the closing `@@` (e.g. a function name).
    section: String,
    body: String,
    old_lines: u64,
    new_lines: u64,
}

impl Hunk {
    /// Parse `@@ -a[,b] +c[,d] @@[ section]`, ignoring the counts.
    fn parse(header: &str) -> Option<Self> {
        let rest = header.strip_prefix("@@ -")?;
        let (ranges, section) = rest.split_once(" @@").or_else(|| rest.split_once("@@"))?;
        let (old, new) = ranges.trim().split_once(" +")?;
        let start = |range: &str| range.split(',').next()?.trim().parse::<u64>().ok();
        Some(Self {
            old_start: start(old)?,
            new_start: start(new)?,
            section: section.to_string(),
            body: String::new(),
            old_lines: 0,
            new_lines: 0,
        })
    }

    fn push(&mut self, line: &str) {
        match line.as_bytes().first() {
            Some(b' ') => {
                self.old_lines += 1;
                self.new_lines += 1;
            },
            Some(b'-') => self.old_lines += 1,
            Some(b'+') => self.new_lines += 1,
            _ => {},
        }
        self.body.push_str(line);
        self.body.push('\n');
    }
}

/// Append a finished hunk to `out` with a recounted header.
fn flush_hunk(out: &mut String, hunk: Option<Hunk>, path: &str) -> Result<()> {
    let Some(h) = hunk else {
        return Ok(());
    };
    if h.old_lines == 0 && h.new_lines == 0 {
        bail!("Diff for {path} has an empty hunk");
    }
    // Keep the model's start positions; only a non-empty range cannot start at 0.
    let old_start = if h.old_lines > 0 {
        h.old_start.max(1)
    } else {
        h.old_start
    };
    let new_start = if h.new_lines > 0 {
        h.new_start.max(1)
    } else {
        h.new_start
    };
    out.push_str(&format!(
        "@@ -{old_start},{} +{new_start},{} @@{}\n",
        h.old_lines, h.new_lines, h.section
    ));
    out.push_str(&h.body);
    Ok(())
}

/// Whether `lines[i]` starts a `---`/`+++` file header.
///
/// Inside a hunk the pair must be followed by a hunk header, so that removed
/// lines which happen to start with `-- ` are not mistaken for headers.
fn is_file_header(lines: &[&str], i: usize, in_hunk: bool) -> bool {
    lines[i].starts_with("--- ")
        && lines.get(i + 1).is_some_and(|l| l.starts_with("+++ "))
        && match lines.get(i + 2) {
            Some(next) => next.starts_with("@@"),
            None => !in_hunk,
        }
}

/// Whether the blank line at `i` is followed (after more blanks) by hunk body.
fn continues_hunk(lines: &[&str], i: usize, in_hunk: bool) -> bool {
    let Some(j) = lines[i..].iter().position(|l| !l.is_empty()).map(|p| p + i) else {
        return false;
    };
    let next = lines[j];
    matches!(next.chars().next(), Some(' ' | '+' | '-' | '\\'))
        && !is_file_header(lines, j, in_hunk)
}

/// Remove a surrounding markdown code fence, if present.
fn strip_code_fence(mut lines: Vec<&str>) -> Vec<&str> {
    let first = lines.iter().position(|l| !l.trim().is_empty());
    let last = lines.iter().rposition(|l| !l.trim().is_empty());
    if let (Some(first), Some(last)) = (first, last)
        && first < last
        && lines[first].trim_start().starts_with("```")
        && lines[last].trim() == "```"
    {
        lines.truncate(last);
        lines.drain(..=first);
    }
    lines
}

/// Extract the path from a header token, stripping timestamps and `a/`/`b/`.
///
/// Returns `None` for `/dev/null`.
fn header_path(token: &str) -> Option<&str> {
    let token = token.split('\t').next().unwrap_or(token).trim();
    let token = token.trim_matches('"');
    if token == "/dev/null" {
        return None;
    }
    Some(
        token
            .strip_prefix("a/")
            .or_else(|| token.strip_prefix("b/"))
            .unwrap_or(token),
    )
}

/// Ensure a header path refers to the declared file.
fn check_header_path(declared: &str, header: Option<&str>) -> Result<()> {
    let Some(header) = header else {
        return Ok(());
    };
    let normalized = normalize_path(header).ok();
    if normalized.as_deref() == Some(declared) {
        Ok(())
    } else {
        bail!("Diff declared for {declared} modifies a different file ({header})")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn change(path: &str, diff: &str) -> FileChange {
        FileChange {
            path: path.to_string(),
            diff: diff.to_string(),
            original_sha: None,
        }
    }

    #[test]
    fn path_normalization() {
        assert_eq!(normalize_path("src/main.rs").unwrap(), "src/main.rs");
        assert_eq!(normalize_path("./src//main.rs ").unwrap(), "src/main.rs");
        assert_eq!(normalize_path("src\\lib.rs").unwrap(), "src/lib.rs");
        for bad in [
            "",
            "/etc/passwd",
            "\\\\server\\share",
            "C:/x.rs",
            "../x.rs",
            "a/../../x",
            ".git/config",
            "sub/.GIT/hooks/pre-commit",
            "a\0b",
            "./",
        ] {
            assert!(normalize_path(bad).is_err(), "should reject {bad:?}");
        }
    }

    #[test]
    fn canonical_diff_passes_through() {
        let diff = "--- a/src/db.rs\n+++ b/src/db.rs\n@@ -1,1 +1,1 @@\n-bad\n+good\n";
        assert_eq!(
            prepare_change(&change("src/db.rs", diff)).unwrap().diff,
            diff
        );
    }

    #[test]
    fn crlf_fence_and_missing_trailing_newline_are_fixed() {
        let diff = "```diff\r\n--- a/x.rs\r\n+++ b/x.rs\r\n@@ -1 +1 @@\r\n-a\r\n+b\r\n```";
        assert_eq!(
            prepare_change(&change("x.rs", diff)).unwrap().diff,
            "--- a/x.rs\n+++ b/x.rs\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        );
    }

    #[test]
    fn headers_are_synthesized_for_bare_hunks() {
        let out = prepare_change(&change("lib.rs", "@@ -1,2 +1,2 @@\n ctx\n-a\n+b")).unwrap();
        assert_eq!(
            out.diff,
            "--- a/lib.rs\n+++ b/lib.rs\n@@ -1,2 +1,2 @@\n ctx\n-a\n+b\n"
        );
    }

    #[test]
    fn unprefixed_headers_and_git_extended_lines_are_canonicalized() {
        let diff = "diff --git a/x.rs b/x.rs\nindex 111..222 100644\n\
                    --- x.rs\t2026-01-01 00:00:00\n+++ x.rs\n@@ -1 +1 @@\n-a\n+b\n";
        assert_eq!(
            prepare_change(&change("x.rs", diff)).unwrap().diff,
            "--- a/x.rs\n+++ b/x.rs\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        );
    }

    #[test]
    fn new_and_deleted_files_keep_dev_null() {
        let new = "--- /dev/null\n+++ b/new.rs\n@@ -0,0 +1,1 @@\n+fn x() {}\n";
        assert_eq!(prepare_change(&change("new.rs", new)).unwrap().diff, new);
        let del = "--- a/old.rs\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-fn x() {}\n";
        assert_eq!(prepare_change(&change("old.rs", del)).unwrap().diff, del);
    }

    #[test]
    fn blank_context_lines_are_restored_and_prose_dropped() {
        let diff = "Here is the fix:\n@@ -1,9 +1,1 @@ fn main\n a\n\n-b\n+c\nThat should do it.";
        assert_eq!(
            prepare_change(&change("f.txt", diff)).unwrap().diff,
            "--- a/f.txt\n+++ b/f.txt\n@@ -1,3 +1,3 @@ fn main\n a\n \n-b\n+c\n"
        );
    }

    #[test]
    fn removed_line_resembling_header_is_kept() {
        let diff = "@@ -1,2 +1,1 @@\n--- not a header\n+++ still not\n";
        let out = prepare_change(&change("f.md", diff)).unwrap();
        assert!(out.diff.contains("\n--- not a header\n+++ still not\n"));
    }

    #[test]
    fn diff_touching_other_file_is_rejected() {
        let diff = "--- a/src/other.rs\n+++ b/src/other.rs\n@@ -1 +1 @@\n-a\n+b\n";
        let err = prepare_change(&change("src/db.rs", diff)).unwrap_err();
        assert!(err.to_string().contains("different file"));

        let git = "diff --git a/.github/x.yml b/.github/x.yml\n@@ -1 +1 @@\n-a\n+b\n";
        assert!(prepare_change(&change("src/db.rs", git)).is_err());

        let multi = "--- a/x.rs\n+++ b/x.rs\n@@ -1 +1 @@\n-a\n+b\n\
                     --- a/y.rs\n+++ b/y.rs\n@@ -1 +1 @@\n-a\n+b\n";
        assert!(prepare_change(&change("x.rs", multi)).is_err());
    }

    #[test]
    fn diffs_without_hunks_or_bad_headers_are_rejected() {
        for bad in [
            "just some text",
            "--- a/x.rs\n+++ b/x.rs\n",
            "@@ bogus @@\n-a\n+b\n",
            "--- a/x.rs\n@@ -1 +1 @@\n-a\n+b\n",
            "--- /dev/null\n+++ /dev/null\n@@ -1 +1 @@\n-a\n+b\n",
        ] {
            assert!(
                prepare_change(&change("x.rs", bad)).is_err(),
                "should reject {bad:?}"
            );
        }
    }

    #[test]
    fn unsafe_paths_are_rejected_before_diff_parsing() {
        let diff = "@@ -1 +1 @@\n-a\n+b\n";
        assert!(prepare_change(&change("../escape.rs", diff)).is_err());
        assert!(prepare_change(&change(".git/hooks/post-commit", diff)).is_err());
    }

    #[test]
    fn prepare_changes_reports_index_and_combine_concatenates() {
        let ok = change("a.rs", "@@ -1 +1 @@\n-a\n+b");
        let bad = change("b.rs", "nothing");
        let err = prepare_changes(&[ok.clone(), bad]).unwrap_err();
        assert!(format!("{err:#}").contains("file_changes[1]"));

        let prepared = prepare_changes(&[ok, change("c.rs", "@@ -1 +1 @@\n-c\n+d")]).unwrap();
        let combined = combine(&prepared);
        assert!(combined.starts_with("--- a/a.rs\n"));
        assert!(combined.contains("\n--- a/c.rs\n"));
    }

    #[test]
    fn huge_diff_is_handled() {
        let mut diff = String::from("@@ -1,50000 +1,50000 @@\n");
        for i in 0..50_000 {
            diff.push_str(&format!("-line {i}\n+LINE {i}\n"));
        }
        let out = prepare_change(&change("big.txt", &diff)).unwrap();
        assert_eq!(out.diff.lines().count(), 100_003);
    }

    #[test]
    fn hunk_counts_are_recounted_and_separators_dropped() {
        let diff = "@@ -2,7 +2,9 @@ fn a()\n x\n-y\n+z\n\n\n@@ -20 +20 @@\n q\n+r\n\n";
        assert_eq!(
            prepare_change(&change("m.rs", diff)).unwrap().diff,
            "--- a/m.rs\n+++ b/m.rs\n@@ -2,2 +2,2 @@ fn a()\n x\n-y\n+z\n@@ -20,1 +20,2 @@\n q\n+r\n"
        );
    }

    #[test]
    fn no_newline_marker_is_preserved_but_not_counted() {
        let diff = "@@ -1 +1 @@\n-a\n\\ No newline at end of file\n+b\n";
        assert_eq!(
            prepare_change(&change("n.txt", diff)).unwrap().diff,
            "--- a/n.txt\n+++ b/n.txt\n@@ -1,1 +1,1 @@\n-a\n\\ No newline at end of file\n+b\n"
        );
    }
}
