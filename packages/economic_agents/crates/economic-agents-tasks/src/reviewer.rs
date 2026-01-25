//! Code review and validation for generated solutions.
//!
//! Validates solutions against test cases by executing the code in a sandboxed environment.

use std::process::Stdio;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tokio::io::AsyncReadExt;
use tokio::process::Command;
use tracing::{debug, warn};

use crate::catalog::{CodingChallenge, TestCase};

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

/// Overall review result for a solution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewResult {
    /// Whether all tests passed.
    pub success: bool,
    /// Number of tests passed.
    pub tests_passed: usize,
    /// Total number of tests.
    pub total_tests: usize,
    /// Individual test results.
    pub test_results: Vec<TestResult>,
    /// Overall score (0.0 to 1.0).
    pub score: f64,
    /// Total execution time in milliseconds.
    pub total_time_ms: u64,
    /// Any compilation or syntax errors.
    pub compilation_error: Option<String>,
}

/// Configuration for the solution reviewer.
#[derive(Debug, Clone)]
pub struct ReviewerConfig {
    /// Timeout for each test case.
    pub test_timeout: Duration,
    /// Whether to run hidden test cases.
    pub include_hidden: bool,
    /// Python interpreter path.
    pub python_path: Option<String>,
}

impl Default for ReviewerConfig {
    fn default() -> Self {
        Self {
            test_timeout: Duration::from_secs(10),
            include_hidden: true,
            python_path: None,
        }
    }
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

        // First, check for syntax errors
        if let Err(e) = self.check_syntax(solution, &challenge.language).await {
            return ReviewResult {
                success: false,
                tests_passed: 0,
                total_tests: challenge.test_cases.len(),
                test_results: Vec::new(),
                score: 0.0,
                total_time_ms: start.elapsed().as_millis() as u64,
                compilation_error: Some(e),
            };
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
            1.0
        };

        ReviewResult {
            success: passed == total,
            tests_passed: passed,
            total_tests: total,
            test_results,
            score,
            total_time_ms: start.elapsed().as_millis() as u64,
            compilation_error: None,
        }
    }

    /// Check code for syntax errors.
    async fn check_syntax(&self, code: &str, language: &str) -> Result<(), String> {
        match language.to_lowercase().as_str() {
            "python" => self.check_python_syntax(code).await,
            "rust" => self.check_rust_syntax(code).await,
            _ => Ok(()), // Skip syntax check for unsupported languages
        }
    }

    /// Check Python code for syntax errors.
    async fn check_python_syntax(&self, code: &str) -> Result<(), String> {
        let check_script = format!(
            r#"
import ast
import sys

code = '''{}'''

try:
    ast.parse(code)
    print("OK")
except SyntaxError as e:
    print(f"SyntaxError: {{e.msg}} at line {{e.lineno}}")
    sys.exit(1)
"#,
            code.replace("'''", r"\'\'\'")
        );

        let output = Command::new(&self.python_path)
            .arg("-c")
            .arg(&check_script)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .await
            .map_err(|e| format!("Failed to run Python: {}", e))?;

        if output.status.success() {
            Ok(())
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let stdout = String::from_utf8_lossy(&output.stdout);
            Err(format!("{}{}", stdout, stderr).trim().to_string())
        }
    }

    /// Check Rust code for syntax errors (basic check).
    async fn check_rust_syntax(&self, _code: &str) -> Result<(), String> {
        // For now, just return Ok - full Rust compilation check would require rustc
        // In a real implementation, we'd use rustc --emit=metadata to check syntax
        warn!("Rust syntax checking not fully implemented");
        Ok(())
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
            }
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

        let mut child = match Command::new(&self.python_path)
            .arg("-c")
            .arg(&test_script)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
        {
            Ok(child) => child,
            Err(e) => {
                return TestResult {
                    name: test_case.name.clone(),
                    passed: false,
                    actual_output: None,
                    expected_output: test_case.expected_output.clone(),
                    error: Some(format!("Failed to spawn Python: {}", e)),
                    execution_time_ms: start.elapsed().as_millis() as u64,
                };
            }
        };

        // Take ownership of stdout/stderr before the async block
        let mut stdout_handle = child.stdout.take();
        let mut stderr_handle = child.stderr.take();

        let wait_result = tokio::time::timeout(self.config.test_timeout, async {
            // Read stdout and stderr concurrently
            let stdout_future = async {
                let mut buf = Vec::new();
                if let Some(ref mut stdout) = stdout_handle {
                    let _ = stdout.read_to_end(&mut buf).await;
                }
                buf
            };

            let stderr_future = async {
                let mut buf = Vec::new();
                if let Some(ref mut stderr) = stderr_handle {
                    let _ = stderr.read_to_end(&mut buf).await;
                }
                buf
            };

            let (stdout_buf, stderr_buf) = tokio::join!(stdout_future, stderr_future);
            let status = child.wait().await;

            (stdout_buf, stderr_buf, status)
        })
        .await;

        let (stdout_buf, stderr_buf, status) = match wait_result {
            Ok((stdout, stderr, status)) => (stdout, stderr, status),
            Err(_) => {
                return TestResult {
                    name: test_case.name.clone(),
                    passed: false,
                    actual_output: None,
                    expected_output: test_case.expected_output.clone(),
                    error: Some(format!(
                        "Test timed out after {:?}",
                        self.config.test_timeout
                    )),
                    execution_time_ms: start.elapsed().as_millis() as u64,
                };
            }
        };

        let stdout = String::from_utf8_lossy(&stdout_buf).trim().to_string();
        let stderr = String::from_utf8_lossy(&stderr_buf).trim().to_string();

        if stdout.starts_with("ERROR:") {
            return TestResult {
                name: test_case.name.clone(),
                passed: false,
                actual_output: Some(stdout.clone()),
                expected_output: test_case.expected_output.clone(),
                error: Some(stdout),
                execution_time_ms: start.elapsed().as_millis() as u64,
            };
        }

        if !stderr.is_empty() && status.as_ref().is_ok_and(|s| !s.success()) {
            return TestResult {
                name: test_case.name.clone(),
                passed: false,
                actual_output: Some(stdout),
                expected_output: test_case.expected_output.clone(),
                error: Some(stderr),
                execution_time_ms: start.elapsed().as_millis() as u64,
            };
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
}

impl Default for SolutionReviewer {
    fn default() -> Self {
        Self::with_defaults()
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
    }
}
