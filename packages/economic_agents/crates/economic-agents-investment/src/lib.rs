//! Investment system and investor agents.
//!
//! This crate handles:
//! - Investment proposals
//! - Investor agents and decision making
//! - Company registry for matching

pub mod models;
pub mod investor;
pub mod registry;

pub use models::{Investment, InvestmentDecision, InvestmentProposal, InvestorProfile, RiskTolerance};
pub use investor::InvestorAgent;
pub use registry::CompanyRegistry;
