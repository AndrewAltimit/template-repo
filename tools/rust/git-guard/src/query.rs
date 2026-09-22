//! [`GitContext`] backed by the real git binary.
//!
//! Queries replay the invocation's repository-selecting global options
//! (`-C`, `-c`, `--git-dir`, ...) and inherit the environment, so they see
//! exactly the config the real command will see, including anything injected
//! on the command line. They only run when needed: alias lookup for
//! non-builtin subcommands, branch/upstream/config lookup for `git push`.

use crate::cli::Invocation;
use crate::policy::GitContext;
use std::process::Stdio;
use wrapper_common::binary_finder::RealBinary;

pub struct RealGit<'a> {
    real: &'a RealBinary,
    context_opts: &'a [String],
}

impl<'a> RealGit<'a> {
    pub fn new(real: &'a RealBinary, inv: &'a Invocation) -> Self {
        Self {
            real,
            context_opts: &inv.context_opts,
        }
    }

    /// Run `git --no-pager <context opts> <args>`; trimmed stdout on success.
    fn git(&self, args: &[&str]) -> Option<String> {
        let output = self
            .real
            .command()
            .arg("--no-pager")
            .args(self.context_opts)
            .args(args)
            .env("GIT_TERMINAL_PROMPT", "0")
            .stdin(Stdio::null())
            .stderr(Stdio::null())
            .output()
            .ok()?;
        if !output.status.success() {
            return None;
        }
        let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
        (!text.is_empty()).then_some(text)
    }
}

impl GitContext for RealGit<'_> {
    fn alias(&self, name: &str) -> Option<String> {
        self.git(&["config", "--get", &format!("alias.{name}")])
    }

    fn current_branch(&self) -> Option<String> {
        self.git(&["symbolic-ref", "--quiet", "--short", "HEAD"])
    }

    fn push_destination(&self) -> Option<String> {
        self.git(&[
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{push}",
        ])
    }

    fn config_get(&self, key: &str) -> Option<String> {
        self.git(&["config", "--get", key])
    }

    fn config_get_regexp(&self, pattern: &str) -> Vec<(String, String)> {
        self.git(&["config", "--get-regexp", pattern])
            .map(|out| {
                out.lines()
                    .map(|line| match line.split_once(' ') {
                        Some((k, v)) => (k.to_string(), v.to_string()),
                        None => (line.to_string(), String::new()),
                    })
                    .collect()
            })
            .unwrap_or_default()
    }

    fn setgid_elevated(&self) -> bool {
        wrapper_common::platform::is_setgid_elevated()
    }
}
