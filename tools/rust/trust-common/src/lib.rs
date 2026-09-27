//! Shared comment-author trust levels for the repository's agent tooling.
//!
//! `automation-cli`, `board-manager` and `github-agents-cli` all decide how
//! much to trust a GitHub login from the `security` section of
//! `.agents.yaml`:
//!
//! ```yaml
//! security:
//!   agent_admins: [AndrewAltimit]          # may direct agents
//!   trusted_sources: ["github-actions[bot]"] # vetted automation
//! ```
//!
//! This crate is the single implementation of that logic:
//!
//! - [`TrustConfig`]: the raw lists, parsed strictly (each list must be a
//!   YAML sequence of strings; anything else is an error).
//! - [`TrustPolicy`] / [`TrustLevel`]: case-insensitive classification of a
//!   login as admin, trusted or community. Admins always outrank trusted
//!   sources, entries are trimmed and blank entries are dropped, so an empty
//!   or anonymous login is never elevated.
//! - [`Fallback`]: what [`TrustConfig::load`] does when the file is missing
//!   or invalid. The consumers genuinely differ here, so the policy is an
//!   explicit parameter rather than a hidden default.
//! - [`source`]: PR-safe file reads. In a pull-request workflow a PR that
//!   modifies a config file gets the base-branch version instead, so a PR
//!   cannot add its author to the allow-list.

mod config;
mod level;
pub mod source;

pub use config::{AGENTS_CONFIG_FILE, Fallback, TrustConfig, TrustError, find_config_file};
pub use level::{TrustLevel, TrustPolicy, normalize_login};
