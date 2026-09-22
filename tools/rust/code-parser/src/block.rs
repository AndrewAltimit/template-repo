//! Fenced code block extraction and filename association.

use std::sync::LazyLock;

use regex::Regex;

use crate::language::language_for_path;
use crate::path::looks_like_path;
use crate::text::{split_lines, strip_indent};

/// Info-string languages whose blocks may legitimately contain nested fences.
const MARKDOWN_LANGS: &[&str] = &["markdown", "md", "mdx"];

/// How many non-blank prose lines above a fence are searched for a filename.
const CONTEXT_LINES: usize = 3;

/// A fenced code block extracted from an AI response.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CodeBlock {
    /// Language tag: from the fence info string, else inferred from `filename`, else `"text"`.
    pub language: String,
    /// Block content with line endings normalized to `\n`, fence indentation removed,
    /// and leading/trailing blank lines dropped. Has no trailing newline.
    pub content: String,
    /// File path associated with the block, if one was found. This is the raw
    /// value from the response; it is sanitized only when the block is applied.
    pub filename: Option<String>,
    /// Raw fence info string (everything after the opening fence), e.g. `"rust src/lib.rs"`.
    pub info: String,
    /// 1-based line number of the opening fence (0 for blocks built by hand).
    pub start_line: usize,
    /// `false` if the response ended before the closing fence (likely truncated output).
    pub terminated: bool,
}

impl CodeBlock {
    /// Create a new code block without a filename.
    pub fn new(language: impl Into<String>, content: impl Into<String>) -> Self {
        Self {
            language: language.into(),
            content: content.into(),
            filename: None,
            info: String::new(),
            start_line: 0,
            terminated: true,
        }
    }

    /// Create a new code block with a filename.
    pub fn with_filename(
        language: impl Into<String>,
        content: impl Into<String>,
        filename: impl Into<String>,
    ) -> Self {
        Self {
            filename: Some(filename.into()),
            ..Self::new(language, content)
        }
    }

    /// Whether this block holds a unified diff rather than full file content.
    ///
    /// True for `diff` / `patch` / `udiff` blocks, or any block whose content starts
    /// with `--- ` / `diff --git` and contains `+++ ` and `@@` lines.
    pub fn is_diff(&self) -> bool {
        if matches!(self.language.as_str(), "diff" | "patch" | "udiff") {
            return true;
        }
        let c = self.content.as_str();
        (c.starts_with("--- ") || c.starts_with("diff --git"))
            && c.contains("\n+++ ")
            && c.contains("\n@@")
    }
}

/// A parsed fence line.
#[derive(Debug, Clone, Copy)]
struct Fence<'a> {
    indent: usize,
    ch: u8,
    len: usize,
    info: &'a str,
}

/// Parse a line as a code fence (three or more backticks or tildes).
///
/// Any amount of space indentation is accepted so fences nested in list items work.
fn parse_fence(line: &str) -> Option<Fence<'_>> {
    let trimmed = line.trim_start_matches(' ');
    let indent = line.len() - trimmed.len();
    let ch = *trimmed.as_bytes().first()?;
    if ch != b'`' && ch != b'~' {
        return None;
    }
    let len = trimmed.bytes().take_while(|&b| b == ch).count();
    if len < 3 {
        return None;
    }
    // Fence chars are ASCII, so `len` is a char boundary.
    let info = trimmed[len..].trim();
    // CommonMark: a backtick fence's info string may not contain backticks
    // (this is what keeps inline ```code``` spans from opening a block).
    if ch == b'`' && info.contains('`') {
        return None;
    }
    Some(Fence {
        indent,
        ch,
        len,
        info,
    })
}

/// Extract all fenced code blocks from `response`.
pub(crate) fn extract(response: &str) -> Vec<CodeBlock> {
    let lines = split_lines(response);
    let mut blocks = Vec::new();
    let mut prose_start = 0;
    let mut i = 0;

    while i < lines.len() {
        let Some(open) = parse_fence(lines[i]) else {
            i += 1;
            continue;
        };
        let (lang, info_path) = parse_info(open.info);
        let (close, terminated) =
            find_close(&lines, i + 1, open, MARKDOWN_LANGS.contains(&lang.as_str()));

        let body: Vec<&str> = lines[i + 1..close]
            .iter()
            .map(|l| strip_indent(l, open.indent))
            .collect();
        let content = trim_blank_lines(&body).join("\n");

        let filename = info_path
            .or_else(|| filename_from_content(&content))
            .or_else(|| filename_from_context(&lines[prose_start..i]));

        let language = if lang.is_empty() {
            filename
                .as_deref()
                .and_then(language_for_path)
                .unwrap_or("text")
                .to_string()
        } else {
            lang
        };

        blocks.push(CodeBlock {
            language,
            content,
            filename,
            info: open.info.to_string(),
            start_line: i + 1,
            terminated,
        });

        i = close + 1;
        prose_start = i.min(lines.len());
    }

    blocks
}

/// Find the closing fence for `open`, starting at line `from`.
///
/// Returns `(close_index, terminated)`; an unterminated block runs to the end of input
/// (`close_index == lines.len()`). For markdown blocks, same-character fences that carry
/// an info string are treated as nested openers, so a ```` ```markdown ```` block
/// that shows a ```` ```python ```` example is not cut short.
fn find_close(lines: &[&str], from: usize, open: Fence<'_>, nested_aware: bool) -> (usize, bool) {
    let mut depth = 0usize;
    for (j, line) in lines.iter().enumerate().skip(from) {
        let Some(f) = parse_fence(line) else {
            continue;
        };
        if f.ch != open.ch || f.len < open.len {
            continue;
        }
        if f.info.is_empty() {
            if depth == 0 {
                return (j, true);
            }
            depth -= 1;
        } else if nested_aware {
            depth += 1;
        }
    }
    (lines.len(), false)
}

/// Drop leading and trailing whitespace-only lines (indentation of other lines is kept).
fn trim_blank_lines<'a, 'b>(lines: &'b [&'a str]) -> &'b [&'a str] {
    let start = lines
        .iter()
        .position(|l| !l.trim().is_empty())
        .unwrap_or(lines.len());
    let end = lines
        .iter()
        .rposition(|l| !l.trim().is_empty())
        .map_or(start, |p| p + 1);
    &lines[start..end]
}

/// Parse a fence info string into `(language, path)`.
///
/// Supported forms: `rust`, `rust src/lib.rs`, `rust:src/lib.rs`, `src/lib.rs`,
/// `rust title="src/lib.rs"` (also `file=`, `filename=`, `path=`, `name=`),
/// `{.rust}`, and `rust,ignore`.
fn parse_info(info: &str) -> (String, Option<String>) {
    let mut tokens = info.split_whitespace();
    let Some(first) = tokens.next() else {
        return (String::new(), None);
    };
    let first = match first.strip_prefix('{') {
        Some(rest) => rest.trim_start_matches('.').trim_end_matches('}'),
        None => first,
    };

    let mut path = None;
    let lang = if let Some((l, p)) = first.split_once(':')
        && looks_like_path(p)
    {
        path = Some(p.to_string());
        l
    } else if looks_like_path(first) && (first.contains('/') || language_for_path(first).is_some())
    {
        path = Some(first.to_string());
        ""
    } else {
        first.split(',').next().unwrap_or("")
    };

    if path.is_none() {
        for tok in tokens {
            let candidate = match tok.split_once('=') {
                Some((key, value)) => {
                    let key = key.to_ascii_lowercase();
                    if !matches!(
                        key.as_str(),
                        "file" | "filename" | "path" | "title" | "name"
                    ) {
                        continue;
                    }
                    value
                },
                None => tok,
            };
            let candidate = candidate.trim_matches(|c| c == '"' || c == '\'' || c == '`');
            if looks_like_path(candidate) {
                path = Some(candidate.to_string());
                break;
            }
        }
    }

    (lang.to_ascii_lowercase(), path)
}

/// `# file: x`, `// path: x`, `<!-- filename: x -->` etc. on the first non-blank line.
static COMMENT_FILE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?i)^\s*(?:#+|//+|--|;+|/\*+|<!--|%)\s*(?:file\s?name|file|path)\s*:\s*(\S+?)\s*(?:\*/|-->)?\s*$",
    )
    .expect("valid regex")
});

/// `File: src/x.rs`, `**Path:** `src/x.rs``, `# filename: x`.
static LABEL_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:file\s?name|file|path)\s*:\s*(?:`([^`]+)`|([^\s`]+))")
        .expect("valid regex")
});

/// `Create file `x``, `update the existing `x``, `write a new file called `x``.
static VERB_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?i)\b(?:create|creating|created|modify|modifying|modified|update|updating|updated|edit|editing|edited|replace|replacing|add|adding|write|writing|save|saving|change|changing|overwrite)\s+(?:the\s+|a\s+)?(?:new\s+|following\s+|updated\s+|existing\s+|whole\s+|entire\s+)?(?:file\s+)?(?:called\s+|named\s+|at\s+)?`([^`]+)`",
    )
    .expect("valid regex")
});

/// `in file `x``, `to the file `x``.
static IN_FILE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:in|to|into|at|of)\s+(?:the\s+)?file\s+`([^`]+)`").expect("valid regex")
});

/// A line ending in a backticked token and a colon: "Here's the updated `config.yaml`:".
static TRAILING_TICK_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"`([^`]+)`\s*:\s*$").expect("valid regex"));

/// A line that is only a path: `### src/main.rs`, `` `src/main.rs`: ``, `1. src/main.rs`.
static BARE_PATH_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^(?:#{1,6}\s+)?(?:[-+]\s+|\d+[.)]\s+)?`?([^\s`]+?)`?\s*:?$").expect("valid regex")
});

fn clean_candidate(raw: &str) -> Option<String> {
    let c = raw
        .trim()
        .trim_matches(|c| c == '\'' || c == '"' || c == '`')
        .trim_end_matches(['.', ',', ':', ';', ')']);
    looks_like_path(c).then(|| c.to_string())
}

fn filename_from_content(content: &str) -> Option<String> {
    let first = content.lines().find(|l| !l.trim().is_empty())?;
    COMMENT_FILE_RE
        .captures(first)
        .and_then(|caps| caps.get(1))
        .and_then(|m| clean_candidate(m.as_str()))
}

fn filename_from_context(prose: &[&str]) -> Option<String> {
    prose
        .iter()
        .rev()
        .filter(|l| !l.trim().is_empty())
        .take(CONTEXT_LINES)
        .find_map(|l| filename_from_line(l))
}

/// Find a filename mentioned on a single line of prose.
pub(crate) fn filename_from_line(line: &str) -> Option<String> {
    // Bold/italic markers only get in the way ("**File:** `x`").
    let cleaned = line.replace('*', "");
    let t = cleaned.trim();
    if t.is_empty() || parse_fence(t).is_some() {
        return None;
    }

    if let Some(caps) = LABEL_RE.captures(t)
        && let Some(m) = caps.get(1).or_else(|| caps.get(2))
        && let Some(f) = clean_candidate(m.as_str())
    {
        return Some(f);
    }
    for re in [&*VERB_RE, &*IN_FILE_RE, &*TRAILING_TICK_RE, &*BARE_PATH_RE] {
        if let Some(f) = re
            .captures_iter(t)
            .filter_map(|caps| caps.get(1))
            .find_map(|m| clean_candidate(m.as_str()))
        {
            return Some(f);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn info_string_forms() {
        assert_eq!(parse_info(""), (String::new(), None));
        assert_eq!(parse_info("Python"), ("python".into(), None));
        assert_eq!(parse_info("rust,ignore"), ("rust".into(), None));
        assert_eq!(parse_info("{.rust}"), ("rust".into(), None));
        assert_eq!(
            parse_info("rust src/lib.rs"),
            ("rust".into(), Some("src/lib.rs".into()))
        );
        assert_eq!(
            parse_info("rust:src/lib.rs"),
            ("rust".into(), Some("src/lib.rs".into()))
        );
        assert_eq!(
            parse_info("src/lib.rs"),
            (String::new(), Some("src/lib.rs".into()))
        );
        assert_eq!(
            parse_info(r#"py title="app/main.py""#),
            ("py".into(), Some("app/main.py".into()))
        );
        assert_eq!(parse_info("c++"), ("c++".into(), None));
        assert_eq!(parse_info("text no path here"), ("text".into(), None));
    }

    #[test]
    fn fence_rules() {
        assert!(parse_fence("```").is_some());
        assert!(parse_fence("   ~~~~ rust").is_some());
        assert!(parse_fence("``").is_none());
        assert!(parse_fence("```inline``` code").is_none());
        assert!(parse_fence("text ```").is_none());
    }

    #[test]
    fn filename_lines() {
        let cases = [
            ("Create file `src/utils.py`:", Some("src/utils.py")),
            ("**File:** `src/a.rs`", Some("src/a.rs")),
            ("### src/main.rs", Some("src/main.rs")),
            ("`Cargo.toml`:", Some("Cargo.toml")),
            ("Here's the updated `config.yaml`:", Some("config.yaml")),
            ("Add this to the file `lib/x.ts`", Some("lib/x.ts")),
            ("# path: tools/run.sh", Some("tools/run.sh")),
            ("Update `serde_json` usage:", None),
            ("Call `foo.bar()` then:", None),
            ("The bug is in `parse.rs`, here is a test", None),
            ("Run the following:", None),
        ];
        for (line, want) in cases {
            assert_eq!(filename_from_line(line).as_deref(), want, "{line}");
        }
    }
}
