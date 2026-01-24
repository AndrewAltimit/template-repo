//! Runtime configuration.

use std::env;

/// Runtime configuration loaded from environment variables.
#[derive(Debug, Clone)]
pub struct RuntimeConfig {
    /// Server port
    pub port: u16,
    /// Bedrock model ID
    pub model_id: String,
    /// AWS region
    pub region: String,
    /// System prompt for the agent
    pub system_prompt: Option<String>,
    /// Maximum iterations per request
    pub max_iterations: u32,
    /// Maximum tokens for model responses
    pub max_tokens: u32,
    /// OpenTelemetry endpoint (optional)
    pub otel_endpoint: Option<String>,
    /// Service name for tracing
    pub service_name: String,
    /// Enable request logging
    pub log_requests: bool,
}

impl RuntimeConfig {
    /// Load configuration from environment variables.
    pub fn from_env() -> Self {
        Self {
            port: env::var("PORT")
                .ok()
                .and_then(|p| p.parse().ok())
                .unwrap_or(8080),

            model_id: env::var("MODEL_ID")
                .unwrap_or_else(|_| "us.anthropic.claude-sonnet-4-20250514-v1:0".to_string()),

            region: env::var("AWS_REGION")
                .or_else(|_| env::var("AWS_DEFAULT_REGION"))
                .unwrap_or_else(|_| "us-east-1".to_string()),

            system_prompt: env::var("SYSTEM_PROMPT").ok(),

            max_iterations: env::var("MAX_ITERATIONS")
                .ok()
                .and_then(|p| p.parse().ok())
                .unwrap_or(10),

            max_tokens: env::var("MAX_TOKENS")
                .ok()
                .and_then(|p| p.parse().ok())
                .unwrap_or(4096),

            otel_endpoint: env::var("OTEL_EXPORTER_OTLP_ENDPOINT").ok(),

            service_name: env::var("OTEL_SERVICE_NAME")
                .unwrap_or_else(|_| "strands-runtime".to_string()),

            log_requests: env::var("LOG_REQUESTS")
                .map(|v| v == "true" || v == "1")
                .unwrap_or(true),
        }
    }

    /// Create a configuration for testing.
    #[cfg(test)]
    pub fn test_config() -> Self {
        Self {
            port: 8080,
            model_id: "test-model".to_string(),
            region: "us-east-1".to_string(),
            system_prompt: None,
            max_iterations: 5,
            max_tokens: 1024,
            otel_endpoint: None,
            service_name: "test-runtime".to_string(),
            log_requests: false,
        }
    }
}

impl Default for RuntimeConfig {
    fn default() -> Self {
        Self::from_env()
    }
}
