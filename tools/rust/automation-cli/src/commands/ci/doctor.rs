//! `automation-cli ci doctor` -- consistency checks between the stage catalog
//! and the repository (workflows, docs, compose file, workspace layout).

use std::path::{Path, PathBuf};

use anyhow::{Result, bail};

use super::stages::{self, IterGroup, Stage, Workspace};
use crate::shared::{output, project};

/// Modes accepted by `automation-cli lint` (and `run-lint-stage.sh`).
pub const LINT_MODES: [&str; 5] = ["format", "ruff", "basic", "full", "links"];

/// Directories never scanned for references.
const SKIP_DIRS: [&str; 9] = [
    ".git",
    "target",
    "node_modules",
    ".venv",
    "venv",
    "outputs",
    "__pycache__",
    "site",
    "htmlcov",
];

/// File extensions scanned for stage references.
const SCAN_EXTS: [&str; 4] = ["md", "yml", "yaml", "sh"];

#[derive(Default)]
struct Report {
    failures: usize,
    warnings: usize,
}

impl Report {
    fn ok(&self, msg: &str) {
        output::success(msg);
    }
    fn warn(&mut self, msg: &str) {
        self.warnings += 1;
        output::warn(msg);
    }
    fn fail(&mut self, msg: &str) {
        self.failures += 1;
        output::fail(msg);
    }
}

pub fn run() -> Result<()> {
    let root = project::enter_project_root()?;
    let mut report = Report::default();

    output::header("Compose services");
    check_compose(&root, &mut report);

    output::header("Rust workspaces and crate groups");
    check_layout(&root, &mut report);

    output::header("Test stage paths");
    for p in [
        "tests",
        "automation/corporate-proxy/tests",
        "automation/corporate-proxy/shared/scripts/test-auto-detection.py",
        "automation/corporate-proxy/shared/scripts/test-content-stripping.py",
        "tools/mcp/mcp_gaea2/Cargo.toml",
        "pyproject.toml",
    ] {
        if root.join(p).exists() {
            report.ok(p);
        } else {
            report.warn(&format!("{p} is used by a test stage but does not exist"));
        }
    }

    output::header("Stage references in workflows, scripts and docs");
    check_references(&root, &mut report);

    println!();
    output::header("Doctor summary");
    output::info(&format!("Failures: {}", report.failures));
    output::info(&format!("Warnings: {}", report.warnings));
    if report.failures > 0 {
        bail!("ci doctor found {} problem(s)", report.failures);
    }
    output::success("CI configuration is consistent");
    Ok(())
}

fn check_compose(root: &Path, report: &mut Report) {
    let path = project::compose_file(root);
    let parsed = std::fs::read_to_string(&path)
        .map_err(anyhow::Error::from)
        .and_then(|s| Ok(serde_yaml::from_str::<serde_yaml::Value>(&s)?));
    let doc = match parsed {
        Ok(doc) => doc,
        Err(e) => {
            report.fail(&format!("cannot parse {}: {e}", path.display()));
            return;
        },
    };
    for service in ["python-ci", "rust-ci"] {
        if doc["services"][service].is_mapping() {
            report.ok(&format!("service `{service}` defined"));
        } else {
            report.fail(&format!(
                "service `{service}` missing from docker-compose.yml"
            ));
        }
    }
}

fn check_layout(root: &Path, report: &mut Report) {
    for ws in Workspace::ALL {
        let dir = root.join(ws.path());
        if !dir.join("Cargo.toml").is_file() {
            report.fail(&format!("{ws}: {} has no Cargo.toml", ws.path()));
            continue;
        }
        report.ok(&format!("{ws}: {}", ws.path()));
        let has_deny_stage = !matches!(ws, Workspace::McpSpriteSheet);
        if has_deny_stage && !dir.join("deny.toml").is_file() {
            report.warn(&format!(
                "{ws}: no deny.toml (cargo-deny falls back to defaults)"
            ));
        }
    }

    if root.join("tools/mcp/mcp_bioforge/Cargo.toml").is_file() {
        report.ok("MCP BioForge server: tools/mcp/mcp_bioforge");
    } else {
        report.fail("bio-* stages expect tools/mcp/mcp_bioforge/Cargo.toml");
    }

    let tamper = root.join(Workspace::TamperBriefcase.path());
    let names = crate_names_below(&tamper, 2);
    for krate in super::TAMPER_HOST_CRATES {
        if names.iter().any(|n| n == krate) {
            report.ok(&format!("tamper crate {krate}"));
        } else {
            report.fail(&format!("tamper-* stages expect crate `{krate}`"));
        }
    }

    for group in IterGroup::ALL {
        match super::discover_group(root, group) {
            Ok(crates) if crates.is_empty() => {
                report.warn(&format!("{group}: no crates found in {}", group.base_dir()));
            },
            Ok(crates) => report.ok(&format!("{group}: {}", crates.join(", "))),
            Err(e) => report.fail(&format!("{group}: {e}")),
        }
    }
}

/// Package names declared by Cargo.toml files up to `depth` levels below `dir`.
fn crate_names_below(dir: &Path, depth: usize) -> Vec<String> {
    let mut names = Vec::new();
    if let Ok(text) = std::fs::read_to_string(dir.join("Cargo.toml"))
        && let Some(name) = package_name(&text)
    {
        names.push(name);
    }
    if depth == 0 {
        return names;
    }
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            let skip = path
                .file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| SKIP_DIRS.contains(&n));
            if path.is_dir() && !skip {
                names.extend(crate_names_below(&path, depth - 1));
            }
        }
    }
    names
}

/// Extract `name = "..."` from the `[package]` table of a Cargo.toml.
fn package_name(toml: &str) -> Option<String> {
    let mut in_package = false;
    for line in toml.lines() {
        let line = line.trim();
        if line.starts_with('[') {
            in_package = line == "[package]";
            continue;
        }
        if in_package
            && let Some(rest) = line.strip_prefix("name")
            && let Some(value) = rest.trim_start().strip_prefix('=')
        {
            return Some(value.trim().trim_matches('"').to_string());
        }
    }
    None
}

/// A reference to a stage/lint mode found in a file.
#[derive(Debug, PartialEq, Eq)]
struct Reference {
    line: usize,
    name: String,
}

/// Find `<marker><name>` occurrences, skipping placeholders (`<stage>`,
/// `${{ ... }}`, `$VAR`), flags, and `#` comment lines (prose such as
/// "built by run-ci.sh script" is not a reference).
fn extract_refs(text: &str, marker: &str) -> Vec<Reference> {
    let mut refs = Vec::new();
    for (idx, line) in text.lines().enumerate() {
        if line.trim_start().starts_with('#') {
            continue;
        }
        let mut rest = line;
        while let Some(pos) = rest.find(marker) {
            rest = &rest[pos + marker.len()..];
            let name: String = rest
                .trim_start_matches(' ')
                .chars()
                .take_while(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
                .collect();
            if !name.is_empty() && !name.starts_with('-') {
                refs.push(Reference {
                    line: idx + 1,
                    name,
                });
            }
        }
    }
    refs
}

fn check_references(root: &Path, report: &mut Report) {
    let mut files = Vec::new();
    collect_files(root, &mut files);
    files.sort();

    let mut checked = 0usize;
    let mut bad = 0usize;
    for file in &files {
        let Ok(text) = std::fs::read_to_string(file) else {
            continue;
        };
        let rel = file
            .strip_prefix(root)
            .unwrap_or(file)
            .display()
            .to_string();
        for marker in ["run-ci.sh ", "automation-cli ci run "] {
            for r in extract_refs(&text, marker) {
                checked += 1;
                if Stage::parse(&r.name).is_err() {
                    bad += 1;
                    let hint = stages::suggest(&r.name)
                        .map(|s| format!(" (did you mean `{s}`?)"))
                        .unwrap_or_default();
                    report.fail(&format!(
                        "{rel}:{}: unknown CI stage `{}`{hint}",
                        r.line, r.name
                    ));
                }
            }
        }
        for marker in ["run-lint-stage.sh ", "automation-cli lint "] {
            for r in extract_refs(&text, marker) {
                checked += 1;
                if !LINT_MODES.contains(&r.name.as_str()) {
                    bad += 1;
                    report.fail(&format!(
                        "{rel}:{}: unknown lint mode `{}` (valid: {})",
                        r.line,
                        r.name,
                        LINT_MODES.join(", ")
                    ));
                }
            }
        }
    }
    if bad == 0 {
        report.ok(&format!(
            "{checked} stage references in {} files all resolve",
            files.len()
        ));
    }
}

fn collect_files(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name();
        let name = name.to_string_lossy();
        let Ok(ft) = entry.file_type() else {
            continue;
        };
        if ft.is_dir() {
            if !SKIP_DIRS.contains(&name.as_ref()) {
                collect_files(&path, out);
            }
        } else if ft.is_file()
            && path
                .extension()
                .and_then(|e| e.to_str())
                .is_some_and(|e| SCAN_EXTS.contains(&e))
        {
            out.push(path);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_refs_finds_names_and_skips_placeholders() {
        let text = "run: ./automation/ci-cd/run-ci.sh econ-fmt\n\
                    automation-cli ci run <stage>\n\
                    ./automation/ci-cd/run-ci.sh ${{ inputs.stage }}\n\
                    x run-ci.sh test -- --timeout=300; run-ci.sh rust-all\n\
                    run-ci.sh --help\n\
                    # Docker image is built by run-ci.sh script\n";
        let refs = extract_refs(text, "run-ci.sh ");
        let names: Vec<_> = refs.iter().map(|r| (r.line, r.name.as_str())).collect();
        assert_eq!(names, [(1, "econ-fmt"), (4, "test"), (4, "rust-all")]);
    }

    #[test]
    fn package_name_reads_package_table_only() {
        let toml = "[workspace]\nmembers = []\n[package]\nname = \"tamper-gate\"\n\
                    [dependencies]\nname = \"not-this\"\n";
        assert_eq!(package_name(toml).as_deref(), Some("tamper-gate"));
        assert_eq!(package_name("[workspace]\nmembers = []\n"), None);
    }

    #[test]
    fn crate_names_below_finds_members() {
        let dir = tempfile::tempdir().unwrap();
        let member = dir.path().join("crates/foo");
        std::fs::create_dir_all(&member).unwrap();
        std::fs::write(dir.path().join("Cargo.toml"), "[workspace]\n").unwrap();
        std::fs::write(member.join("Cargo.toml"), "[package]\nname = \"foo\"\n").unwrap();
        assert_eq!(crate_names_below(dir.path(), 2), ["foo"]);
        assert!(crate_names_below(dir.path(), 1).is_empty());
    }

    #[test]
    fn lint_modes_match_lint_subcommands() {
        use clap::CommandFactory;
        #[derive(clap::Parser)]
        #[allow(dead_code)]
        struct Probe {
            #[command(subcommand)]
            action: super::super::lint::LintAction,
        }
        let cmd = Probe::command();
        let mut subs: Vec<_> = cmd
            .get_subcommands()
            .map(|s| s.get_name().to_string())
            .collect();
        subs.sort();
        let mut modes: Vec<_> = LINT_MODES.iter().map(|s| s.to_string()).collect();
        modes.sort();
        assert_eq!(subs, modes);
    }
}
