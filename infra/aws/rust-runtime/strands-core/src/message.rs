//! Message types for agent conversations.
//!
//! Models the conversation structure used in agent interactions,
//! following the Bedrock Converse API message format.

use crate::content::{ContentBlock, SystemContent};
use serde::{Deserialize, Serialize};

/// A message in a conversation.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Message {
    /// The role of the message sender
    pub role: Role,

    /// Content blocks within the message
    pub content: Vec<ContentBlock>,
}

impl Message {
    /// Create a new user message with text content.
    pub fn user(text: impl Into<String>) -> Self {
        Self {
            role: Role::User,
            content: vec![ContentBlock::text(text)],
        }
    }

    /// Create a new user message with multiple content blocks.
    pub fn user_with_content(content: Vec<ContentBlock>) -> Self {
        Self {
            role: Role::User,
            content,
        }
    }

    /// Create a new assistant message with text content.
    pub fn assistant(text: impl Into<String>) -> Self {
        Self {
            role: Role::Assistant,
            content: vec![ContentBlock::text(text)],
        }
    }

    /// Create a new assistant message with multiple content blocks.
    pub fn assistant_with_content(content: Vec<ContentBlock>) -> Self {
        Self {
            role: Role::Assistant,
            content,
        }
    }

    /// Check if this message contains any tool use blocks.
    pub fn has_tool_use(&self) -> bool {
        self.content.iter().any(|c| c.is_tool_use())
    }

    /// Extract all tool use blocks from this message.
    pub fn tool_uses(&self) -> impl Iterator<Item = &crate::content::ToolUseContent> {
        self.content.iter().filter_map(|c| c.as_tool_use())
    }

    /// Extract all text from this message.
    pub fn text(&self) -> String {
        self.content
            .iter()
            .filter_map(|c| c.as_text())
            .collect::<Vec<_>>()
            .join("")
    }

    /// Check if this is a user message.
    pub fn is_user(&self) -> bool {
        self.role == Role::User
    }

    /// Check if this is an assistant message.
    pub fn is_assistant(&self) -> bool {
        self.role == Role::Assistant
    }
}

/// The role of a message sender.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    /// User/human message
    User,

    /// Assistant/model message
    Assistant,
}

impl std::fmt::Display for Role {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Role::User => write!(f, "user"),
            Role::Assistant => write!(f, "assistant"),
        }
    }
}

/// A list of messages representing a conversation.
pub type Messages = Vec<Message>;

/// Reason why the model stopped generating.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum StopReason {
    /// Model completed its response naturally
    EndTurn,

    /// Model wants to use a tool
    ToolUse,

    /// Maximum tokens reached
    MaxTokens,

    /// Content was filtered by guardrails
    ContentFiltered,

    /// Guardrail intervention
    GuardrailIntervened,

    /// Stop sequence encountered
    StopSequence,
}

impl StopReason {
    /// Check if the model wants to continue (i.e., use a tool).
    pub fn wants_to_continue(&self) -> bool {
        matches!(self, StopReason::ToolUse)
    }

    /// Check if this is a terminal stop reason.
    pub fn is_terminal(&self) -> bool {
        !self.wants_to_continue()
    }
}

/// System prompt configuration.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct SystemPrompt {
    /// System prompt content blocks
    pub content: Vec<SystemContent>,
}

impl SystemPrompt {
    /// Create a system prompt from text.
    pub fn new(text: impl Into<String>) -> Self {
        Self {
            content: vec![SystemContent {
                text: text.into(),
                cache_point: None,
            }],
        }
    }

    /// Create an empty system prompt.
    pub fn empty() -> Self {
        Self::default()
    }

    /// Check if the system prompt is empty.
    pub fn is_empty(&self) -> bool {
        self.content.is_empty()
    }

    /// Get the full system prompt text.
    pub fn text(&self) -> String {
        self.content
            .iter()
            .map(|c| c.text.as_str())
            .collect::<Vec<_>>()
            .join("\n")
    }
}

/// Usage metrics for a model response.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Default)]
#[serde(rename_all = "camelCase")]
pub struct Usage {
    /// Number of input tokens processed
    pub input_tokens: u32,

    /// Number of output tokens generated
    pub output_tokens: u32,

    /// Total tokens (input + output)
    pub total_tokens: u32,

    /// Tokens read from cache (if prompt caching enabled)
    #[serde(default)]
    pub cache_read_input_tokens: u32,

    /// Tokens written to cache (if prompt caching enabled)
    #[serde(default)]
    pub cache_write_input_tokens: u32,
}

impl Usage {
    /// Create usage from input and output token counts.
    pub fn new(input_tokens: u32, output_tokens: u32) -> Self {
        Self {
            input_tokens,
            output_tokens,
            total_tokens: input_tokens + output_tokens,
            ..Default::default()
        }
    }

    /// Add another usage to this one.
    pub fn add(&mut self, other: &Usage) {
        self.input_tokens += other.input_tokens;
        self.output_tokens += other.output_tokens;
        self.total_tokens += other.total_tokens;
        self.cache_read_input_tokens += other.cache_read_input_tokens;
        self.cache_write_input_tokens += other.cache_write_input_tokens;
    }
}
