//! Comment analysis and classification

mod classifier;
mod decision;

// Public API exports (some may not be used internally but are part of the library interface)
#[allow(unused_imports)]
pub use classifier::{classify, is_relevant_author, Action, Classification, DEFAULT_ADMIN_USER};
#[allow(unused_imports)]
pub use decision::{CommentSummary, Decision, Priority, ResponseType};
