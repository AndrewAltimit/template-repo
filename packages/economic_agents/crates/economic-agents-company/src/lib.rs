//! Company formation and management.
//!
//! This crate handles:
//! - Company lifecycle management
//! - Business plan generation
//! - Product development
//! - Sub-agent management

pub mod builder;
pub mod models;
pub mod sub_agents;

pub use builder::CompanyBuilder;
pub use models::{BusinessPlan, Company, CompanyStage, Product};
