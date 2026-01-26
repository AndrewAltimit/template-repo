//! Core trait definitions for economic agent backends.
//!
//! This crate defines the abstract interfaces that all backend implementations
//! must satisfy. The three core interfaces are:
//!
//! - [`Wallet`] - Cryptocurrency/payment operations
//! - [`Marketplace`] - Task discovery and execution
//! - [`Compute`] - Compute resource management
//!
//! These interfaces are designed to be async-first and implementation-agnostic,
//! allowing seamless switching between mock (simulation) and real (production)
//! backends.

pub mod compute;
pub mod error;
pub mod marketplace;
pub mod types;
pub mod wallet;

pub use compute::Compute;
pub use error::*;
pub use marketplace::{Marketplace, TaskFilter};
pub use types::*;
pub use wallet::Wallet;
