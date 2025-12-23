//! Configuration module
//!
//! Handles loading and parsing of .secrets.yaml configuration files.

pub mod loader;
pub mod types;

pub use loader::load_config;
pub use types::Config;
