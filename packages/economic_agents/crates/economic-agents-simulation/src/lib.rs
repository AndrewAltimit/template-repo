//! Simulation realism features.
//!
//! This crate provides realistic simulation of:
//! - Network latency
//! - Market dynamics (bull/bear/crash cycles)
//! - Competitor agents
//! - Reputation systems
//! - Feedback generation

pub mod latency;
pub mod market;
pub mod competition;
pub mod reputation;
pub mod feedback;

pub use latency::LatencySimulator;
pub use market::{MarketDynamics, MarketPhase};
pub use competition::CompetitorSimulator;
pub use reputation::{ReputationSystem, ReputationTier};
pub use feedback::FeedbackGenerator;
