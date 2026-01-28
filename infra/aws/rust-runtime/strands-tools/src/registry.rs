//! Tool registry for managing available tools.

use std::collections::HashMap;
use std::sync::Arc;

use strands_core::{
    BoxedTool, Result, StrandsError, Tool, ToolContext, ToolExecutionResult, ToolSpec,
};
use tracing::{debug, instrument};

/// Registry for managing tools available to agents.
pub struct ToolRegistry {
    /// Registered tools by name
    tools: HashMap<String, BoxedTool>,
}

impl ToolRegistry {
    /// Create a new empty registry.
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
        }
    }

    /// Register a tool.
    pub fn register<T: Tool + 'static>(&mut self, tool: T) {
        let spec = tool.spec();
        debug!(tool = %spec.name, "Registering tool");
        self.tools.insert(spec.name.clone(), Arc::new(tool));
    }

    /// Register a boxed tool.
    pub fn register_boxed(&mut self, tool: BoxedTool) {
        let spec = tool.spec();
        debug!(tool = %spec.name, "Registering boxed tool");
        self.tools.insert(spec.name.clone(), tool);
    }

    /// Get a tool by name.
    pub fn get(&self, name: &str) -> Option<&BoxedTool> {
        self.tools.get(name)
    }

    /// Check if a tool exists.
    pub fn contains(&self, name: &str) -> bool {
        self.tools.contains_key(name)
    }

    /// Get all tool specifications.
    pub fn specs(&self) -> Vec<ToolSpec> {
        self.tools.values().map(|t| t.spec()).collect()
    }

    /// Get all tool names.
    pub fn names(&self) -> Vec<&str> {
        self.tools.keys().map(|s| s.as_str()).collect()
    }

    /// Get the number of registered tools.
    pub fn len(&self) -> usize {
        self.tools.len()
    }

    /// Check if the registry is empty.
    pub fn is_empty(&self) -> bool {
        self.tools.is_empty()
    }

    /// Remove a tool by name.
    pub fn remove(&mut self, name: &str) -> Option<BoxedTool> {
        debug!(tool = %name, "Removing tool");
        self.tools.remove(name)
    }

    /// Clear all tools.
    pub fn clear(&mut self) {
        debug!("Clearing all tools");
        self.tools.clear();
    }

    /// Execute a tool by name.
    #[instrument(skip(self, input, context), fields(tool = %name))]
    pub async fn execute(
        &self,
        name: &str,
        input: serde_json::Value,
        context: &ToolContext,
    ) -> Result<ToolExecutionResult> {
        let tool = self
            .tools
            .get(name)
            .ok_or_else(|| StrandsError::tool_not_found(name))?;

        debug!(input = %input, "Executing tool");
        tool.execute(input, context).await
    }
}

impl Default for ToolRegistry {
    fn default() -> Self {
        Self::new()
    }
}

impl FromIterator<BoxedTool> for ToolRegistry {
    fn from_iter<I: IntoIterator<Item = BoxedTool>>(iter: I) -> Self {
        let mut registry = Self::new();
        for tool in iter {
            registry.register_boxed(tool);
        }
        registry
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use async_trait::async_trait;

    struct TestTool {
        name: String,
    }

    #[async_trait]
    impl Tool for TestTool {
        fn spec(&self) -> ToolSpec {
            ToolSpec::no_params(&self.name, "A test tool")
        }

        async fn execute(
            &self,
            _input: serde_json::Value,
            _context: &ToolContext,
        ) -> Result<ToolExecutionResult> {
            Ok(ToolExecutionResult::success_text("Test result"))
        }
    }

    #[test]
    fn test_register_and_get() {
        let mut registry = ToolRegistry::new();
        registry.register(TestTool {
            name: "test".to_string(),
        });

        assert!(registry.contains("test"));
        assert!(!registry.contains("other"));
        assert_eq!(registry.len(), 1);
    }

    #[tokio::test]
    async fn test_execute() {
        let mut registry = ToolRegistry::new();
        registry.register(TestTool {
            name: "test".to_string(),
        });

        let result = registry
            .execute("test", serde_json::json!({}), &ToolContext::default())
            .await
            .unwrap();

        assert_eq!(result.status, strands_core::ToolResultStatus::Success);
    }
}
