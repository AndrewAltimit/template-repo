//! JSON response tools for structured agent output.
//!
//! Provides tools for validating and committing JSON responses:
//! - `validate_json`: Validates JSON against a schema
//! - `commit_response`: Finalizes the response and signals loop termination

mod commit_response;
mod state;
mod validate_json;

pub use commit_response::CommitResponseTool;
pub use state::{CommittedResponse, JsonResponseState};
pub use validate_json::ValidateJsonTool;
