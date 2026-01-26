//! LLM-powered decision engine using Claude CLI.
//!
//! This module provides an LLM-based decision engine that uses the Claude Code CLI
//! to make decisions about agent actions. It supports configurable prompts,
//! fallback behavior, and robust error handling.

use std::env;
use std::process::Stdio;
use std::time::Duration;

use async_trait::async_trait;
use economic_agents_interfaces::Result;
use serde::{Deserialize, Serialize};
use tokio::io::AsyncWriteExt;
use tokio::process::Command;
use tracing::{debug, error, info, warn};

use crate::config::{AgentConfig, Personality};
use crate::decision::{
    Decision, DecisionEngine, DecisionType, ResourceAllocation, RuleBasedEngine,
};
use crate::state::AgentState;

/// Configuration for the LLM decision engine.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmConfig {
    /// Model to use (e.g., "sonnet", "opus", "haiku").
    pub model: String,
    /// Request timeout in seconds.
    #[serde(with = "humantime_serde")]
    pub timeout: Duration,
    /// Whether to enable fallback to rule-based engine.
    pub fallback_enabled: bool,
    /// Custom system prompt override.
    pub system_prompt: Option<String>,
    /// Path to claude binary (auto-detected if None).
    pub claude_path: Option<String>,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            model: "sonnet".to_string(),
            timeout: Duration::from_secs(900), // 15 minutes for complex reasoning
            fallback_enabled: true,
            system_prompt: None,
            claude_path: None,
        }
    }
}

/// Response from Claude for resource allocation decisions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllocationResponse {
    /// Percentage of time for task work (0.0-1.0).
    pub task_work: f64,
    /// Percentage of time for company work (0.0-1.0).
    pub company_work: f64,
    /// Percentage of time for other activities (0.0-1.0).
    pub other: f64,
    /// Reasoning for the allocation.
    pub reasoning: String,
}

/// LLM-powered decision engine using Claude CLI.
///
/// Uses the Claude Code CLI to make decisions based on the current agent state.
/// Falls back to rule-based decisions if Claude is unavailable or fails.
pub struct LlmDecisionEngine {
    /// LLM configuration.
    config: LlmConfig,
    /// Fallback rule-based engine.
    fallback: RuleBasedEngine,
    /// Cached path to claude binary.
    claude_path: Option<String>,
}

impl LlmDecisionEngine {
    /// Create a new LLM decision engine with the given configuration.
    pub fn new(config: LlmConfig) -> Self {
        let claude_path = config.claude_path.clone().or_else(find_claude_binary);

        if claude_path.is_some() {
            info!("LLM Decision Engine initialized with Claude CLI");
        } else {
            warn!("Claude CLI not found, LLM engine will fall back to rule-based decisions");
        }

        Self {
            config,
            fallback: RuleBasedEngine::new(),
            claude_path,
        }
    }

    /// Create with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(LlmConfig::default())
    }

    /// Create with a specific model.
    pub fn with_model(model: impl Into<String>) -> Self {
        Self::new(LlmConfig {
            model: model.into(),
            ..Default::default()
        })
    }

    /// Check if Claude CLI is available.
    pub fn is_available(&self) -> bool {
        self.claude_path.is_some()
    }

    /// Generate the system prompt for decision making.
    fn system_prompt(&self) -> String {
        self.config.system_prompt.clone().unwrap_or_else(|| {
            r#"You are an autonomous economic agent decision engine. Your role is to analyze the agent's current state and make strategic decisions to ensure survival and growth.

CRITICAL: You must respond with ONLY a valid JSON object. No explanation, no markdown, just the JSON.

The JSON must have these exact fields:
- "decision_type": One of "work_on_tasks", "purchase_compute", "work_on_company", "seek_investment", or "wait"
- "reasoning": A brief explanation of your decision (1-2 sentences)
- "confidence": A number between 0 and 1
- "hours": (only for purchase_compute) Number of hours to purchase

Decision priorities (in order):
1. SURVIVAL: If compute_hours < 10, you MUST work on tasks to earn money
2. STABILITY: If balance < 50 and compute_hours < 20, focus on task work
3. GROWTH: If balance > 100 and stable, consider company formation
4. OPTIMIZATION: Balance task work and company investment based on personality

Example responses:
{"decision_type": "work_on_tasks", "reasoning": "Low compute hours require immediate income.", "confidence": 0.95}
{"decision_type": "purchase_compute", "reasoning": "Adequate balance allows compute purchase.", "confidence": 0.8, "hours": 24}
{"decision_type": "work_on_company", "reasoning": "Stable finances enable growth investment.", "confidence": 0.7}"#.to_string()
        })
    }

    /// Generate the user prompt with current state.
    fn user_prompt(&self, state: &AgentState, config: &AgentConfig) -> String {
        format!(
            r#"AGENT STATE (respond with JSON only):
- Balance: ${:.2}
- Compute Hours Remaining: {:.1}
- Tasks Completed: {} | Failed: {}
- Total Earnings: ${:.2} | Expenses: ${:.2}
- Has Company: {}
- Reputation: {:.2}
- Current Cycle: {}
- Consecutive Failures: {}

CONFIGURATION:
- Personality: {:?}
- Survival Buffer: {:.1} hours
- Company Threshold: ${:.2}

What decision should this agent make? Respond with ONLY the JSON object."#,
            state.balance,
            state.compute_hours,
            state.tasks_completed,
            state.tasks_failed,
            state.total_earnings,
            state.total_expenses,
            state.has_company,
            state.reputation,
            state.current_cycle,
            state.consecutive_failures,
            config.personality,
            config.survival_buffer_hours,
            config.company_threshold
        )
    }

    /// Generate prompt for resource allocation decisions.
    fn allocation_prompt(&self, state: &AgentState, config: &AgentConfig) -> String {
        format!(
            r#"As an economic agent decision engine, determine optimal resource allocation.

AGENT STATE:
- Balance: ${:.2}
- Compute Hours: {:.1}
- Has Company: {}
- Reputation: {:.2}
- Personality: {:?}

Respond with ONLY a JSON object:
{{"task_work": 0.6, "company_work": 0.3, "other": 0.1, "reasoning": "Brief explanation"}}

Values must sum to 1.0. Consider:
- Low balance/compute -> prioritize task_work
- Has company -> balance task_work and company_work
- Aggressive personality -> more company_work
- Risk averse -> more task_work"#,
            state.balance,
            state.compute_hours,
            state.has_company,
            state.reputation,
            config.personality
        )
    }

    /// Parse the LLM response into a Decision.
    fn parse_decision_response(&self, response: &str) -> Option<Decision> {
        #[derive(Deserialize)]
        struct LlmResponse {
            decision_type: String,
            reasoning: String,
            confidence: f64,
            hours: Option<f64>,
        }

        // Extract JSON from response (might be wrapped in markdown or have extra text)
        let json_str = extract_json(response)?;

        let parsed: LlmResponse = serde_json::from_str(&json_str).ok()?;

        let decision_type = match parsed
            .decision_type
            .to_lowercase()
            .replace('_', "")
            .as_str()
        {
            "workontasks" | "worktasks" | "tasks" => DecisionType::WorkOnTasks,
            "purchasecompute" | "buycompute" | "compute" => DecisionType::PurchaseCompute {
                hours: parsed.hours.unwrap_or(24.0),
            },
            "workoncompany" | "company" | "formcompany" => DecisionType::WorkOnCompany,
            "seekinvestment" | "investment" | "invest" => DecisionType::SeekInvestment,
            "wait" | "idle" | "rest" => DecisionType::Wait,
            _ => {
                warn!("Unknown decision type: {}", parsed.decision_type);
                return None;
            }
        };

        Some(Decision {
            decision_type,
            reasoning: parsed.reasoning,
            confidence: parsed.confidence.clamp(0.0, 1.0),
        })
    }

    /// Parse the LLM response into a ResourceAllocation.
    fn parse_allocation_response(&self, response: &str) -> Option<ResourceAllocation> {
        let json_str = extract_json(response)?;
        let parsed: AllocationResponse = serde_json::from_str(&json_str).ok()?;

        // Normalize to ensure sum is 1.0
        let total = parsed.task_work + parsed.company_work + parsed.other;
        if total <= 0.0 {
            return None;
        }

        Some(ResourceAllocation {
            task_work: (parsed.task_work / total).clamp(0.0, 1.0),
            company_work: (parsed.company_work / total).clamp(0.0, 1.0),
            other: (parsed.other / total).clamp(0.0, 1.0),
        })
    }

    /// Call Claude CLI with a prompt.
    async fn call_claude(&self, prompt: &str) -> Result<String> {
        let claude_path = self.claude_path.as_ref().ok_or_else(|| {
            economic_agents_interfaces::EconomicAgentError::Configuration(
                "Claude CLI not found".to_string(),
            )
        })?;

        debug!("Calling Claude CLI with model: {}", self.config.model);

        // Build command:
        // --print: Non-interactive mode, output response and exit
        // --dangerously-skip-permissions: Auto-approve all tool uses
        // --model: Specify the model to use
        let mut cmd = Command::new(claude_path);
        cmd.arg("--print")
            .arg("--dangerously-skip-permissions")
            .arg("--model")
            .arg(&self.config.model)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        let mut child = cmd.spawn().map_err(|e| {
            economic_agents_interfaces::EconomicAgentError::Internal(format!(
                "Failed to spawn Claude CLI: {}",
                e
            ))
        })?;

        // Write prompt to stdin
        if let Some(mut stdin) = child.stdin.take() {
            stdin.write_all(prompt.as_bytes()).await.map_err(|e| {
                economic_agents_interfaces::EconomicAgentError::Internal(format!(
                    "Failed to write to Claude stdin: {}",
                    e
                ))
            })?;
            // Close stdin to signal end of input
            drop(stdin);
        }

        // Wait for completion with timeout
        // Note: kill_on_drop(true) ensures the subprocess is killed if the Child is dropped
        // (e.g., on timeout), preventing resource leaks.
        let output = tokio::time::timeout(self.config.timeout, child.wait_with_output())
            .await
            .map_err(|_| {
                warn!(
                    "Claude CLI timed out after {:?}, process will be killed",
                    self.config.timeout
                );
                economic_agents_interfaces::EconomicAgentError::Internal(format!(
                    "Claude CLI timed out after {:?}",
                    self.config.timeout
                ))
            })?
            .map_err(|e| {
                economic_agents_interfaces::EconomicAgentError::Internal(format!(
                    "Claude CLI failed: {}",
                    e
                ))
            })?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("Claude CLI failed with stderr: {}", stderr);
            return Err(economic_agents_interfaces::EconomicAgentError::Internal(
                format!(
                    "Claude CLI exited with status {}: {}",
                    output.status, stderr
                ),
            ));
        }

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();

        // Strip ANSI escape codes and clean up
        let cleaned = strip_ansi_codes(&stdout);

        debug!("Claude response length: {} chars", cleaned.len());

        Ok(cleaned)
    }

    /// Make a decision using Claude CLI.
    async fn decide_with_llm(&self, state: &AgentState, config: &AgentConfig) -> Result<Decision> {
        let system = self.system_prompt();
        let user = self.user_prompt(state, config);

        let full_prompt = format!("{}\n\n---\n\n{}", system, user);

        let response = self.call_claude(&full_prompt).await?;

        self.parse_decision_response(&response).ok_or_else(|| {
            economic_agents_interfaces::EconomicAgentError::Internal(
                "Failed to parse Claude response as decision".to_string(),
            )
        })
    }

    /// Allocate resources using Claude CLI.
    async fn allocate_with_llm(
        &self,
        state: &AgentState,
        config: &AgentConfig,
    ) -> Result<ResourceAllocation> {
        let prompt = self.allocation_prompt(state, config);

        let response = self.call_claude(&prompt).await?;

        self.parse_allocation_response(&response).ok_or_else(|| {
            economic_agents_interfaces::EconomicAgentError::Internal(
                "Failed to parse Claude response as allocation".to_string(),
            )
        })
    }
}

impl Default for LlmDecisionEngine {
    fn default() -> Self {
        Self::with_defaults()
    }
}

#[async_trait]
impl DecisionEngine for LlmDecisionEngine {
    async fn decide(&self, state: &AgentState, config: &AgentConfig) -> Result<Decision> {
        debug!("LLM decision engine making decision");

        // Check if Claude CLI is available
        if !self.is_available() {
            if self.config.fallback_enabled {
                info!("Claude CLI not available, using fallback engine");
                return self.fallback.decide(state, config).await;
            } else {
                return Err(
                    economic_agents_interfaces::EconomicAgentError::Configuration(
                        "Claude CLI not available and fallback disabled".to_string(),
                    ),
                );
            }
        }

        // Try to call Claude
        match self.decide_with_llm(state, config).await {
            Ok(decision) => {
                info!(
                    decision_type = ?decision.decision_type,
                    confidence = %decision.confidence,
                    reasoning = %decision.reasoning,
                    "LLM decision made"
                );
                Ok(decision)
            }
            Err(e) => {
                if self.config.fallback_enabled {
                    warn!(error = %e, "LLM call failed, using fallback");
                    self.fallback.decide(state, config).await
                } else {
                    Err(e)
                }
            }
        }
    }

    async fn allocate_resources(
        &self,
        state: &AgentState,
        config: &AgentConfig,
    ) -> Result<ResourceAllocation> {
        // Check if Claude CLI is available
        if !self.is_available() {
            debug!("Claude CLI not available for allocation, using fallback");
            return self.fallback.allocate_resources(state, config).await;
        }

        // Try LLM-based allocation
        match self.allocate_with_llm(state, config).await {
            Ok(allocation) => {
                debug!(
                    task_work = %allocation.task_work,
                    company_work = %allocation.company_work,
                    "LLM allocation made"
                );
                Ok(allocation)
            }
            Err(e) => {
                if self.config.fallback_enabled {
                    warn!(error = %e, "LLM allocation failed, using fallback");

                    // Get base allocation and adjust by personality
                    let base = self.fallback.allocate_resources(state, config).await?;

                    let adjusted = match config.personality {
                        Personality::RiskAverse => ResourceAllocation {
                            task_work: (base.task_work + 0.1).min(1.0),
                            company_work: (base.company_work - 0.05).max(0.0),
                            other: base.other,
                        },
                        Personality::Aggressive => ResourceAllocation {
                            task_work: (base.task_work - 0.1).max(0.2),
                            company_work: (base.company_work + 0.1).min(0.7),
                            other: base.other,
                        },
                        Personality::Balanced => base,
                    };

                    Ok(adjusted)
                } else {
                    Err(e)
                }
            }
        }
    }
}

/// Find the claude binary by checking common locations.
fn find_claude_binary() -> Option<String> {
    // 1. Check CLAUDE_PATH environment variable first
    if let Ok(path) = env::var("CLAUDE_PATH")
        && !path.is_empty()
        && verify_binary(&path)
    {
        info!("Using claude from CLAUDE_PATH: {}", path);
        return Some(path);
    }

    let home = env::var("HOME").unwrap_or_default();

    // 2. Build candidates list
    let mut candidates = vec![
        "claude".to_string(), // PATH lookup
        "/usr/local/bin/claude".to_string(),
        "/usr/bin/claude".to_string(),
    ];

    // 3. Check NVM node versions
    if !home.is_empty() {
        let nvm_versions_dir = format!("{}/.nvm/versions/node", home);
        if let Ok(entries) = std::fs::read_dir(&nvm_versions_dir) {
            let mut node_versions: Vec<_> = entries
                .filter_map(|e| e.ok())
                .filter(|e| e.path().is_dir())
                .map(|e| e.file_name().to_string_lossy().to_string())
                .collect();
            // Sort descending to prefer newer versions
            node_versions.sort_by(|a, b| b.cmp(a));
            for version in node_versions {
                candidates.push(format!("{}/{}/bin/claude", nvm_versions_dir, version));
            }
        }

        // 4. Check npm global
        candidates.push(format!("{}/.npm-global/bin/claude", home));
    }

    // Try each candidate
    for candidate in &candidates {
        if verify_binary(candidate) {
            debug!("Found claude at: {}", candidate);
            return Some(candidate.clone());
        }
    }

    None
}

/// Verify a binary exists and runs successfully.
fn verify_binary(path: &str) -> bool {
    std::process::Command::new(path)
        .arg("--version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Strip ANSI escape codes from output.
fn strip_ansi_codes(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();

    while let Some(c) = chars.next() {
        if c == '\x1b' {
            // Skip escape sequence
            if chars.peek() == Some(&'[') {
                chars.next(); // consume '['
                // Skip until we hit a letter (end of escape sequence)
                while let Some(&next) = chars.peek() {
                    chars.next();
                    if next.is_ascii_alphabetic() {
                        break;
                    }
                }
            }
        } else {
            result.push(c);
        }
    }

    result
}

/// Extract JSON from a response that might have extra text.
fn extract_json(response: &str) -> Option<String> {
    // Look for JSON object boundaries
    let start = response.find('{')?;
    let end = response.rfind('}')?;

    if end > start {
        Some(response[start..=end].to_string())
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_llm_config_default() {
        let config = LlmConfig::default();
        assert!(config.fallback_enabled);
        assert_eq!(config.model, "sonnet");
        assert_eq!(config.timeout, Duration::from_secs(900));
    }

    #[test]
    fn test_parse_response_valid() {
        let engine = LlmDecisionEngine::with_defaults();
        let response =
            r#"{"decision_type": "work_on_tasks", "reasoning": "Need money", "confidence": 0.8}"#;
        let decision = engine.parse_decision_response(response).unwrap();
        assert!(matches!(decision.decision_type, DecisionType::WorkOnTasks));
        assert_eq!(decision.confidence, 0.8);
    }

    #[test]
    fn test_parse_response_with_markdown() {
        let engine = LlmDecisionEngine::with_defaults();
        let response = r#"Here is my decision:
```json
{"decision_type": "purchase_compute", "reasoning": "Low hours", "confidence": 0.9, "hours": 12.0}
```"#;
        let decision = engine.parse_decision_response(response).unwrap();
        assert!(matches!(
            decision.decision_type,
            DecisionType::PurchaseCompute { hours } if (hours - 12.0).abs() < 0.001
        ));
    }

    #[test]
    fn test_parse_response_invalid() {
        let engine = LlmDecisionEngine::with_defaults();
        let response = "This is not JSON";
        assert!(engine.parse_decision_response(response).is_none());
    }

    #[test]
    fn test_parse_allocation_response() {
        let engine = LlmDecisionEngine::with_defaults();
        let response = r#"{"task_work": 0.6, "company_work": 0.3, "other": 0.1, "reasoning": "Balanced approach"}"#;
        let allocation = engine.parse_allocation_response(response).unwrap();
        assert!((allocation.task_work - 0.6).abs() < 0.001);
        assert!((allocation.company_work - 0.3).abs() < 0.001);
    }

    #[test]
    fn test_system_prompt_generation() {
        let engine = LlmDecisionEngine::with_defaults();
        let prompt = engine.system_prompt();
        assert!(prompt.contains("autonomous economic agent"));
        assert!(prompt.contains("decision_type"));
    }

    #[test]
    fn test_user_prompt_generation() {
        let engine = LlmDecisionEngine::with_defaults();
        let state = AgentState::new(100.0, 24.0);
        let config = AgentConfig::default();
        let prompt = engine.user_prompt(&state, &config);
        assert!(prompt.contains("Balance: $100.00"));
        assert!(prompt.contains("Compute Hours Remaining: 24.0"));
    }

    #[test]
    fn test_strip_ansi_codes() {
        let input = "\x1b[32mGreen text\x1b[0m and normal";
        let output = strip_ansi_codes(input);
        assert_eq!(output, "Green text and normal");
    }

    #[test]
    fn test_extract_json() {
        let input = "Here is the response: {\"key\": \"value\"} and more text";
        let json = extract_json(input).unwrap();
        assert_eq!(json, r#"{"key": "value"}"#);
    }

    #[test]
    fn test_extract_json_nested() {
        let input = r#"{"outer": {"inner": "value"}}"#;
        let json = extract_json(input).unwrap();
        assert_eq!(json, input);
    }

    #[tokio::test]
    async fn test_fallback_when_no_claude() {
        let engine = LlmDecisionEngine::with_defaults();
        let state = AgentState::new(100.0, 24.0);
        let config = AgentConfig::default();

        // If Claude is not available, should fall back to rule-based engine
        let decision = engine.decide(&state, &config).await.unwrap();
        assert!(decision.confidence > 0.0);
    }

    #[test]
    fn test_find_claude_binary() {
        // This test just verifies the function runs without panicking
        let _ = find_claude_binary();
    }

    #[test]
    fn test_decision_type_parsing_variants() {
        let engine = LlmDecisionEngine::with_defaults();

        // Test various formats
        let test_cases = vec![
            (
                r#"{"decision_type": "work_on_tasks", "reasoning": "test", "confidence": 0.5}"#,
                DecisionType::WorkOnTasks,
            ),
            (
                r#"{"decision_type": "WorkOnTasks", "reasoning": "test", "confidence": 0.5}"#,
                DecisionType::WorkOnTasks,
            ),
            (
                r#"{"decision_type": "WORK_ON_TASKS", "reasoning": "test", "confidence": 0.5}"#,
                DecisionType::WorkOnTasks,
            ),
            (
                r#"{"decision_type": "wait", "reasoning": "test", "confidence": 0.5}"#,
                DecisionType::Wait,
            ),
        ];

        for (input, expected_type) in test_cases {
            let decision = engine.parse_decision_response(input).unwrap();
            assert_eq!(
                std::mem::discriminant(&decision.decision_type),
                std::mem::discriminant(&expected_type),
                "Failed for input: {}",
                input
            );
        }
    }
}
