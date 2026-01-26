//! Task catalog, execution, and review for autonomous agents.
//!
//! This crate provides:
//! - A catalog of coding challenges for agents to solve
//! - Task execution using Claude CLI for code generation
//! - Code review and validation against test cases

mod catalog;
mod executor;
mod reviewer;

pub use catalog::{CodingChallenge, TaskCatalog, TestCase};
pub use executor::{ExecutionResult, ExecutorConfig, TaskExecutor};
pub use reviewer::{ReviewResult, SolutionReviewer, TestResult};
