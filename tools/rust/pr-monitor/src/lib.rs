//! pr-monitor library
//!
//! GitHub PR comment monitoring with intelligent analysis. The binary is a thin
//! wrapper around this library:
//!
//! - [`github`]: data model and `gh`-based client (one GraphQL call per poll)
//! - [`analysis`]: comment classification and JSON decision types
//! - [`monitor`]: author/type filtering and the polling loop

pub mod analysis;
pub mod cli;
pub mod error;
pub mod github;
pub mod monitor;

pub use analysis::{Classification, Decision, classify};
pub use cli::Args;
pub use error::{Error, Result};
pub use github::{Comment, GhClient, PrSource};
pub use monitor::{Filter, Found, Poller, PollerConfig};
