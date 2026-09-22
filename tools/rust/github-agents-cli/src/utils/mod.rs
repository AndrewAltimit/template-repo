//! Utility functions for GitHub operations, subprocesses and text handling.
//!
//! This module provides async-first wrappers around the GitHub CLI (`gh`)
//! and git commands, a hardened subprocess runner for agent CLIs, and
//! UTF-8 safe text helpers.

mod github;
pub mod process;
pub mod text;

pub use github::{
    authenticated_login, check_gh_available, parse_paginated_array, post_comment, run_gh_command,
    run_gh_command_with_stderr,
};
pub use text::truncate_str;
