//! `automation-cli ci doctor`: consistency checks between the stage catalog
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

/// Directories in `tools/mcp/` that are shared libraries, not servers.
const MCP_NON_SERVER_DIRS: [&str; 2] = ["mcp_core", "mcp_core_rust"];

/// Docs that state the total number of MCP servers.
const MCP_COUNT_DOCS: [&str; 4] = [
    "README.md",
    "AGENTS.md",
    "docs/QUICKSTART.md",
    "docs/mcp/README.md",
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

    output::header("MCP server count in docs");
    check_mcp_server_count(&root, &mut report);

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

/// Number of MCP server directories in `tools/mcp/` (shared cores excluded).
fn mcp_server_count(root: &Path) -> std::io::Result<usize> {
    let mut count = 0;
    for entry in std::fs::read_dir(root.join("tools/mcp"))?.flatten() {
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if entry.file_type().is_ok_and(|t| t.is_dir())
            && !name.starts_with('.')
            && !MCP_NON_SERVER_DIRS.contains(&name.as_ref())
        {
            count += 1;
        }
    }
    Ok(count)
}

/// Totals stated as "<N> MCP server(s)" (case-insensitive), with the line
/// number. Only a number directly before "MCP server" counts, so subset
/// phrasing such as "19 active MCP servers" or the "(19 active, 2 legacy)"
/// in "21 MCP servers (19 active, 2 legacy)" is not a total.
fn stated_mcp_counts(text: &str) -> Vec<(usize, usize)> {
    const NEEDLE: &str = "mcp server";
    let mut found = Vec::new();
    for (idx, line) in text.lines().enumerate() {
        let lower = line.to_ascii_lowercase();
        let mut from = 0;
        while let Some(pos) = lower[from..].find(NEEDLE) {
            let at = from + pos;
            from = at + NEEDLE.len();
            let before = line[..at].trim_end();
            let digits_start = before
                .rfind(|c: char| !c.is_ascii_digit())
                .map_or(0, |i| i + 1);
            let digits = &before[digits_start..];
            // Skip identifiers such as "v2 MCP server".
            let glued = before[..digits_start]
                .chars()
                .next_back()
                .is_some_and(|c| c.is_ascii_alphanumeric());
            if !glued && let Ok(n) = digits.parse() {
                found.push((idx + 1, n));
            }
        }
    }
    found
}

/// Warn when a doc states a different MCP server total than `tools/mcp/`.
fn check_mcp_server_count(root: &Path, report: &mut Report) {
    let actual = match mcp_server_count(root) {
        Ok(n) => n,
        Err(e) => {
            report.warn(&format!("cannot list tools/mcp: {e}"));
            return;
        },
    };
    let mut drift = false;
    for doc in MCP_COUNT_DOCS {
        let Ok(text) = std::fs::read_to_string(root.join(doc)) else {
            continue;
        };
        for (line, n) in stated_mcp_counts(&text) {
            if n != actual {
                drift = true;
                report.warn(&format!(
                    "{doc}:{line}: states {n} MCP servers, but tools/mcp has {actual} \
                     (excluding {})",
                    MCP_NON_SERVER_DIRS.join(", ")
                ));
            }
        }
    }
    if !drift {
        report.ok(&format!("{actual} MCP servers in tools/mcp; docs agree"));
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
    fn stated_mcp_counts_reads_totals_only() {
        let text = "**21 MCP Servers** (19 active, 2 legacy)\n\
                    19 active MCP servers spanning code quality\n\
                    [21 MCP servers](#mcp-servers) and 1 MCP server here\n\
                    a v2 MCP server, no count\n\
                    MCP servers: 20\n";
        assert_eq!(stated_mcp_counts(text), [(1, 21), (3, 21), (3, 1)]);
    }

    #[test]
    fn mcp_server_count_excludes_shared_cores() {
        let dir = tempfile::tempdir().unwrap();
        for d in ["mcp_core", "mcp_core_rust", "mcp_a", "mcp_b", ".cache"] {
            std::fs::create_dir_all(dir.path().join("tools/mcp").join(d)).unwrap();
        }
        std::fs::write(dir.path().join("tools/mcp/README.md"), "").unwrap();
        assert_eq!(mcp_server_count(dir.path()).unwrap(), 2);

        std::fs::write(dir.path().join("README.md"), "2 MCP servers\n").unwrap();
        std::fs::create_dir_all(dir.path().join("docs")).unwrap();
        std::fs::write(dir.path().join("docs/QUICKSTART.md"), "3 MCP servers\n").unwrap();
        let mut report = Report::default();
        check_mcp_server_count(dir.path(), &mut report);
        assert_eq!((report.warnings, report.failures), (1, 0));
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
