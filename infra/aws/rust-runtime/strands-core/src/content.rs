//! Content block types for multi-modal conversations.
//!
//! Models the content types supported by AWS Bedrock Converse API,
//! including text, images, documents, tool use, and tool results.

use bytes::Bytes;
use serde::{Deserialize, Serialize};

/// A content block within a message.
///
/// Messages contain a list of content blocks, each representing
/// different types of content (text, images, tool calls, etc.).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum ContentBlock {
    /// Plain text content
    Text(String),

    /// Image content with binary data
    Image(ImageContent),

    /// Document content (PDF, etc.)
    Document(DocumentContent),

    /// A request to use a tool
    ToolUse(ToolUseContent),

    /// The result of a tool execution
    ToolResult(ToolResultContent),

    /// Model reasoning/thinking content
    Reasoning(ReasoningContent),

    /// Guardrail evaluation content
    Guard(GuardContent),
}

impl ContentBlock {
    /// Create a text content block.
    pub fn text(text: impl Into<String>) -> Self {
        Self::Text(text.into())
    }

    /// Create a tool use content block.
    pub fn tool_use(id: impl Into<String>, name: impl Into<String>, input: serde_json::Value) -> Self {
        Self::ToolUse(ToolUseContent {
            tool_use_id: id.into(),
            name: name.into(),
            input,
        })
    }

    /// Create a tool result content block.
    pub fn tool_result(
        tool_use_id: impl Into<String>,
        content: Vec<ToolResultContentBlock>,
        status: ToolResultStatus,
    ) -> Self {
        Self::ToolResult(ToolResultContent {
            tool_use_id: tool_use_id.into(),
            content,
            status,
        })
    }

    /// Extract text if this is a text block.
    pub fn as_text(&self) -> Option<&str> {
        match self {
            Self::Text(t) => Some(t),
            _ => None,
        }
    }

    /// Extract tool use if this is a tool use block.
    pub fn as_tool_use(&self) -> Option<&ToolUseContent> {
        match self {
            Self::ToolUse(t) => Some(t),
            _ => None,
        }
    }

    /// Check if this is a tool use block.
    pub fn is_tool_use(&self) -> bool {
        matches!(self, Self::ToolUse(_))
    }
}

/// Image content with format and data.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ImageContent {
    /// Image format (png, jpeg, gif, webp)
    pub format: ImageFormat,

    /// Image data source
    pub source: ImageSource,
}

/// Supported image formats.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ImageFormat {
    Png,
    Jpeg,
    Gif,
    Webp,
}

/// Image data source.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum ImageSource {
    /// Base64-encoded image bytes
    Bytes(#[serde(with = "base64_bytes")] Bytes),
}

/// Document content.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct DocumentContent {
    /// Document format
    pub format: DocumentFormat,

    /// Document name
    pub name: String,

    /// Document data source
    pub source: DocumentSource,
}

/// Supported document formats.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum DocumentFormat {
    Pdf,
    Csv,
    Doc,
    Docx,
    Xls,
    Xlsx,
    Html,
    Txt,
    Md,
}

/// Document data source.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum DocumentSource {
    /// Base64-encoded document bytes
    Bytes(#[serde(with = "base64_bytes")] Bytes),
}

/// Tool use request from the model.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ToolUseContent {
    /// Unique identifier for this tool use
    pub tool_use_id: String,

    /// Name of the tool to invoke
    pub name: String,

    /// Input parameters as JSON
    pub input: serde_json::Value,
}

/// Result of a tool execution.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ToolResultContent {
    /// The tool use ID this result corresponds to
    pub tool_use_id: String,

    /// Result content blocks
    pub content: Vec<ToolResultContentBlock>,

    /// Execution status
    pub status: ToolResultStatus,
}

/// Content within a tool result.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum ToolResultContentBlock {
    /// Text result
    Text(String),

    /// JSON result
    Json(serde_json::Value),

    /// Image result
    Image(ImageContent),

    /// Document result
    Document(DocumentContent),
}

impl ToolResultContentBlock {
    /// Create a text result.
    pub fn text(text: impl Into<String>) -> Self {
        Self::Text(text.into())
    }

    /// Create a JSON result.
    pub fn json(value: serde_json::Value) -> Self {
        Self::Json(value)
    }
}

/// Tool execution status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Default)]
#[serde(rename_all = "lowercase")]
pub enum ToolResultStatus {
    /// Tool executed successfully
    #[default]
    Success,

    /// Tool execution failed
    Error,
}

/// Model reasoning/thinking content.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ReasoningContent {
    /// The reasoning text
    pub text: String,

    /// Optional signature for verification
    #[serde(skip_serializing_if = "Option::is_none")]
    pub signature: Option<String>,
}

/// Guardrail content for evaluation.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct GuardContent {
    /// Text to evaluate
    pub text: String,

    /// Qualifiers for the content
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub qualifiers: Vec<String>,
}

/// System prompt content block.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct SystemContent {
    /// System prompt text
    pub text: String,

    /// Optional cache point for conversation optimization
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cache_point: Option<CachePoint>,
}

/// Cache point for conversation history optimization.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct CachePoint {
    /// Cache type
    #[serde(rename = "type")]
    pub cache_type: CacheType,
}

/// Types of caching.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CacheType {
    /// Default caching behavior
    Default,
}

/// Streaming delta content.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum DeltaContent {
    /// Partial text
    Text(String),

    /// Partial tool use
    ToolUse {
        /// Partial input JSON
        input: String,
    },

    /// Reasoning delta
    Reasoning {
        /// Partial reasoning text
        text: String,
    },
}

// Helper module for base64 serialization of bytes
mod base64_bytes {
    use base64::{engine::general_purpose::STANDARD, Engine};
    use bytes::Bytes;
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(bytes: &Bytes, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&STANDARD.encode(bytes))
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Bytes, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        STANDARD
            .decode(s)
            .map(Bytes::from)
            .map_err(serde::de::Error::custom)
    }
}
