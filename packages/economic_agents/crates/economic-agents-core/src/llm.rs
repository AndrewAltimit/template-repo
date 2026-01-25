//! LLM-powered decision engine.
//!
//! This module provides an LLM-based decision engine that uses language models
//! to make decisions about agent actions. It supports configurable prompts,
//! fallback behavior, and integration with various LLM providers.

use std::time::Duration;

use async_trait::async_trait;
use economic_agents_interfaces::Result;
use serde::{Deserialize, Serialize};
use tracing::{debug, info, warn};

use crate::config::{AgentConfig, Personality};
use crate::decision::{Decision, DecisionEngine, DecisionType, ResourceAllocation, RuleBasedEngine};
use crate::state::AgentState;

/// Configuration for the LLM decision engine.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmConfig {
    /// Model identifier (e.g., "claude-3-sonnet", "gpt-4").
    pub model: String,
    /// API endpoint URL.
    pub api_url: String,
    /// API key (should be loaded from environment in production).
    #[serde(skip_serializing)]
    pub api_key: Option<String>,
    /// Request timeout.
    #[serde(with = "humantime_serde")]
    pub timeout: Duration,
    /// Maximum tokens in response.
    pub max_tokens: u32,
    /// Temperature for sampling (0.0-1.0).
    pub temperature: f64,
    /// Whether to enable fallback to rule-based engine.
    pub fallback_enabled: bool,
    /// Custom system prompt override.
    pub system_prompt: Option<String>,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            model: "claude-3-sonnet-20240229".to_string(),
            api_url: "https://api.anthropic.com/v1/messages".to_string(),
            api_key: None,
            timeout: Duration::from_secs(30),
            max_tokens: 1024,
            temperature: 0.7,
            fallback_enabled: true,
            system_prompt: None,
        }
    }
}

/// LLM-powered decision engine.
///
/// Uses a language model to make decisions based on the current agent state.
/// Falls back to rule-based decisions if the LLM is unavailable or fails.
pub struct LlmDecisionEngine {
    /// LLM configuration.
    config: LlmConfig,
    /// Fallback rule-based engine.
    fallback: RuleBasedEngine,
    /// HTTP client for API calls.
    #[allow(dead_code)]
    client: reqwest::Client,
}

impl LlmDecisionEngine {
    /// Create a new LLM decision engine with the given configuration.
    pub fn new(config: LlmConfig) -> Self {
        let client = reqwest::Client::builder()
            .timeout(config.timeout)
            .build()
            .expect("Failed to create HTTP client");

        Self {
            config,
            fallback: RuleBasedEngine::new(),
            client,
        }
    }

    /// Create with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(LlmConfig::default())
    }

    /// Set the API key.
    pub fn with_api_key(mut self, key: impl Into<String>) -> Self {
        self.config.api_key = Some(key.into());
        self
    }

    /// Generate the system prompt for decision making.
    fn system_prompt(&self) -> String {
        self.config.system_prompt.clone().unwrap_or_else(|| {
            r#"You are an autonomous economic agent decision engine. Your role is to analyze the agent's current state and make strategic decisions.

You must respond with a JSON object containing:
- "decision_type": One of "work_on_tasks", "purchase_compute", "work_on_company", "seek_investment", or "wait"
- "reasoning": A brief explanation of your decision
- "confidence": A number between 0 and 1 indicating your confidence
- "hours" (optional): If decision_type is "purchase_compute", the number of hours to purchase

Consider these factors:
1. Survival: If compute hours are low, prioritize earning money or purchasing compute
2. Growth: If financially stable, consider company formation
3. Risk: Adjust strategy based on agent personality (risk_averse, balanced, aggressive)
4. Efficiency: Choose tasks with good reward-to-effort ratios

Be strategic and consider long-term sustainability."#.to_string()
        })
    }

    /// Generate the user prompt with current state.
    fn user_prompt(&self, state: &AgentState, config: &AgentConfig) -> String {
        format!(
            r#"Current Agent State:
- Balance: ${:.2}
- Compute Hours: {:.1}
- Tasks Completed: {}
- Tasks Failed: {}
- Total Earnings: ${:.2}
- Has Company: {}
- Reputation: {:.2}
- Current Cycle: {}

Agent Configuration:
- Personality: {:?}
- Survival Buffer: {:.1} hours
- Company Threshold: ${:.2}

Based on this state, what decision should the agent make?"#,
            state.balance,
            state.compute_hours,
            state.tasks_completed,
            state.tasks_failed,
            state.total_earnings,
            state.has_company,
            state.reputation,
            state.current_cycle,
            config.personality,
            config.survival_buffer_hours,
            config.company_threshold
        )
    }

    /// Parse the LLM response into a Decision.
    fn parse_response(&self, response: &str) -> Option<Decision> {
        // Try to parse as JSON
        #[derive(Deserialize)]
        struct LlmResponse {
            decision_type: String,
            reasoning: String,
            confidence: f64,
            hours: Option<f64>,
        }

        // Extract JSON from response (it might be wrapped in markdown code blocks)
        let json_str = if let Some(start) = response.find('{') {
            if let Some(end) = response.rfind('}') {
                &response[start..=end]
            } else {
                response
            }
        } else {
            response
        };

        let parsed: LlmResponse = serde_json::from_str(json_str).ok()?;

        let decision_type = match parsed.decision_type.to_lowercase().as_str() {
            "work_on_tasks" | "workontasks" => DecisionType::WorkOnTasks,
            "purchase_compute" | "purchasecompute" => {
                DecisionType::PurchaseCompute {
                    hours: parsed.hours.unwrap_or(24.0),
                }
            }
            "work_on_company" | "workoncompany" => DecisionType::WorkOnCompany,
            "seek_investment" | "seekinvestment" => DecisionType::SeekInvestment,
            "wait" => DecisionType::Wait,
            _ => return None,
        };

        Some(Decision {
            decision_type,
            reasoning: parsed.reasoning,
            confidence: parsed.confidence.clamp(0.0, 1.0),
        })
    }

    /// Call the LLM API (placeholder - needs actual implementation).
    #[allow(dead_code)]
    async fn call_llm(&self, _state: &AgentState, _config: &AgentConfig) -> Result<String> {
        // This is a placeholder. In production, this would:
        // 1. Build the API request with system and user prompts
        // 2. Send the request to the LLM provider
        // 3. Parse and return the response
        //
        // For now, we'll return an error to trigger fallback behavior.
        Err(economic_agents_interfaces::EconomicAgentError::Network(
            "LLM API not yet implemented".to_string(),
        ))
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

        // Check if API key is configured
        if self.config.api_key.is_none() {
            if self.config.fallback_enabled {
                info!("No API key configured, using fallback engine");
                return self.fallback.decide(state, config).await;
            } else {
                return Err(economic_agents_interfaces::EconomicAgentError::Configuration(
                    "LLM API key not configured".to_string(),
                ));
            }
        }

        // Try to call the LLM
        match self.call_llm(state, config).await {
            Ok(response) => {
                if let Some(decision) = self.parse_response(&response) {
                    info!(
                        decision_type = ?decision.decision_type,
                        confidence = %decision.confidence,
                        "LLM decision made"
                    );
                    Ok(decision)
                } else if self.config.fallback_enabled {
                    warn!("Failed to parse LLM response, using fallback");
                    self.fallback.decide(state, config).await
                } else {
                    Err(economic_agents_interfaces::EconomicAgentError::Internal(
                        "Failed to parse LLM response".to_string(),
                    ))
                }
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
        // For resource allocation, use a simpler personality-based approach
        // LLM is better suited for strategic decisions
        let base_allocation = self.fallback.allocate_resources(state, config).await?;

        // Adjust based on personality for LLM-driven agents
        let adjusted = match config.personality {
            Personality::RiskAverse => ResourceAllocation {
                task_work: (base_allocation.task_work + 0.1).min(1.0),
                company_work: (base_allocation.company_work - 0.05).max(0.0),
                other: base_allocation.other,
            },
            Personality::Aggressive => ResourceAllocation {
                task_work: (base_allocation.task_work - 0.1).max(0.2),
                company_work: (base_allocation.company_work + 0.1).min(0.7),
                other: base_allocation.other,
            },
            Personality::Balanced => base_allocation,
        };

        Ok(adjusted)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_llm_config_default() {
        let config = LlmConfig::default();
        assert!(config.fallback_enabled);
        assert_eq!(config.temperature, 0.7);
    }

    #[test]
    fn test_parse_response_valid() {
        let engine = LlmDecisionEngine::with_defaults();
        let response = r#"{"decision_type": "work_on_tasks", "reasoning": "Need money", "confidence": 0.8}"#;
        let decision = engine.parse_response(response).unwrap();
        assert!(matches!(decision.decision_type, DecisionType::WorkOnTasks));
        assert_eq!(decision.confidence, 0.8);
    }

    #[test]
    fn test_parse_response_with_markdown() {
        let engine = LlmDecisionEngine::with_defaults();
        let response = r#"```json
{"decision_type": "purchase_compute", "reasoning": "Low hours", "confidence": 0.9, "hours": 12.0}
```"#;
        let decision = engine.parse_response(response).unwrap();
        assert!(matches!(
            decision.decision_type,
            DecisionType::PurchaseCompute { hours } if (hours - 12.0).abs() < 0.001
        ));
    }

    #[test]
    fn test_parse_response_invalid() {
        let engine = LlmDecisionEngine::with_defaults();
        let response = "This is not JSON";
        assert!(engine.parse_response(response).is_none());
    }

    #[test]
    fn test_system_prompt_generation() {
        let engine = LlmDecisionEngine::with_defaults();
        let prompt = engine.system_prompt();
        assert!(prompt.contains("autonomous economic agent"));
    }

    #[test]
    fn test_user_prompt_generation() {
        let engine = LlmDecisionEngine::with_defaults();
        let state = AgentState::new(100.0, 24.0);
        let config = AgentConfig::default();
        let prompt = engine.user_prompt(&state, &config);
        assert!(prompt.contains("Balance: $100.00"));
        assert!(prompt.contains("Compute Hours: 24.0"));
    }

    #[tokio::test]
    async fn test_fallback_when_no_api_key() {
        let engine = LlmDecisionEngine::with_defaults();
        let state = AgentState::new(100.0, 24.0);
        let config = AgentConfig::default();

        // Should fall back to rule-based engine
        let decision = engine.decide(&state, &config).await.unwrap();
        assert!(decision.confidence > 0.0);
    }
}
