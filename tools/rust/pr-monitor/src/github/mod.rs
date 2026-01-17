//! GitHub API interaction via `gh` CLI

mod client;
mod types;

// Public API exports (some may not be used internally but are part of the library interface)
pub use client::GhClient;
#[allow(unused_imports)]
pub use types::{Author, Comment, CommitDetails, CommitInfo, CommitterInfo, PrCommentsResponse};
