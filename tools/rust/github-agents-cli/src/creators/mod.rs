//! Issue creators for automated GitHub issue generation.
//!
//! # Available Creators
//!
//! - **IssueCreator** - Creates issues from analysis findings with
//!   fingerprint deduplication and board integration

mod issue;

pub use issue::{CreationResult, IssueCreator};
