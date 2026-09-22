//! Pure parsers for external tool output.
//!
//! Kept free of I/O so each format can be unit tested against captured
//! samples. Every parser is best effort: unrecognized input yields `None` or
//! an empty list rather than an error, and callers fall back to raw output.

use serde_json::{Value, json};

/// Does `line` look like a `file:line:col: message` diagnostic?
///
/// Matches the concise formats of ruff, flake8, ty, golint, and
/// `cargo clippy --message-format=short`. Windows drive letters (`C:\x.py:1:2:`)
/// are handled because we search for the `:<digits>:<digits>:` pattern rather
/// than splitting on the first colon.
pub fn is_diagnostic_line(line: &str) -> bool {
    let bytes = line.as_bytes();
    let mut i = 1; // need at least one char of file name before the colon
    while i < bytes.len() {
        if bytes[i] == b':' {
            let (ok, next) = digits_then_colon(bytes, i + 1);
            if ok {
                let (ok2, _) = digits_then_colon(bytes, next);
                if ok2 {
                    return true;
                }
            }
        }
        i += 1;
    }
    false
}

/// Returns (matched, index after the colon) for `\d+:` starting at `start`.
fn digits_then_colon(bytes: &[u8], start: usize) -> (bool, usize) {
    let mut j = start;
    while j < bytes.len() && bytes[j].is_ascii_digit() {
        j += 1;
    }
    if j > start && j < bytes.len() && bytes[j] == b':' {
        (true, j + 1)
    } else {
        (false, start)
    }
}

/// All diagnostic lines in `text`, trimmed.
pub fn diagnostic_lines(text: &str) -> Vec<String> {
    text.lines()
        .map(str::trim_end)
        .filter(|l| is_diagnostic_line(l))
        .map(str::to_string)
        .collect()
}

/// Convert `eslint --format json` output into `file:line:col: severity message [rule]`
/// lines. Returns `None` if the output is not eslint JSON.
pub fn eslint_issues(stdout: &str) -> Option<Vec<String>> {
    let files: Vec<Value> = serde_json::from_str(stdout.trim()).ok()?;
    let mut out = Vec::new();
    for file in &files {
        let path = file.get("filePath").and_then(Value::as_str).unwrap_or("?");
        for m in file
            .get("messages")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            let line = m.get("line").and_then(Value::as_u64).unwrap_or(0);
            let col = m.get("column").and_then(Value::as_u64).unwrap_or(0);
            let sev = match m.get("severity").and_then(Value::as_u64) {
                Some(2) => "error",
                _ => "warning",
            };
            let msg = m.get("message").and_then(Value::as_str).unwrap_or("");
            let rule = m
                .get("ruleId")
                .and_then(Value::as_str)
                .map(|r| format!(" [{r}]"))
                .unwrap_or_default();
            out.push(format!("{path}:{line}:{col}: {sev} {msg}{rule}"));
        }
    }
    Some(out)
}

/// Formatter families whose "needs formatting" output we know how to read.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FormatterKind {
    Ruff,
    Black,
    Prettier,
    Gofmt,
    Rustfmt,
}

/// Files a formatter reported as not formatted (deduplicated, in order).
pub fn unformatted_files(kind: FormatterKind, stdout: &str, stderr: &str) -> Vec<String> {
    let mut files: Vec<String> = Vec::new();
    let mut push = |f: &str| {
        let f = f.trim();
        if !f.is_empty() && !files.iter().any(|x| x == f) {
            files.push(f.to_string());
        }
    };
    let text = format!("{stdout}\n{stderr}");
    match kind {
        FormatterKind::Ruff => {
            let mut prev_unformatted = false;
            for line in text.lines() {
                if let Some(f) = line.strip_prefix("Would reformat: ") {
                    push(f);
                } else if prev_unformatted && let Some(rest) = line.trim().strip_prefix("--> ") {
                    push(strip_location(rest));
                }
                prev_unformatted = line.starts_with("unformatted:");
            }
        },
        FormatterKind::Black => {
            for line in text.lines() {
                if let Some(f) = line.strip_prefix("would reformat ") {
                    push(f);
                }
            }
        },
        FormatterKind::Prettier => {
            for line in text.lines() {
                if let Some(f) = line.strip_prefix("[warn] ")
                    && !f.starts_with("Code style issues")
                {
                    push(f);
                }
            }
        },
        FormatterKind::Gofmt => {
            // `gofmt -l` prints one path per line; `gofmt -d` prints diffs
            // whose headers look like `diff -u a.go.orig a.go`.
            for line in stdout.lines() {
                if let Some(rest) = line.strip_prefix("diff ") {
                    if let Some(last) = rest.split_whitespace().last() {
                        push(last);
                    }
                } else if !line.starts_with(['+', '-', '@', ' ']) && !line.trim().is_empty() {
                    push(line);
                }
            }
        },
        FormatterKind::Rustfmt => {
            for line in text.lines() {
                if let Some(rest) = line.strip_prefix("Diff in ") {
                    let rest = rest.trim_end_matches(':');
                    let file = match rest.rfind(" at line ") {
                        Some(i) => &rest[..i],
                        None => strip_location(rest),
                    };
                    push(file);
                }
            }
        },
    }
    files
}

/// `path:12:3` / `path:12` -> `path` (keeps Windows drive letters intact).
fn strip_location(s: &str) -> &str {
    let mut end = s.len();
    for _ in 0..2 {
        if let Some(i) = s[..end].rfind(':')
            && !s[i + 1..end].is_empty()
            && s[i + 1..end].bytes().all(|b| b.is_ascii_digit())
        {
            end = i;
        }
    }
    &s[..end]
}

/// Parsed bandit report.
#[derive(Debug, Clone)]
pub struct BanditReport {
    pub findings: Vec<Value>,
    /// Counts by severity plus the number of files bandit failed to parse.
    pub summary: Value,
    pub errors: Vec<Value>,
}

/// Parse `bandit -f json` output.
pub fn bandit(stdout: &str) -> Option<BanditReport> {
    let data: Value = serde_json::from_str(extract_json_object(stdout)?).ok()?;
    let findings = data.get("results")?.as_array()?.clone();
    let errors = data
        .get("errors")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let count = |sev: &str| {
        findings
            .iter()
            .filter(|f| f.get("issue_severity").and_then(Value::as_str) == Some(sev))
            .count()
    };
    let summary = json!({
        "high": count("HIGH"),
        "medium": count("MEDIUM"),
        "low": count("LOW"),
        "errors": errors.len(),
    });
    Some(BanditReport {
        findings,
        summary,
        errors,
    })
}

/// Bandit (and some pip plugins) may print banner text before the JSON body;
/// return the slice from the first `{` to the last `}`.
fn extract_json_object(s: &str) -> Option<&str> {
    let start = s.find('{')?;
    let end = s.rfind('}')?;
    (end >= start).then(|| &s[start..=end])
}

/// Flatten `pip-audit --format json` output into one entry per vulnerability:
/// `{package, version, id, fix_versions, aliases, description}`.
///
/// Handles both the current shape (`{"dependencies": [...], "fixes": [...]}`)
/// and the legacy top-level array. Returns `None` if the output is not
/// pip-audit JSON.
pub fn pip_audit(stdout: &str) -> Option<Vec<Value>> {
    let data: Value = serde_json::from_str(stdout.trim()).ok()?;
    let deps = match &data {
        Value::Object(o) => o.get("dependencies")?.as_array()?.clone(),
        Value::Array(a) => a.clone(),
        _ => return None,
    };
    let mut out = Vec::new();
    for dep in &deps {
        let name = dep.get("name").cloned().unwrap_or(Value::Null);
        let version = dep.get("version").cloned().unwrap_or(Value::Null);
        for v in dep
            .get("vulns")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            out.push(json!({
                "package": name,
                "version": version,
                "id": v.get("id").cloned().unwrap_or(Value::Null),
                "fix_versions": v.get("fix_versions").cloned().unwrap_or_else(|| json!([])),
                "aliases": v.get("aliases").cloned().unwrap_or_else(|| json!([])),
                "description": v.get("description").cloned().unwrap_or(Value::Null),
            }));
        }
    }
    Some(out)
}

/// Parsed `md-link-checker --json` report.
#[derive(Debug, Clone, PartialEq)]
pub struct LinkReport {
    pub files_checked: usize,
    pub total_links: usize,
    pub broken_links: usize,
    pub all_valid: bool,
    /// `{file, url, lines, error}` per broken link, plus `{file, error}` per
    /// unreadable file.
    pub broken: Vec<Value>,
}

/// Parse `md-link-checker --json` output.
pub fn md_links(stdout: &str) -> Option<LinkReport> {
    let data: Value = serde_json::from_str(stdout.trim()).ok()?;
    let as_usize = |k: &str| data.get(k).and_then(Value::as_u64).map(|v| v as usize);
    let files_checked = as_usize("files_checked")?;
    let total_links = as_usize("total_links").unwrap_or(0);
    let broken_links = as_usize("broken_links").unwrap_or(0);
    let all_valid = data
        .get("all_valid")
        .and_then(Value::as_bool)
        .unwrap_or(broken_links == 0);

    let mut broken = Vec::new();
    for file in data
        .get("results")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let fname = file.get("file").cloned().unwrap_or(Value::Null);
        if let Some(err) = file.get("error") {
            broken.push(json!({"file": fname, "error": err}));
        }
        for link in file
            .get("links")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            if link.get("valid").and_then(Value::as_bool) == Some(false) {
                broken.push(json!({
                    "file": fname,
                    "url": link.get("url").cloned().unwrap_or(Value::Null),
                    "lines": link.get("lines").cloned().unwrap_or_else(|| json!([])),
                    "error": link.get("error").cloned().unwrap_or(Value::Null),
                }));
            }
        }
    }
    Some(LinkReport {
        files_checked,
        total_links,
        broken_links,
        all_valid,
        broken,
    })
}

/// Parse pytest's final summary line (e.g.
/// `==== 3 passed, 1 failed, 2 skipped in 0.52s ====` or, with `-q`,
/// `3 passed in 0.01s`) into `{"passed": 3, "failed": 1, ...}`.
pub fn pytest_summary(output: &str) -> Option<Value> {
    for line in output.lines().rev() {
        let line = line.trim().trim_matches('=').trim();
        let Some(idx) = line.rfind(" in ") else {
            continue;
        };
        let (counts, _) = line.split_at(idx);
        let mut map = serde_json::Map::new();
        for part in counts.split(", ") {
            let mut it = part.split_whitespace();
            let (Some(n), Some(word), None) = (it.next(), it.next(), it.next()) else {
                map.clear();
                break;
            };
            let Ok(n) = n.parse::<u64>() else {
                map.clear();
                break;
            };
            // Normalize singular/plural ("1 error" / "2 errors").
            let key = match word {
                "error" | "errors" => "errors",
                "warning" | "warnings" => "warnings",
                "rerun" | "reruns" => "rerun",
                other => other,
            };
            map.insert(key.to_string(), json!(n));
        }
        if !map.is_empty() {
            return Some(Value::Object(map));
        }
        if counts.trim() == "no tests ran" {
            return Some(json!({"no_tests_ran": true}));
        }
    }
    None
}

/// Extract `edition = "20xx"` from a Cargo.toml's `[package]` table.
pub fn cargo_edition(cargo_toml: &str) -> Option<String> {
    let mut in_package = false;
    for line in cargo_toml.lines() {
        let t = line.trim();
        if t.starts_with('[') {
            in_package = t == "[package]";
            continue;
        }
        if in_package
            && let Some(rest) = t.strip_prefix("edition")
            && let Some(val) = rest.trim_start().strip_prefix('=')
        {
            let v = val.trim().trim_matches('"').trim_matches('\'');
            if v.len() == 4 && v.bytes().all(|b| b.is_ascii_digit()) {
                return Some(v.to_string());
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn diagnostic_detection() {
        assert!(is_diagnostic_line(
            "a.py:1:8: F401 [*] `os` imported but unused"
        ));
        assert!(is_diagnostic_line(r"C:\x\a.py:10:2: E302 expected"));
        assert!(is_diagnostic_line(
            "src/main.rs:3:9: warning: unused variable: `x`"
        ));
        assert!(!is_diagnostic_line("Found 1 error."));
        assert!(!is_diagnostic_line(
            "[*] 1 fixable with the `--fix` option."
        ));
        assert!(!is_diagnostic_line(
            "warning: `x` (bin \"y\") generated 1 warning"
        ));
        assert!(!is_diagnostic_line("time 12:30:"));
        assert!(!is_diagnostic_line(""));
    }

    #[test]
    fn ruff_check_output() {
        let out = "a.py:1:8: F401 [*] `os` imported but unused\nb.py:2:1: E999 x\nFound 2 errors.\n[*] 1 fixable with the `--fix` option.\n";
        let d = diagnostic_lines(out);
        assert_eq!(d.len(), 2);
        assert!(d[0].starts_with("a.py:1:8"));
    }

    #[test]
    fn eslint_json() {
        let out = r#"[{"filePath":"/w/a.js","messages":[{"ruleId":"no-unused-vars","severity":2,"message":"'x' is unused","line":1,"column":5},{"ruleId":null,"severity":1,"message":"parse","line":3,"column":1}],"errorCount":1}, {"filePath":"/w/b.js","messages":[]}]"#;
        let issues = eslint_issues(out).unwrap();
        assert_eq!(
            issues,
            vec![
                "/w/a.js:1:5: error 'x' is unused [no-unused-vars]",
                "/w/a.js:3:1: warning parse"
            ]
        );
        assert!(eslint_issues("Oops! Something went wrong").is_none());
    }

    #[test]
    fn ruff_format_new_and_old_styles() {
        let new = "unformatted: File would be reformatted\n --> b.py:1:2\n  |\n  - x=1\n1 + x = 1\n\n1 file would be reformatted, 1 file already formatted\n";
        assert_eq!(
            unformatted_files(FormatterKind::Ruff, new, ""),
            vec!["b.py"]
        );
        let old =
            "Would reformat: src/a.py\nWould reformat: src/b.py\n2 files would be reformatted\n";
        assert_eq!(
            unformatted_files(FormatterKind::Ruff, old, ""),
            vec!["src/a.py", "src/b.py"]
        );
    }

    #[test]
    fn black_prettier_gofmt_rustfmt() {
        assert_eq!(
            unformatted_files(
                FormatterKind::Black,
                "",
                "would reformat /w/b.py\n\nOh no!\n1 file would be reformatted."
            ),
            vec!["/w/b.py"]
        );
        assert_eq!(
            unformatted_files(
                FormatterKind::Prettier,
                "Checking formatting...\n[warn] src/a.ts\n[warn] Code style issues found in the above file. Run Prettier with --write to fix.\n",
                ""
            ),
            vec!["src/a.ts"]
        );
        assert_eq!(
            unformatted_files(FormatterKind::Gofmt, "a.go\nsub/b.go\n", ""),
            vec!["a.go", "sub/b.go"]
        );
        assert_eq!(
            unformatted_files(
                FormatterKind::Gofmt,
                "diff -u a.go.orig a.go\n--- a.go.orig\n+++ a.go\n@@ -1 +1 @@\n-x\n+y\n",
                ""
            ),
            vec!["a.go"]
        );
        assert_eq!(
            unformatted_files(
                FormatterKind::Rustfmt,
                "Diff in /w/src/main.rs:1:\n-fn main(){}\nDiff in /w/src/lib.rs at line 4:\nDiff in /w/src/main.rs:9:\n",
                ""
            ),
            vec!["/w/src/main.rs", "/w/src/lib.rs"]
        );
    }

    #[test]
    fn strip_location_keeps_drive() {
        assert_eq!(strip_location(r"C:\a\b.py:1:2"), r"C:\a\b.py");
        assert_eq!(strip_location("b.py:3"), "b.py");
        assert_eq!(strip_location("b.py"), "b.py");
    }

    #[test]
    fn bandit_report() {
        let out = r#"[main] INFO profile include tests: None
{"errors": [{"filename": "x.py", "reason": "syntax error"}], "results": [
 {"issue_severity": "HIGH", "test_id": "B602", "issue_text": "shell=True"},
 {"issue_severity": "LOW", "test_id": "B404", "issue_text": "subprocess"},
 {"issue_severity": "LOW", "test_id": "B603", "issue_text": "x"}
]}"#;
        let r = bandit(out).unwrap();
        assert_eq!(r.findings.len(), 3);
        assert_eq!(r.summary["high"], 1);
        assert_eq!(r.summary["low"], 2);
        assert_eq!(r.summary["medium"], 0);
        assert_eq!(r.summary["errors"], 1);
        assert!(bandit("not json").is_none());
        assert!(bandit("{\"no_results\": 1}").is_none());
    }

    #[test]
    fn pip_audit_current_and_legacy() {
        let current = r#"{"dependencies": [
            {"name": "requests", "version": "2.19.0", "vulns": [
                {"id": "PYSEC-2018-28", "fix_versions": ["2.20.0"], "aliases": ["CVE-2018-18074"], "description": "d"}]},
            {"name": "idna", "version": "3.7", "vulns": []},
            {"name": "local", "skip_reason": "not on PyPI"}
        ], "fixes": []}"#;
        let v = pip_audit(current).unwrap();
        assert_eq!(v.len(), 1);
        assert_eq!(v[0]["package"], "requests");
        assert_eq!(v[0]["id"], "PYSEC-2018-28");
        assert_eq!(v[0]["fix_versions"][0], "2.20.0");

        let legacy = r#"[{"name": "a", "version": "1", "vulns": [{"id": "X"}, {"id": "Y"}]}]"#;
        assert_eq!(pip_audit(legacy).unwrap().len(), 2);

        assert_eq!(pip_audit(r#"{"dependencies": []}"#).unwrap().len(), 0);
        assert!(pip_audit("ERROR: could not resolve").is_none());
        assert!(pip_audit(r#"{"other": 1}"#).is_none());
    }

    #[test]
    fn md_link_report() {
        let out = r#"{"success": true, "files_checked": 2, "total_links": 5, "broken_links": 1,
            "file_errors": 1, "all_valid": false, "results": [
            {"file": "a.md", "links": [
                {"url": "./ok.md", "valid": true, "lines": [1]},
                {"url": "./gone.md", "valid": false, "error": "File not found", "lines": [3, 7]}
            ], "broken_count": 1, "total_count": 2},
            {"file": "b.md", "links": [], "broken_count": 0, "total_count": 0, "error": "permission denied"}
        ]}"#;
        let r = md_links(out).unwrap();
        assert_eq!(r.files_checked, 2);
        assert_eq!(r.broken_links, 1);
        assert!(!r.all_valid);
        assert_eq!(r.broken.len(), 2);
        assert_eq!(r.broken[0]["url"], "./gone.md");
        assert_eq!(r.broken[0]["lines"][1], 7);
        assert_eq!(r.broken[1]["file"], "b.md");
        assert_eq!(r.broken[1]["error"], "permission denied");
        assert!(md_links("error: bad args").is_none());
    }

    #[test]
    fn pytest_summaries() {
        let full = "collected 6 items\n\n...\n===== 3 passed, 1 failed, 2 skipped, 1 warning in 0.52s =====\n";
        let s = pytest_summary(full).unwrap();
        assert_eq!(s["passed"], 3);
        assert_eq!(s["failed"], 1);
        assert_eq!(s["skipped"], 2);
        assert_eq!(s["warnings"], 1);

        let quiet = "..\n2 passed in 0.01s\n";
        assert_eq!(pytest_summary(quiet).unwrap()["passed"], 2);

        let errs = "=== 1 error in 0.10s ===";
        assert_eq!(pytest_summary(errs).unwrap()["errors"], 1);

        let none = "=== no tests ran in 0.01s ===";
        assert_eq!(pytest_summary(none).unwrap()["no_tests_ran"], true);

        assert!(pytest_summary("ERROR: file or directory not found: x").is_none());
    }

    #[test]
    fn cargo_edition_parsing() {
        let toml =
            "[package]\nname = \"x\"\nedition = \"2024\"\n\n[dependencies]\nedition = \"1999\"\n";
        assert_eq!(cargo_edition(toml).as_deref(), Some("2024"));
        assert_eq!(cargo_edition("[workspace]\nmembers = []\n"), None);
        assert_eq!(cargo_edition("[package]\nedition.workspace = true\n"), None);
    }
}
