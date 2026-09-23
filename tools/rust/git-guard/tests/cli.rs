//! End-to-end tests: run the built `git` wrapper against a fake real git.
//!
//! The fake git is a shell script placed first on PATH. It answers the
//! wrapper's context queries from `FAKE_*` variables and otherwise echoes its
//! arguments and exits with `$FAKE_EXIT`.
#![cfg(unix)]

use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

const FAKE_GIT: &str = r#"#!/bin/sh
last=""
for a in "$@"; do last="$a"; done
case " $* " in
  *" config --get alias."*)
    name="${last#alias.}"
    eval "v=\${FAKE_ALIAS_$name:-}"
    if [ -n "$v" ]; then printf '%s\n' "$v"; exit 0; fi
    exit 1 ;;
  *" symbolic-ref "*)
    if [ -n "$FAKE_BRANCH" ]; then echo "$FAKE_BRANCH"; exit 0; fi
    exit 1 ;;
  *" rev-parse --abbrev-ref --symbolic-full-name "*) exit 1 ;;
  *" config --get"*) exit 1 ;;
esac
if [ "$1" = "catstdin" ]; then cat; exit 0; fi
echo "FAKE-GIT $*"
echo "CHAIN=$__WRAPPER_GUARD_RECURSION_GIT"
exit "${FAKE_EXIT:-0}"
"#;

/// Installs `contents` as an executable script at `dest`.
///
/// The script is staged in a sibling file and copied into place by `cp`, so
/// this process never holds a writable fd to `dest`. Writing it in-process
/// races with parallel tests: a sibling test's fork can inherit the open fd
/// before its exec closes it, and exec'ing `dest` then fails with ETXTBSY
/// ("Text file busy").
fn install_script(dest: &Path, contents: &str) {
    let staged = dest.with_extension("src");
    std::fs::write(&staged, contents).unwrap();
    let status = Command::new("cp").arg(&staged).arg(dest).status().unwrap();
    assert!(status.success(), "cp {} failed", dest.display());
    std::fs::set_permissions(dest, std::fs::Permissions::from_mode(0o755)).unwrap();
}

struct Env {
    dir: tempfile::TempDir,
}

impl Env {
    fn new() -> Self {
        let dir = tempfile::tempdir().unwrap();
        let bin = dir.path().join("bin");
        std::fs::create_dir(&bin).unwrap();
        let git = bin.join("git");
        install_script(&git, FAKE_GIT);
        Self { dir }
    }

    fn bin(&self) -> PathBuf {
        self.dir.path().join("bin")
    }

    fn log_dir(&self) -> PathBuf {
        self.dir.path().join("logs")
    }

    fn cmd(&self, args: &[&str]) -> Command {
        let mut cmd = Command::new(env!("CARGO_BIN_EXE_git"));
        cmd.args(args)
            .env_clear()
            .env("PATH", format!("{}:/usr/bin:/bin", self.bin().display()))
            .env("WRAPPER_GUARD_LOG_DIR", self.log_dir())
            .env("HOME", self.dir.path());
        cmd
    }

    fn run(&self, args: &[&str]) -> Output {
        self.cmd(args).output().unwrap()
    }
}

fn stdout(o: &Output) -> String {
    String::from_utf8_lossy(&o.stdout).into_owned()
}

fn stderr(o: &Output) -> String {
    String::from_utf8_lossy(&o.stderr).into_owned()
}

#[test]
fn allowed_command_passes_through_with_exit_code() {
    let env = Env::new();
    let out = env
        .cmd(&["status", "-sb"])
        .env("FAKE_EXIT", "3")
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(3));
    assert!(stdout(&out).contains("FAKE-GIT status -sb"));
}

#[test]
fn chain_variable_is_passed_to_real_git() {
    let env = Env::new();
    let out = env.run(&["status"]);
    let wrapper = Path::new(env!("CARGO_BIN_EXE_git")).canonicalize().unwrap();
    assert!(stdout(&out).contains(&format!("CHAIN={}", wrapper.display())));
}

#[test]
fn nested_invocation_from_hooks_still_works() {
    // Regression: the old guard aborted whenever the variable was set, which
    // broke every git hook that itself runs `git`.
    let env = Env::new();
    let out = env
        .cmd(&["status"])
        .env("__WRAPPER_GUARD_RECURSION_GIT", "/some/other/wrapper/git")
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(0), "stderr: {}", stderr(&out));
    assert!(stdout(&out).contains("FAKE-GIT status"));
}

#[test]
fn stdin_is_passed_through() {
    use std::io::Write;
    let env = Env::new();
    let mut child = env
        .cmd(&["catstdin"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(b"hello from stdin")
        .unwrap();
    let out = child.wait_with_output().unwrap();
    assert_eq!(stdout(&out), "hello from stdin");
}

#[test]
fn blocked_operations_exit_1_with_banner() {
    let env = Env::new();
    for args in [
        &["push", "--force"][..],
        &["-C", "/tmp", "push", "-uf", "origin", "x"],
        &["push", "origin", "+feature"],
        &["push", "origin", "HEAD:main"],
        &["commit", "--no-verif", "-m", "x"],
        &["-c", "core.hooksPath=/dev/null", "commit", "-m", "x"],
    ] {
        let out = env.run(args);
        assert_eq!(out.status.code(), Some(1), "git {}", args.join(" "));
        assert!(stderr(&out).contains("GIT-GUARD: OPERATION BLOCKED"));
        assert!(!stdout(&out).contains("FAKE-GIT"), "real git must not run");
    }
}

#[test]
fn env_injected_hooks_path_is_blocked() {
    let env = Env::new();
    let out = env
        .cmd(&["commit", "-m", "x"])
        .env("GIT_CONFIG_COUNT", "1")
        .env("GIT_CONFIG_KEY_0", "core.hooksPath")
        .env("GIT_CONFIG_VALUE_0", "/dev/null")
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
}

#[test]
fn aliases_are_resolved_through_real_git() {
    let env = Env::new();
    let out = env
        .cmd(&["yolo", "origin", "feature"])
        .env("FAKE_ALIAS_yolo", "push --force")
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    assert!(stderr(&out).contains("--force"));

    let out = env
        .cmd(&["st"])
        .env("FAKE_ALIAS_st", "status -sb")
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(0));
    assert!(stdout(&out).contains("FAKE-GIT st"));
}

#[test]
fn push_head_on_main_is_blocked() {
    let env = Env::new();
    let out = env
        .cmd(&["push", "origin", "HEAD"])
        .env("FAKE_BRANCH", "main")
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    let out = env
        .cmd(&["push", "origin", "HEAD"])
        .env("FAKE_BRANCH", "feature")
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(0), "stderr: {}", stderr(&out));
}

#[test]
fn integrity_flag() {
    let env = Env::new();
    let out = env.run(&["--wrapper-integrity"]);
    assert_eq!(out.status.code(), Some(0));
    let text = stdout(&out);
    assert!(text.contains("wrapper=git-guard"));
    let hash = text
        .lines()
        .find_map(|l| l.strip_prefix("source_hash="))
        .unwrap();
    assert_eq!(hash.len(), 64);
}

#[test]
fn audit_log_records_block_with_redaction() {
    let env = Env::new();
    env.run(&[
        "push",
        "https://user:s3cret@github.com/o/r.git",
        "HEAD:main",
    ]);
    let log = std::fs::read_to_string(env.log_dir().join("audit.log")).unwrap();
    assert!(log.contains("\"action\":\"blocked\""));
    assert!(!log.contains("s3cret"));
}

#[test]
fn missing_real_git_is_an_error() {
    let dir = tempfile::tempdir().unwrap();
    let out = Command::new(env!("CARGO_BIN_EXE_git"))
        .arg("status")
        .env_clear()
        .env("PATH", dir.path())
        .env("WRAPPER_GUARD_LOG_DIR", dir.path())
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    assert!(stderr(&out).contains("not found"));
}

#[test]
fn relative_path_entries_are_ignored() {
    // A repository-planted ./git must never be executed.
    let env = Env::new();
    let out = Command::new(env!("CARGO_BIN_EXE_git"))
        .arg("status")
        .current_dir(env.dir.path())
        .env_clear()
        .env("PATH", "bin")
        .env("WRAPPER_GUARD_LOG_DIR", env.log_dir())
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    assert!(!stdout(&out).contains("FAKE-GIT"));
}
