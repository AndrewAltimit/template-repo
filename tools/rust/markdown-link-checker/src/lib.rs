//! Markdown link checker library.
//!
//! The `md-link-checker` binary is a thin CLI wrapper over this crate. The
//! pipeline is:
//!
//! 1. [`discover`] finds markdown files (honoring `.gitignore` and
//!    `.mdlinkignore`).
//! 2. [`parse`] extracts every link destination (inline, reference, autolink,
//!    image, raw HTML `href`/`src`) plus the set of GitHub heading anchors.
//! 3. [`target`] classifies each destination (same-page anchor, local path,
//!    external URL, unsupported scheme).
//! 4. [`local`] validates local paths and fragments; [`http`] validates
//!    external URLs with deduplication, rate limiting and retries.
//! 5. [`report`] holds the result types (JSON schema) and human rendering.
//!
//! [`checker::check_paths`] ties the stages together.

pub mod checker;
pub mod discover;
pub mod filters;
pub mod html;
pub mod http;
pub mod local;
pub mod parse;
pub mod report;
pub mod slug;
pub mod target;

pub use checker::{CheckOptions, check_files, check_paths};
pub use report::{CheckResults, FileResult, LinkResult};
