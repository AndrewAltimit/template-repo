//! Backend adapters for virtual character control.
//!
//! This module provides the trait interface and implementations
//! for different virtual character platforms.

mod adapter;
mod mock;
pub mod movement;
mod vrchat;

use std::sync::Arc;
use tokio::sync::RwLock;

pub use adapter::{AudioOutcome, BackendAdapter, BackendError, BackendResult, EmoteAction};
pub use mock::MockBackend;
pub use vrchat::{AudioPlaybackMode, VRChatConfig, VRChatRemoteBackend};

/// The active backend slot shared between tools and the sequence player.
pub type SharedBackend = Arc<RwLock<Option<Box<dyn BackendAdapter>>>>;

/// Identifiers accepted by `set_backend`.
pub const BACKEND_NAMES: &[&str] = &["mock", "vrchat_remote"];

/// Construct a (disconnected) backend by identifier.
pub fn create_backend(name: &str) -> Option<Box<dyn BackendAdapter>> {
    match name {
        "mock" => Some(Box::new(MockBackend::new())),
        "vrchat_remote" => Some(Box::new(VRChatRemoteBackend::new())),
        _ => None,
    }
}
