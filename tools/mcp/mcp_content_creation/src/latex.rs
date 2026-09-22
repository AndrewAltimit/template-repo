//! Pure LaTeX helpers: template wrapping, TikZ document assembly, log
//! parsing, and page-range parsing. Nothing in here spawns processes.

use std::collections::BTreeSet;

use crate::types::LatexTemplate;

/// Packages loaded by the non-custom templates.
const TEMPLATE_PACKAGES: &str =
    "\\usepackage{amsmath}\n\\usepackage{amssymb}\n\\usepackage{graphicx}\n";

/// TikZ libraries always loaded by `render_tikz`.
pub const DEFAULT_TIKZ_LIBRARIES: &[&str] = &["arrows.meta", "positioning", "shapes", "calc"];

/// Maximum number of LaTeX errors/warnings reported back to the caller.
const MAX_REPORTED: usize = 10;

/// Does the source already declare its document class?
pub fn has_documentclass(content: &str) -> bool {
    content.contains("\\documentclass") || content.contains("\\documentstyle")
}

/// Wrap a LaTeX fragment in the given template.
///
/// Content that already has a `\documentclass`, and any content with the
/// `custom` template, is returned unchanged.
pub fn wrap_with_template(content: &str, template: LatexTemplate) -> String {
    let class = match template {
        LatexTemplate::Custom => return content.to_string(),
        _ if has_documentclass(content) => return content.to_string(),
        LatexTemplate::Article => "article",
        LatexTemplate::Report => "report",
        LatexTemplate::Book => "book",
        LatexTemplate::Beamer => "beamer",
    };
    format!(
        "\\documentclass{{{}}}\n{}\\begin{{document}}\n{}\n\\end{{document}}\n",
        class, TEMPLATE_PACKAGES, content
    )
}

/// Is `name` a plausible LaTeX package / TikZ library name?
///
/// Restricting names to `[A-Za-z0-9._-]` keeps caller-supplied names from
/// smuggling extra preamble code into the generated document.
pub fn is_valid_tex_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 64
        && name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_'))
        && name
            .chars()
            .next()
            .is_some_and(|c| c.is_ascii_alphanumeric())
}

/// Build a standalone document for a TikZ snippet.
///
/// - Full documents (containing `\documentclass`) are passed through.
/// - Snippets without a `tikzpicture` environment or `\tikz` command are
///   wrapped in `\begin{tikzpicture} ... \end{tikzpicture}`.
/// - Extra `libraries` and `packages` are validated with
///   [`is_valid_tex_name`] and de-duplicated.
pub fn build_tikz_document(
    code: &str,
    libraries: &[String],
    packages: &[String],
) -> Result<String, String> {
    if code.trim().is_empty() {
        return Err("tikz_code must not be empty".to_string());
    }
    if has_documentclass(code) {
        return Ok(code.to_string());
    }

    for name in libraries.iter().chain(packages) {
        if !is_valid_tex_name(name) {
            return Err(format!(
                "invalid package/library name '{}': only letters, digits, '.', '-', '_' are allowed",
                name
            ));
        }
    }

    let mut libs: Vec<&str> = DEFAULT_TIKZ_LIBRARIES.to_vec();
    for lib in libraries {
        if !libs.contains(&lib.as_str()) {
            libs.push(lib);
        }
    }

    let mut preamble = String::from("\\usepackage{tikz}\n");
    let mut seen = BTreeSet::new();
    for pkg in packages {
        if pkg != "tikz" && seen.insert(pkg.as_str()) {
            preamble.push_str(&format!("\\usepackage{{{}}}\n", pkg));
        }
    }
    preamble.push_str(&format!("\\usetikzlibrary{{{}}}\n", libs.join(",")));

    let body = if code.contains("\\begin{tikzpicture}") || code.contains("\\tikz") {
        code.to_string()
    } else {
        format!("\\begin{{tikzpicture}}\n{}\n\\end{{tikzpicture}}", code)
    };

    Ok(format!(
        "\\documentclass[tikz,border=10pt]{{standalone}}\n{}\\begin{{document}}\n{}\n\\end{{document}}\n",
        preamble, body
    ))
}

/// Does the document need an extra pass for a table of contents / lists?
/// (LaTeX does not emit a "Rerun" warning for these.)
pub fn needs_toc_pass(document: &str) -> bool {
    ["\\tableofcontents", "\\listoffigures", "\\listoftables"]
        .iter()
        .any(|cmd| document.contains(cmd))
}

/// Does the `.aux` file request a BibTeX run?
pub fn aux_needs_bibtex(aux: &str) -> bool {
    aux.contains("\\bibdata{")
}

/// Key facts extracted from a LaTeX `.log` file.
#[derive(Debug, Default, Clone, PartialEq)]
pub struct LogSummary {
    /// Error messages (`! ...` lines plus their `l.N` context), capped.
    pub errors: Vec<String>,
    /// Distinct LaTeX/package/class warnings, capped.
    pub warnings: Vec<String>,
    /// The log asks for another LaTeX run.
    pub needs_rerun: bool,
    /// The document uses biblatex with the biber backend (not supported).
    pub wants_biber: bool,
}

/// Parse a LaTeX log. Assumes `max_print_line` is large enough that messages
/// are not hard-wrapped (the engine sets it), but copes with wrapping.
pub fn parse_log(log: &str) -> LogSummary {
    let lines: Vec<&str> = log.lines().collect();
    let mut summary = LogSummary::default();

    let mut i = 0;
    while i < lines.len() {
        let line = lines[i];
        if let Some(msg) = line.strip_prefix('!') {
            let msg = msg.trim();
            let is_noise = msg.starts_with("==> Fatal error occurred")
                || msg == "Emergency stop."
                || msg.is_empty();
            if !is_noise {
                let mut entry = msg.to_string();
                // Attach the "l.<n> <source>" context line, if close by.
                for next in lines.iter().skip(i + 1).take(8) {
                    if is_line_ref(next) {
                        entry.push_str(&format!(" [{}]", next.trim()));
                        break;
                    }
                }
                if summary.errors.len() < MAX_REPORTED && !summary.errors.contains(&entry) {
                    summary.errors.push(entry);
                }
            }
        } else if is_warning_line(line) {
            let w = line.trim().to_string();
            if summary.warnings.len() < MAX_REPORTED && !summary.warnings.contains(&w) {
                summary.warnings.push(w);
            }
        }
        let lower = line.to_ascii_lowercase();
        if lower.contains("rerun to get")
            || lower.contains("label(s) may have changed")
            || lower.contains("rerun latex")
        {
            summary.needs_rerun = true;
        }
        if lower.contains("please (re)run biber") || lower.contains("run biber") {
            summary.wants_biber = true;
        }
        i += 1;
    }

    // Only report "Emergency stop" style noise when nothing better exists.
    if summary.errors.is_empty() && lines.iter().any(|l| l.starts_with("! ")) {
        summary
            .errors
            .push("LaTeX stopped with a fatal error".to_string());
    }
    summary
}

fn is_line_ref(line: &str) -> bool {
    line.strip_prefix("l.")
        .and_then(|rest| rest.chars().next())
        .is_some_and(|c| c.is_ascii_digit())
}

fn is_warning_line(line: &str) -> bool {
    let t = line.trim_start();
    // Font substitutions are noise, and "Shell escape disabled" is the
    // sandbox working as intended (emitted by standalone/shellesc).
    if t.starts_with("LaTeX Font Warning") || t.contains("Shell escape disabled") {
        return false;
    }
    t.starts_with("LaTeX Warning:")
        || ((t.starts_with("Package ") || t.starts_with("Class ")) && t.contains(" Warning:"))
}

/// Parse a page specification against a document with `total_pages` pages.
///
/// Accepts `none`/empty (no pages), `all`, single pages (`3`), comma lists
/// (`1,3,5`), and ranges (`2-4`, open-ended `5-`). Pages outside
/// `1..=total_pages` are dropped. Malformed parts are an error rather than
/// being silently ignored.
pub fn parse_page_spec(spec: &str, total_pages: u32) -> Result<Vec<u32>, String> {
    let spec = spec.trim();
    if spec.is_empty() || spec.eq_ignore_ascii_case("none") {
        return Ok(Vec::new());
    }
    if spec.eq_ignore_ascii_case("all") {
        return Ok((1..=total_pages).collect());
    }

    let bad = |part: &str| {
        format!(
            "invalid page specification '{}' (use e.g. '1', '1,3,5', '2-4', 'all', 'none')",
            part
        )
    };

    let mut pages = BTreeSet::new();
    for part in spec.split(',') {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }
        if let Some((start, end)) = part.split_once('-') {
            let start: u32 = start.trim().parse().map_err(|_| bad(part))?;
            let end: u32 = if end.trim().is_empty() {
                total_pages
            } else {
                end.trim().parse().map_err(|_| bad(part))?
            };
            if start > end {
                return Err(bad(part));
            }
            let lo = start.max(1);
            let hi = end.min(total_pages);
            pages.extend(lo..=hi);
        } else {
            let page: u32 = part.parse().map_err(|_| bad(part))?;
            if (1..=total_pages).contains(&page) {
                pages.insert(page);
            }
        }
    }
    Ok(pages.into_iter().collect())
}

/// Extract the page count from `pdfinfo` output.
pub fn parse_pdfinfo_pages(output: &str) -> Option<u32> {
    output.lines().find_map(|line| {
        line.strip_prefix("Pages:")
            .and_then(|rest| rest.trim().parse().ok())
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn template_wraps_fragments_only() {
        let wrapped = wrap_with_template("Hello", LatexTemplate::Article);
        assert!(wrapped.starts_with("\\documentclass{article}"));
        assert!(wrapped.contains("\\usepackage{amsmath}"));
        assert!(wrapped.contains("\\begin{document}\nHello\n\\end{document}"));

        let full = "\\documentclass{report}\\begin{document}x\\end{document}";
        assert_eq!(wrap_with_template(full, LatexTemplate::Article), full);
        assert_eq!(wrap_with_template("raw", LatexTemplate::Custom), "raw");
        assert!(wrap_with_template("f", LatexTemplate::Beamer).contains("{beamer}"));
    }

    #[test]
    fn tex_name_validation() {
        assert!(is_valid_tex_name("arrows.meta"));
        assert!(is_valid_tex_name("pgfplots"));
        assert!(is_valid_tex_name("decorations.pathmorphing"));
        assert!(!is_valid_tex_name(""));
        assert!(!is_valid_tex_name("x}\\input{/etc/passwd"));
        assert!(!is_valid_tex_name(".hidden"));
        assert!(!is_valid_tex_name("a b"));
    }

    #[test]
    fn tikz_document_wraps_bare_commands() {
        let doc = build_tikz_document("\\draw (0,0) -- (1,1);", &[], &[]).unwrap();
        assert!(doc.contains("\\begin{tikzpicture}\n\\draw"));
        assert!(doc.contains("\\usetikzlibrary{arrows.meta,positioning,shapes,calc}"));
        assert!(doc.starts_with("\\documentclass[tikz,border=10pt]{standalone}"));
    }

    #[test]
    fn tikz_document_keeps_existing_environment_and_adds_extras() {
        let code = "\\begin{tikzpicture}\\draw (0,0) circle (1);\\end{tikzpicture}";
        let doc = build_tikz_document(
            code,
            &["calc".into(), "decorations.pathmorphing".into()],
            &["pgfplots".into(), "pgfplots".into(), "tikz".into()],
        )
        .unwrap();
        assert_eq!(doc.matches("\\begin{tikzpicture}").count(), 1);
        assert_eq!(doc.matches("\\usepackage{pgfplots}").count(), 1);
        assert_eq!(doc.matches("\\usepackage{tikz}").count(), 1);
        assert!(doc.contains("calc,decorations.pathmorphing}"));
    }

    #[test]
    fn tikz_document_rejects_injection_and_empty_code() {
        assert!(build_tikz_document("x", &[], &["a}\\input{x".into()]).is_err());
        assert!(build_tikz_document("   ", &[], &[]).is_err());
        let full = "\\documentclass{standalone}\\begin{document}x\\end{document}";
        assert_eq!(build_tikz_document(full, &[], &[]).unwrap(), full);
    }

    #[test]
    fn parse_log_extracts_errors_with_context() {
        let log = "\
This is pdfTeX
! Undefined control sequence.
l.5 \\foo
         bar
! Emergency stop.
!  ==> Fatal error occurred, no output PDF file produced!
";
        let s = parse_log(log);
        assert_eq!(s.errors, vec!["Undefined control sequence. [l.5 \\foo]"]);
        assert!(!s.needs_rerun);
    }

    #[test]
    fn parse_log_only_noise_still_reports_failure() {
        let s = parse_log("! Emergency stop.\n");
        assert_eq!(s.errors.len(), 1);
    }

    #[test]
    fn parse_log_detects_warnings_and_rerun() {
        let log = "\
LaTeX Warning: Reference `s1' on page 1 undefined on input line 6.
LaTeX Font Warning: Font shape `OT1/cmr/bx/sc' undefined
Package shellesc Warning: Shell escape disabled on input line 73.
Package hyperref Warning: Token not allowed in a PDF string
LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.
LaTeX Warning: Reference `s1' on page 1 undefined on input line 6.
";
        let s = parse_log(log);
        assert!(s.needs_rerun);
        assert_eq!(s.warnings.len(), 3);
        assert!(s.errors.is_empty());
        assert!(!s.warnings.iter().any(|w| w.contains("Font Warning")));
    }

    #[test]
    fn parse_log_detects_biber() {
        let s = parse_log("Package biblatex Warning: Please (re)run Biber on the file:\n");
        assert!(s.wants_biber);
    }

    #[test]
    fn bibtex_and_toc_detection() {
        assert!(aux_needs_bibtex("\\relax\n\\bibdata{refs}\n"));
        assert!(!aux_needs_bibtex("\\relax\n"));
        assert!(needs_toc_pass("\\tableofcontents"));
        assert!(!needs_toc_pass("plain"));
    }

    #[test]
    fn page_spec_parsing() {
        assert_eq!(parse_page_spec("1", 10).unwrap(), vec![1]);
        assert_eq!(parse_page_spec("1,3,5", 10).unwrap(), vec![1, 3, 5]);
        assert_eq!(parse_page_spec("1-5", 10).unwrap(), vec![1, 2, 3, 4, 5]);
        assert_eq!(parse_page_spec("all", 3).unwrap(), vec![1, 2, 3]);
        assert_eq!(parse_page_spec("ALL", 2).unwrap(), vec![1, 2]);
        assert!(parse_page_spec("none", 10).unwrap().is_empty());
        assert!(parse_page_spec("", 10).unwrap().is_empty());
        assert_eq!(parse_page_spec("8-", 10).unwrap(), vec![8, 9, 10]);
        assert_eq!(parse_page_spec("3,1-2,3", 10).unwrap(), vec![1, 2, 3]);
        assert_eq!(parse_page_spec("0,11,2", 10).unwrap(), vec![2]);
        assert_eq!(parse_page_spec("9-100", 10).unwrap(), vec![9, 10]);
    }

    #[test]
    fn page_spec_rejects_garbage() {
        assert!(parse_page_spec("abc", 10).is_err());
        assert!(parse_page_spec("5-1", 10).is_err());
        assert!(parse_page_spec("-3", 10).is_err());
        assert!(parse_page_spec("1-x", 10).is_err());
    }

    #[test]
    fn pdfinfo_parsing() {
        let out = "Title: x\nPages:          12\nEncrypted: no\n";
        assert_eq!(parse_pdfinfo_pages(out), Some(12));
        assert_eq!(parse_pdfinfo_pages("Title: x\n"), None);
    }
}
