//! End-to-end tests of the `github-agents` binary for commands that do not
//! need network access.

use assert_cmd::Command;
use assert_cmd::cargo::cargo_bin_cmd;
use predicates::prelude::*;

fn cli() -> Command {
    let mut cmd = cargo_bin_cmd!("github-agents");
    // Keep tests hermetic: no config file, no inherited allow-list overrides
    cmd.env_remove("AI_AGENT_ALLOWED_USERS")
        .env_remove("AI_AGENT_DEFAULT_ADMIN")
        .env_remove("GITHUB_REPOSITORY")
        .env_remove("GITHUB_BASE_REF")
        .env_remove("GITHUB_EVENT_PATH");
    cmd
}

#[test]
fn help_lists_all_subcommands() {
    cli().arg("--help").assert().success().stdout(
        predicate::str::contains("issue-monitor")
            .and(predicate::str::contains("pr-monitor"))
            .and(predicate::str::contains("refinement-monitor"))
            .and(predicate::str::contains("pr-review"))
            .and(predicate::str::contains("iteration-check"))
            .and(predicate::str::contains("analyze"))
            .and(predicate::str::contains("security")),
    );
}

#[test]
fn parse_trigger_json() {
    cli()
        .args([
            "security",
            "--config",
            "does-not-exist.yaml",
            "--format",
            "json",
            "parse-trigger",
            "--comment",
            "LGTM [Approved][Claude]",
        ])
        .assert()
        .success()
        .stdout(
            predicate::str::contains(r#""action": "approved""#)
                .and(predicate::str::contains(r#""agent": "claude""#)),
        );
}

#[test]
fn parse_trigger_ignores_quoted_text() {
    cli()
        .args([
            "security",
            "parse-trigger",
            "--comment",
            "> [Approved][Claude]",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("No trigger found"));
}

#[test]
fn check_user_denied_exits_8() {
    cli()
        .args([
            "security",
            "--config",
            "does-not-exist.yaml",
            "check-user",
            "--username",
            "definitely-not-an-admin",
        ])
        .assert()
        .code(8)
        .stdout(predicate::str::contains("NOT allowed"));
}

#[test]
fn check_user_bot_denied() {
    cli()
        .args([
            "security",
            "--config",
            "does-not-exist.yaml",
            "check-user",
            "--username",
            "github-actions[bot]",
        ])
        .assert()
        .code(8);
}

#[test]
fn check_action_allowed() {
    cli()
        .args([
            "security",
            "--config",
            "does-not-exist.yaml",
            "check-action",
            "--action",
            "issue_approved",
        ])
        .assert()
        .success();
}

#[test]
fn validate_pr_commit_rejects_malformed_sha() {
    cli()
        .args([
            "security",
            "validate-pr-commit",
            "--pr",
            "1",
            "--expected-sha",
            "zzzzzzz",
        ])
        .assert()
        .code(1)
        .stderr(predicate::str::contains("expected-sha"));
}

#[test]
fn monitors_require_repository() {
    cli()
        .arg("issue-monitor")
        .assert()
        .failure()
        .stderr(predicate::str::contains("GITHUB_REPOSITORY"));
}

#[test]
fn invalid_format_rejected() {
    cli()
        .args([
            "security",
            "--format",
            "yaml",
            "parse-trigger",
            "--comment",
            "x",
        ])
        .assert()
        .failure();
}
