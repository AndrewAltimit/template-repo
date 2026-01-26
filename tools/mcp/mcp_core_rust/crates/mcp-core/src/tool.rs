//! Tool trait and related types for MCP servers.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;

use crate::error::Result;

/// Content types that can be returned from a tool
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Content {
    /// Text content
    Text {
        /// The text content
        text: String,
    },
    /// Image content (base64 encoded)
    Image {
        /// Base64 encoded image data
        data: String,
        /// MIME type of the image
        #[serde(rename = "mimeType")]
        mime_type: String,
    },
    /// Resource reference
    Resource {
        /// URI of the resource
        uri: String,
        /// MIME type of the resource
        #[serde(rename = "mimeType")]
        mime_type: String,
    },
}

impl Content {
    /// Create text content
    pub fn text(text: impl Into<String>) -> Self {
        Self::Text { text: text.into() }
    }

    /// Create text content from a serializable value (JSON formatted)
    pub fn json<T: Serialize>(value: &T) -> Result<Self> {
        let text = serde_json::to_string_pretty(value)?;
        Ok(Self::text(text))
    }
}

/// Result of a tool execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    /// Content returned by the tool
    pub content: Vec<Content>,
    /// Whether the result represents an error
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    #[serde(rename = "isError")]
    pub is_error: bool,
}

impl ToolResult {
    /// Create a successful result with text content
    pub fn text(text: impl Into<String>) -> Self {
        Self {
            content: vec![Content::text(text)],
            is_error: false,
        }
    }

    /// Create a successful result with JSON content
    pub fn json<T: Serialize>(value: &T) -> Result<Self> {
        Ok(Self {
            content: vec![Content::json(value)?],
            is_error: false,
        })
    }

    /// Create an error result
    pub fn error(message: impl Into<String>) -> Self {
        Self {
            content: vec![Content::text(message)],
            is_error: true,
        }
    }

    /// Create a result with multiple content items
    pub fn with_content(content: Vec<Content>) -> Self {
        Self {
            content,
            is_error: false,
        }
    }
}

/// Tool schema information for MCP protocol
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolSchema {
    /// Tool name
    pub name: String,
    /// Tool description
    pub description: String,
    /// JSON Schema for input parameters
    #[serde(rename = "inputSchema")]
    pub input_schema: Value,
}

/// A single MCP tool that can be executed
#[async_trait]
pub trait Tool: Send + Sync {
    /// Get the tool's unique name
    fn name(&self) -> &str;

    /// Get the tool's description
    fn description(&self) -> &str;

    /// Get the JSON Schema for the tool's parameters
    fn schema(&self) -> Value;

    /// Execute the tool with the given arguments
    async fn execute(&self, args: Value) -> Result<ToolResult>;

    /// Get the full tool schema for MCP protocol
    fn tool_schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().to_string(),
            description: self.description().to_string(),
            input_schema: self.schema(),
        }
    }
}

/// Type alias for a boxed tool
pub type BoxedTool = Arc<dyn Tool>;

/// Registry for managing MCP tools
#[derive(Default)]
pub struct ToolRegistry {
    tools: HashMap<String, BoxedTool>,
}

impl ToolRegistry {
    /// Create a new empty tool registry
    pub fn new() -> Self {
        Self::default()
    }

    /// Register a tool in the registry
    pub fn register<T: Tool + 'static>(&mut self, tool: T) {
        let name = tool.name().to_string();
        self.tools.insert(name, Arc::new(tool));
    }

    /// Register a boxed tool in the registry
    pub fn register_boxed(&mut self, tool: BoxedTool) {
        let name = tool.name().to_string();
        self.tools.insert(name, tool);
    }

    /// Get a tool by name
    pub fn get(&self, name: &str) -> Option<&BoxedTool> {
        self.tools.get(name)
    }

    /// List all registered tools
    pub fn list(&self) -> Vec<ToolSchema> {
        self.tools.values().map(|t| t.tool_schema()).collect()
    }

    /// Get tool names
    pub fn names(&self) -> Vec<&str> {
        self.tools.keys().map(String::as_str).collect()
    }

    /// Check if a tool exists
    pub fn contains(&self, name: &str) -> bool {
        self.tools.contains_key(name)
    }

    /// Get the number of registered tools
    pub fn len(&self) -> usize {
        self.tools.len()
    }

    /// Check if the registry is empty
    pub fn is_empty(&self) -> bool {
        self.tools.is_empty()
    }
}

/// Builder for creating tools with closures (useful for simple tools)
pub struct FnTool<F>
where
    F: Fn(Value) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<ToolResult>> + Send>>
        + Send
        + Sync,
{
    name: String,
    description: String,
    schema: Value,
    handler: F,
}

impl<F> FnTool<F>
where
    F: Fn(Value) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<ToolResult>> + Send>>
        + Send
        + Sync,
{
    /// Create a new function-based tool
    pub fn new(
        name: impl Into<String>,
        description: impl Into<String>,
        schema: Value,
        handler: F,
    ) -> Self {
        Self {
            name: name.into(),
            description: description.into(),
            schema,
            handler,
        }
    }
}

#[async_trait]
impl<F> Tool for FnTool<F>
where
    F: Fn(Value) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<ToolResult>> + Send>>
        + Send
        + Sync,
{
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        &self.description
    }

    fn schema(&self) -> Value {
        self.schema.clone()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        (self.handler)(args).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    struct EchoTool;

    #[async_trait]
    impl Tool for EchoTool {
        fn name(&self) -> &str {
            "echo"
        }

        fn description(&self) -> &str {
            "Echo the input message"
        }

        fn schema(&self) -> Value {
            json!({
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo"
                    }
                },
                "required": ["message"]
            })
        }

        async fn execute(&self, args: Value) -> Result<ToolResult> {
            let message = args
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("no message");
            Ok(ToolResult::text(format!("Echo: {message}")))
        }
    }

    #[test]
    fn test_tool_registry() {
        let mut registry = ToolRegistry::new();
        registry.register(EchoTool);

        assert!(registry.contains("echo"));
        assert_eq!(registry.len(), 1);

        let tools = registry.list();
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].name, "echo");
    }

    #[tokio::test]
    async fn test_tool_execution() {
        let tool = EchoTool;
        let result = tool.execute(json!({"message": "hello"})).await.unwrap();

        assert!(!result.is_error);
        assert_eq!(result.content.len(), 1);

        if let Content::Text { text } = &result.content[0] {
            assert_eq!(text, "Echo: hello");
        } else {
            panic!("Expected text content");
        }
    }
}
