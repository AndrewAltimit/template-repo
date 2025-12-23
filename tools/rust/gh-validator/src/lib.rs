//! gh-validator library
//!
//! GitHub CLI wrapper for comment validation and secret masking.
//! This library provides all the validation logic that can be used
//! independently of the CLI binary.

pub mod config;
pub mod error;
pub mod gh_finder;
pub mod validation;

pub use config::{load_config, Config};
pub use error::{Error, Result};
pub use validation::{CommentValidator, SecretMasker, UrlValidator};
