//! gh-validator: a `gh` wrapper that validates content posted by AI agents.
//!
//! Install this binary as `gh` ahead of the real GitHub CLI on PATH (or as
//! the setgid `/usr/bin/gh` in hardened mode).
//!
//! Commands that carry no user content (`gh pr list`, `gh api user`) are
//! executed immediately. Commands that post content - `--body`, `--title`,
//! `--notes`, `--body-file`, `--notes-file`, `pr create --template`,
//! `gh api -f/-F/--input`, `gh gist create` - are validated first:
//! secrets masked, emoji rejected, @mentions neutralized, reaction images
//! verified, and content files replaced by sanitized private copies. See
//! `policy.rs` for commands that are refused outright.
//!
//! `--gh-validator-strip-invalid-images` (consumed, not passed to gh): drop
//! invalid reaction images instead of failing. Used by CI review bots.

use std::ffi::OsString;
use std::process::{Command, exit};

use gh_validator::aliases::{self, Resolution};
use gh_validator::args::{self, Parsed};
use gh_validator::sanitize::{self, Outcome, Validators};
use gh_validator::{Error, SecretMasker, UrlValidator, load_config, policy};
use wrapper_common::audit::Auditor;
use wrapper_common::binary_finder::{self, RealBinary};

include!(concat!(env!("OUT_DIR"), "/integrity.rs"));

const WRAPPER_NAME: &str = "gh-validator";
const STRIP_INVALID_IMAGES_FLAG: &str = "--gh-validator-strip-invalid-images";

fn main() {
    exit(run());
}

fn run() -> i32 {
    let raw: Vec<OsString> = std::env::args_os().skip(1).collect();
    let lossy: Vec<String> = raw
        .iter()
        .map(|a| a.to_string_lossy().into_owned())
        .collect();

    if wrapper_common::integrity::check_integrity_flag(&lossy, WRAPPER_NAME, SOURCE_HASH) {
        return 0;
    }

    let strip_invalid_images = raw.iter().any(|a| a == STRIP_INVALID_IMAGES_FLAG);
    let os_args: Vec<OsString> = raw
        .into_iter()
        .filter(|a| a != STRIP_INVALID_IMAGES_FLAG)
        .collect();
    let args: Vec<String> = lossy
        .into_iter()
        .filter(|a| a != STRIP_INVALID_IMAGES_FLAG)
        .collect();

    let real = match binary_finder::find_real_binary("gh") {
        Ok(real) => real,
        Err(e) => return report(&Error::from(e)),
    };
    let auditor = Auditor::new(WRAPPER_NAME, real.path(), SOURCE_HASH);

    match plan(&args, &os_args, strip_invalid_images) {
        Ok(Plan::Exec { args: None }) => {
            auditor.allowed(&args);
            execute(&real, &os_args, &auditor, &args)
        },
        Ok(Plan::Exec { args: Some(new) }) => {
            auditor.allowed(&new);
            execute(&real, &new, &auditor, &new)
        },
        Ok(Plan::Run {
            args: new,
            temp_files,
            notices,
            pr_create,
        }) => {
            for notice in &notices {
                eprintln!("[gh-validator] {notice}");
            }
            auditor.allowed(&new);
            let code = match wrapper_common::exec::run(&real, &new) {
                Ok(code) => code,
                Err(e) => {
                    auditor.error(&new, &e.to_string());
                    return report(&Error::from(e));
                },
            };
            drop(temp_files);
            if pr_create && code == 0 {
                notify_pr_monitoring(&real, &new);
            }
            code
        },
        Ok(Plan::Skip { notice }) => {
            eprintln!("[gh-validator] WARNING: {notice}");
            auditor.blocked(&masked_for_log(&args), &notice);
            0
        },
        Err(e) => {
            auditor.blocked(&masked_for_log(&args), &e.to_string());
            report(&e)
        },
    }
}

/// What to do with an invocation.
enum Plan {
    /// Exec gh directly: with the original arguments (`None`) or with
    /// alias-expanded ones.
    Exec { args: Option<Vec<String>> },
    /// Spawn gh with sanitized arguments, then clean up / notify.
    Run {
        args: Vec<String>,
        temp_files: sanitize::TempFiles,
        notices: Vec<String>,
        pr_create: bool,
    },
    /// Do not run gh at all (nothing left to post).
    Skip { notice: String },
}

fn plan(args: &[String], os_args: &[OsString], strip_images: bool) -> Result<Plan, Error> {
    let mut parsed = args::parse(args);
    let mut effective: Option<Vec<String>> = None;

    if let Some((cmd_index, cmd)) = parsed.positionals.first().cloned()
        && !aliases::is_builtin(&cmd)
    {
        let setgid = wrapper_common::platform::is_setgid_elevated();
        match aliases::resolve(args, cmd_index) {
            Resolution::Expanded(expanded) => {
                parsed = args::parse(&expanded);
                effective = Some(expanded);
            },
            Resolution::Shell(_) if setgid => {
                return Err(policy::setgid_block(format!("shell alias '{cmd}'")));
            },
            Resolution::Unknown if setgid => {
                return Err(policy::setgid_block(format!("unknown command '{cmd}'")));
            },
            // Non-hardened: shell aliases re-enter this wrapper for inner
            // `gh` calls; unknown commands are extensions or typos.
            Resolution::Shell(_) | Resolution::Unknown => {},
        }
    }
    let current = effective.as_deref().unwrap_or(args);
    policy::check(&parsed, current)?;

    let pr_create = is_pr_create(&parsed);
    let needs_content = !parsed.slots.is_empty() || policy::is_gist_create(&parsed);

    if !needs_content && !pr_create {
        return Ok(Plan::Exec { args: effective });
    }
    if !needs_content {
        // `gh pr create --fill` etc.: nothing to sanitize, but run as a
        // child so the monitoring notice can be printed afterwards.
        return Ok(Plan::Run {
            args: current.to_vec(),
            temp_files: sanitize::TempFiles::default(),
            notices: Vec::new(),
            pr_create,
        });
    }

    if os_args.iter().any(|a| a.to_str().is_none()) {
        return Err(Error::Blocked {
            reason: "non-UTF-8 arguments cannot be validated".to_string(),
            help: None,
        });
    }

    let config = load_config()?;
    let masker = SecretMasker::new(&config);
    let urls = UrlValidator::default();
    let validators = Validators::new(&config, &masker, &urls, strip_images);
    match sanitize::sanitize(current, &validators)? {
        Outcome::Run {
            args,
            temp_files,
            notices,
        } => Ok(Plan::Run {
            args,
            temp_files,
            notices,
            pr_create,
        }),
        Outcome::Skip { notice } => Ok(Plan::Skip { notice }),
    }
}

/// Arguments with secrets masked, for audit entries of refused commands
/// (the configured masker when available, otherwise the built-in baseline).
fn masked_for_log(args: &[String]) -> Vec<String> {
    let mut config = load_config().unwrap_or_default();
    config.settings.log_masked_secrets = false;
    SecretMasker::new(&config).mask_args(args).0
}

fn is_pr_create(parsed: &Parsed) -> bool {
    parsed.command() == Some("pr") && parsed.subcommand() == Some("create")
}

fn execute<S: AsRef<std::ffi::OsStr>>(
    real: &RealBinary,
    exec_args: &[S],
    auditor: &Auditor,
    log_args: &[String],
) -> i32 {
    let err = wrapper_common::exec::exec(real, exec_args);
    auditor.error(log_args, &err.to_string());
    report(&Error::from(err))
}

fn report(e: &Error) -> i32 {
    eprintln!("ERROR: {e}");
    if let Some(help) = e.help_text() {
        eprintln!("\n{help}");
    }
    1
}

/// After a successful `gh pr create`, tell the agent how to monitor it.
fn notify_pr_monitoring(real: &RealBinary, args: &[String]) {
    let mut view = vec![
        "pr".to_string(),
        "view".to_string(),
        "--json".to_string(),
        "number,url".to_string(),
    ];
    if let Some(repo) = extract_repo_flag(args) {
        view.push(format!("--repo={repo}"));
    }
    let Some((number, url)) = real
        .command()
        .args(&view)
        .stdin(std::process::Stdio::null())
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| parse_pr_view_json(&String::from_utf8_lossy(&o.stdout)))
    else {
        return;
    };

    // One git call for both values: HEAD sha, then branch name.
    let git = Command::new("git")
        .args(["rev-parse", "HEAD", "--abbrev-ref", "HEAD"])
        .stdin(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).into_owned())
        .unwrap_or_default();
    let mut lines = git.lines();
    let sha = lines.next().unwrap_or("HEAD");
    let branch = lines.next().unwrap_or("unknown");

    let rule = "============================================================";
    eprintln!(
        "\n{rule}\nPR FEEDBACK MONITORING\n{rule}\n\n\
         PR #{number} created on branch '{branch}'\n{url}\n\n\
         To monitor for admin and AI agent review feedback:\n\n  \
         pr-monitor {number} --since-commit {sha}\n\n\
         This will watch for:\n  \
         - Admin comments and approval commands\n  \
         - AI agent code review feedback\n  \
         - CI/CD validation results\n\n{rule}"
    );
}

/// `--repo` / `-R` value, if present.
fn extract_repo_flag(args: &[String]) -> Option<String> {
    let mut iter = args.iter();
    while let Some(arg) = iter.next() {
        if arg == "--" {
            break;
        }
        if arg == "-R" || arg == "--repo" {
            return iter.next().cloned();
        }
        if let Some(repo) = arg.strip_prefix("--repo=") {
            return Some(repo.to_string());
        }
        if let Some(repo) = arg.strip_prefix("-R").filter(|r| !r.is_empty()) {
            return Some(repo.trim_start_matches('=').to_string());
        }
    }
    None
}

/// Parse `{"number":N,"url":"..."}` from `gh pr view --json number,url`.
///
/// Hand-rolled to avoid a JSON dependency for one fixed-shape payload;
/// tolerates whitespace and either field order.
fn parse_pr_view_json(json: &str) -> Option<(u32, String)> {
    let after = |key: &str| {
        let i = json.find(key)? + key.len();
        Some(json[i..].trim_start().strip_prefix(':')?.trim_start())
    };
    let num = after("\"number\"")?;
    let end = num.find(|c: char| !c.is_ascii_digit()).unwrap_or(num.len());
    let number = num[..end].parse().ok()?;
    let url = after("\"url\"")?.strip_prefix('"')?;
    let url = &url[..url.find('"')?];
    Some((number, url.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn source_hash_is_valid() {
        assert!(wrapper_common::integrity::is_valid_hash(SOURCE_HASH));
    }

    #[test]
    fn repo_flag_forms() {
        let a = |s: &[&str]| s.iter().map(|x| x.to_string()).collect::<Vec<_>>();
        assert_eq!(
            extract_repo_flag(&a(&["pr", "create", "-R", "o/r"])),
            Some("o/r".into())
        );
        assert_eq!(extract_repo_flag(&a(&["--repo=o/r"])), Some("o/r".into()));
        assert_eq!(extract_repo_flag(&a(&["-Ro/r"])), Some("o/r".into()));
        assert_eq!(extract_repo_flag(&a(&["pr", "create"])), None);
    }

    #[test]
    fn pr_view_json() {
        assert_eq!(
            parse_pr_view_json(r#"{"number":123,"url":"https://github.com/o/r/pull/123"}"#),
            Some((123, "https://github.com/o/r/pull/123".into()))
        );
        assert_eq!(
            parse_pr_view_json(r#"{"url": "https://x/pull/7", "number": 7}"#),
            Some((7, "https://x/pull/7".into()))
        );
        assert_eq!(parse_pr_view_json(r#"{"number":"abc","url":"u"}"#), None);
        assert_eq!(
            parse_pr_view_json(r#"{"number":5,"url":"unterminated"#),
            None
        );
        assert_eq!(parse_pr_view_json(""), None);
        assert_eq!(parse_pr_view_json("{}"), None);
    }
}
