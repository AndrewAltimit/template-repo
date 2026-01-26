//! Observability and auditing for studying AI agent decision patterns.
//!
//! This module provides comprehensive observability metrics and auditing tools
//! for studying autonomous AI agent behaviors, decision-making patterns, and
//! emergent strategies in economic environments.
//!
//! # Components
//!
//! - [`DecisionPatternAnalyzer`] - Analyzes long-term agent decision patterns
//! - [`LLMQualityAnalyzer`] - Measures LLM decision-making quality
//! - [`RiskProfiler`] - Profiles agent risk tolerance and crisis behaviors
//! - [`EmergentBehaviorDetector`] - Detects novel and unexpected agent strategies

mod decision_analyzer;
mod emergent_behavior;
mod llm_quality;
mod risk_profiler;

pub use decision_analyzer::{
    DecisionPatternAnalyzer, DecisionRecord, DecisionTrend, StrategyAlignment, TrendDirection,
};
pub use emergent_behavior::{
    BehaviorDecisionRecord, BehaviorPattern, EmergentBehaviorDetector, NovelStrategy,
};
pub use llm_quality::{
    Hallucination, HallucinationSeverity, LLMDecisionRecord, LLMQualityAnalyzer, LLMQualityMetrics,
};
pub use risk_profiler::{
    CrisisDecision, CrisisSeverity, RiskCategory, RiskDecisionRecord, RiskProfiler, RiskTolerance,
};
