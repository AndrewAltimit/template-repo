//! Gaea.Swarm.exe automation (Gaea2 2.2.6.0 command line).
//!
//! Builds run as child processes with a hard timeout; on timeout the process is
//! killed (`kill_on_drop`) rather than left running in the background. A
//! semaphore limits concurrent builds because Gaea is GPU/RAM heavy and
//! parallel builds on one machine mostly thrash.

use std::collections::BTreeMap;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::Arc;
use std::time::{Duration, Instant};

use tokio::process::Command;
use tokio::sync::Semaphore;

use crate::types::ExecutionResult;

/// Maximum bytes of stdout/stderr kept per stream (tail).
const MAX_CAPTURE: usize = 16 * 1024;
/// Output file extensions Gaea2 writes on build.
const OUTPUT_EXTENSIONS: &[&str] = &[
    "exr",
    "png",
    "tiff",
    "tif",
    "raw",
    "r16",
    "r32",
    "hdr",
    "jpg",
    "jpeg",
    "obj",
    "fbx",
    "glb",
    "mesh",
    "heightfield",
];
/// Limits for scanning the build directory.
const MAX_SCAN_DEPTH: usize = 4;
const MAX_OUTPUT_FILES: usize = 500;

/// Options for one Gaea.Swarm build.
#[derive(Debug, Clone, Default)]
pub struct RunOptions {
    /// Build resolution (one of 512..8192).
    pub resolution: u32,
    /// Build output directory.
    pub build_path: PathBuf,
    pub profile: Option<String>,
    pub region: Option<String>,
    pub seed: Option<u64>,
    pub target_node: Option<String>,
    /// Automation variable overrides (`-v name:value`).
    pub variables: BTreeMap<String, String>,
    pub ignore_cache: bool,
    pub verbose: bool,
    pub timeout: Duration,
}

/// Build the Gaea.Swarm argument list (pure; unit tested).
pub fn build_args(project: &Path, opts: &RunOptions) -> Vec<OsString> {
    let mut args: Vec<OsString> = vec![
        "--Filename".into(),
        project.as_os_str().to_owned(),
        "--resolution".into(),
        opts.resolution.to_string().into(),
        "--buildpath".into(),
        opts.build_path.as_os_str().to_owned(),
        // Required for unattended automation.
        "--silent".into(),
    ];
    if let Some(p) = &opts.profile {
        args.extend(["--profile".into(), p.into()]);
    }
    if let Some(r) = &opts.region {
        args.extend(["--region".into(), r.into()]);
    }
    if let Some(s) = opts.seed {
        args.extend(["--seed".into(), s.to_string().into()]);
    }
    if let Some(n) = &opts.target_node {
        args.extend(["--node".into(), n.into()]);
    }
    for (key, value) in &opts.variables {
        args.extend(["-v".into(), format!("{key}:{value}").into()]);
    }
    if opts.ignore_cache {
        args.push("--ignorecache".into());
    }
    if opts.verbose {
        args.push("--verbose".into());
    }
    args
}

/// Validate a free-form CLI argument value so it cannot be mistaken for a flag.
pub fn check_arg_value(label: &str, value: &str) -> Result<(), String> {
    if value.trim().is_empty() {
        return Err(format!("{label} must not be empty"));
    }
    if value.starts_with('-') {
        return Err(format!("{label} must not start with '-'"));
    }
    if value.chars().any(|c| c.is_control()) {
        return Err(format!("{label} must not contain control characters"));
    }
    Ok(())
}

/// CLI automation for running Gaea2 projects.
pub struct Gaea2CLI {
    gaea_path: PathBuf,
    permits: Arc<Semaphore>,
}

impl Gaea2CLI {
    /// Create a new CLI automation instance allowing `max_concurrent` builds.
    pub fn new(gaea_path: PathBuf, max_concurrent: usize) -> Self {
        Self {
            gaea_path,
            permits: Arc::new(Semaphore::new(max_concurrent.max(1))),
        }
    }

    /// Run a Gaea2 project and collect the generated files.
    pub async fn run_project(&self, project_path: &Path, opts: &RunOptions) -> ExecutionResult {
        if !project_path.is_file() {
            return ExecutionResult::failure(format!(
                "Project file not found: {}",
                project_path.display()
            ));
        }
        if let Err(e) = tokio::fs::create_dir_all(&opts.build_path).await {
            return ExecutionResult::failure(format!(
                "Failed to create build directory {}: {e}",
                opts.build_path.display()
            ));
        }

        let Ok(_permit) = self.permits.acquire().await else {
            return ExecutionResult::failure("Build queue closed");
        };

        let args = build_args(project_path, opts);
        tracing::info!("Running Gaea2: {} {:?}", self.gaea_path.display(), args);

        let mut cmd = Command::new(&self.gaea_path);
        cmd.args(&args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        let start = Instant::now();
        let child = match cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                return ExecutionResult::failure(format!(
                    "Failed to start {}: {e}",
                    self.gaea_path.display()
                ))
            },
        };

        let output_dir = Some(opts.build_path.display().to_string());
        // Dropping the `wait_with_output` future on timeout drops the child,
        // and `kill_on_drop` terminates the process.
        let outcome = tokio::time::timeout(opts.timeout, child.wait_with_output()).await;
        let elapsed = Some(start.elapsed().as_secs_f64());

        match outcome {
            Ok(Ok(output)) => {
                let stdout = tail(&output.stdout);
                let stderr = tail(&output.stderr);
                let exit_code = output.status.code();
                if output.status.success() {
                    let output_files = find_output_files(&opts.build_path).await;
                    ExecutionResult {
                        success: true,
                        file_count: output_files.len(),
                        output_files,
                        output_dir,
                        execution_time: elapsed,
                        exit_code,
                        stdout,
                        stderr,
                        ..Default::default()
                    }
                } else {
                    ExecutionResult {
                        success: false,
                        error: Some(format!(
                            "Gaea2 exited with code {}{}",
                            exit_code.map_or("unknown".to_string(), |c| c.to_string()),
                            stderr
                                .as_deref()
                                .map(|s| format!(": {}", s.trim()))
                                .unwrap_or_default()
                        )),
                        output_dir,
                        execution_time: elapsed,
                        exit_code,
                        stdout,
                        stderr,
                        ..Default::default()
                    }
                }
            },
            Ok(Err(e)) => ExecutionResult {
                execution_time: elapsed,
                ..ExecutionResult::failure(format!("Failed while waiting for Gaea2: {e}"))
            },
            Err(_) => ExecutionResult {
                output_dir,
                execution_time: elapsed,
                timed_out: true,
                ..ExecutionResult::failure(format!(
                    "Build timed out after {} seconds and was terminated",
                    opts.timeout.as_secs()
                ))
            },
        }
    }
}

/// Keep the last `MAX_CAPTURE` bytes of a stream as lossy UTF-8.
fn tail(bytes: &[u8]) -> Option<String> {
    if bytes.is_empty() {
        return None;
    }
    let start = bytes.len().saturating_sub(MAX_CAPTURE);
    let text = String::from_utf8_lossy(&bytes[start..]).to_string();
    Some(if start > 0 {
        format!("[... {start} bytes truncated ...]\n{text}")
    } else {
        text
    })
}

/// Find generated output files under `dir` (recursively: Gaea organizes build
/// outputs into per-node sub-folders).
pub async fn find_output_files(dir: &Path) -> Vec<String> {
    let mut files = Vec::new();
    let mut stack = vec![(dir.to_path_buf(), 0usize)];
    while let Some((current, depth)) = stack.pop() {
        let Ok(mut entries) = tokio::fs::read_dir(&current).await else {
            continue;
        };
        while let Ok(Some(entry)) = entries.next_entry().await {
            let Ok(ft) = entry.file_type().await else {
                continue;
            };
            let path = entry.path();
            if ft.is_dir() {
                if depth < MAX_SCAN_DEPTH {
                    stack.push((path, depth + 1));
                }
            } else if ft.is_file() {
                let is_output = path
                    .extension()
                    .map(|e| e.to_string_lossy().to_lowercase())
                    .is_some_and(|e| OUTPUT_EXTENSIONS.contains(&e.as_str()));
                if is_output {
                    files.push(path.display().to_string());
                    if files.len() >= MAX_OUTPUT_FILES {
                        files.sort();
                        return files;
                    }
                }
            }
        }
    }
    files.sort();
    files
}

#[cfg(test)]
mod tests {
    use super::*;

    fn opts(dir: &Path) -> RunOptions {
        RunOptions {
            resolution: 1024,
            build_path: dir.join("build"),
            timeout: Duration::from_secs(20),
            ..Default::default()
        }
    }

    #[test]
    fn builds_expected_arguments() {
        let mut o = opts(Path::new("out"));
        o.profile = Some("Final".into());
        o.seed = Some(7);
        o.variables.insert("Height".into(), "0.5".into());
        o.variables.insert("Name".into(), "abc".into());
        o.ignore_cache = true;
        let args: Vec<String> = build_args(Path::new("p.terrain"), &o)
            .into_iter()
            .map(|a| a.to_string_lossy().to_string())
            .collect();
        assert_eq!(&args[..2], &["--Filename", "p.terrain"]);
        assert!(args.windows(2).any(|w| w == ["--resolution", "1024"]));
        assert!(args.contains(&"--silent".to_string()));
        assert!(args.windows(2).any(|w| w == ["--profile", "Final"]));
        assert!(args.windows(2).any(|w| w == ["--seed", "7"]));
        // Variables are raw values, not JSON-quoted.
        assert!(args.windows(2).any(|w| w == ["-v", "Name:abc"]));
        assert!(args.windows(2).any(|w| w == ["-v", "Height:0.5"]));
        assert!(args.contains(&"--ignorecache".to_string()));
        assert!(!args.contains(&"--verbose".to_string()));
    }

    #[test]
    fn arg_values_cannot_inject_flags() {
        assert!(check_arg_value("profile", "Final").is_ok());
        assert!(check_arg_value("profile", "--silent").is_err());
        assert!(check_arg_value("profile", "").is_err());
        assert!(check_arg_value("profile", "a\nb").is_err());
    }

    #[test]
    fn tail_truncates() {
        assert_eq!(tail(b""), None);
        assert_eq!(tail(b"abc").as_deref(), Some("abc"));
        let big = vec![b'x'; MAX_CAPTURE + 10];
        let t = tail(&big).unwrap();
        assert!(t.starts_with("[... 10 bytes truncated"));
    }

    #[tokio::test]
    async fn find_output_files_recurses() {
        let dir = tempfile::tempdir().unwrap();
        assert!(find_output_files(dir.path()).await.is_empty());
        let sub = dir.path().join("Export").join("deep");
        std::fs::create_dir_all(&sub).unwrap();
        std::fs::write(dir.path().join("a.png"), "x").unwrap();
        std::fs::write(sub.join("b.EXR"), "x").unwrap();
        std::fs::write(sub.join("report.json"), "x").unwrap();
        let files = find_output_files(dir.path()).await;
        assert_eq!(files.len(), 2, "{files:?}");
    }

    /// Write a fake Gaea executable that exits with `code` after `sleep_secs`.
    fn fake_gaea(dir: &Path, code: i32, sleep_secs: u32) -> PathBuf {
        #[cfg(windows)]
        {
            let p = dir.join(format!("fake_gaea_{code}_{sleep_secs}.cmd"));
            let wait = if sleep_secs > 0 {
                format!("ping -n {} 127.0.0.1 >nul\r\n", sleep_secs + 1)
            } else {
                String::new()
            };
            std::fs::write(
                &p,
                format!("@echo off\r\necho building %*\r\n{wait}exit /b {code}\r\n"),
            )
            .unwrap();
            p
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let p = dir.join(format!("fake_gaea_{code}_{sleep_secs}.sh"));
            std::fs::write(
                &p,
                format!("#!/bin/sh\necho building \"$@\"\nsleep {sleep_secs}\nexit {code}\n"),
            )
            .unwrap();
            std::fs::set_permissions(&p, std::fs::Permissions::from_mode(0o755)).unwrap();
            p
        }
    }

    #[tokio::test]
    async fn runs_fake_gaea_success_and_failure() {
        let dir = tempfile::tempdir().unwrap();
        let project = dir.path().join("p.terrain");
        std::fs::write(&project, "{}").unwrap();

        let ok = Gaea2CLI::new(fake_gaea(dir.path(), 0, 0), 1);
        let r = ok.run_project(&project, &opts(dir.path())).await;
        assert!(r.success, "{r:?}");
        assert_eq!(r.exit_code, Some(0));
        assert!(r.stdout.unwrap_or_default().contains("building"));

        let bad = Gaea2CLI::new(fake_gaea(dir.path(), 3, 0), 1);
        let r = bad.run_project(&project, &opts(dir.path())).await;
        assert!(!r.success);
        assert_eq!(r.exit_code, Some(3));
        assert!(r.error.unwrap().contains("code 3"));
    }

    #[tokio::test]
    async fn times_out_and_reports() {
        let dir = tempfile::tempdir().unwrap();
        let project = dir.path().join("p.terrain");
        std::fs::write(&project, "{}").unwrap();
        let slow = Gaea2CLI::new(fake_gaea(dir.path(), 0, 5), 1);
        let mut o = opts(dir.path());
        o.timeout = Duration::from_millis(500);
        let r = slow.run_project(&project, &o).await;
        assert!(!r.success);
        assert!(r.timed_out);
    }

    #[tokio::test]
    async fn missing_project_or_executable() {
        let dir = tempfile::tempdir().unwrap();
        let cli = Gaea2CLI::new(dir.path().join("missing.exe"), 1);
        let r = cli
            .run_project(&dir.path().join("nope.terrain"), &opts(dir.path()))
            .await;
        assert!(r.error.unwrap().contains("not found"));

        let project = dir.path().join("p.terrain");
        std::fs::write(&project, "{}").unwrap();
        let r = cli.run_project(&project, &opts(dir.path())).await;
        assert!(r.error.unwrap().contains("Failed to start"));
    }
}
