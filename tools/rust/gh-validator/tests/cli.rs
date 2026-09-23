//! End-to-end tests: run the built `gh` wrapper against a fake real gh.
//!
//! The fake gh echoes its arguments, prints the contents of any
//! `--body-file`/`-F` file it receives, and answers `pr view --json`.
#![cfg(unix)]

use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

const FAKE_GH: &str = r#"#!/bin/sh
if [ "$1 $2" = "pr view" ]; then
  echo '{"number":42,"url":"https://github.com/o/r/pull/42"}'
  exit 0
fi
echo "FAKE-GH $*"
prev=""
for a in "$@"; do
  if [ "$prev" = "--body-file" ] || [ "$prev" = "-F" ]; then
    echo "FILE-PATH:$a"
    echo "FILE-CONTENT:$(cat "$a")"
  fi
  prev="$a"
done
if [ "$1" = "catstdin" ]; then cat; fi
exit "${FAKE_EXIT:-0}"
"#;

const CONFIG: &str = r#"
version: "1.0.0"
environment_variables:
  - MY_SECRET
patterns:
  - name: CUSTOM
    pattern: "custom_[a-z]{8}"
auto_detection:
  enabled: true
  include_patterns: ["*_TOKEN"]
settings:
  log_masked_secrets: false
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
        let gh = bin.join("gh");
        install_script(&gh, FAKE_GH);
        // Workspace with config and a .git marker (stops the upward search).
        let ws = dir.path().join("ws");
        std::fs::create_dir_all(ws.join(".git")).unwrap();
        std::fs::write(ws.join(".secrets.yaml"), CONFIG).unwrap();
        std::fs::create_dir(dir.path().join("ghconfig")).unwrap();
        Self { dir }
    }

    fn ws(&self) -> PathBuf {
        self.dir.path().join("ws")
    }

    fn cmd(&self, args: &[&str]) -> Command {
        let mut cmd = Command::new(env!("CARGO_BIN_EXE_gh"));
        cmd.args(args)
            .current_dir(self.ws())
            .env_clear()
            .env(
                "PATH",
                format!("{}:/usr/bin:/bin", self.dir.path().join("bin").display()),
            )
            .env("HOME", self.dir.path())
            .env("TMPDIR", self.dir.path())
            .env("GH_CONFIG_DIR", self.dir.path().join("ghconfig"))
            .env("WRAPPER_GUARD_LOG_DIR", self.dir.path().join("logs"));
        cmd
    }

    fn run(&self, args: &[&str]) -> Output {
        self.cmd(args).output().unwrap()
    }

    fn write(&self, name: &str, content: &str) -> PathBuf {
        let p = self.ws().join(name);
        std::fs::write(&p, content).unwrap();
        p
    }
}

fn out(o: &Output) -> String {
    String::from_utf8_lossy(&o.stdout).into_owned()
}

fn err(o: &Output) -> String {
    String::from_utf8_lossy(&o.stderr).into_owned()
}

#[test]
fn fast_path_passes_through_with_exit_code() {
    let env = Env::new();
    let o = env
        .cmd(&["pr", "list"])
        .env("FAKE_EXIT", "4")
        .output()
        .unwrap();
    assert_eq!(o.status.code(), Some(4));
    assert!(out(&o).contains("FAKE-GH pr list"));
}

#[test]
fn fast_path_does_not_need_config() {
    let env = Env::new();
    std::fs::remove_file(env.ws().join(".secrets.yaml")).unwrap();
    let o = env.run(&["repo", "view"]);
    assert_eq!(o.status.code(), Some(0), "{}", err(&o));
}

#[test]
fn blocked_entries_in_audit_log_are_masked() {
    let env = Env::new();
    let o = env
        .cmd(&[
            "pr",
            "comment",
            "1",
            "--body",
            "pw hunter2-secret \u{1F600}",
        ])
        .env("MY_SECRET", "hunter2-secret")
        .output()
        .unwrap();
    assert_eq!(o.status.code(), Some(1));
    let log = std::fs::read_to_string(env.dir.path().join("logs/audit.log")).unwrap();
    assert!(log.contains("\"action\":\"blocked\""));
    assert!(!log.contains("hunter2"));
}

#[test]
fn stdin_passes_through_on_fast_path() {
    use std::io::Write;
    let env = Env::new();
    let mut child = env
        .cmd(&["catstdin"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.take().unwrap().write_all(b"piped").unwrap();
    let o = child.wait_with_output().unwrap();
    assert!(out(&o).contains("piped"));
}

#[test]
fn inline_body_is_masked_and_mentions_neutralized() {
    let env = Env::new();
    let o = env
        .cmd(&[
            "pr",
            "comment",
            "1",
            "--body",
            "cc @octocat key=hunter2-secret",
        ])
        .env("MY_SECRET", "hunter2-secret")
        .output()
        .unwrap();
    assert_eq!(o.status.code(), Some(0), "{}", err(&o));
    assert!(out(&o).contains("cc `@octocat` key=[MASKED_MY_SECRET]"));
    assert!(!out(&o).contains("hunter2"));
}

#[test]
fn body_file_is_sanitized_via_private_copy() {
    let env = Env::new();
    let body = env.write("body.md", "token custom_abcdefgh\nthanks @hubot\n");
    let o = env.run(&["pr", "comment", "1", "--body-file", body.to_str().unwrap()]);
    assert_eq!(o.status.code(), Some(0), "{}", err(&o));
    let stdout = out(&o);
    assert!(stdout.contains("FILE-CONTENT:token [MASKED_CUSTOM]"));
    assert!(stdout.contains("thanks `@hubot`"));
    // Original untouched, temp copy removed after gh exits.
    assert_eq!(
        std::fs::read_to_string(&body).unwrap(),
        "token custom_abcdefgh\nthanks @hubot\n"
    );
    let temp = stdout
        .lines()
        .find_map(|l| l.strip_prefix("FILE-PATH:"))
        .unwrap();
    assert_ne!(Path::new(temp), body);
    assert!(!Path::new(temp).exists());
}

#[test]
fn emoji_blocked_in_args_and_files() {
    let env = Env::new();
    let o = env.run(&["issue", "create", "-t", "Launch \u{1F680}", "-b", "x"]);
    assert_eq!(o.status.code(), Some(1));
    assert!(err(&o).contains("emoji"));
    assert!(!out(&o).contains("FAKE-GH"));

    let body = env.write("b.md", "done \u{2705}");
    let o = env.run(&["pr", "comment", "1", "-F", body.to_str().unwrap()]);
    assert_eq!(o.status.code(), Some(1));
}

#[test]
fn api_bypasses_are_closed() {
    let env = Env::new();
    let o = env.run(&[
        "api",
        "repos/o/r/issues/1/comments",
        "-f",
        "body=hi \u{1F600}",
    ]);
    assert_eq!(o.status.code(), Some(1));

    let o = env
        .cmd(&[
            "api",
            "repos/o/r/issues/1/comments",
            "-f",
            "body=pw hunter2-secret",
        ])
        .env("MY_SECRET", "hunter2-secret")
        .output()
        .unwrap();
    assert_eq!(o.status.code(), Some(0), "{}", err(&o));
    assert!(out(&o).contains("body=pw [MASKED_MY_SECRET]"));

    let o = env.run(&["api", "graphql", "--input", "-"]);
    assert_eq!(o.status.code(), Some(1));
    assert!(err(&o).contains("stdin"));
}

#[test]
fn aliases_are_expanded_and_validated() {
    let env = Env::new();
    std::fs::write(
        env.dir.path().join("ghconfig/config.yml"),
        "aliases:\n  c: pr comment 1 --body \"$1\"\n  pl: pr list\n",
    )
    .unwrap();
    let o = env.run(&["c", "hi \u{1F600}"]);
    assert_eq!(o.status.code(), Some(1), "{}", out(&o));

    let o = env.run(&["c", "ping @octocat"]);
    assert_eq!(o.status.code(), Some(0), "{}", err(&o));
    assert!(out(&o).contains("FAKE-GH pr comment 1 --body ping `@octocat`"));

    let o = env.run(&["pl"]);
    assert!(out(&o).contains("FAKE-GH pr list"));
}

#[test]
fn blocked_commands() {
    let env = Env::new();
    for args in [
        &["alias", "set", "c", "pr comment"][..],
        &["extension", "install", "o/gh-x"],
        &["pr", "comment", "1", "--editor"],
        &["pr", "comment", "1", "--body-file", "-"],
        &["pr", "comment", "1", "--body-file", "does-not-exist.md"],
        &[
            "pr",
            "comment",
            "1",
            "--body",
            "![Reaction](https://x/reaction/a.png)",
        ],
    ] {
        let o = env.run(args);
        assert_eq!(o.status.code(), Some(1), "gh {}", args.join(" "));
        assert!(!out(&o).contains("FAKE-GH"), "gh {}", args.join(" "));
    }
}

#[test]
fn strip_flag_is_consumed() {
    let env = Env::new();
    let body = env.write("b.md", "text\n");
    let o = env.run(&[
        "pr",
        "comment",
        "1",
        "--gh-validator-strip-invalid-images",
        "--body-file",
        body.to_str().unwrap(),
    ]);
    assert_eq!(o.status.code(), Some(0), "{}", err(&o));
    assert!(!out(&o).contains("strip-invalid-images"));
}

#[test]
fn pr_create_prints_monitoring_notice() {
    let env = Env::new();
    let o = env.run(&["pr", "create", "--title", "t", "--body", "b"]);
    assert_eq!(o.status.code(), Some(0), "{}", err(&o));
    assert!(err(&o).contains("PR FEEDBACK MONITORING"));
    assert!(err(&o).contains("pr-monitor 42"));

    // Failure exit codes are forwarded and no notice is printed.
    let o = env
        .cmd(&["pr", "create", "--title", "t", "--body", "b"])
        .env("FAKE_EXIT", "2")
        .output()
        .unwrap();
    assert_eq!(o.status.code(), Some(2));
    assert!(!err(&o).contains("PR FEEDBACK MONITORING"));
}

#[test]
fn integrity_flag() {
    let env = Env::new();
    let o = env.run(&["--wrapper-integrity"]);
    assert_eq!(o.status.code(), Some(0));
    assert!(out(&o).contains("wrapper=gh-validator"));
    assert!(out(&o).contains("source_hash="));
}

#[test]
fn audit_log_masks_secrets() {
    let env = Env::new();
    env.cmd(&["pr", "comment", "1", "--body", "pw hunter2-secret"])
        .env("MY_SECRET", "hunter2-secret")
        .output()
        .unwrap();
    let log = std::fs::read_to_string(env.dir.path().join("logs/audit.log")).unwrap();
    assert!(log.contains("[MASKED_MY_SECRET]"));
    assert!(!log.contains("hunter2"));
}
