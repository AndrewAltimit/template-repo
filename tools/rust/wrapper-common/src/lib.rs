//! Shared library for CLI wrapper hardening
//!
//! Provides common functionality for git-guard and gh-validator:
//! - Binary discovery with hardened path support
//! - Structured audit logging
//! - Compile-time integrity verification
//! - Platform-specific process execution

pub mod audit;
pub mod binary_finder;
pub mod error;
pub mod exec;
pub mod integrity;
