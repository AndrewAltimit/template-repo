//! Company formation and management.
//!
//! This crate handles:
//! - Company lifecycle management
//! - Business plan generation
//! - Product development
//! - Sub-agent management

pub mod models;
pub mod builder;
pub mod sub_agents;

pub use models::{Company, CompanyStage, BusinessPlan, Product};
pub use builder::CompanyBuilder;
