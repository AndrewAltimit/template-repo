//! Analyzers for codebase analysis.
//!
//! Provides the finding model and the AI-agent-backed analyzer that turns
//! agent output into findings which can be converted to GitHub issues.

mod agent;
mod finding;

pub use agent::{AgentAnalyzer, default_analysis_prompt};
#[cfg(test)]
pub(crate) use finding::{AffectedFile, test_finding};
pub use finding::{AnalysisFinding, FindingCategory, FindingPriority};
