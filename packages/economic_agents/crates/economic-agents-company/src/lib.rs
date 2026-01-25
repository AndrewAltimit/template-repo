//! Company formation and management.
//!
//! This crate handles:
//! - Company lifecycle management
//! - Business plan generation
//! - Product development
//! - Sub-agent management
//! - Autonomous sub-agent delegation

pub mod autonomy;
pub mod builder;
pub mod models;
pub mod sub_agents;

pub use autonomy::{
    AutonomousSubAgent, AutonomousSubAgentManager, DelegatedTask, DelegationResult,
    DelegationStatus, Delegator, SubAgentBudget,
};
pub use builder::CompanyBuilder;
pub use models::{BusinessPlan, Company, CompanyStage, Product};
pub use sub_agents::{
    ExecutiveTitle, SubAgent, SubAgentManager, SubAgentRole, Team, TeamSummary,
};
