//! Streaming event types for agent responses.
//!
//! These events are emitted during agent execution to provide
//! real-time visibility into the agent's actions.

use crate::content::{ContentBlock, ToolResultContentBlock};
use crate::message::{Message, StopReason, Usage};
use serde::{Deserialize, Serialize};

/// Events emitted during agent execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum AgentEvent {
    /// Agent has started processing
    Start {
        /// Unique invocation ID
        invocation_id: String,
    },

    /// Streaming text content
    TextDelta {
        /// Partial text content
        text: String,
    },

    /// A complete content block was generated
    ContentBlock {
        /// The content block
        block: ContentBlock,
    },

    /// Tool execution is starting
    ToolStart {
        /// Tool use ID
        tool_use_id: String,

        /// Tool name
        name: String,

        /// Tool input
        input: serde_json::Value,
    },

    /// Tool execution completed
    ToolEnd {
        /// Tool use ID
        tool_use_id: String,

        /// Tool name
        name: String,

        /// Execution result
        result: Vec<ToolResultContentBlock>,

        /// Whether execution succeeded
        success: bool,
    },

    /// Model thinking/reasoning content
    Reasoning {
        /// Reasoning text
        text: String,
    },

    /// Message completed
    MessageComplete {
        /// The complete message
        message: Message,

        /// Why the model stopped
        stop_reason: StopReason,
    },

    /// Token usage metrics
    Metrics {
        /// Usage statistics
        usage: Usage,
    },

    /// Agent completed successfully
    Complete {
        /// Final message
        message: Message,

        /// Stop reason
        stop_reason: StopReason,

        /// Total usage across all iterations
        total_usage: Usage,

        /// Number of iterations (model calls)
        iterations: u32,
    },

    /// An error occurred
    Error {
        /// Error message
        message: String,

        /// Error code for categorization
        code: Option<String>,

        /// Whether the error is retryable
        retryable: bool,
    },

    /// Content was redacted by guardrails
    Redacted {
        /// Redaction reason
        reason: String,

        /// The redacted content (replacement)
        content: String,
    },
}

impl AgentEvent {
    /// Create a start event.
    pub fn start(invocation_id: impl Into<String>) -> Self {
        Self::Start {
            invocation_id: invocation_id.into(),
        }
    }

    /// Create a text delta event.
    pub fn text_delta(text: impl Into<String>) -> Self {
        Self::TextDelta { text: text.into() }
    }

    /// Create a content block event.
    pub fn content_block(block: ContentBlock) -> Self {
        Self::ContentBlock { block }
    }

    /// Create a tool start event.
    pub fn tool_start(
        tool_use_id: impl Into<String>,
        name: impl Into<String>,
        input: serde_json::Value,
    ) -> Self {
        Self::ToolStart {
            tool_use_id: tool_use_id.into(),
            name: name.into(),
            input,
        }
    }

    /// Create a tool end event.
    pub fn tool_end(
        tool_use_id: impl Into<String>,
        name: impl Into<String>,
        result: Vec<ToolResultContentBlock>,
        success: bool,
    ) -> Self {
        Self::ToolEnd {
            tool_use_id: tool_use_id.into(),
            name: name.into(),
            result,
            success,
        }
    }

    /// Create a message complete event.
    pub fn message_complete(message: Message, stop_reason: StopReason) -> Self {
        Self::MessageComplete {
            message,
            stop_reason,
        }
    }

    /// Create a metrics event.
    pub fn metrics(usage: Usage) -> Self {
        Self::Metrics { usage }
    }

    /// Create a complete event.
    pub fn complete(
        message: Message,
        stop_reason: StopReason,
        total_usage: Usage,
        iterations: u32,
    ) -> Self {
        Self::Complete {
            message,
            stop_reason,
            total_usage,
            iterations,
        }
    }

    /// Create an error event.
    pub fn error(message: impl Into<String>, retryable: bool) -> Self {
        Self::Error {
            message: message.into(),
            code: None,
            retryable,
        }
    }

    /// Create an error event with code.
    pub fn error_with_code(
        message: impl Into<String>,
        code: impl Into<String>,
        retryable: bool,
    ) -> Self {
        Self::Error {
            message: message.into(),
            code: Some(code.into()),
            retryable,
        }
    }

    /// Check if this is an error event.
    pub fn is_error(&self) -> bool {
        matches!(self, Self::Error { .. })
    }

    /// Check if this is a terminal event.
    pub fn is_terminal(&self) -> bool {
        matches!(self, Self::Complete { .. } | Self::Error { .. })
    }
}

/// Type alias for an event stream.
pub type EventStream = std::pin::Pin<
    Box<dyn futures::Stream<Item = AgentEvent> + Send>,
>;
