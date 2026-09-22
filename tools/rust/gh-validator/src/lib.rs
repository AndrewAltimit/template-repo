//! gh-validator library: everything except process entry lives here so it
//! can be unit-tested.
//!
//! - [`args`]: pflag-compatible parsing of gh arguments into content slots
//! - [`aliases`]: gh alias expansion
//! - [`policy`]: operations refused outright
//! - [`sanitize`]: per-slot validation, masking, and private temp copies
//! - [`validation`]: secret masking, emoji / mention / formatting checks,
//!   reaction URL verification
//! - [`config`]: `.secrets.yaml` discovery and parsing

pub mod aliases;
pub mod args;
pub mod config;
pub mod error;
pub mod policy;
pub mod sanitize;
pub mod validation;

pub use config::{Config, load_config};
pub use error::{Error, Result};
pub use validation::{SecretMasker, UrlValidator};
