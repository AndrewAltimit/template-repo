//! Strands Core - Fundamental types for agent systems
//!
//! This crate provides the core type definitions that model conversation
//! messages, tool interactions, and agent state. Types are designed to
//! be compatible with the AWS Bedrock Converse API.

pub mod content;
pub mod error;
pub mod event;
pub mod message;
pub mod tool;

pub use content::*;
pub use error::*;
pub use event::*;
pub use message::*;
pub use tool::*;
