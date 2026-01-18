//! Analyzers for codebase analysis.
//!
//! This module provides the infrastructure for analyzing codebases
//! and generating findings that can be converted to GitHub issues.
//!
//! # Available Analyzers
//!
//! - **AgentAnalyzer** - AI agent-based analyzer that delegates to Claude, Gemini, etc.

mod base;

pub use base::{
    AffectedFile, AgentAnalyzer, AnalysisFinding, BaseAnalyzer, EffortEstimate, FindingCategory,
    FindingPriority,
};
