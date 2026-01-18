//! Security module for GitHub AI Agents.
//!
//! Provides authorization, rate limiting, and security checks for agent operations.

pub mod manager;

pub use manager::{SecurityConfig, SecurityManager, TriggerInfo};
