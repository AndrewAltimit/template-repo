//! GitHub utility functions.
//!
//! Provides async wrappers around the GitHub CLI (`gh`) and git commands.

use std::io::Write;
use std::process::Stdio;
use std::time::Duration;

use serde::de::DeserializeOwned;
use tokio::process::Command;
use tracing::{debug, error, warn};

use crate::error::Error;

/// Upper bound for a single `gh`/`git` invocation. These are network-bound
/// API calls; anything slower than this is hung, not busy.
const COMMAND_TIMEOUT: Duration = Duration::from_secs(300);

/// Raw result of a captured command.
struct Captured {
    stdout: String,
    stderr: String,
    code: i32,
    success: bool,
}

/// Run `program args...`, capturing output, with a hard timeout.
async fn run_captured(
    program: &str,
    args: &[&str],
    not_found: fn() -> Error,
) -> Result<Captured, Error> {
    debug!("Running: {} {}", program, args.join(" "));

    let mut cmd = Command::new(program);
    cmd.args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);

    let output = tokio::time::timeout(COMMAND_TIMEOUT, cmd.output())
        .await
        .map_err(|_| {
            Error::MonitorFailed(format!(
                "{} {} timed out after {}s",
                program,
                args.first().unwrap_or(&""),
                COMMAND_TIMEOUT.as_secs()
            ))
        })?
        .map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                not_found()
            } else {
                Error::Io(e)
            }
        })?;

    Ok(Captured {
        stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
        code: output.status.code().unwrap_or(-1),
        success: output.status.success(),
    })
}

/// Short description of a command for logs (never includes bodies).
fn describe(program: &str, args: &[&str]) -> String {
    let shown: Vec<&str> = args.iter().take(4).copied().collect();
    format!("{} {}", program, shown.join(" "))
}

/// Run a GitHub CLI command asynchronously.
///
/// # Arguments
///
/// * `args` - Command arguments (without the `gh` prefix)
/// * `check` - Whether to return an error on non-zero exit code
///
/// # Returns
///
/// Command stdout on success, or None if check is false and command failed.
pub async fn run_gh_command(args: &[&str], check: bool) -> Result<Option<String>, Error> {
    let out = run_captured("gh", args, || Error::GhNotFound).await?;

    if out.success {
        if out.stdout.trim().is_empty() && !out.stderr.trim().is_empty() {
            debug!("gh stderr (stdout empty): {}", out.stderr.trim());
        }
        return Ok(Some(out.stdout));
    }

    let level_msg = format!(
        "GitHub CLI command failed (exit code {}): {}",
        out.code,
        describe("gh", args)
    );
    if check {
        error!("{}", level_msg);
    } else {
        warn!("{}", level_msg);
    }
    if !out.stderr.trim().is_empty() {
        warn!("stderr: {}", out.stderr.trim());
    }

    if check {
        Err(Error::GhCommandFailed {
            exit_code: out.code,
            stdout: out.stdout,
            stderr: out.stderr,
        })
    } else {
        Ok(None)
    }
}

/// Run a GitHub CLI command and capture both stdout and stderr.
///
/// # Returns
///
/// Tuple of (stdout, stderr, return_code); empty streams are `None`.
pub async fn run_gh_command_with_stderr(
    args: &[&str],
) -> Result<(Option<String>, Option<String>, i32), Error> {
    let out = run_captured("gh", args, || Error::GhNotFound).await?;
    let non_empty = |s: String| {
        let t = s.trim();
        (!t.is_empty()).then(|| t.to_string())
    };
    Ok((non_empty(out.stdout), non_empty(out.stderr), out.code))
}

/// Post a comment on an issue or PR using `--body-file`.
///
/// Writing the body to a private temp file avoids argv size limits and shell
/// escaping problems (e.g. markdown images through gh-validator).
///
/// `kind` is `"issue"` or `"pr"`.
pub async fn post_comment(kind: &str, number: u64, repo: &str, body: &str) -> Result<(), Error> {
    let mut file = tempfile::Builder::new()
        .prefix("github-agents-comment-")
        .suffix(".md")
        .tempfile()?;
    file.write_all(body.as_bytes())?;
    file.flush()?;
    let path = file.path().to_string_lossy().into_owned();

    run_gh_command(
        &[
            kind,
            "comment",
            &number.to_string(),
            "--repo",
            repo,
            "--body-file",
            &path,
        ],
        true,
    )
    .await?;
    Ok(())
}

/// Login of the account `gh` is authenticated as, if it can be determined.
///
/// GitHub Actions installation tokens cannot call `/user`; `None` is returned
/// in that case (the caller then relies on bot-account detection).
pub async fn authenticated_login() -> Option<String> {
    match run_gh_command(&["api", "user", "--jq", ".login"], false).await {
        Ok(Some(login)) => {
            let login = login.trim().to_string();
            (!login.is_empty()).then_some(login)
        },
        _ => None,
    }
}

/// Parse the output of `gh api --paginate`, which concatenates one JSON
/// array per page (`[...][...]`), into a single vector.
///
/// Uses a streaming JSON parser, so brackets inside string values cannot
/// confuse page splitting.
pub fn parse_paginated_array<T: DeserializeOwned>(json: &str) -> Result<Vec<T>, Error> {
    let mut all = Vec::new();
    for page in serde_json::Deserializer::from_str(json).into_iter::<Vec<T>>() {
        all.extend(page?);
    }
    Ok(all)
}

/// Check if the GitHub CLI is available and authenticated.
/// (Checks by running command directly, avoiding `which` for Docker compatibility)
pub async fn check_gh_available() -> Result<(), Error> {
    let version = run_captured("gh", &["--version"], || Error::GhNotFound).await?;
    if !version.success {
        return Err(Error::GhNotFound);
    }

    let auth = run_captured("gh", &["auth", "status"], || Error::GhNotFound).await?;
    if !auth.success {
        return Err(Error::GhNotAuthenticated);
    }

    debug!("GitHub CLI available and authenticated");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;

    #[derive(Debug, Deserialize, PartialEq)]
    struct Item {
        body: String,
    }

    #[test]
    fn paginated_single_page() {
        let items: Vec<Item> = parse_paginated_array(r#"[{"body":"a"},{"body":"b"}]"#).unwrap();
        assert_eq!(items.len(), 2);
    }

    #[test]
    fn paginated_multiple_pages_with_brackets_in_strings() {
        // Unbalanced brackets inside string values must not break parsing
        let json = r#"[{"body":"see item 1] and ["}][{"body":"[CONTINUE]"}]
[{"body":"third ]]]"}]"#;
        let items: Vec<Item> = parse_paginated_array(json).unwrap();
        assert_eq!(
            items,
            vec![
                Item {
                    body: "see item 1] and [".into()
                },
                Item {
                    body: "[CONTINUE]".into()
                },
                Item {
                    body: "third ]]]".into()
                },
            ]
        );
    }

    #[test]
    fn paginated_empty_and_invalid() {
        let items: Vec<Item> = parse_paginated_array("").unwrap();
        assert!(items.is_empty());
        let items: Vec<Item> = parse_paginated_array("[]").unwrap();
        assert!(items.is_empty());
        assert!(parse_paginated_array::<Item>("[{\"body\":").is_err());
    }

    #[test]
    fn describe_omits_bodies() {
        let d = describe("gh", &["issue", "comment", "1", "--body", "secret body"]);
        assert!(!d.contains("secret body"));
    }
}
