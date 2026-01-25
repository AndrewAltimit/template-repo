//! Core autonomous agent logic and decision engine.
//!
//! This crate contains the main agent orchestrator, state management,
//! decision engines (rule-based and LLM-powered), and task selection strategies.

pub mod agent;
pub mod config;
pub mod decision;
pub mod state;
pub mod strategy;

pub use agent::AutonomousAgent;
pub use config::AgentConfig;
pub use state::AgentState;
