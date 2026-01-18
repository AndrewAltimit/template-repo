//! Issue creators for automated GitHub issue generation.
//!
//! This module provides infrastructure for creating GitHub issues
//! from analysis findings with deduplication and board integration.
//!
//! # Available Creators
//!
//! - **IssueCreator** - Creates issues from analysis findings

mod issue;

pub use issue::{CreationResult, IssueCreator, IssuePriority, IssueSize, IssueType};
