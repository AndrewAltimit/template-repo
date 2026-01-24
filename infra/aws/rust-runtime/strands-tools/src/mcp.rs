//! MCP (Model Context Protocol) tool integration.
//!
//! Provides adapters for exposing MCP servers as Strands tools,
//! allowing agents to use MCP-compatible tool servers.
//!
//! Note: This module requires the `mcp` feature to be enabled.
//! The implementation connects to MCP servers via the `rmcp` crate
//! and wraps their tools as Strands-compatible tools.

use std::collections::HashMap;
use std::sync::Arc;

use async_trait::async_trait;
use rmcp::model::CallToolRequestParam;
use rmcp::service::RunningService;
use rmcp::RoleClient;
use serde_json::Value;
use strands_core::{
    InputSchema, PropertySchema, Result, StrandsError, Tool, ToolContext, ToolExecutionResult,
    ToolSpec,
};
use tracing::{debug, instrument};

/// An MCP tool adapter that wraps an MCP server tool as a Strands tool.
pub struct McpToolAdapter {
    /// Tool name
    name: String,
    /// Tool description
    description: String,
    /// Input schema for the tool
    input_schema: InputSchema,
    /// The MCP client service
    client: Arc<RunningService<RoleClient, ()>>,
}

impl McpToolAdapter {
    /// Create a new MCP tool adapter from tool listing metadata.
    pub fn new(
        name: String,
        description: String,
        input_schema: InputSchema,
        client: Arc<RunningService<RoleClient, ()>>,
    ) -> Self {
        Self {
            name,
            description,
            input_schema,
            client,
        }
    }

    /// Get the tool name.
    pub fn name(&self) -> &str {
        &self.name
    }
}

#[async_trait]
impl Tool for McpToolAdapter {
    fn spec(&self) -> ToolSpec {
        ToolSpec {
            name: self.name.clone(),
            description: self.description.clone(),
            input_schema: self.input_schema.clone(),
        }
    }

    #[instrument(skip(self, input, _context), fields(tool = %self.name))]
    async fn execute(
        &self,
        input: serde_json::Value,
        _context: &ToolContext,
    ) -> Result<ToolExecutionResult> {
        debug!("Executing MCP tool");

        let arguments = if input.is_object() && !input.as_object().unwrap().is_empty() {
            Some(
                input
                    .as_object()
                    .unwrap()
                    .iter()
                    .map(|(k, v)| (k.clone(), v.clone()))
                    .collect(),
            )
        } else {
            None
        };

        let request = CallToolRequestParam {
            name: self.name.clone().into(),
            arguments,
            task: None,
        };

        let result = self.client.call_tool(request).await.map_err(|e| {
            StrandsError::tool(&self.name, format!("MCP call failed: {e}"))
        })?;

        // Check if any content indicates an error
        let is_error = result.is_error.unwrap_or(false);

        // Collect text content from the result.
        // Content is Annotated<RawContent> which derefs to RawContent.
        let text: String = result
            .content
            .iter()
            .filter_map(|c| match &c.raw {
                rmcp::model::RawContent::Text(t) => Some(t.text.clone()),
                _ => None,
            })
            .collect::<Vec<_>>()
            .join("\n");

        if is_error {
            Ok(ToolExecutionResult::error(text))
        } else {
            Ok(ToolExecutionResult::success_text(text))
        }
    }
}

/// Load tools from an MCP server and return them as Strands tool adapters.
///
/// Connects to the given MCP client service, lists available tools,
/// and wraps each one as a `McpToolAdapter`.
pub async fn load_mcp_tools(
    client: Arc<RunningService<RoleClient, ()>>,
) -> Result<Vec<McpToolAdapter>> {
    let tools_result = client.list_tools(None).await.map_err(|e| {
        StrandsError::tool("mcp", format!("Failed to list MCP tools: {e}"))
    })?;

    let mut adapters = Vec::new();
    for tool in tools_result.tools {
        let name = tool.name.to_string();
        let description = tool
            .description
            .as_ref()
            .map(|d| d.to_string())
            .unwrap_or_default();

        // Convert MCP input schema to Strands InputSchema
        let input_schema = convert_mcp_schema(&tool.input_schema);

        debug!(tool = %name, "Loaded MCP tool");
        adapters.push(McpToolAdapter::new(name, description, input_schema, client.clone()));
    }

    Ok(adapters)
}

/// Convert an MCP tool's input schema to a Strands InputSchema.
///
/// MCP schemas are represented as `JsonObject` (a `serde_json::Map<String, Value>`).
/// We extract the top-level properties and required fields.
fn convert_mcp_schema(schema: &serde_json::Map<String, Value>) -> InputSchema {
    let mut properties = HashMap::new();
    let mut required = Vec::new();

    if let Some(Value::Object(props)) = schema.get("properties") {
        for (name, prop_schema) in props {
            let prop_obj = prop_schema.as_object();
            let description = prop_obj
                .and_then(|o| o.get("description"))
                .and_then(|d| d.as_str())
                .unwrap_or("")
                .to_string();
            let prop_type = prop_obj
                .and_then(|o| o.get("type"))
                .and_then(|t| t.as_str())
                .unwrap_or("string")
                .to_string();

            let enum_values = prop_obj
                .and_then(|o| o.get("enum"))
                .and_then(|e| e.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|v| v.as_str().map(|s| s.to_string()))
                        .collect()
                });

            let items = prop_obj
                .and_then(|o| o.get("items"))
                .and_then(|i| i.as_object())
                .map(|item_obj| {
                    let item_type = item_obj
                        .get("type")
                        .and_then(|t| t.as_str())
                        .unwrap_or("string")
                        .to_string();
                    let item_desc = item_obj
                        .get("description")
                        .and_then(|d| d.as_str())
                        .unwrap_or("")
                        .to_string();
                    let item_enum = item_obj
                        .get("enum")
                        .and_then(|e| e.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                                .collect()
                        });
                    Box::new(PropertySchema {
                        property_type: item_type,
                        description: item_desc,
                        enum_values: item_enum,
                        items: None,
                    })
                });

            properties.insert(
                name.clone(),
                PropertySchema {
                    property_type: prop_type,
                    description,
                    enum_values,
                    items,
                },
            );
        }
    }

    if let Some(Value::Array(req)) = schema.get("required") {
        for r in req {
            if let Some(s) = r.as_str() {
                required.push(s.to_string());
            }
        }
    }

    InputSchema {
        schema_type: "object".to_string(),
        properties,
        required,
    }
}
