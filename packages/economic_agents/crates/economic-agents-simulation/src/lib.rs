//! Simulation realism features.
//!
//! This crate provides realistic simulation of:
//! - Network latency
//! - Market dynamics (bull/bear/crash cycles)
//! - Competitor agents
//! - Reputation systems
//! - Feedback generation

pub mod competition;
pub mod feedback;
pub mod latency;
pub mod market;
pub mod reputation;

pub use competition::CompetitorSimulator;
pub use feedback::FeedbackGenerator;
pub use latency::LatencySimulator;
pub use market::{MarketDynamics, MarketPhase};
pub use reputation::{ReputationSystem, ReputationTier};
