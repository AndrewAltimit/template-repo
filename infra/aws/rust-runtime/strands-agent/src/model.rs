//! Model provider trait.
//!
//! Defines the interface that model providers (Bedrock, OpenAI, etc.)
//! must implement to work with the agent framework.

use async_trait::async_trait;
use futures::Stream;
use std::pin::Pin;

use strands_core::{Message, Messages, Result, StopReason, SystemPrompt, ToolConfig, Usage};

/// Response from a model invocation.
#[derive(Debug, Clone)]
pub struct ModelResponse {
    /// The assistant's response message
    pub message: Message,

    /// Why the model stopped generating
    pub stop_reason: StopReason,

    /// Token usage for this response
    pub usage: Usage,
}

/// Streaming chunk from a model.
#[derive(Debug, Clone)]
pub enum ModelStreamChunk {
    /// Partial text content
    TextDelta(String),

    /// Tool use block started
    ToolUseStart { tool_use_id: String, name: String },

    /// Partial tool input
    ToolInputDelta {
        tool_use_id: String,
        input_delta: String,
    },

    /// Tool use block completed
    ToolUseEnd {
        tool_use_id: String,
        input: serde_json::Value,
    },

    /// Reasoning/thinking content
    ReasoningDelta(String),

    /// Message completed
    MessageComplete {
        message: Message,
        stop_reason: StopReason,
    },

    /// Usage metrics
    Usage(Usage),
}

/// A stream of model response chunks.
pub type ModelStream = Pin<Box<dyn Stream<Item = Result<ModelStreamChunk>> + Send>>;

/// Configuration for model inference.
#[derive(Debug, Clone, Default)]
pub struct InferenceConfig {
    /// Maximum tokens to generate
    pub max_tokens: Option<u32>,

    /// Temperature for sampling (0.0 - 1.0)
    pub temperature: Option<f32>,

    /// Top-p sampling parameter
    pub top_p: Option<f32>,

    /// Stop sequences
    pub stop_sequences: Vec<String>,
}

impl InferenceConfig {
    /// Create a new inference config with default values.
    pub fn new() -> Self {
        Self::default()
    }

    /// Set max tokens.
    pub fn with_max_tokens(mut self, max_tokens: u32) -> Self {
        self.max_tokens = Some(max_tokens);
        self
    }

    /// Set temperature.
    pub fn with_temperature(mut self, temperature: f32) -> Self {
        self.temperature = Some(temperature);
        self
    }

    /// Set top-p.
    pub fn with_top_p(mut self, top_p: f32) -> Self {
        self.top_p = Some(top_p);
        self
    }

    /// Add a stop sequence.
    pub fn with_stop_sequence(mut self, sequence: impl Into<String>) -> Self {
        self.stop_sequences.push(sequence.into());
        self
    }
}

/// Request to a model.
#[derive(Debug, Clone)]
pub struct ModelRequest {
    /// Conversation messages
    pub messages: Messages,

    /// System prompt
    pub system: SystemPrompt,

    /// Tool configuration
    pub tools: ToolConfig,

    /// Inference parameters
    pub inference_config: InferenceConfig,
}

impl ModelRequest {
    /// Create a new model request.
    pub fn new(messages: Messages) -> Self {
        Self {
            messages,
            system: SystemPrompt::empty(),
            tools: ToolConfig::empty(),
            inference_config: InferenceConfig::default(),
        }
    }

    /// Set the system prompt.
    pub fn with_system(mut self, system: SystemPrompt) -> Self {
        self.system = system;
        self
    }

    /// Set the tool configuration.
    pub fn with_tools(mut self, tools: ToolConfig) -> Self {
        self.tools = tools;
        self
    }

    /// Set the inference config.
    pub fn with_inference_config(mut self, config: InferenceConfig) -> Self {
        self.inference_config = config;
        self
    }
}

/// Trait for model providers.
///
/// Implement this trait to add support for new model providers
/// (e.g., Bedrock, OpenAI, Anthropic API directly, etc.).
#[async_trait]
pub trait Model: Send + Sync {
    /// Get the model identifier.
    fn model_id(&self) -> &str;

    /// Invoke the model and return a complete response.
    ///
    /// This is a convenience method that collects the stream into a single response.
    async fn invoke(&self, request: ModelRequest) -> Result<ModelResponse>;

    /// Invoke the model and return a stream of response chunks.
    ///
    /// This is the primary method for streaming responses.
    async fn stream(&self, request: ModelRequest) -> Result<ModelStream>;
}

/// Type alias for a boxed model provider.
pub type BoxedModel = Box<dyn Model>;
