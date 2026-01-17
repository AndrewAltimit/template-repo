//! pr-monitor library
//!
//! GitHub PR comment monitoring with intelligent analysis.
//! This library provides all the monitoring and analysis logic that can be used
//! independently of the CLI binary.

pub mod analysis;
pub mod cli;
pub mod error;
pub mod github;
pub mod monitor;

pub use analysis::{classify, Classification, Decision};
pub use cli::Args;
pub use error::{Error, Result};
pub use github::{Comment, GhClient};
pub use monitor::Poller;
