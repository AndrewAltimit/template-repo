//! Investment system and investor agents.
//!
//! This crate handles:
//! - Investment proposals
//! - Investor agents and decision making
//! - Company registry for matching

pub mod investor;
pub mod models;
pub mod registry;

pub use investor::InvestorAgent;
pub use models::{
    Investment, InvestmentDecision, InvestmentProposal, InvestorProfile, RiskTolerance,
};
pub use registry::CompanyRegistry;
