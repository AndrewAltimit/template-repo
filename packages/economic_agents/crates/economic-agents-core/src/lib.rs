//! Core autonomous agent logic and decision engine.
//!
//! This crate contains the main agent orchestrator, state management,
//! decision engines (rule-based and LLM-powered), and task selection strategies.
//!
//! # Example
//!
//! ```rust,ignore
//! use economic_agents_core::{AgentConfig, AutonomousAgent, Backends};
//! use economic_agents_mock::MockBackendFactory;
//!
//! // Create backends
//! let backends = MockBackendFactory::create_default().await;
//!
//! // Create and run agent
//! let config = AgentConfig::default();
//! let mut agent = AutonomousAgent::with_backends(config, backends);
//! let results = agent.run(Some(10)).await?;
//! ```

pub mod agent;
pub mod config;
pub mod cycle;
pub mod decision;
pub mod llm;
pub mod runner;
pub mod state;
pub mod strategy;

pub use agent::{AutonomousAgent, Backends};
pub use config::{AgentConfig, EngineType, OperatingMode, Personality, TaskSelectionStrategy};
pub use cycle::{
    AllocationRecord, CompanyFormationResult, CompanyWorkResult, CycleResult, DecisionRecord,
    InvestmentResult, TaskWorkResult,
};
pub use decision::{Decision, DecisionEngine, DecisionType, ResourceAllocation, RuleBasedEngine};
pub use llm::{LlmConfig, LlmDecisionEngine};
pub use runner::{AgentCommand, AgentEvent, AgentHandle, AgentRunner, AgentStatus, RunnerConfig};
pub use state::AgentState;
pub use strategy::select_task;
