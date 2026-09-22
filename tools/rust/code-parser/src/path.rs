//! Path validation: sanitizing AI-supplied paths and recognizing path-like tokens.

use crate::error::{CodeParserError, Result};
use tracing::warn;

/// Upper bound on accepted path length (bytes).
const MAX_PATH_LEN: usize = 4096;

/// Extensionless file names that are still clearly files.
const BARE_FILE_NAMES: &[&str] = &[
    "Dockerfile",
    "Containerfile",
    "Makefile",
    "GNUmakefile",
    "Justfile",
    "justfile",
    "Gemfile",
    "Rakefile",
    "Procfile",
    "Jenkinsfile",
    "Vagrantfile",
    "LICENSE",
    "README",
    "CODEOWNERS",
];

/// Validate and normalize a relative path taken from an AI response.
///
/// Rejects absolute paths (`/x`, `C:\x`, `\\server\x`, `~/x`), any `..` component,
/// control characters, `:` (drive letters / NTFS alternate data streams), paths
/// that end in a separator, and anything inside a `.git` directory. Backslashes
/// are treated as separators. Redundant `./` and `//` segments are removed and
/// the result uses `/` separators.
pub(crate) fn sanitize(filename: &str) -> Result<String> {
    let raw = filename.trim();

    if raw.is_empty() {
        return Err(CodeParserError::InvalidFilename(
            "empty filename".to_string(),
        ));
    }
    if raw.len() > MAX_PATH_LEN {
        return Err(CodeParserError::InvalidFilename(
            "path too long".to_string(),
        ));
    }
    if raw.chars().any(char::is_control) {
        warn!("Rejecting filename with control characters: {:?}", raw);
        return Err(CodeParserError::InvalidFilename(
            "contains control characters".to_string(),
        ));
    }

    let normalized = raw.replace('\\', "/");
    let bytes = normalized.as_bytes();
    let has_drive = bytes.len() >= 2 && bytes[0].is_ascii_alphabetic() && bytes[1] == b':';
    if normalized.starts_with('/') || normalized.starts_with('~') || has_drive {
        warn!("Rejecting absolute path: {}", raw);
        return Err(CodeParserError::PathTraversal(raw.to_string()));
    }
    if normalized.contains(':') {
        return Err(CodeParserError::InvalidFilename(format!(
            "contains ':': {raw}"
        )));
    }
    if normalized.ends_with('/') {
        return Err(CodeParserError::InvalidFilename(format!(
            "refers to a directory: {raw}"
        )));
    }

    let mut parts: Vec<&str> = Vec::new();
    for component in normalized.split('/') {
        match component {
            "" | "." => {},
            ".." => {
                warn!("Rejecting path with parent directory reference: {}", raw);
                return Err(CodeParserError::PathTraversal(raw.to_string()));
            },
            c if c.eq_ignore_ascii_case(".git") => {
                warn!("Rejecting path inside .git: {}", raw);
                return Err(CodeParserError::PathTraversal(raw.to_string()));
            },
            c => parts.push(c),
        }
    }

    if parts.is_empty() {
        return Err(CodeParserError::InvalidFilename(format!(
            "no path components: {raw}"
        )));
    }
    Ok(parts.join("/"))
}

/// Heuristic: does `s` look like a file path (as opposed to prose or an identifier)?
///
/// Accepts tokens with a file extension (`src/main.rs`, `.env`), well-known
/// extensionless names (`Dockerfile`), or multi-segment paths (`bin/tool`).
/// This does not check safety; use [`sanitize`] for that.
pub(crate) fn looks_like_path(s: &str) -> bool {
    if s.is_empty() || s.len() > MAX_PATH_LEN || s.contains("://") {
        return false;
    }
    if s.starts_with('-') || s.starts_with('$') {
        return false;
    }
    let bad_char = |c: char| {
        c.is_whitespace()
            || c.is_control()
            || matches!(
                c,
                '`' | '"'
                    | '\''
                    | '*'
                    | '?'
                    | '<'
                    | '>'
                    | '|'
                    | '('
                    | ')'
                    | '{'
                    | '}'
                    | '='
                    | ','
                    | ';'
                    | '!'
                    | '#'
                    | '%'
                    | '&'
                    | '^'
                    | '$'
                    | ':'
            )
    };
    if s.chars().any(bad_char) {
        return false;
    }

    let last = s.rsplit(['/', '\\']).next().unwrap_or(s);
    if last.is_empty() {
        return false;
    }
    if BARE_FILE_NAMES.contains(&last) || has_extension(last) {
        return true;
    }
    s.contains('/') && !s.starts_with("//") && s.split('/').all(|seg| !seg.is_empty())
}

/// `name.ext` or `.dotfile`, where the extension is short, alphanumeric, and has a letter.
fn has_extension(name: &str) -> bool {
    let Some((stem, ext)) = name.rsplit_once('.') else {
        return false;
    };
    if stem.ends_with('.') {
        return false;
    }
    !ext.is_empty()
        && ext.len() <= 16
        && ext
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
        && ext.chars().any(|c| c.is_ascii_alphabetic())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitize_normalizes() {
        assert_eq!(sanitize("./test.py").unwrap(), "test.py");
        assert_eq!(sanitize(" src//a/./b.rs ").unwrap(), "src/a/b.rs");
        assert_eq!(sanitize("src\\win\\x.rs").unwrap(), "src/win/x.rs");
    }

    #[test]
    fn sanitize_rejects_escapes() {
        for bad in [
            "/etc/passwd",
            "C:\\Windows\\system32",
            "c:foo",
            "\\\\server\\share\\x",
            "\\root.txt",
            "~/.ssh/authorized_keys",
            "../x",
            "a/../../x",
            "..\\..\\x",
            ".git/hooks/pre-commit",
            "sub/.GIT/config",
        ] {
            assert!(
                matches!(sanitize(bad), Err(CodeParserError::PathTraversal(_))),
                "{bad} should be blocked"
            );
        }
    }

    #[test]
    fn sanitize_rejects_malformed() {
        for bad in [
            "",
            "   ",
            ".",
            "./",
            "dir/",
            "a\0b",
            "a\nb",
            "a\tb",
            "file.txt:stream",
        ] {
            assert!(
                matches!(sanitize(bad), Err(CodeParserError::InvalidFilename(_))),
                "{bad:?} should be invalid"
            );
        }
        assert!(sanitize(&"a".repeat(MAX_PATH_LEN + 1)).is_err());
    }

    #[test]
    fn path_heuristic() {
        for ok in [
            "src/main.rs",
            "main.py",
            ".env",
            "Dockerfile",
            "bin/tool",
            "@scope/pkg/x.ts",
        ] {
            assert!(looks_like_path(ok), "{ok}");
        }
        for no in [
            "",
            "hello world",
            "foo()",
            "std::fs",
            "serde_json",
            "v1.2",
            "https://x.io/a.js",
            "--flag",
            "a/",
            "x=1.py",
        ] {
            assert!(!looks_like_path(no), "{no}");
        }
    }
}
