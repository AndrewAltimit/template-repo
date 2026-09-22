//! Edit instructions: inline "change X to Y" sentences and SEARCH/REPLACE blocks.

use std::borrow::Cow;
use std::sync::LazyLock;

use regex::Regex;
use tracing::warn;

use crate::block::filename_from_line;
use crate::error::{CodeParserError, Result};
use crate::path::looks_like_path;
use crate::text::{line_of, newline_of, split_lines};

/// A targeted text replacement extracted from an AI response.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EditInstruction {
    /// The file to edit (raw; sanitized when applied).
    pub file: String,
    /// The text to find. Empty means "append `new`" (or create the file).
    pub old: String,
    /// The replacement text.
    pub new: String,
}

/// ``In file `x`, change `old` to `new` ``
static INLINE_TICK_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?i)\b(?:In|Edit|Modify|Update)\s+(?:the\s+)?(?:file\s+)?`([^`]+)`[,:]?\s*(?:change|replace|update)\s+`([^`]+)`\s+(?:to|with)\s+`([^`]+)`",
    )
    .expect("valid regex")
});

/// `In file x, change "old" to "new"`
static INLINE_QUOTE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r#"(?i)\b(?:In|Edit|Modify|Update)\s+(?:the\s+)?(?:file\s+)?([^\s,:]+)[,:]?\s*(?:change|replace|update)\s+"([^"]+)"\s+(?:to|with)\s+"([^"]+)""#,
    )
    .expect("valid regex")
});

static SEARCH_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*<{5,9}\s*SEARCH\s*$").expect("valid regex"));
static DIVIDER_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*={5,9}\s*$").expect("valid regex"));
static REPLACE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*>{5,9}\s*REPLACE\s*$").expect("valid regex"));

/// Parse all edit instructions in `response`, in document order.
pub(crate) fn parse(response: &str) -> Vec<EditInstruction> {
    let mut found: Vec<(usize, EditInstruction)> = Vec::new();

    for re in [&*INLINE_TICK_RE, &*INLINE_QUOTE_RE] {
        for caps in re.captures_iter(response) {
            let (Some(whole), Some(file), Some(old), Some(new)) =
                (caps.get(0), caps.get(1), caps.get(2), caps.get(3))
            else {
                continue;
            };
            let file = file
                .as_str()
                .trim_matches(|c| c == '`' || c == '"' || c == '\'');
            if !looks_like_path(file) {
                continue;
            }
            found.push((
                line_of(response, whole.start()),
                EditInstruction {
                    file: file.to_string(),
                    old: old.as_str().to_string(),
                    new: new.as_str().to_string(),
                },
            ));
        }
    }

    found.extend(parse_search_replace(&split_lines(response)));
    found.sort_by_key(|(line, _)| *line);
    found.into_iter().map(|(_, e)| e).collect()
}

/// Parse Aider-style blocks:
///
/// ```text
/// path/to/file.py
/// <<<<<<< SEARCH
/// old
/// =======
/// new
/// >>>>>>> REPLACE
/// ```
///
/// The filename is taken from the nearest preceding path-like line (or a fence info
/// string). Consecutive blocks with nothing but blank/fence lines between them
/// inherit the previous block's file. Unterminated blocks are dropped.
fn parse_search_replace(lines: &[&str]) -> Vec<(usize, EditInstruction)> {
    let mut out = Vec::new();
    let mut last_file: Option<String> = None;
    let mut last_end: Option<usize> = None;
    let mut i = 0;

    while i < lines.len() {
        if !SEARCH_RE.is_match(lines[i]) {
            i += 1;
            continue;
        }
        let start = i;
        let lower = last_end.map_or(0, |e| e + 1);
        let file = file_before(&lines[lower..start]).or_else(|| {
            let only_separators = lines[lower..start]
                .iter()
                .all(|l| l.trim().is_empty() || is_fence(l));
            if last_end.is_some() && only_separators {
                last_file.clone()
            } else {
                None
            }
        });

        let Some(divider) = (start + 1..lines.len()).find(|&j| DIVIDER_RE.is_match(lines[j]))
        else {
            warn!("Unterminated SEARCH block at line {}", start + 1);
            break;
        };
        let Some(end) = (divider + 1..lines.len()).find(|&j| REPLACE_RE.is_match(lines[j])) else {
            warn!("SEARCH block at line {} has no REPLACE marker", start + 1);
            break;
        };

        match file {
            Some(file) => {
                out.push((
                    start,
                    EditInstruction {
                        file: file.clone(),
                        old: lines[start + 1..divider].join("\n"),
                        new: lines[divider + 1..end].join("\n"),
                    },
                ));
                last_file = Some(file);
            },
            None => warn!("SEARCH/REPLACE block at line {} has no filename", start + 1),
        }
        last_end = Some(end);
        i = end + 1;
    }
    out
}

fn is_fence(line: &str) -> bool {
    let t = line.trim_start();
    t.starts_with("```") || t.starts_with("~~~")
}

/// Look back (up to 3 non-blank lines) for the file a SEARCH block applies to.
fn file_before(lines: &[&str]) -> Option<String> {
    lines
        .iter()
        .rev()
        .filter(|l| !l.trim().is_empty())
        .take(3)
        .find_map(|line| {
            if is_fence(line) {
                let info = line.trim().trim_start_matches(['`', '~']).trim();
                return info
                    .split_whitespace()
                    .map(|t| t.rsplit_once(':').map_or(t, |(_, p)| p))
                    .find(|t| looks_like_path(t))
                    .map(str::to_string);
            }
            filename_from_line(line)
        })
}

/// Apply one edit to `content`.
///
/// The old text must match exactly once. CRLF files are handled transparently; if no
/// exact match exists, a line-wise match that ignores trailing whitespace is tried.
/// An empty `old` appends `new` (which also covers creating a new file from `""`).
pub(crate) fn apply(content: &str, edit: &EditInstruction) -> Result<String> {
    if edit.old.is_empty() {
        let mut out = content.to_string();
        if !out.is_empty() && !out.ends_with('\n') {
            out.push_str(newline_of(content));
        }
        out.push_str(&edit.new);
        if !edit.new.is_empty() && !out.ends_with('\n') {
            out.push('\n');
        }
        return Ok(out);
    }

    let (old, new): (Cow<'_, str>, Cow<'_, str>) =
        if content.contains("\r\n") && !edit.old.contains("\r\n") {
            (
                edit.old.replace('\n', "\r\n").into(),
                edit.new.replace('\n', "\r\n").into(),
            )
        } else {
            (edit.old.as_str().into(), edit.new.as_str().into())
        };

    match content.matches(old.as_ref()).count() {
        1 => Ok(content.replacen(old.as_ref(), new.as_ref(), 1)),
        0 => replace_lines_loosely(content, edit)?.ok_or_else(|| CodeParserError::SearchNotFound {
            file: edit.file.clone(),
        }),
        count => Err(CodeParserError::AmbiguousEdit {
            file: edit.file.clone(),
            count,
        }),
    }
}

/// Line-wise replacement ignoring trailing whitespace differences.
fn replace_lines_loosely(content: &str, edit: &EditInstruction) -> Result<Option<String>> {
    let old: Vec<&str> = edit.old.lines().map(str::trim_end).collect();
    if old.is_empty() {
        return Ok(None);
    }
    let src: Vec<&str> = content.lines().collect();
    let hits: Vec<usize> = src
        .windows(old.len())
        .enumerate()
        .filter(|(_, w)| w.iter().zip(&old).all(|(a, b)| a.trim_end() == *b))
        .map(|(p, _)| p)
        .collect();

    match hits.as_slice() {
        [] => Ok(None),
        [p] => {
            let nl = newline_of(content);
            let mut lines: Vec<&str> = Vec::with_capacity(src.len());
            lines.extend_from_slice(&src[..*p]);
            lines.extend(edit.new.lines());
            lines.extend_from_slice(&src[p + old.len()..]);
            let mut out = lines.join(nl);
            if content.ends_with('\n') && !out.is_empty() {
                out.push_str(nl);
            }
            Ok(Some(out))
        },
        many => Err(CodeParserError::AmbiguousEdit {
            file: edit.file.clone(),
            count: many.len(),
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn edit(old: &str, new: &str) -> EditInstruction {
        EditInstruction {
            file: "f.txt".into(),
            old: old.into(),
            new: new.into(),
        }
    }

    #[test]
    fn inline_requires_path_like_target() {
        let r = "In `foo()`, change `a` to `b`. Then in file `x.py`, replace `c` with `d`.";
        let e = parse(r);
        assert_eq!(e.len(), 1);
        assert_eq!(e[0].file, "x.py");
        // No word boundary: "Within" must not be read as "in".
        assert!(parse("Within `x.py`, change `a` to `b`").is_empty());
    }

    #[test]
    fn apply_exact_and_ambiguous() {
        assert_eq!(apply("a\nb\nc\n", &edit("b", "B")).unwrap(), "a\nB\nc\n");
        assert!(matches!(
            apply("x x", &edit("x", "y")),
            Err(CodeParserError::AmbiguousEdit { count: 2, .. })
        ));
        assert!(matches!(
            apply("abc", &edit("zzz", "y")),
            Err(CodeParserError::SearchNotFound { .. })
        ));
    }

    #[test]
    fn apply_crlf_and_trailing_ws() {
        assert_eq!(
            apply("a\r\nb\r\nc\r\n", &edit("a\nb", "x\ny")).unwrap(),
            "x\r\ny\r\nc\r\n"
        );
        assert_eq!(
            apply("a  \nb\t\nc\n", &edit("a\nb", "z")).unwrap(),
            "z\nc\n"
        );
    }

    #[test]
    fn apply_append() {
        assert_eq!(apply("", &edit("", "new")).unwrap(), "new\n");
        assert_eq!(apply("a", &edit("", "b")).unwrap(), "a\nb\n");
    }
}
