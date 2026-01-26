//! Mock implementations for testing and simulation.
//!
//! This crate provides in-memory implementations of the core interfaces
//! for testing and simulation purposes.

pub mod compute;
pub mod factory;
pub mod marketplace;
pub mod wallet;

pub use compute::MockCompute;
pub use factory::{MockBackendConfig, MockBackendFactory, MockBackends};
pub use marketplace::MockMarketplace;
pub use wallet::MockWallet;
