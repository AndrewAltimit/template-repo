//! GitHub API interaction via `gh` CLI

mod client;
mod types;

pub use client::{GhClient, RepoSpec};
pub use types::{
    Author, Comment, CommentKind, GHOST_LOGIN, OlderPage, PrCommentsResponse, PrSnapshot,
};

use crate::error::Result;

/// Source of PR conversation data.
///
/// Implemented by [`GhClient`]; abstracted so the polling logic can be tested
/// without network access.
pub trait PrSource {
    /// Newest comments and reviews plus PR state
    fn snapshot(&self, pr_number: u32) -> Result<PrSnapshot>;

    /// Page of conversation comments preceding the `before` cursor
    fn older_comments(&self, pr_number: u32, before: &str) -> Result<OlderPage>;

    /// Page of reviews preceding the `before` cursor
    fn older_reviews(&self, pr_number: u32, before: &str) -> Result<OlderPage>;
}
