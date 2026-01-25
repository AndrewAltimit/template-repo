//! # ITK Net
//!
//! P2P networking for multiplayer video synchronization.
//!
//! This crate provides:
//! - LAN peer discovery via UDP broadcast
//! - Reliable and unreliable messaging via laminar
//! - Session management with leader election
//! - Integration with itk-sync for clock/playback sync
//!
//! ## Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────┐
//! │                         Session                              │
//! │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
//! │  │  Discovery  │  │    Peers    │  │    SyncManager      │  │
//! │  │  (UDP bcast)│  │  (laminar)  │  │  (ClockSync +       │  │
//! │  │             │  │             │  │   PlaybackSync)     │  │
//! │  └─────────────┘  └─────────────┘  └─────────────────────┘  │
//! └─────────────────────────────────────────────────────────────┘
//! ```
//!
//! ## Sync Flow
//!
//! 1. Leader broadcasts `SyncState` every 500ms (unreliable)
//! 2. Followers use `DriftCorrector` for smooth catch-up
//! 3. `ClockPing/Pong` exchanges estimate clock offset
//! 4. Commands (play/pause/seek) sent reliably

pub mod discovery;
pub mod error;
pub mod peer;
pub mod session;
pub mod sync_manager;

pub use discovery::Discovery;
pub use error::{NetError, Result};
pub use peer::{Peer, PeerEvent, PeerManager};
pub use session::{Session, SessionConfig, SessionEvent, SessionRole};
pub use sync_manager::SyncManager;

/// Default port for multiplayer sync
pub const DEFAULT_PORT: u16 = 7331;

/// Discovery broadcast port
pub const DISCOVERY_PORT: u16 = 7332;

/// Sync broadcast interval in milliseconds
pub const SYNC_INTERVAL_MS: u64 = 500;

/// Clock ping interval in milliseconds
pub const CLOCK_PING_INTERVAL_MS: u64 = 2000;
