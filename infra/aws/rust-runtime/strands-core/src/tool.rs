//! Tool definition types and execution interfaces.
//!
//! Tools are capabilities that agents can invoke to interact with
//! external systems, perform computations, or access data.

use crate::content::{ToolResultContentBlock, ToolResultStatus};
use crate::error::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// Tool specification for the model.
///
/// Defines the tool's name, description, and input schema following
/// the JSON Schema specification.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ToolSpec {
    /// Unique name of the tool
    pub name: String,

    /// Human-readable description of what the tool does
    pub description: String,

    /// JSON Schema for the tool's input parameters
    pub input_schema: InputSchema,
}

impl ToolSpec {
    /// Create a new tool specification.
    pub fn new(
        name: impl Into<String>,
        description: impl Into<String>,
        input_schema: InputSchema,
    ) -> Self {
        Self {
            name: name.into(),
            description: description.into(),
            input_schema,
        }
    }

    /// Create a tool with no parameters.
    pub fn no_params(name: impl Into<String>, description: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            description: description.into(),
            input_schema: InputSchema::empty(),
        }
    }
}

/// JSON Schema for tool input parameters.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct InputSchema {
    /// Schema type (always "object" for tool inputs)
    #[serde(rename = "type")]
    pub schema_type: String,

    /// Property definitions
    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    pub properties: HashMap<String, PropertySchema>,

    /// Required property names
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub required: Vec<String>,
}

impl InputSchema {
    /// Create an empty schema (tool takes no parameters).
    pub fn empty() -> Self {
        Self {
            schema_type: "object".to_string(),
            properties: HashMap::new(),
            required: Vec::new(),
        }
    }

    /// Create a schema builder.
    pub fn builder() -> InputSchemaBuilder {
        InputSchemaBuilder::new()
    }
}

/// Builder for creating input schemas.
#[derive(Debug, Default)]
pub struct InputSchemaBuilder {
    properties: HashMap<String, PropertySchema>,
    required: Vec<String>,
}

impl InputSchemaBuilder {
    /// Create a new builder.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a string property.
    pub fn string(
        mut self,
        name: impl Into<String>,
        description: impl Into<String>,
        required: bool,
    ) -> Self {
        let name = name.into();
        self.properties.insert(
            name.clone(),
            PropertySchema {
                property_type: "string".to_string(),
                description: description.into(),
                enum_values: None,
                items: None,
            },
        );
        if required {
            self.required.push(name);
        }
        self
    }

    /// Add an integer property.
    pub fn integer(
        mut self,
        name: impl Into<String>,
        description: impl Into<String>,
        required: bool,
    ) -> Self {
        let name = name.into();
        self.properties.insert(
            name.clone(),
            PropertySchema {
                property_type: "integer".to_string(),
                description: description.into(),
                enum_values: None,
                items: None,
            },
        );
        if required {
            self.required.push(name);
        }
        self
    }

    /// Add a number property.
    pub fn number(
        mut self,
        name: impl Into<String>,
        description: impl Into<String>,
        required: bool,
    ) -> Self {
        let name = name.into();
        self.properties.insert(
            name.clone(),
            PropertySchema {
                property_type: "number".to_string(),
                description: description.into(),
                enum_values: None,
                items: None,
            },
        );
        if required {
            self.required.push(name);
        }
        self
    }

    /// Add a boolean property.
    pub fn boolean(
        mut self,
        name: impl Into<String>,
        description: impl Into<String>,
        required: bool,
    ) -> Self {
        let name = name.into();
        self.properties.insert(
            name.clone(),
            PropertySchema {
                property_type: "boolean".to_string(),
                description: description.into(),
                enum_values: None,
                items: None,
            },
        );
        if required {
            self.required.push(name);
        }
        self
    }

    /// Add an enum property.
    pub fn enum_values(
        mut self,
        name: impl Into<String>,
        description: impl Into<String>,
        values: Vec<String>,
        required: bool,
    ) -> Self {
        let name = name.into();
        self.properties.insert(
            name.clone(),
            PropertySchema {
                property_type: "string".to_string(),
                description: description.into(),
                enum_values: Some(values),
                items: None,
            },
        );
        if required {
            self.required.push(name);
        }
        self
    }

    /// Add an array property.
    pub fn array(
        mut self,
        name: impl Into<String>,
        description: impl Into<String>,
        items_type: impl Into<String>,
        required: bool,
    ) -> Self {
        let name = name.into();
        self.properties.insert(
            name.clone(),
            PropertySchema {
                property_type: "array".to_string(),
                description: description.into(),
                enum_values: None,
                items: Some(Box::new(PropertySchema {
                    property_type: items_type.into(),
                    description: String::new(),
                    enum_values: None,
                    items: None,
                })),
            },
        );
        if required {
            self.required.push(name);
        }
        self
    }

    /// Build the input schema.
    pub fn build(self) -> InputSchema {
        InputSchema {
            schema_type: "object".to_string(),
            properties: self.properties,
            required: self.required,
        }
    }
}

/// Schema for a single property.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PropertySchema {
    /// Property type (string, integer, number, boolean, array, object)
    #[serde(rename = "type")]
    pub property_type: String,

    /// Description of the property
    pub description: String,

    /// Allowed values for enum types
    #[serde(rename = "enum", skip_serializing_if = "Option::is_none")]
    pub enum_values: Option<Vec<String>>,

    /// Item schema for array types
    #[serde(skip_serializing_if = "Option::is_none")]
    pub items: Option<Box<PropertySchema>>,
}

/// Result of executing a tool.
#[derive(Debug, Clone)]
pub struct ToolExecutionResult {
    /// The content blocks of the result
    pub content: Vec<ToolResultContentBlock>,

    /// Execution status
    pub status: ToolResultStatus,
}

impl ToolExecutionResult {
    /// Create a successful text result.
    pub fn success_text(text: impl Into<String>) -> Self {
        Self {
            content: vec![ToolResultContentBlock::text(text)],
            status: ToolResultStatus::Success,
        }
    }

    /// Create a successful JSON result.
    pub fn success_json(value: serde_json::Value) -> Self {
        Self {
            content: vec![ToolResultContentBlock::json(value)],
            status: ToolResultStatus::Success,
        }
    }

    /// Create an error result.
    pub fn error(message: impl Into<String>) -> Self {
        Self {
            content: vec![ToolResultContentBlock::text(message)],
            status: ToolResultStatus::Error,
        }
    }
}

/// Context passed to tool execution.
#[derive(Debug, Clone, Default)]
pub struct ToolContext {
    /// Session ID if running within a session
    pub session_id: Option<String>,

    /// Additional context data
    pub metadata: HashMap<String, serde_json::Value>,
}

/// Trait for executable tools.
///
/// Implement this trait to create custom tools that agents can invoke.
#[async_trait]
pub trait Tool: Send + Sync {
    /// Get the tool specification.
    fn spec(&self) -> ToolSpec;

    /// Execute the tool with the given input.
    async fn execute(
        &self,
        input: serde_json::Value,
        context: &ToolContext,
    ) -> Result<ToolExecutionResult>;
}

/// Type alias for a boxed tool.
pub type BoxedTool = Arc<dyn Tool>;

/// Collection of tool specifications for sending to the model.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ToolConfig {
    /// List of available tools
    pub tools: Vec<ToolSpec>,

    /// Tool choice configuration
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_choice: Option<ToolChoice>,
}

impl ToolConfig {
    /// Create an empty tool config.
    pub fn empty() -> Self {
        Self::default()
    }

    /// Create a tool config from specs.
    pub fn from_specs(specs: Vec<ToolSpec>) -> Self {
        Self {
            tools: specs,
            tool_choice: None,
        }
    }

    /// Set the tool choice.
    pub fn with_choice(mut self, choice: ToolChoice) -> Self {
        self.tool_choice = Some(choice);
        self
    }

    /// Check if any tools are available.
    pub fn has_tools(&self) -> bool {
        !self.tools.is_empty()
    }
}

/// Tool choice configuration.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ToolChoice {
    /// Let the model decide whether to use tools
    Auto,

    /// Force the model to use any tool
    Any,

    /// Force the model to use a specific tool
    Tool { name: String },

    /// Don't use any tools
    None,
}
