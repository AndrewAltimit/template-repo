//! Small text helpers shared by the parsers.

/// Split text into lines, accepting both `\n` and `\r\n` terminators.
///
/// Unlike [`str::lines`], a trailing newline yields a final empty line; callers
/// treat blank lines as insignificant so this does not matter.
pub(crate) fn split_lines(text: &str) -> Vec<&str> {
    text.split('\n')
        .map(|l| l.strip_suffix('\r').unwrap_or(l))
        .collect()
}

/// 0-based line index of a byte offset (which must lie on a char boundary).
pub(crate) fn line_of(text: &str, byte_offset: usize) -> usize {
    text.as_bytes()[..byte_offset.min(text.len())]
        .iter()
        .filter(|&&b| b == b'\n')
        .count()
}

/// Strip up to `n` leading ASCII spaces.
pub(crate) fn strip_indent(line: &str, n: usize) -> &str {
    let spaces = line.bytes().take(n).take_while(|&b| b == b' ').count();
    &line[spaces..]
}

/// Newline sequence used by `text` (`\r\n` if any CRLF is present).
pub(crate) fn newline_of(text: &str) -> &'static str {
    if text.contains("\r\n") { "\r\n" } else { "\n" }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splits_crlf_and_lf() {
        assert_eq!(split_lines("a\r\nb\nc"), vec!["a", "b", "c"]);
    }

    #[test]
    fn line_of_counts_newlines() {
        assert_eq!(line_of("a\nb\nc", 0), 0);
        assert_eq!(line_of("a\nb\nc", 2), 1);
        assert_eq!(line_of("a\nb\nc", 100), 2);
    }

    #[test]
    fn strip_indent_is_bounded() {
        assert_eq!(strip_indent("    x", 2), "  x");
        assert_eq!(strip_indent(" x", 4), "x");
        assert_eq!(strip_indent("\tx", 4), "\tx");
    }
}
