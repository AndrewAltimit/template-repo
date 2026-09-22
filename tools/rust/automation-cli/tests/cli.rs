//! End-to-end tests of the CLI surface that do not need Docker.

use assert_cmd::Command;
use assert_cmd::cargo::cargo_bin_cmd;
use predicates::prelude::*;

fn cli() -> Command {
    cargo_bin_cmd!("automation-cli")
}

#[test]
fn help_for_every_subcommand() {
    for sub in [
        vec!["ci"],
        vec!["ci", "run"],
        vec!["ci", "list"],
        vec!["ci", "doctor"],
        vec!["lint"],
        vec!["review", "respond"],
        vec!["review", "failure"],
        vec!["review", "precommit"],
        vec!["wait"],
        vec!["launch"],
        vec!["service"],
        vec!["setup"],
        vec!["proxy"],
    ] {
        let mut args = sub.clone();
        args.push("--help");
        cli().args(&args).assert().success();
    }
}

#[test]
fn ci_list_names_is_machine_readable() {
    let out = cli().args(["ci", "list", "--names"]).output().unwrap();
    assert!(out.status.success());
    let stdout = String::from_utf8(out.stdout).unwrap();
    let names: Vec<&str> = stdout.lines().collect();
    for expected in [
        "format",
        "econ-full",
        "rust-all",
        "rust-full",
        "tools-clippy",
    ] {
        assert!(names.contains(&expected), "missing {expected}");
    }
    assert!(names.iter().all(|n| !n.contains(' ')));
    // No duplicates even though `full` appears in two groups.
    let mut sorted = names.clone();
    sorted.sort_unstable();
    sorted.dedup();
    assert_eq!(sorted.len(), names.len());
}

#[test]
fn ci_list_human_output() {
    cli()
        .args(["ci", "list"])
        .assert()
        .success()
        .stdout(predicate::str::contains("Available CI stages:"))
        .stdout(predicate::str::contains("Composite:"));
}

#[test]
fn unknown_stage_fails_fast_with_hint() {
    // Must fail before touching docker or looking for the project root.
    let dir = tempfile::tempdir().unwrap();
    cli()
        .current_dir(dir.path())
        .args(["ci", "run", "lint-ful"])
        .assert()
        .failure()
        .stderr(predicate::str::contains("unknown stage: lint-ful"))
        .stderr(predicate::str::contains("Did you mean `lint-full`?"));
}

#[test]
fn outside_project_root_is_a_clear_error() {
    let dir = tempfile::tempdir().unwrap();
    cli()
        .current_dir(dir.path())
        .args(["setup", "agents"])
        .assert()
        .failure()
        .stderr(predicate::str::contains("could not find project root"));
}

#[test]
fn wait_times_out_on_closed_port() {
    cli()
        .args(["wait", "--port", "1", "--timeout", "0", "--quiet"])
        .assert()
        .code(1)
        .stderr(predicate::str::contains("timeout after 0s"));
}

#[test]
fn wait_succeeds_on_open_port_with_host_port_syntax() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    cli()
        .args(["wait", &format!("127.0.0.1:{port}"), "--timeout", "5"])
        .assert()
        .success();
}

#[test]
fn wait_requires_a_port() {
    cli().args(["wait"]).assert().code(2);
}

#[test]
fn invalid_enum_values_are_rejected_by_clap() {
    cli().args(["lint", "bogus"]).assert().code(2);
    cli().args(["launch", "bogus"]).assert().code(2);
    cli().args(["proxy", "test", "bogus"]).assert().code(2);
    cli()
        .args(["service", "start", "--mode", "bogus"])
        .assert()
        .code(2);
}

fn fake_repo() -> tempfile::TempDir {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    std::fs::write(root.join("CLAUDE.md"), "# test\n").unwrap();
    std::fs::write(
        root.join("docker-compose.yml"),
        "services:\n  python-ci:\n    image: x\n  rust-ci:\n    image: y\n",
    )
    .unwrap();
    dir
}

#[test]
fn doctor_flags_unknown_stage_references() {
    let dir = fake_repo();
    std::fs::create_dir_all(dir.path().join(".github/workflows")).unwrap();
    std::fs::write(
        dir.path().join(".github/workflows/ci.yml"),
        "steps:\n  - run: ./automation/ci-cd/run-ci.sh econ-fmtt\n  - run: automation-cli lint basic\n",
    )
    .unwrap();
    cli()
        .current_dir(dir.path())
        .args(["ci", "doctor"])
        .assert()
        .failure()
        .stderr(predicate::str::contains(
            ".github/workflows/ci.yml:2: unknown CI stage `econ-fmtt`",
        ))
        .stderr(predicate::str::contains("did you mean `econ-fmt`?"));
}

#[test]
fn doctor_reports_missing_ci_service() {
    let dir = fake_repo();
    std::fs::write(
        dir.path().join("docker-compose.yml"),
        "services:\n  python-ci:\n    image: x\n",
    )
    .unwrap();
    cli()
        .current_dir(dir.path())
        .args(["ci", "doctor"])
        .assert()
        .failure()
        .stderr(predicate::str::contains("service `rust-ci` missing"));
}
