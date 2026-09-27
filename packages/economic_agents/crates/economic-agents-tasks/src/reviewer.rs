//! Code review and validation for generated solutions.
//!
//! Validates solutions against test cases by executing LLM-generated code in a
//! child process.
//!
//! # Isolation: what is and is not provided
//!
//! Every child process (Python interpreter or `rustc`) is started with
//! process-level hardening:
//!
//! - **Clean environment.** The parent environment is cleared. Only `PATH`, a
//!   temp/home directory pointing at the scratch directory, and (on Windows)
//!   `SYSTEMROOT` are set. `rustc` additionally receives the rustup/cargo
//!   variables it needs to locate a toolchain. API keys and other secrets in
//!   the harness environment are not inherited.
//! - **Isolated interpreter.** Python runs with `-I` (ignore `PYTHON*`
//!   variables and user site-packages, do not add the script directory to
//!   `sys.path`) and `-S` (do not import `site`).
//! - **Scratch working directory.** Each run gets a fresh temporary directory
//!   that is deleted afterwards.
//! - **Wall-clock timeout.** The child is killed when the timeout elapses (on
//!   Unix the whole process group is killed).
//! - **Output caps.** At most [`ReviewerConfig::max_output_bytes`] of stdout
//!   and stderr are read; a child that exceeds the cap is killed.
//! - **Resource limits (Unix only).** `RLIMIT_CPU`, `RLIMIT_FSIZE`,
//!   `RLIMIT_CORE`, and (for the interpreter) `RLIMIT_AS` are set before exec.
//!
//! This is **not a security boundary**. The code still runs as the same user as
//! the harness, with the same filesystem view and full network access, and can
//! read any file that user can read. Resource limits are not applied on
//! Windows. For untrusted code, either run the whole harness inside a
//! disposable container with no network and no credentials, or set
//! [`ReviewerConfig::sandbox_command`] so each interpreter invocation is
//! wrapped in a container or sandbox of your choosing.

use std::ffi::OsString;
use std::path::Path;
use std::process::{ExitStatus, Stdio};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWriteExt};
use tokio::process::{Child, Command};
use tracing::{debug, warn};

use crate::catalog::{CodingChallenge, TestCase};

/// Fallback `PATH` when the harness has none.
#[cfg(not(windows))]
const DEFAULT_PATH: &str = "/usr/local/bin:/usr/bin:/bin";
#[cfg(windows)]
const DEFAULT_PATH: &str = r"C:\Windows\System32;C:\Windows";

/// Python snippet that parses (but never executes) source read from stdin.
const PYTHON_SYNTAX_CHECK: &str = r#"import ast, sys
src = sys.stdin.buffer.read().decode("utf-8", "replace")
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"SyntaxError: {e.msg} at line {e.lineno}")
    sys.exit(1)
print("OK")
"#;

/// Result of a single test case execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestResult {
    /// Name of the test case.
    pub name: String,
    /// Whether the test passed.
    pub passed: bool,
    /// Actual output from the code.
    pub actual_output: Option<String>,
    /// Expected output.
    pub expected_output: String,
    /// Error message if execution failed.
    pub error: Option<String>,
    /// Execution time in milliseconds.
    pub execution_time_ms: u64,
}

/// Outcome of the pre-execution syntax/compile check.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", content = "detail", rename_all = "snake_case")]
pub enum SyntaxCheck {
    /// The check ran and the code is valid.
    Passed,
    /// The check ran and found an error.
    Failed(String),
    /// The check could not be performed (tool unavailable or language
    /// unsupported). A skipped check is never treated as a pass.
    Skipped(String),
}

impl Default for SyntaxCheck {
    fn default() -> Self {
        SyntaxCheck::Skipped("not recorded".to_string())
    }
}

/// Overall review result for a solution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewResult {
    /// Whether the solution was verified: the syntax check passed, at least
    /// one test ran, and all tests passed.
    pub success: bool,
    /// Number of tests passed.
    pub tests_passed: usize,
    /// Total number of tests.
    pub total_tests: usize,
    /// Individual test results.
    pub test_results: Vec<TestResult>,
    /// Overall score (0.0 to 1.0). Zero when no tests ran.
    pub score: f64,
    /// Total execution time in milliseconds.
    pub total_time_ms: u64,
    /// Any compilation or syntax errors.
    pub compilation_error: Option<String>,
    /// Outcome of the syntax/compile check.
    #[serde(default)]
    pub syntax_check: SyntaxCheck,
}

/// Configuration for the solution reviewer.
#[derive(Debug, Clone)]
pub struct ReviewerConfig {
    /// Wall-clock timeout for each test case.
    pub test_timeout: Duration,
    /// Wall-clock timeout for the Rust compile check.
    pub compile_timeout: Duration,
    /// Whether to run hidden test cases.
    pub include_hidden: bool,
    /// Python interpreter path.
    pub python_path: Option<String>,
    /// `rustc` path (defaults to `rustc` on `PATH`).
    pub rustc_path: Option<String>,
    /// Maximum bytes read from each of stdout and stderr before the child is
    /// killed.
    pub max_output_bytes: usize,
    /// Address-space limit for the interpreter (`RLIMIT_AS`, Unix only).
    /// Not applied when `sandbox_command` is set.
    pub memory_limit_bytes: Option<u64>,
    /// Largest file the child may write (`RLIMIT_FSIZE`, Unix only).
    pub file_size_limit_bytes: u64,
    /// Optional command prefix that wraps every interpreter invocation, for
    /// example `["docker", "run", "--rm", "-i", "--network=none",
    /// "--memory=256m", "python:3.12-slim"]`. The interpreter path and its
    /// arguments are appended. The prefix must forward stdin (`-i` for
    /// Docker) and is responsible for its own cleanup; killing the local
    /// client on timeout does not necessarily stop a container. Unix resource
    /// limits are not applied to the prefix command.
    pub sandbox_command: Option<Vec<String>>,
}

impl Default for ReviewerConfig {
    fn default() -> Self {
        Self {
            test_timeout: Duration::from_secs(10),
            compile_timeout: Duration::from_secs(30),
            include_hidden: true,
            python_path: None,
            rustc_path: None,
            max_output_bytes: 64 * 1024,
            memory_limit_bytes: Some(512 * 1024 * 1024),
            file_size_limit_bytes: 16 * 1024 * 1024,
            sandbox_command: None,
        }
    }
}

/// Which environment a child process receives.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum EnvProfile {
    /// Runs untrusted code: minimal environment, optional sandbox prefix.
    Interpreter,
    /// Runs a compiler over untrusted code without executing it; needs
    /// toolchain-locating variables.
    Compiler,
}

/// Resource limits applied to a child (Unix only).
#[derive(Debug, Clone, Copy)]
#[cfg_attr(not(unix), allow(dead_code))]
struct ChildLimits {
    cpu_secs: u64,
    address_space_bytes: Option<u64>,
    file_size_bytes: u64,
}

/// Captured output of a hardened child process.
#[derive(Debug)]
struct ProcessOutput {
    status: Option<ExitStatus>,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
    timed_out: bool,
    truncated: bool,
}

/// Reviews and validates solutions against test cases.
pub struct SolutionReviewer {
    config: ReviewerConfig,
    python_path: String,
}

impl SolutionReviewer {
    /// Create a new solution reviewer with the given configuration.
    pub fn new(config: ReviewerConfig) -> Self {
        let python_path = config
            .python_path
            .clone()
            .unwrap_or_else(|| find_python().unwrap_or_else(|| "python3".to_string()));

        if config.sandbox_command.is_none() {
            debug!(
                "Solution reviewer runs generated code with process-level hardening only; \
                 this is not a security boundary"
            );
        }

        Self {
            config,
            python_path,
        }
    }

    /// Create with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(ReviewerConfig::default())
    }

    /// Review a solution against a coding challenge.
    pub async fn review(&self, challenge: &CodingChallenge, solution: &str) -> ReviewResult {
        let start = std::time::Instant::now();

        let syntax_check = self.check_syntax(solution, &challenge.language).await;
        match &syntax_check {
            SyntaxCheck::Failed(e) => {
                return ReviewResult {
                    success: false,
                    tests_passed: 0,
                    total_tests: challenge.test_cases.len(),
                    test_results: Vec::new(),
                    score: 0.0,
                    total_time_ms: start.elapsed().as_millis() as u64,
                    compilation_error: Some(e.clone()),
                    syntax_check,
                };
            },
            SyntaxCheck::Skipped(reason) => {
                warn!(
                    "Syntax check skipped ({}); review cannot be reported as successful",
                    reason
                );
            },
            SyntaxCheck::Passed => {},
        }

        // Filter test cases based on config
        let test_cases: Vec<&TestCase> = challenge
            .test_cases
            .iter()
            .filter(|tc| self.config.include_hidden || !tc.hidden)
            .collect();

        let mut test_results = Vec::new();
        let mut passed = 0;

        for test_case in &test_cases {
            let result = self.run_test(challenge, solution, test_case).await;

            if result.passed {
                passed += 1;
            }
            test_results.push(result);
        }

        let total = test_cases.len();
        let score = if total > 0 {
            passed as f64 / total as f64
        } else {
            0.0
        };

        ReviewResult {
            success: syntax_check == SyntaxCheck::Passed && total > 0 && passed == total,
            tests_passed: passed,
            total_tests: total,
            test_results,
            score,
            total_time_ms: start.elapsed().as_millis() as u64,
            compilation_error: None,
            syntax_check,
        }
    }

    /// Check code for syntax errors.
    async fn check_syntax(&self, code: &str, language: &str) -> SyntaxCheck {
        match language.to_lowercase().as_str() {
            "python" => self.check_python_syntax(code).await,
            "rust" => self.check_rust_syntax(code).await,
            other => SyntaxCheck::Skipped(format!("no syntax checker for language '{}'", other)),
        }
    }

    /// Check Python code for syntax errors. The source is parsed with `ast`
    /// (never executed) and passed on stdin, so it cannot escape a string
    /// literal in the checker script.
    async fn check_python_syntax(&self, code: &str) -> SyntaxCheck {
        let args = vec![
            "-I".to_string(),
            "-S".to_string(),
            "-c".to_string(),
            PYTHON_SYNTAX_CHECK.to_string(),
        ];

        let output = match self
            .run_hardened(
                &self.python_path,
                &args,
                Some(code.as_bytes()),
                self.config.test_timeout,
                EnvProfile::Interpreter,
                None,
            )
            .await
        {
            Ok(output) => output,
            Err(e) => return SyntaxCheck::Skipped(format!("failed to run Python: {}", e)),
        };

        if output.timed_out {
            return SyntaxCheck::Failed(format!(
                "Syntax check timed out after {:?}",
                self.config.test_timeout
            ));
        }

        if output.status.is_some_and(|s| s.success()) {
            SyntaxCheck::Passed
        } else {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);
            SyntaxCheck::Failed(format!("{}{}", stdout, stderr).trim().to_string())
        }
    }

    /// Check Rust code by type-checking it as a library crate with
    /// `rustc --emit=metadata` (no code generation, nothing is executed).
    /// Returns [`SyntaxCheck::Skipped`] if `rustc` cannot be started.
    async fn check_rust_syntax(&self, code: &str) -> SyntaxCheck {
        let rustc = self
            .config
            .rustc_path
            .clone()
            .unwrap_or_else(|| "rustc".to_string());

        let dir = match scratch_dir() {
            Ok(dir) => dir,
            Err(e) => return SyntaxCheck::Skipped(format!("cannot create temp dir: {}", e)),
        };
        let src = dir.path().join("solution.rs");
        if let Err(e) = std::fs::write(&src, code) {
            return SyntaxCheck::Skipped(format!("cannot write source file: {}", e));
        }
        let out = dir.path().join("solution.rmeta");

        let args = vec![
            "--edition".to_string(),
            "2021".to_string(),
            "--crate-type".to_string(),
            "lib".to_string(),
            "--crate-name".to_string(),
            "solution".to_string(),
            "--emit=metadata".to_string(),
            "--cap-lints".to_string(),
            "allow".to_string(),
            "-o".to_string(),
            out.to_string_lossy().into_owned(),
            src.to_string_lossy().into_owned(),
        ];

        let output = match self
            .run_hardened(
                &rustc,
                &args,
                None,
                self.config.compile_timeout,
                EnvProfile::Compiler,
                Some(dir.path()),
            )
            .await
        {
            Ok(output) => output,
            Err(e) => {
                return SyntaxCheck::Skipped(format!("rustc unavailable ({}): {}", rustc, e));
            },
        };

        if output.timed_out {
            return SyntaxCheck::Failed(format!(
                "rustc timed out after {:?}",
                self.config.compile_timeout
            ));
        }

        if output.status.is_some_and(|s| s.success()) {
            SyntaxCheck::Passed
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr);
            SyntaxCheck::Failed(stderr.trim().to_string())
        }
    }

    /// Run a single test case.
    async fn run_test(
        &self,
        challenge: &CodingChallenge,
        solution: &str,
        test_case: &TestCase,
    ) -> TestResult {
        let start = std::time::Instant::now();

        match challenge.language.to_lowercase().as_str() {
            "python" => {
                self.run_python_test(challenge, solution, test_case, start)
                    .await
            },
            lang => TestResult {
                name: test_case.name.clone(),
                passed: false,
                actual_output: None,
                expected_output: test_case.expected_output.clone(),
                error: Some(format!("Unsupported language: {}", lang)),
                execution_time_ms: start.elapsed().as_millis() as u64,
            },
        }
    }

    /// Run a Python test case.
    async fn run_python_test(
        &self,
        challenge: &CodingChallenge,
        solution: &str,
        test_case: &TestCase,
        start: std::time::Instant,
    ) -> TestResult {
        // Build the test script
        let function_name = extract_function_name(&challenge.function_template);
        let inputs = test_case.inputs.join(", ");

        let test_script = format!(
            r#"
{}

# Run the test
try:
    result = {}({})
    print(repr(result))
except Exception as e:
    print(f"ERROR: {{type(e).__name__}}: {{e}}")
"#,
            solution, function_name, inputs
        );

        debug!("Running test script:\n{}", test_script);

        let fail = |error: String, actual: Option<String>| TestResult {
            name: test_case.name.clone(),
            passed: false,
            actual_output: actual,
            expected_output: test_case.expected_output.clone(),
            error: Some(error),
            execution_time_ms: start.elapsed().as_millis() as u64,
        };

        let args = vec![
            "-I".to_string(),
            "-S".to_string(),
            "-c".to_string(),
            test_script,
        ];

        let output = match self
            .run_hardened(
                &self.python_path,
                &args,
                None,
                self.config.test_timeout,
                EnvProfile::Interpreter,
                None,
            )
            .await
        {
            Ok(output) => output,
            Err(e) => return fail(format!("Failed to spawn Python: {}", e), None),
        };

        if output.timed_out {
            return fail(
                format!("Test timed out after {:?}", self.config.test_timeout),
                None,
            );
        }

        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

        if output.truncated {
            return fail(
                format!(
                    "Output exceeded {} bytes; process killed",
                    self.config.max_output_bytes
                ),
                None,
            );
        }

        if stdout.starts_with("ERROR:") {
            return fail(stdout.clone(), Some(stdout));
        }

        if output.status.is_none_or(|s| !s.success()) {
            let error = if stderr.is_empty() {
                format!("Process exited abnormally: {:?}", output.status)
            } else {
                stderr
            };
            return fail(error, Some(stdout));
        }

        // Compare output
        let passed = compare_outputs(&stdout, &test_case.expected_output);

        TestResult {
            name: test_case.name.clone(),
            passed,
            actual_output: Some(stdout),
            expected_output: test_case.expected_output.clone(),
            error: if passed {
                None
            } else {
                Some("Output mismatch".to_string())
            },
            execution_time_ms: start.elapsed().as_millis() as u64,
        }
    }

    /// Spawn `program args...` with the hardening described in the module
    /// docs, feed it `stdin_data`, and collect capped output.
    ///
    /// `workdir` is used as the working directory if given; otherwise a fresh
    /// scratch directory is created and removed afterwards.
    async fn run_hardened(
        &self,
        program: &str,
        args: &[String],
        stdin_data: Option<&[u8]>,
        timeout: Duration,
        profile: EnvProfile,
        workdir: Option<&Path>,
    ) -> std::io::Result<ProcessOutput> {
        let owned_dir;
        let workdir = match workdir {
            Some(dir) => dir,
            None => {
                owned_dir = scratch_dir()?;
                owned_dir.path()
            },
        };

        let sandbox_prefix = match (&self.config.sandbox_command, profile) {
            (Some(prefix), EnvProfile::Interpreter) if !prefix.is_empty() => Some(prefix),
            _ => None,
        };

        let mut cmd = match sandbox_prefix {
            Some(prefix) => {
                let mut cmd = Command::new(&prefix[0]);
                cmd.args(&prefix[1..]).arg(program).args(args);
                cmd
            },
            None => {
                let mut cmd = Command::new(program);
                cmd.args(args);
                cmd
            },
        };

        cmd.current_dir(workdir)
            .env_clear()
            .envs(minimal_env(workdir, profile))
            .stdin(if stdin_data.is_some() {
                Stdio::piped()
            } else {
                Stdio::null()
            })
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        #[cfg(unix)]
        {
            cmd.process_group(0);
            if sandbox_prefix.is_none() {
                let limits = ChildLimits {
                    cpu_secs: timeout.as_secs() + 1,
                    address_space_bytes: match profile {
                        EnvProfile::Interpreter => self.config.memory_limit_bytes,
                        // Compilers reserve large virtual mappings; rely on
                        // the CPU limit and wall-clock timeout instead.
                        EnvProfile::Compiler => None,
                    },
                    file_size_bytes: self.config.file_size_limit_bytes,
                };
                apply_rlimits(&mut cmd, limits);
            }
        }

        let mut child = cmd.spawn()?;

        let stdin_handle = child.stdin.take();
        let stdout_handle = child.stdout.take();
        let stderr_handle = child.stderr.take();
        let cap = self.config.max_output_bytes;

        let run = async {
            let write = async move {
                if let (Some(data), Some(mut stdin)) = (stdin_data, stdin_handle) {
                    // A child that exits without reading stdin closes the pipe;
                    // that is not an error for our purposes.
                    let _ = stdin.write_all(data).await;
                }
            };
            let ((), (stdout, out_trunc), (stderr, err_trunc)) = tokio::join!(
                write,
                read_capped(stdout_handle, cap),
                read_capped(stderr_handle, cap)
            );
            let truncated = out_trunc || err_trunc;
            if truncated {
                kill_process_tree(&mut child).await;
            }
            let status = child.wait().await.ok();
            (stdout, stderr, truncated, status)
        };

        match tokio::time::timeout(timeout, run).await {
            Ok((stdout, stderr, truncated, status)) => Ok(ProcessOutput {
                status,
                stdout,
                stderr,
                timed_out: false,
                truncated,
            }),
            Err(_) => {
                warn!("Child process timed out after {:?}; killing it", timeout);
                kill_process_tree(&mut child).await;
                Ok(ProcessOutput {
                    status: None,
                    stdout: Vec::new(),
                    stderr: Vec::new(),
                    timed_out: true,
                    truncated: false,
                })
            },
        }
    }
}

impl Default for SolutionReviewer {
    fn default() -> Self {
        Self::with_defaults()
    }
}

/// Create a fresh scratch directory for one child process.
fn scratch_dir() -> std::io::Result<tempfile::TempDir> {
    tempfile::Builder::new().prefix("econ-review-").tempdir()
}

/// Build the minimal environment for a child process.
fn minimal_env(workdir: &Path, profile: EnvProfile) -> Vec<(&'static str, OsString)> {
    let wd = workdir.as_os_str().to_owned();
    let mut env: Vec<(&'static str, OsString)> = vec![(
        "PATH",
        std::env::var_os("PATH").unwrap_or_else(|| OsString::from(DEFAULT_PATH)),
    )];

    #[cfg(windows)]
    {
        // Python and rustc need SYSTEMROOT on Windows to initialize.
        if let Some(root) = std::env::var_os("SYSTEMROOT") {
            env.push(("SYSTEMROOT", root));
        }
        env.push(("TEMP", wd.clone()));
        env.push(("TMP", wd.clone()));
    }
    #[cfg(not(windows))]
    env.push(("TMPDIR", wd.clone()));

    match profile {
        EnvProfile::Interpreter => {
            env.push(("HOME", wd));
        },
        EnvProfile::Compiler => {
            // The rustup proxy locates the toolchain through these.
            for key in [
                "HOME",
                "USERPROFILE",
                "RUSTUP_HOME",
                "CARGO_HOME",
                "RUSTUP_TOOLCHAIN",
            ] {
                if let Some(value) = std::env::var_os(key) {
                    env.push((key, value));
                }
            }
        },
    }

    env
}

/// Read up to `cap` bytes; returns the data and whether the cap was exceeded.
async fn read_capped<R: AsyncRead + Unpin>(handle: Option<R>, cap: usize) -> (Vec<u8>, bool) {
    let Some(reader) = handle else {
        return (Vec::new(), false);
    };
    let mut buf = Vec::new();
    let mut limited = reader.take(cap as u64 + 1);
    let _ = limited.read_to_end(&mut buf).await;
    let truncated = buf.len() > cap;
    buf.truncate(cap);
    (buf, truncated)
}

/// Kill the child and, on Unix, every process in its process group.
async fn kill_process_tree(child: &mut Child) {
    #[cfg(unix)]
    if let Some(pid) = child.id() {
        // The child was spawned with `process_group(0)`, so its pid is also
        // its process group id. It has not been reaped yet (we hold the Child
        // and have not observed its exit), so the id cannot have been reused.
        // SAFETY: kill(2) takes plain integers and touches no memory.
        unsafe {
            libc::kill(-(pid as libc::pid_t), libc::SIGKILL);
        }
    }
    let _ = child.kill().await;
}

/// Install `setrlimit` calls that run in the child between fork and exec.
#[cfg(unix)]
fn apply_rlimits(cmd: &mut Command, limits: ChildLimits) {
    let hook = move || -> std::io::Result<()> {
        let set = |resource, value: u64| -> std::io::Result<()> {
            let mut current = libc::rlimit {
                rlim_cur: 0,
                rlim_max: 0,
            };
            // SAFETY: `current` is a valid, writable rlimit on our stack.
            if unsafe { libc::getrlimit(resource, &mut current) } != 0 {
                return Err(std::io::Error::last_os_error());
            }
            // Never try to raise the hard limit (that needs privileges).
            let value = (value as libc::rlim_t).min(current.rlim_max);
            let new = libc::rlimit {
                rlim_cur: value,
                rlim_max: value,
            };
            // SAFETY: `new` is a valid rlimit on our stack.
            if unsafe { libc::setrlimit(resource, &new) } != 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        };
        set(libc::RLIMIT_CPU, limits.cpu_secs)?;
        set(libc::RLIMIT_FSIZE, limits.file_size_bytes)?;
        set(libc::RLIMIT_CORE, 0)?;
        if let Some(bytes) = limits.address_space_bytes {
            set(libc::RLIMIT_AS, bytes)?;
        }
        Ok(())
    };
    // SAFETY: the hook runs in the forked child before exec. It only calls
    // getrlimit(2)/setrlimit(2), which are async-signal-safe, and it neither
    // allocates nor takes locks on the success path.
    unsafe {
        cmd.pre_exec(hook);
    }
}

/// Extract the function name from a template.
fn extract_function_name(template: &str) -> String {
    // Look for "def function_name(" pattern
    if let Some(start) = template.find("def ") {
        let after_def = &template[start + 4..];
        if let Some(end) = after_def.find('(') {
            return after_def[..end].trim().to_string();
        }
    }

    // Look for "fn function_name(" pattern (Rust)
    if let Some(start) = template.find("fn ") {
        let after_fn = &template[start + 3..];
        if let Some(end) = after_fn.find('(') {
            return after_fn[..end].trim().to_string();
        }
    }

    // Default fallback
    "solution".to_string()
}

/// Compare actual and expected outputs with some flexibility.
fn compare_outputs(actual: &str, expected: &str) -> bool {
    let actual = actual.trim();
    let expected = expected.trim();

    // Direct comparison
    if actual == expected {
        return true;
    }

    // Try comparing as Python repr strings
    // e.g., "'Fizz'" vs "Fizz" or "\"Fizz\"" vs "Fizz"
    let actual_unquoted = actual.trim_matches('\'').trim_matches('"');
    let expected_unquoted = expected.trim_matches('\'').trim_matches('"');

    if actual_unquoted == expected_unquoted {
        return true;
    }

    // Try numeric comparison for floats
    if let (Ok(a), Ok(e)) = (actual.parse::<f64>(), expected.parse::<f64>())
        && (a - e).abs() < 1e-9
    {
        return true;
    }

    false
}

/// Find Python interpreter.
fn find_python() -> Option<String> {
    for candidate in &["python3", "python", "/usr/bin/python3", "/usr/bin/python"] {
        if std::process::Command::new(candidate)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok_and(|s| s.success())
        {
            return Some((*candidate).to_string());
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_function_name_python() {
        let template = "def fizzbuzz(n: int) -> str:";
        assert_eq!(extract_function_name(template), "fizzbuzz");
    }

    #[test]
    fn test_extract_function_name_rust() {
        let template = "fn calculate(x: i32) -> i32 {";
        assert_eq!(extract_function_name(template), "calculate");
    }

    #[test]
    fn test_compare_outputs_exact() {
        assert!(compare_outputs("Fizz", "Fizz"));
        assert!(compare_outputs("42", "42"));
    }

    #[test]
    fn test_compare_outputs_quoted() {
        assert!(compare_outputs("'Fizz'", "Fizz"));
        assert!(compare_outputs("\"Buzz\"", "Buzz"));
    }

    #[test]
    fn test_compare_outputs_whitespace() {
        assert!(compare_outputs("  Fizz  ", "Fizz"));
        assert!(compare_outputs("42\n", "42"));
    }

    #[test]
    fn test_compare_outputs_numeric() {
        assert!(compare_outputs("3.14159", "3.14159"));
        assert!(compare_outputs("3.141590000", "3.14159"));
    }

    #[test]
    fn test_compare_outputs_mismatch() {
        assert!(!compare_outputs("Fizz", "Buzz"));
        assert!(!compare_outputs("42", "43"));
    }

    #[tokio::test]
    async fn test_reviewer_creation() {
        let reviewer = SolutionReviewer::with_defaults();
        assert!(reviewer.config.include_hidden);
        assert!(reviewer.config.sandbox_command.is_none());
    }

    fn challenge(language: &str, test_cases: Vec<TestCase>) -> CodingChallenge {
        CodingChallenge {
            id: "t".to_string(),
            name: "t".to_string(),
            description: String::new(),
            language: language.to_string(),
            function_template: "def add(a, b):".to_string(),
            test_cases,
            difficulty: 0.1,
            estimated_hours: 0.1,
            reward: 1.0,
            tags: Vec::new(),
        }
    }

    fn add_case() -> TestCase {
        TestCase {
            name: "add".to_string(),
            inputs: vec!["1".to_string(), "2".to_string()],
            expected_output: "3".to_string(),
            hidden: false,
        }
    }

    #[tokio::test]
    async fn test_unsupported_language_is_skipped_not_passed() {
        let reviewer = SolutionReviewer::with_defaults();
        let review = reviewer
            .review(&challenge("cobol", vec![add_case()]), "whatever")
            .await;
        assert!(matches!(review.syntax_check, SyntaxCheck::Skipped(_)));
        assert!(!review.success);
    }

    #[tokio::test]
    async fn test_rust_check_skipped_when_rustc_missing() {
        let reviewer = SolutionReviewer::new(ReviewerConfig {
            rustc_path: Some("definitely-not-a-real-rustc-binary".to_string()),
            ..Default::default()
        });
        let check = reviewer.check_rust_syntax("pub fn f() {}").await;
        assert!(matches!(check, SyntaxCheck::Skipped(_)), "{:?}", check);

        // A skipped check must never produce a successful review.
        let review = reviewer
            .review(&challenge("rust", Vec::new()), "pub fn f() {}")
            .await;
        assert!(!review.success);
        assert_eq!(review.score, 0.0);
    }

    fn rustc_available() -> bool {
        std::process::Command::new("rustc")
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok_and(|s| s.success())
    }

    #[tokio::test]
    async fn test_rust_check_accepts_valid_and_rejects_invalid() {
        if !rustc_available() {
            eprintln!("rustc not available; skipping");
            return;
        }
        let reviewer = SolutionReviewer::with_defaults();
        let ok = reviewer
            .check_rust_syntax("pub fn add(a: i32, b: i32) -> i32 { a + b }")
            .await;
        assert_eq!(ok, SyntaxCheck::Passed);

        let bad = reviewer
            .check_rust_syntax("pub fn add(a: i32, b: i32) -> i32 { a + }")
            .await;
        assert!(matches!(bad, SyntaxCheck::Failed(_)), "{:?}", bad);

        let type_error = reviewer
            .check_rust_syntax("pub fn f() -> i32 { \"no\" }")
            .await;
        assert!(
            matches!(type_error, SyntaxCheck::Failed(_)),
            "{:?}",
            type_error
        );
    }

    #[cfg(unix)]
    fn sh_args(script: &str) -> Vec<String> {
        vec!["-c".to_string(), script.to_string()]
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn test_hardened_runner_clears_environment() {
        // Cargo sets CARGO_MANIFEST_DIR for the test process; the child must
        // not inherit it.
        assert!(std::env::var_os("CARGO_MANIFEST_DIR").is_some());
        let reviewer = SolutionReviewer::with_defaults();
        let output = reviewer
            .run_hardened(
                "/bin/sh",
                &sh_args("env"),
                None,
                Duration::from_secs(5),
                EnvProfile::Interpreter,
                None,
            )
            .await
            .unwrap();
        let env = String::from_utf8_lossy(&output.stdout);
        assert!(!env.contains("CARGO_MANIFEST_DIR"), "{}", env);
        assert!(env.contains("PATH="), "{}", env);
        assert!(env.contains("HOME="), "{}", env);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn test_hardened_runner_enforces_timeout() {
        let reviewer = SolutionReviewer::with_defaults();
        let start = std::time::Instant::now();
        let output = reviewer
            .run_hardened(
                "/bin/sh",
                &sh_args("sleep 30"),
                None,
                Duration::from_millis(300),
                EnvProfile::Interpreter,
                None,
            )
            .await
            .unwrap();
        assert!(output.timed_out);
        assert!(start.elapsed() < Duration::from_secs(10));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn test_hardened_runner_caps_output() {
        let reviewer = SolutionReviewer::new(ReviewerConfig {
            max_output_bytes: 1024,
            ..Default::default()
        });
        let output = reviewer
            .run_hardened(
                "/bin/sh",
                &sh_args("yes"),
                None,
                Duration::from_secs(5),
                EnvProfile::Interpreter,
                None,
            )
            .await
            .unwrap();
        assert!(output.truncated);
        assert!(!output.timed_out);
        assert_eq!(output.stdout.len(), 1024);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn test_hardened_runner_sets_cpu_limit() {
        let reviewer = SolutionReviewer::with_defaults();
        let output = reviewer
            .run_hardened(
                "/bin/sh",
                &sh_args("ulimit -t"),
                None,
                Duration::from_secs(5),
                EnvProfile::Interpreter,
                None,
            )
            .await
            .unwrap();
        let limit = String::from_utf8_lossy(&output.stdout).trim().to_string();
        // Wall-clock timeout (5s) + 1, unless the inherited hard limit was lower.
        let secs: u64 = limit.parse().expect("numeric CPU limit");
        assert!(secs <= 6, "cpu limit {}", secs);
    }

    #[tokio::test]
    async fn test_python_review_end_to_end() {
        let Some(python) = find_python() else {
            eprintln!("python not available; skipping");
            return;
        };
        let reviewer = SolutionReviewer::new(ReviewerConfig {
            python_path: Some(python),
            test_timeout: Duration::from_secs(2),
            ..Default::default()
        });

        let good = reviewer
            .review(
                &challenge("python", vec![add_case()]),
                "def add(a, b):\n    return a + b\n",
            )
            .await;
        assert_eq!(good.syntax_check, SyntaxCheck::Passed);
        assert!(good.success, "{:?}", good);

        // Source containing triple quotes must not break the syntax checker.
        let quoted = reviewer
            .review(
                &challenge("python", vec![add_case()]),
                "def add(a, b):\n    '''doc'''\n    return a + b\n",
            )
            .await;
        assert!(quoted.success, "{:?}", quoted);

        let bad = reviewer
            .review(&challenge("python", vec![add_case()]), "def add(a, b)\n")
            .await;
        assert!(matches!(bad.syntax_check, SyntaxCheck::Failed(_)));
        assert!(!bad.success);

        let slow = reviewer
            .review(
                &challenge("python", vec![add_case()]),
                "def add(a, b):\n    while True:\n        pass\n",
            )
            .await;
        assert!(!slow.success);
        let err = slow.test_results[0].error.clone().unwrap_or_default();
        assert!(err.contains("timed out"), "{}", err);

        let env_probe = reviewer
            .review(
                &challenge("python", vec![add_case()]),
                "import os\ndef add(a, b):\n    return 3 if 'CARGO_MANIFEST_DIR' not in os.environ else 0\n",
            )
            .await;
        assert!(env_probe.success, "{:?}", env_probe);
    }
}
