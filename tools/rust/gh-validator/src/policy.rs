//! Operations gh-validator refuses outright (before any content checks).
//!
//! | Blocked | Why |
//! |---------|-----|
//! | `gh alias set`, `gh alias import` | aliases can hide content-posting commands from the wrapper |
//! | `gh extension install/upgrade` (`extensions`, `ext`) | extensions run arbitrary unvalidated code as `gh <name>` |
//! | `--editor` / `-e` on `pr`/`issue` `create`/`comment` | content typed in an editor (or produced by `$GH_EDITOR`) is never seen by the wrapper |
//! | content from stdin: `--body-file -`, `-F -`, `--notes-file -`, `api -F k=@-`, `api --input -`, `gist create -` or no files | stdin cannot be validated |
//! | in hardened (setgid) mode: shell aliases and unknown top-level commands (extensions) | they would run with the `wrapper-guard` group and could reach the real binaries |

use crate::args::{Parsed, SlotKind};
use crate::error::{Error, Result};

const ALIAS_HELP: &str =
    "gh aliases can hide commands from gh-validator. Run the full command instead.";
const EXTENSION_HELP: &str =
    "gh extensions run unvalidated code. Ask a human to install extensions.";
const EDITOR_HELP: &str = "Write the content to a file and pass it with --body-file instead.";

fn blocked(reason: impl Into<String>, help: &'static str) -> Error {
    Error::Blocked {
        reason: reason.into(),
        help: Some(help),
    }
}

/// Reject invocations that can never be validated.
pub fn check(parsed: &Parsed, args: &[String]) -> Result<()> {
    let command = parsed.command();
    let sub = parsed.subcommand();

    match (command, sub) {
        (Some("alias"), Some(s @ ("set" | "import"))) => {
            return Err(blocked(format!("gh alias {s}"), ALIAS_HELP));
        },
        (Some("extension" | "extensions" | "ext"), Some(s @ ("install" | "upgrade"))) => {
            return Err(blocked(format!("gh extension {s}"), EXTENSION_HELP));
        },
        (Some("pr" | "issue"), Some("create" | "comment")) if parsed.editor => {
            return Err(blocked(
                "--editor: content written in an editor bypasses validation",
                EDITOR_HELP,
            ));
        },
        _ => {},
    }

    for slot in &parsed.slots {
        if slot.kind.is_file() && slot.value(args) == "-" {
            let flag = match slot.kind {
                SlotKind::ApiFieldFile => {
                    format!("{} {}=@", slot.flag, slot.field.as_deref().unwrap_or(""))
                },
                _ => slot.flag.clone(),
            };
            return Err(Error::StdinBlocked { flag });
        }
    }

    if is_gist_create(parsed) {
        let files: Vec<&str> = parsed.operands().map(|(_, s)| s.as_str()).collect();
        if files.is_empty() || files.contains(&"-") {
            return Err(Error::StdinBlocked {
                flag: "gh gist create".to_string(),
            });
        }
    }
    Ok(())
}

/// `gh gist create <files>`.
pub fn is_gist_create(parsed: &Parsed) -> bool {
    matches!(parsed.command(), Some("gist" | "gists")) && parsed.subcommand() == Some("create")
}

/// Error for commands that cannot be allowed in hardened (setgid) mode.
pub fn setgid_block(what: String) -> Error {
    Error::Blocked {
        reason: format!("{what} in hardened mode"),
        help: Some(
            "Shell aliases and extensions would run with the wrapper-guard group\n\
             and could invoke the real binaries directly.",
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::args::parse;

    fn check_args(s: &[&str]) -> Result<()> {
        let args: Vec<String> = s.iter().map(|x| x.to_string()).collect();
        check(&parse(&args), &args)
    }

    #[test]
    fn alias_and_extension_management_blocked() {
        assert!(check_args(&["alias", "set", "c", "pr comment"]).is_err());
        assert!(check_args(&["alias", "import", "a.yml"]).is_err());
        assert!(check_args(&["extension", "install", "o/gh-x"]).is_err());
        assert!(check_args(&["ext", "upgrade", "--all"]).is_err());
        assert!(check_args(&["alias", "list"]).is_ok());
        assert!(check_args(&["extension", "list"]).is_ok());
    }

    #[test]
    fn editor_blocked_for_content_commands() {
        assert!(check_args(&["pr", "comment", "1", "--editor"]).is_err());
        assert!(check_args(&["issue", "create", "-e"]).is_err());
        assert!(check_args(&["pr", "create", "-we"]).is_err());
        // -e means --env elsewhere.
        assert!(check_args(&["secret", "set", "X", "-e", "prod"]).is_ok());
    }

    #[test]
    fn stdin_blocked_everywhere() {
        for args in [
            &["pr", "comment", "1", "--body-file", "-"][..],
            &["pr", "comment", "1", "-F", "-"],
            &["pr", "comment", "1", "-F-"],
            &["pr", "comment", "1", "--body-file=-"],
            &["release", "create", "v1", "--notes-file", "-"],
            &["release", "create", "v1", "-F", "-"],
            &["api", "repos/o/r/issues/1/comments", "-F", "body=@-"],
            &["api", "graphql", "--input", "-"],
            &["gist", "create"],
            &["gist", "create", "-"],
        ] {
            assert!(
                matches!(check_args(args), Err(Error::StdinBlocked { .. })),
                "{args:?}"
            );
        }
    }

    #[test]
    fn ordinary_commands_pass() {
        assert!(check_args(&["pr", "list"]).is_ok());
        assert!(check_args(&["pr", "comment", "1", "--body-file", "b.md"]).is_ok());
        assert!(check_args(&["gist", "create", "a.txt"]).is_ok());
        assert!(check_args(&["api", "user"]).is_ok());
    }
}
