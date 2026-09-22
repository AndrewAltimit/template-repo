//! git-guard: a `git` wrapper that blocks dangerous operations for AI agents.
//!
//! Install this binary as `git` ahead of the real git on PATH (or as the
//! setgid `/usr/bin/git` in hardened mode). It parses the command line the
//! way git does, expands aliases, and refuses:
//!
//! - force pushes (`--force`, `-f` in any short-flag cluster,
//!   `--force-with-lease`, `--force-if-includes`, `+refspec`, `--mirror`)
//! - skipped or redirected hooks (`--no-verify`, `commit -n`,
//!   `core.hooksPath` / config includes via `-c`, `--config-env`,
//!   `GIT_CONFIG_*`, or `git config`)
//! - pushes that can update `main` / `master` (explicit refspecs, `HEAD` or
//!   bare `git push` on/tracking a protected branch, `--all`, `--prune`,
//!   `push.default=matching`, `send-pack`, `subtree push`)
//!
//! See `policy.rs` for the full rules. Allowed commands are handed to the
//! real git via `exec()` (Unix), so stdio, signals, and exit codes pass
//! through untouched. Every invocation is audit-logged.

mod cli;
mod policy;
mod query;

use std::ffi::OsString;
use std::process::exit;

use wrapper_common::audit::Auditor;
use wrapper_common::binary_finder::{self, RealBinary};
use wrapper_common::error::CommonError;

include!(concat!(env!("OUT_DIR"), "/integrity.rs"));

const WRAPPER_NAME: &str = "git-guard";

fn main() {
    exit(run());
}

fn run() -> i32 {
    // Keep the raw OsStrings for exec so non-UTF-8 arguments (file names)
    // reach git byte-for-byte; policy checks use a lossy copy.
    let os_args: Vec<OsString> = std::env::args_os().skip(1).collect();
    let args: Vec<String> = os_args
        .iter()
        .map(|a| a.to_string_lossy().into_owned())
        .collect();

    if wrapper_common::integrity::check_integrity_flag(&args, WRAPPER_NAME, SOURCE_HASH) {
        return 0;
    }

    let real = match binary_finder::find_real_binary("git") {
        Ok(real) => real,
        Err(e) => return report_error(&e),
    };
    let auditor = Auditor::new(WRAPPER_NAME, real.path(), SOURCE_HASH);

    let inv = cli::parse(&args);
    let env = git_config_env();
    let violations = policy::check(&inv, &env, &query::RealGit::new(&real, &inv));

    if !violations.is_empty() {
        let reasons = violations
            .iter()
            .map(|v| format!("{}: {}", v.what, v.why))
            .collect::<Vec<_>>()
            .join("; ");
        auditor.blocked(&args, &reasons);
        eprint!("{}", blocked_message(&violations, &real));
        return 1;
    }

    auditor.allowed(&args);
    let err = wrapper_common::exec::exec(&real, &os_args);
    auditor.error(&args, &err.to_string());
    report_error(&err)
}

/// `GIT_CONFIG_*` variables (the only ones the policy inspects).
fn git_config_env() -> Vec<(String, String)> {
    std::env::vars_os()
        .filter_map(|(k, v)| {
            let k = k.to_string_lossy();
            k.starts_with("GIT_CONFIG_")
                .then(|| (k.into_owned(), v.to_string_lossy().into_owned()))
        })
        .collect()
}

fn report_error(e: &CommonError) -> i32 {
    eprintln!("ERROR: {e}");
    if let Some(help) = e.help_text() {
        eprintln!("\n{help}");
    }
    1
}

fn blocked_message(violations: &[policy::Violation], real: &RealBinary) -> String {
    let rule = "============================================================";
    let mut msg = format!(
        "\n{rule}\nGIT-GUARD: OPERATION BLOCKED\n{rule}\n\n\
         The following operation(s) are not allowed:\n\n"
    );
    for v in violations {
        msg.push_str(&format!("  - {} : {}\n", v.what, v.why));
    }
    msg.push_str(
        "\nThis safety mechanism prevents AI assistants from performing\n\
         destructive git operations or bypassing code review.\n\n\
         If a human needs this operation, run the real git binary directly:\n\n",
    );
    let hardened = binary_finder::hardened_path("git");
    if real.path() == hardened || hardened.exists() {
        msg.push_str(&format!("  sudo {} <command>\n", hardened.display()));
    } else {
        msg.push_str(&format!("  {} <command>\n", real.path().display()));
    }
    msg.push_str(&format!("\n{rule}\n"));
    msg
}

#[cfg(test)]
mod tests {
    #[test]
    fn source_hash_is_valid() {
        assert!(wrapper_common::integrity::is_valid_hash(super::SOURCE_HASH));
    }
}
