//! Backend adapters for virtual character control.
//!
//! This module provides the trait interface and implementations
//! for different virtual character platforms.

mod adapter;
mod mock;
mod vrchat;

pub use adapter::{BackendAdapter, BackendError, BackendResult};
pub use mock::MockBackend;
pub use vrchat::VRChatRemoteBackend;
