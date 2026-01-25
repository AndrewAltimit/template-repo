//! Report generation for economic agents.
//!
//! This module provides comprehensive report generation for analyzing
//! agent behavior, generating audit trails, and producing governance analyses.

mod generator;
mod models;

pub use generator::{
    AgentData, CompanyData, DecisionData, ReportGenerator, SubAgentData, TransactionData,
};
pub use models::{
    AuditTrail, ExecutiveSummary, GovernanceAnalysis, Report, ReportContent, ReportType,
    TechnicalReport,
};
