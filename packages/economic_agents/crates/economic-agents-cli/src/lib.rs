//! Economic Agents CLI library.
//!
//! This crate provides the CLI interface for running economic agent simulations.

pub mod config;
pub mod runner;
pub mod scenarios;

pub use config::{AgentFileConfig, DashboardFileConfig};
pub use runner::{AgentRunResult, ScenarioResult, run_agent, run_scenario};
pub use scenarios::Scenario;
