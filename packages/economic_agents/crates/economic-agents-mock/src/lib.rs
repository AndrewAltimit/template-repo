//! Mock implementations for testing and simulation.
//!
//! This crate provides in-memory implementations of the core interfaces
//! for testing and simulation purposes.

pub mod wallet;
pub mod marketplace;
pub mod compute;
pub mod factory;

pub use wallet::MockWallet;
pub use marketplace::MockMarketplace;
pub use compute::MockCompute;
pub use factory::MockBackendFactory;
