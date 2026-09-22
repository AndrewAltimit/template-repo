//! Code Review Processor
//!
//! Processes the JSON produced by the AgentCore `/code-review` endpoint and
//! performs the deterministic follow-up actions: posting the review as a PR
//! comment, applying and committing proposed fixes, and opening a PR.
//!
//! Module overview:
//! - [`review`]: lenient parsing of the endpoint response into a [`review::Review`]
//! - [`patch`]: path safety checks and normalization of model-generated diffs
//! - [`comment`]: PR comment / PR body formatting and size limits
//! - [`git`], [`github`]: `git` and `gh` wrappers
//! - [`processor`]: orchestration and the JSON [`processor::Summary`]

pub mod cli;
pub mod command;
pub mod comment;
pub mod git;
pub mod github;
pub mod patch;
pub mod processor;
pub mod review;

/// Process exit codes.
pub mod exit_code {
    /// Everything requested succeeded.
    pub const SUCCESS: u8 = 0;
    /// Invalid input, or a git / GitHub operation failed.
    pub const ERROR: u8 = 1;
    /// Invalid command-line arguments (emitted by clap).
    pub const USAGE: u8 = 2;
    /// Review severity met `--fail-on-severity`.
    pub const SEVERITY_THRESHOLD: u8 = 3;
}
