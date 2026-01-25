//! Economic Agents CLI library.
//!
//! This crate provides the CLI interface for running economic agent simulations.

pub mod config;
pub mod runner;
pub mod scenarios;

pub use config::{AgentFileConfig, DashboardFileConfig};
pub use runner::{run_agent, run_scenario, AgentRunResult, ScenarioResult};
pub use scenarios::Scenario;
