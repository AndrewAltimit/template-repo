//! State persistence for economic agents.
//!
//! This module provides file-based persistence for agent state
//! and company registry, enabling save/resume functionality.

mod state_manager;

pub use state_manager::{
    LoadedAgentState, LoadedRegistry, PersistenceError, SavedAgentMetadata, SerializedDecision,
    StateManager,
};
