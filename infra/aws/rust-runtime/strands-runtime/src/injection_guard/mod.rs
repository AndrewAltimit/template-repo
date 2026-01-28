//! Prompt injection detection and prevention.
//!
//! This module provides AI-based detection of prompt injection attacks,
//! including DAN-style jailbreaks, purpose redirection, and instruction override attempts.

mod detector;
mod patterns;

pub use detector::{AttackCategory, InjectionAnalysis, InjectionDetector};
pub use patterns::{AttackPattern, PatternMatch, PatternMatcher};
