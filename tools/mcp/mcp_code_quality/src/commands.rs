//! Pure command builders: map validated, canonical inputs to [`CommandSpec`]s.
//!
//! Nothing here touches the filesystem or spawns anything, so the exact argv
//! each tool receives is unit tested. All path arguments are canonical
//! absolute paths produced by [`crate::paths::PathPolicy`], so none of them
//! can be interpreted as an option by the target tool.

use crate::parsers::FormatterKind;
use crate::process::CommandSpec;
use crate::types::{Language, Linter, PythonFormatter, Severity};
use std::path::{Path, PathBuf};

/// Where cargo puts build artifacts for clippy runs. The workspace is usually
/// mounted read-only in the container, so `target/` next to the crate is not
/// writable; a shared scratch dir also lets repeated runs reuse the build.
pub fn cargo_target_dir() -> PathBuf {
    std::env::temp_dir().join("mcp-code-quality-cargo-target")
}

/// What a formatter should do.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FormatMode {
    /// Report only; `diff` additionally asks for a diff where supported.
    Check { diff: bool },
    /// Rewrite files in place.
    Write,
}

/// Inputs for a format command.
#[derive(Debug, Clone)]
pub struct FormatRequest<'a> {
    pub language: Language,
    pub python_formatter: PythonFormatter,
    pub target: &'a Path,
    pub target_is_dir: bool,
    /// For Rust directories: whether `target/Cargo.toml` exists.
    pub has_cargo_toml: bool,
    /// Rust edition for single-file rustfmt runs.
    pub rust_edition: &'a str,
    pub mode: FormatMode,
}

/// A built format command plus how to interpret its output.
#[derive(Debug, Clone)]
pub struct FormatCommand {
    pub spec: CommandSpec,
    pub kind: FormatterKind,
    pub notes: Vec<String>,
}

/// Build the formatter invocation. Errors describe unsupported inputs.
pub fn format_command(req: &FormatRequest<'_>) -> Result<FormatCommand, String> {
    let check = matches!(req.mode, FormatMode::Check { .. });
    let diff = matches!(req.mode, FormatMode::Check { diff: true });
    let mut notes = Vec::new();

    let (spec, kind) = match req.language {
        Language::Python => match req.python_formatter {
            PythonFormatter::Ruff => {
                let mut s = CommandSpec::new("ruff").args(["format", "--no-cache"]);
                if check {
                    s = s.arg("--check");
                }
                if diff {
                    s = s.arg("--diff");
                }
                (s.path_arg(req.target), FormatterKind::Ruff)
            },
            PythonFormatter::Black => {
                let mut s = CommandSpec::new("black");
                if check {
                    s = s.arg("--check");
                }
                if diff {
                    s = s.arg("--diff");
                }
                (s.path_arg(req.target), FormatterKind::Black)
            },
        },
        Language::Javascript | Language::Typescript => {
            if diff {
                notes.push("prettier has no diff mode; reporting file names only".to_string());
            }
            let flag = if check { "--check" } else { "--write" };
            (
                CommandSpec::new("prettier").arg(flag).path_arg(req.target),
                FormatterKind::Prettier,
            )
        },
        Language::Go => {
            let flag = match req.mode {
                FormatMode::Check { diff: true } => "-d",
                FormatMode::Check { diff: false } => "-l",
                FormatMode::Write => "-w",
            };
            (
                CommandSpec::new("gofmt").arg(flag).path_arg(req.target),
                FormatterKind::Gofmt,
            )
        },
        Language::Rust => {
            if req.target_is_dir {
                if !req.has_cargo_toml {
                    return Err(format!(
                        "{} is a directory without a Cargo.toml; pass a crate directory or a single .rs file",
                        req.target.display()
                    ));
                }
                let mut s = CommandSpec::new("cargo").arg("fmt");
                if check {
                    s = s.arg("--check");
                }
                (s.cwd(req.target), FormatterKind::Rustfmt)
            } else {
                let mut s = CommandSpec::new("rustfmt");
                if check {
                    s = s.arg("--check");
                }
                (
                    s.args(["--edition", req.rust_edition]).path_arg(req.target),
                    FormatterKind::Rustfmt,
                )
            }
        },
    };
    Ok(FormatCommand { spec, kind, notes })
}

/// Did the formatter fail for a reason other than "files need formatting"?
/// (Syntax errors, bad config, internal errors.)
pub fn format_exit_is_error(kind: FormatterKind, code: i32) -> bool {
    match kind {
        // 0 = ok, 1 = would reformat, 2 = error
        FormatterKind::Ruff | FormatterKind::Prettier => !(0..=1).contains(&code),
        // 0 = ok, 1 = would reformat, 123 = internal error
        FormatterKind::Black => code != 0 && code != 1,
        // gofmt: 0 even when files differ; non-zero means a parse error
        FormatterKind::Gofmt => code != 0,
        // rustfmt --check uses 1 for both diffs and errors; decided by output
        FormatterKind::Rustfmt => code != 0 && code != 1,
    }
}

/// A built lint command and where its diagnostics are printed.
#[derive(Debug, Clone)]
pub struct LintCommand {
    pub spec: CommandSpec,
    /// Diagnostics are on stderr (clippy) rather than stdout.
    pub diagnostics_on_stderr: bool,
    /// Output is eslint JSON.
    pub eslint_json: bool,
    pub notes: Vec<String>,
}

/// Build the linter invocation.
pub fn lint_command(
    linter: Linter,
    target: &Path,
    target_is_dir: bool,
    has_cargo_toml: bool,
    config: Option<&Path>,
) -> Result<LintCommand, String> {
    let mut notes = Vec::new();
    let mut diagnostics_on_stderr = false;
    let mut eslint_json = false;

    let spec = match linter {
        Linter::Flake8 => {
            let mut s = CommandSpec::new("flake8");
            if let Some(c) = config {
                s = s.arg("--config").path_arg(c);
            }
            s.path_arg(target)
        },
        Linter::Ruff => {
            let mut s = CommandSpec::new("ruff").args([
                "check",
                "--no-cache",
                "--output-format",
                "concise",
            ]);
            if let Some(c) = config {
                s = s.arg("--config").path_arg(c);
            }
            s.path_arg(target)
        },
        Linter::Eslint => {
            eslint_json = true;
            let mut s = CommandSpec::new("eslint").args(["--format", "json"]);
            if let Some(c) = config {
                s = s.arg("--config").path_arg(c);
            }
            s.path_arg(target)
        },
        Linter::Golint => {
            if config.is_some() {
                notes.push("golint has no config file support; 'config' was ignored".to_string());
            }
            CommandSpec::new("golint").path_arg(target)
        },
        Linter::Clippy => {
            if !target_is_dir || !has_cargo_toml {
                return Err(format!(
                    "clippy needs a crate directory containing Cargo.toml; got {}",
                    target.display()
                ));
            }
            diagnostics_on_stderr = true;
            let mut s = CommandSpec::new("cargo")
                .args(["clippy", "--quiet", "--message-format=short"])
                .cwd(target)
                .env("CARGO_TARGET_DIR", cargo_target_dir().display().to_string());
            if let Some(c) = config {
                // clippy reads clippy.toml from CLIPPY_CONF_DIR.
                let dir = c.parent().unwrap_or(c);
                s = s.env("CLIPPY_CONF_DIR", dir.display().to_string());
                if c.file_name().and_then(|n| n.to_str()) != Some("clippy.toml")
                    && c.file_name().and_then(|n| n.to_str()) != Some(".clippy.toml")
                {
                    notes.push(format!(
                        "clippy only reads 'clippy.toml'/'.clippy.toml'; using the directory {}",
                        dir.display()
                    ));
                }
            }
            s
        },
    };
    Ok(LintCommand {
        spec,
        diagnostics_on_stderr,
        eslint_json,
        notes,
    })
}

/// Build `ty check`. A `pyproject.toml` config selects the project directory
/// (`--project`); any other file is passed as `--config-file` (ty.toml).
/// `strict` maps to `--error-on-warning` (ty has no separate strict mode).
pub fn type_check_command(target: &Path, config: Option<&Path>, strict: bool) -> CommandSpec {
    let mut s = CommandSpec::new("ty").args(["check", "--output-format", "concise"]);
    if strict {
        s = s.arg("--error-on-warning");
    }
    if let Some(c) = config {
        if c.file_name().and_then(|n| n.to_str()) == Some("pyproject.toml") {
            s = s.arg("--project").path_arg(c.parent().unwrap_or(c));
        } else {
            s = s.arg("--config-file").path_arg(c);
        }
    }
    s.path_arg(target)
}

/// Is a `run_tests` `pattern` a file glob (e.g. `test_*.py`) rather than a
/// `-k` keyword expression?
pub fn pattern_is_file_glob(pattern: &str) -> bool {
    let p = pattern.trim();
    p.ends_with(".py") || (p.contains('*') && !p.contains(' '))
}

/// Inputs for pytest.
#[derive(Debug, Clone, Default)]
pub struct PytestRequest<'a> {
    pub target: PathBuf,
    pub working_dir: Option<&'a Path>,
    pub pattern: Option<&'a str>,
    pub markers: Option<&'a str>,
    pub verbose: bool,
    pub coverage: bool,
    pub fail_fast: bool,
}

/// Build the pytest invocation. The cache provider is disabled and the
/// coverage data file goes to the temp dir so a read-only workspace works.
pub fn pytest_command(req: &PytestRequest<'_>) -> CommandSpec {
    let mut s = CommandSpec::new("pytest")
        .path_arg(&req.target)
        .args(["-p", "no:cacheprovider"]);
    if req.verbose {
        s = s.arg("-v");
    }
    if req.fail_fast {
        s = s.arg("-x");
    }
    if req.coverage {
        let source = req
            .working_dir
            .map(|d| d.display().to_string())
            .unwrap_or_else(|| ".".to_string());
        s = s
            .arg(format!("--cov={source}"))
            .arg("--cov-report=term-missing")
            .env(
                "COVERAGE_FILE",
                std::env::temp_dir()
                    .join(format!("mcp-code-quality-{}.coverage", std::process::id()))
                    .display()
                    .to_string(),
            );
    }
    if let Some(p) = req.pattern {
        if pattern_is_file_glob(p) {
            s = s.arg("-o").arg(format!("python_files={p}"));
        } else {
            s = s.arg("-k").arg(p);
        }
    }
    if let Some(m) = req.markers {
        s = s.arg("-m").arg(m);
    }
    if let Some(d) = req.working_dir {
        s = s.cwd(d);
    }
    s
}

/// Build `bandit` (recursive, JSON output).
pub fn bandit_command(target: &Path, severity: Severity, confidence: Severity) -> CommandSpec {
    CommandSpec::new("bandit")
        .arg("-r")
        .path_arg(target)
        .arg(format!("--severity-level={severity}"))
        .arg(format!("--confidence-level={confidence}"))
        .args(["-f", "json", "-q"])
}

/// Build `pip-audit` for a requirements file.
pub fn pip_audit_command(requirements: &Path) -> CommandSpec {
    CommandSpec::new("pip-audit")
        .arg("-r")
        .path_arg(requirements)
        .args(["--format", "json", "--progress-spinner", "off"])
}

/// Inputs for md-link-checker.
#[derive(Debug, Clone)]
pub struct LinkCheckRequest<'a> {
    pub target: &'a Path,
    pub check_external: bool,
    pub timeout: u32,
    pub concurrent: u32,
    pub ignore_patterns: &'a [String],
    pub exclude: &'a [String],
    pub skip_anchors: bool,
}

/// Build the md-link-checker invocation. User patterns are attached with
/// `--flag=value` so a pattern beginning with `-` stays a value.
pub fn link_check_command(req: &LinkCheckRequest<'_>) -> CommandSpec {
    let mut s = CommandSpec::new("md-link-checker")
        .path_arg(req.target)
        .arg("--json")
        .arg(format!("--timeout={}", req.timeout))
        .arg(format!("--concurrent={}", req.concurrent));
    if !req.check_external {
        s = s.arg("--internal-only");
    }
    if req.skip_anchors {
        s = s.arg("--skip-anchors");
    }
    for p in req.ignore_patterns {
        s = s.arg(format!("--ignore={p}"));
    }
    for e in req.exclude {
        s = s.arg(format!("--exclude={e}"));
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p(s: &str) -> PathBuf {
        PathBuf::from(s)
    }

    fn fmt_req(language: Language, mode: FormatMode) -> FormatRequest<'static> {
        FormatRequest {
            language,
            python_formatter: PythonFormatter::Ruff,
            target: Path::new("/w/src"),
            target_is_dir: true,
            has_cargo_toml: true,
            rust_edition: "2021",
            mode,
        }
    }

    #[test]
    fn python_format_commands() {
        let c = format_command(&fmt_req(
            Language::Python,
            FormatMode::Check { diff: false },
        ))
        .unwrap();
        assert_eq!(c.spec.display(), "ruff format --no-cache --check /w/src");
        let c =
            format_command(&fmt_req(Language::Python, FormatMode::Check { diff: true })).unwrap();
        assert_eq!(
            c.spec.display(),
            "ruff format --no-cache --check --diff /w/src"
        );
        let mut r = fmt_req(Language::Python, FormatMode::Write);
        r.python_formatter = PythonFormatter::Black;
        let c = format_command(&r).unwrap();
        assert_eq!(c.spec.display(), "black /w/src");
        assert_eq!(c.kind, FormatterKind::Black);
    }

    #[test]
    fn js_go_format_commands() {
        let c = format_command(&fmt_req(
            Language::Typescript,
            FormatMode::Check { diff: true },
        ))
        .unwrap();
        assert_eq!(c.spec.display(), "prettier --check /w/src");
        assert_eq!(c.notes.len(), 1);
        let c = format_command(&fmt_req(Language::Javascript, FormatMode::Write)).unwrap();
        assert_eq!(c.spec.display(), "prettier --write /w/src");
        let c = format_command(&fmt_req(Language::Go, FormatMode::Check { diff: false })).unwrap();
        assert_eq!(c.spec.display(), "gofmt -l /w/src");
        let c = format_command(&fmt_req(Language::Go, FormatMode::Write)).unwrap();
        assert_eq!(c.spec.display(), "gofmt -w /w/src");
    }

    #[test]
    fn rust_format_commands() {
        let c =
            format_command(&fmt_req(Language::Rust, FormatMode::Check { diff: false })).unwrap();
        assert_eq!(c.spec.display(), "cargo fmt --check");
        assert_eq!(c.spec.cwd.as_deref(), Some(Path::new("/w/src")));

        let mut r = fmt_req(Language::Rust, FormatMode::Check { diff: false });
        r.has_cargo_toml = false;
        assert!(format_command(&r).unwrap_err().contains("Cargo.toml"));

        let mut r = fmt_req(Language::Rust, FormatMode::Write);
        r.target = Path::new("/w/src/main.rs");
        r.target_is_dir = false;
        r.rust_edition = "2024";
        let c = format_command(&r).unwrap();
        assert_eq!(c.spec.display(), "rustfmt --edition 2024 /w/src/main.rs");
    }

    #[test]
    fn format_exit_codes() {
        assert!(!format_exit_is_error(FormatterKind::Ruff, 1));
        assert!(format_exit_is_error(FormatterKind::Ruff, 2));
        assert!(format_exit_is_error(FormatterKind::Black, 123));
        assert!(!format_exit_is_error(FormatterKind::Black, 1));
        assert!(format_exit_is_error(FormatterKind::Gofmt, 2));
        assert!(!format_exit_is_error(FormatterKind::Rustfmt, 1));
    }

    #[test]
    fn lint_commands() {
        let t = p("/w/src");
        let cfg = p("/w/ruff.toml");
        let c = lint_command(Linter::Ruff, &t, true, false, Some(&cfg)).unwrap();
        assert_eq!(
            c.spec.display(),
            "ruff check --no-cache --output-format concise --config /w/ruff.toml /w/src"
        );
        let c = lint_command(Linter::Flake8, &t, true, false, None).unwrap();
        assert_eq!(c.spec.display(), "flake8 /w/src");
        let c = lint_command(Linter::Eslint, &t, true, false, None).unwrap();
        assert!(c.eslint_json);
        assert_eq!(c.spec.display(), "eslint --format json /w/src");
        let c = lint_command(Linter::Golint, &t, true, false, Some(&cfg)).unwrap();
        assert_eq!(c.notes.len(), 1);
    }

    #[test]
    fn clippy_command() {
        let t = p("/w/crate");
        assert!(lint_command(Linter::Clippy, &t, true, false, None).is_err());
        assert!(lint_command(Linter::Clippy, &t, false, true, None).is_err());
        let cfg = p("/w/crate/clippy.toml");
        let c = lint_command(Linter::Clippy, &t, true, true, Some(&cfg)).unwrap();
        assert!(c.diagnostics_on_stderr);
        assert_eq!(
            c.spec.display(),
            "cargo clippy --quiet --message-format=short"
        );
        assert_eq!(c.spec.cwd.as_deref(), Some(t.as_path()));
        assert!(
            c.spec
                .env
                .iter()
                .any(|(k, v)| k == "CLIPPY_CONF_DIR" && v == "/w/crate")
        );
        assert!(c.spec.env.iter().any(|(k, _)| k == "CARGO_TARGET_DIR"));
        assert!(c.notes.is_empty());
    }

    #[test]
    fn ty_commands() {
        let t = p("/w/src");
        assert_eq!(
            type_check_command(&t, None, false).display(),
            "ty check --output-format concise /w/src"
        );
        let py = p("/w/pyproject.toml");
        assert_eq!(
            type_check_command(&t, Some(&py), true).display(),
            "ty check --output-format concise --error-on-warning --project /w /w/src"
        );
        let tyt = p("/w/ty.toml");
        assert_eq!(
            type_check_command(&t, Some(&tyt), false).display(),
            "ty check --output-format concise --config-file /w/ty.toml /w/src"
        );
    }

    #[test]
    fn pytest_commands() {
        assert!(pattern_is_file_glob("test_*.py"));
        assert!(pattern_is_file_glob("check_*"));
        assert!(!pattern_is_file_glob("not slow and parse"));
        assert!(!pattern_is_file_glob("test_login"));

        let wd = p("/w");
        let req = PytestRequest {
            target: p("/w/tests"),
            working_dir: Some(&wd),
            pattern: Some("test_*.py"),
            markers: Some("not slow"),
            verbose: true,
            coverage: true,
            fail_fast: true,
        };
        let s = pytest_command(&req);
        assert_eq!(
            s.display(),
            "pytest /w/tests -p no:cacheprovider -v -x --cov=/w --cov-report=term-missing -o python_files=test_*.py -m 'not slow'"
        );
        assert_eq!(s.cwd.as_deref(), Some(wd.as_path()));
        assert!(s.env.iter().any(|(k, _)| k == "COVERAGE_FILE"));

        let req = PytestRequest {
            target: p("/w/tests"),
            pattern: Some("login"),
            ..Default::default()
        };
        assert_eq!(
            pytest_command(&req).display(),
            "pytest /w/tests -p no:cacheprovider -k login"
        );
    }

    #[test]
    fn bandit_pip_audit_md() {
        assert_eq!(
            bandit_command(&p("/w"), Severity::Medium, Severity::High).display(),
            "bandit -r /w --severity-level=medium --confidence-level=high -f json -q"
        );
        assert_eq!(
            pip_audit_command(&p("/w/requirements.txt")).display(),
            "pip-audit -r /w/requirements.txt --format json --progress-spinner off"
        );
        let ignore = vec!["-evil".to_string(), "localhost".to_string()];
        let exclude = vec!["vendor/**".to_string()];
        let s = link_check_command(&LinkCheckRequest {
            target: Path::new("/w/docs"),
            check_external: false,
            timeout: 5,
            concurrent: 3,
            ignore_patterns: &ignore,
            exclude: &exclude,
            skip_anchors: true,
        });
        assert_eq!(
            s.display(),
            "md-link-checker /w/docs --json --timeout=5 --concurrent=3 --internal-only --skip-anchors --ignore=-evil --ignore=localhost --exclude=vendor/**"
        );
    }
}
