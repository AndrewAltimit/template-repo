//! Strands Agent - Core agent loop and conversation management
//!
//! This crate provides the main Agent implementation that orchestrates
//! conversations between users, models, and tools.

pub mod agent;
pub mod conversation;
pub mod loop_control;
pub mod model;

pub use agent::{Agent, AgentBuilder, AgentConfig, AgentResult};
pub use conversation::ConversationManager;
pub use loop_control::{
    termination_channel, LoopTerminationSignal, TerminationReceiver, TerminationSender,
};
pub use model::{InferenceConfig, Model};
