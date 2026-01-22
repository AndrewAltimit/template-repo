//! Strands Session - Session management with AgentCore Memory integration
//!
//! This crate provides session management capabilities including:
//! - Conversation history persistence
//! - Session state management
//! - AWS Bedrock AgentCore Memory integration

pub mod manager;
pub mod memory;
pub mod session;

pub use manager::SessionManager;
pub use memory::AgentCoreMemory;
pub use session::{Session, SessionConfig, SessionState};
