//! `automation-cli setup <action>` -- host / self-hosted runner setup.

use std::path::Path;

use anyhow::{Context, Result, bail};
use clap::Subcommand;

use crate::shared::{output, process, project};

#[derive(Subcommand)]
pub enum SetupAction {
    /// Check host prerequisites for AI agents (reports missing tools)
    Agents,
    /// Setup GitHub Actions runner (runs automation/setup/runner/setup-runner.sh)
    Runner,
    /// Setup GitHub Actions runner with system dependencies (setup-runner-full.sh)
    RunnerFull,
    /// Fix runner permissions: output dirs, Python caches, .env USER_ID/GROUP_ID,
    /// git safe.directory
    Permissions,
    /// Initialize Docker output directories owned by the current user
    InitDirs,
}

/// Output directories bind-mounted by the MCP containers.
const OUTPUT_DIRS: [&str; 7] = [
    "outputs",
    "outputs/video-editor",
    "outputs/manim",
    "outputs/latex",
    "outputs/content-creation",
    "outputs/blender",
    "outputs/meme-generator",
];

pub fn run(action: SetupAction) -> Result<()> {
    let root = project::enter_project_root()?;
    match action {
        SetupAction::Agents => setup_agents(&root),
        SetupAction::Runner => run_script(&root, "automation/setup/runner/setup-runner.sh"),
        SetupAction::RunnerFull => {
            run_script(&root, "automation/setup/runner/setup-runner-full.sh")
        },
        SetupAction::Permissions => setup_permissions(&root),
        SetupAction::InitDirs => init_dirs(&root),
    }
}

fn run_script(root: &Path, script: &str) -> Result<()> {
    if !root.join(script).is_file() {
        bail!("setup script not found: {script}");
    }
    process::run("bash", &[script])
}

fn setup_agents(root: &Path) -> Result<()> {
    output::header("Checking host environment for AI agents");
    let mut issues = Vec::new();

    for (cmd, desc) in [
        ("git", "Version control"),
        ("gh", "GitHub CLI"),
        ("docker", "Container runtime"),
        ("cargo", "Rust toolchain"),
    ] {
        if process::command_exists(cmd) {
            output::success(&format!("{cmd} ({desc}) found"));
        } else {
            output::fail(&format!("{cmd} ({desc}) not found"));
            issues.push(format!("Install {cmd}: {desc}"));
        }
    }

    for (cmd, desc) in [("claude", "Claude CLI"), ("node", "Node.js runtime")] {
        if process::command_exists(cmd) {
            output::success(&format!("{cmd} ({desc}) found"));
        } else {
            output::warn(&format!("{cmd} ({desc}) not found (optional)"));
        }
    }

    if process::command_exists("gh") {
        if process::run_check("gh", &["auth", "status"])? {
            output::success("GitHub CLI authenticated");
        } else {
            output::warn("GitHub CLI not authenticated (run: gh auth login)");
            issues.push("Run: gh auth login".to_string());
        }
    }

    let agents_binary = root.join("tools/rust/github-agents-cli/target/release/github-agents");
    if agents_binary.is_file() || process::command_exists("github-agents") {
        output::success("github-agents binary found");
    } else {
        output::warn("github-agents binary not built");
        output::info("  Build with: cd tools/rust/github-agents-cli && cargo build --release");
        issues.push("Build github-agents binary".to_string());
    }

    println!();
    if issues.is_empty() {
        output::success("All agent prerequisites satisfied!");
    } else {
        output::header("Action items");
        for issue in &issues {
            output::info(&format!("  - {issue}"));
        }
    }
    Ok(())
}

/// Create the output directories (skipping symlinks, which may point at
/// external storage).
fn create_output_dirs(root: &Path) -> Result<()> {
    for dir in OUTPUT_DIRS {
        let path = root.join(dir);
        if path.is_symlink() {
            output::info(&format!("Skipping symlink: {dir}"));
            continue;
        }
        if !path.exists() {
            output::step(&format!("Creating {dir}..."));
            std::fs::create_dir_all(&path)
                .with_context(|| format!("failed to create {}", path.display()))?;
        }
    }
    Ok(())
}

fn setup_permissions(root: &Path) -> Result<()> {
    output::header("Setting up GitHub Actions runner permissions");
    create_output_dirs(root)?;

    output::step("Cleaning Python cache files...");
    let removed = remove_python_caches(root);
    output::info(&format!("Removed {removed} cache entries"));

    let (uid, gid) = project::user_ids();
    output::info(&format!("Docker user: {uid}:{gid}"));

    // Update USER_ID/GROUP_ID in .env without clobbering other settings
    // (the file usually also holds API keys).
    let env_path = root.join(".env");
    let existing = match std::fs::read_to_string(&env_path) {
        Ok(s) => s,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(e) => return Err(e).context("failed to read .env"),
    };
    let updated = upsert_env(
        &existing,
        &[
            ("USER_ID", &uid.to_string()),
            ("GROUP_ID", &gid.to_string()),
        ],
    );
    if updated != existing {
        std::fs::write(&env_path, updated).context("failed to write .env")?;
        output::success(".env USER_ID/GROUP_ID updated");
    } else {
        output::info(".env already up to date");
    }

    let root_str = root.to_string_lossy();
    let already_safe = process::run_capture(
        "git",
        &["config", "--global", "--get-all", "safe.directory"],
    )
    .is_ok_and(|out| out.lines().any(|l| l.trim() == root_str || l.trim() == "*"));
    if !already_safe
        && let Err(e) = process::run(
            "git",
            &["config", "--global", "--add", "safe.directory", &root_str],
        )
    {
        output::warn(&format!("could not add git safe.directory: {e}"));
    }

    output::success("Permissions setup complete");
    Ok(())
}

/// Recursively delete `__pycache__` / `.pytest_cache` dirs and `*.pyc` files,
/// skipping VCS and build trees. Returns the number of entries removed.
fn remove_python_caches(dir: &Path) -> usize {
    let mut removed = 0;
    let Ok(entries) = std::fs::read_dir(dir) else {
        return 0;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name();
        let name = name.to_string_lossy();
        let Ok(ft) = entry.file_type() else {
            continue;
        };
        if ft.is_dir() {
            if matches!(name.as_ref(), "__pycache__" | ".pytest_cache") {
                match std::fs::remove_dir_all(&path) {
                    Ok(()) => removed += 1,
                    Err(e) => output::warn(&format!("cannot remove {}: {e}", path.display())),
                }
            } else if !matches!(name.as_ref(), ".git" | "target" | "node_modules") {
                removed += remove_python_caches(&path);
            }
        } else if ft.is_file() && name.ends_with(".pyc") {
            match std::fs::remove_file(&path) {
                Ok(()) => removed += 1,
                Err(e) => output::warn(&format!("cannot remove {}: {e}", path.display())),
            }
        }
    }
    removed
}

/// Set `KEY=value` lines in dotenv content, replacing existing assignments
/// in place and appending missing keys. Other lines are preserved verbatim.
fn upsert_env(content: &str, vars: &[(&str, &str)]) -> String {
    let mut seen = vec![false; vars.len()];
    let mut out: Vec<String> = content
        .lines()
        .map(|line| {
            let key = line
                .trim_start()
                .trim_start_matches("export ")
                .split('=')
                .next()
                .unwrap_or("")
                .trim();
            match vars.iter().position(|(k, _)| *k == key) {
                Some(i) if line.contains('=') => {
                    seen[i] = true;
                    format!("{}={}", vars[i].0, vars[i].1)
                },
                _ => line.to_string(),
            }
        })
        .collect();
    for (i, (k, v)) in vars.iter().enumerate() {
        if !seen[i] {
            out.push(format!("{k}={v}"));
        }
    }
    let mut s = out.join("\n");
    s.push('\n');
    s
}

fn init_dirs(root: &Path) -> Result<()> {
    output::header("Initializing Docker output directories");
    create_output_dirs(root)?;

    // Fix ownership via Docker to avoid needing sudo.
    output::step("Fixing directory ownership...");
    let (uid, gid) = project::user_ids();
    let mount = format!("{}:/work", root.join("outputs").display());
    let owner = format!("{uid}:{gid}");
    if let Err(e) = process::run(
        "docker",
        &[
            "run",
            "--rm",
            "-v",
            &mount,
            "busybox:1.36.1",
            "chown",
            "-R",
            &owner,
            "/work",
        ],
    ) {
        output::warn(&format!("could not fix ownership via docker: {e}"));
    }

    output::success("Output directories initialized");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn upsert_env_replaces_and_appends() {
        let input = "# comment\nOPENAI_KEY=secret\nUSER_ID=1\nexport GROUP_ID=2\n";
        let out = upsert_env(input, &[("USER_ID", "1000"), ("GROUP_ID", "1000")]);
        assert_eq!(
            out,
            "# comment\nOPENAI_KEY=secret\nUSER_ID=1000\nGROUP_ID=1000\n"
        );
    }

    #[test]
    fn upsert_env_appends_missing_keys() {
        let out = upsert_env("A=1", &[("USER_ID", "5")]);
        assert_eq!(out, "A=1\nUSER_ID=5\n");
        assert_eq!(upsert_env("", &[("X", "1")]), "X=1\n");
    }

    #[test]
    fn upsert_env_does_not_match_prefixes() {
        let out = upsert_env("USER_ID_EXTRA=7\n", &[("USER_ID", "5")]);
        assert_eq!(out, "USER_ID_EXTRA=7\nUSER_ID=5\n");
    }

    #[test]
    fn python_cache_cleanup() {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path();
        std::fs::create_dir_all(root.join("pkg/__pycache__")).unwrap();
        std::fs::write(root.join("pkg/__pycache__/m.cpython.pyc"), "").unwrap();
        std::fs::write(root.join("pkg/stray.pyc"), "").unwrap();
        std::fs::write(root.join("pkg/keep.py"), "").unwrap();
        std::fs::create_dir_all(root.join(".git/__pycache__")).unwrap();
        assert_eq!(remove_python_caches(root), 2);
        assert!(root.join("pkg/keep.py").exists());
        assert!(!root.join("pkg/__pycache__").exists());
        assert!(
            root.join(".git/__pycache__").exists(),
            ".git must be skipped"
        );
    }
}
