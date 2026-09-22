//! Thin wrapper around external commands (`git`, `gh`, `patch`).

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use anyhow::{Context, Result, bail};
use tracing::debug;

/// Captured result of a finished command.
#[derive(Debug)]
pub struct Output {
    /// Whether the command exited with status 0.
    pub success: bool,
    /// Standard output (lossy UTF-8).
    pub stdout: String,
    /// Standard error (lossy UTF-8).
    pub stderr: String,
}

/// Runs external programs, optionally in a fixed working directory.
#[derive(Debug, Clone, Default)]
pub struct Runner {
    cwd: Option<PathBuf>,
}

impl Runner {
    /// Create a runner that uses the process working directory.
    pub fn new() -> Self {
        Self::default()
    }

    /// Create a runner that executes commands in `dir`.
    pub fn in_dir(dir: impl AsRef<Path>) -> Self {
        Self {
            cwd: Some(dir.as_ref().to_path_buf()),
        }
    }

    /// Run `program` with `args`, feeding `stdin` if given, and capture output.
    ///
    /// Fails only if the program could not be started; a non-zero exit is
    /// reported through [`Output::success`].
    pub fn run(&self, program: &str, args: &[&str], stdin: Option<&str>) -> Result<Output> {
        debug!("Running: {program} {}", args.join(" "));
        let mut cmd = Command::new(program);
        cmd.args(args)
            .stdin(if stdin.is_some() {
                Stdio::piped()
            } else {
                Stdio::null()
            })
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        if let Some(dir) = &self.cwd {
            cmd.current_dir(dir);
        }

        let mut child = cmd
            .spawn()
            .with_context(|| format!("Failed to start `{program}` (is it installed?)"))?;
        // Write stdin from a separate thread so a child that fills its stdout
        // pipe before draining stdin cannot deadlock us.
        let writer = match (stdin, child.stdin.take()) {
            (Some(input), Some(mut pipe)) => {
                let input = input.to_owned();
                Some(std::thread::spawn(move || pipe.write_all(input.as_bytes())))
            },
            _ => None,
        };
        let output = child
            .wait_with_output()
            .with_context(|| format!("Failed to wait for `{program}`"))?;
        if let Some(writer) = writer {
            // A broken pipe just means the child exited early; its status says why.
            let _ = writer.join();
        }

        Ok(Output {
            success: output.status.success(),
            stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
            stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
        })
    }

    /// Run a command and fail with its stderr if it exits non-zero.
    pub fn run_ok(&self, program: &str, args: &[&str], stdin: Option<&str>) -> Result<String> {
        let output = self.run(program, args, stdin)?;
        if !output.success {
            let detail = if output.stderr.trim().is_empty() {
                output.stdout.trim()
            } else {
                output.stderr.trim()
            };
            bail!("`{program} {}` failed: {detail}", args.join(" "));
        }
        Ok(output.stdout)
    }

    /// Whether `program` can be started at all.
    pub fn is_available(&self, program: &str) -> bool {
        self.run(program, &["--version"], None).is_ok()
    }
}
