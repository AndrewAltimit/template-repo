//! JSON validation tool.
//!
//! Validates JSON responses against an expected schema, allowing the agent
//! to iterate and fix errors before committing.

use async_trait::async_trait;
use jsonschema::Validator;
use strands_core::{InputSchema, Result, Tool, ToolContext, ToolExecutionResult, ToolSpec};
use tracing::{debug, warn};

use super::state::JsonResponseState;

/// Tool for validating JSON against an expected schema.
pub struct ValidateJsonTool {
    state: JsonResponseState,
    validator: Option<Validator>,
}

impl ValidateJsonTool {
    /// Create a new validation tool with the given state.
    pub fn new(state: JsonResponseState) -> Self {
        // Pre-compile the JSON schema validator
        let validator = Validator::new(&state.schema)
            .map_err(|e| {
                warn!(error = %e, "Failed to compile JSON schema");
            })
            .ok();

        Self { state, validator }
    }

    /// Validate the JSON string against the schema.
    fn validate(&self, json_str: &str) -> std::result::Result<serde_json::Value, Vec<String>> {
        // First, parse the JSON
        let value: serde_json::Value = match serde_json::from_str(json_str) {
            Ok(v) => v,
            Err(e) => {
                return Err(vec![format!("Invalid JSON syntax: {}", e)]);
            }
        };

        // Then validate against schema
        if let Some(ref validator) = self.validator {
            if !validator.is_valid(&value) {
                // Collect validation errors
                let error = validator
                    .validate(&value)
                    .expect_err("Already checked is_valid");
                let error_messages = vec![error.to_string()];
                return Err(error_messages);
            }
        }

        Ok(value)
    }
}

#[async_trait]
impl Tool for ValidateJsonTool {
    fn spec(&self) -> ToolSpec {
        ToolSpec {
            name: "validate_json".to_string(),
            description: "Validate a JSON response against the expected schema. \
                Call this tool with your JSON response to check if it's valid. \
                If validation fails, you'll receive error messages to help fix the issues. \
                Once validation passes, call commit_response to finalize."
                .to_string(),
            input_schema: InputSchema::builder()
                .string(
                    "json_response",
                    "The complete JSON response to validate. Must be a valid JSON string.",
                    true,
                )
                .build(),
        }
    }

    async fn execute(
        &self,
        input: serde_json::Value,
        _context: &ToolContext,
    ) -> Result<ToolExecutionResult> {
        // Check if already committed
        if self.state.is_committed() {
            return Ok(ToolExecutionResult::error(
                "Response already committed. No further validation needed.",
            ));
        }

        // Increment attempt counter
        let attempt = self.state.increment_attempts();

        // Check if max attempts exceeded
        if attempt > self.state.max_attempts {
            return Ok(ToolExecutionResult::error(format!(
                "Maximum validation attempts ({}) exceeded. \
                 The code review has failed due to too many invalid JSON responses.",
                self.state.max_attempts
            )));
        }

        // Extract json_response parameter
        let json_str = match input.get("json_response").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => {
                return Ok(ToolExecutionResult::error(
                    "Missing required parameter 'json_response'. \
                     Please provide the JSON response as a string.",
                ));
            }
        };

        debug!(
            attempt,
            json_len = json_str.len(),
            "Validating JSON response"
        );

        // Validate
        match self.validate(json_str) {
            Ok(_) => Ok(ToolExecutionResult::success_text(format!(
                "Validation PASSED (attempt {}/{}). \
                     Your JSON response is valid. \
                     Now call the commit_response tool with the same JSON to finalize.",
                attempt, self.state.max_attempts
            ))),
            Err(errors) => {
                let error_list = errors
                    .iter()
                    .enumerate()
                    .map(|(i, e)| format!("{}. {}", i + 1, e))
                    .collect::<Vec<_>>()
                    .join("\n");

                Ok(ToolExecutionResult::success_text(format!(
                    "Validation FAILED (attempt {}/{}).\n\n\
                     Errors found:\n{}\n\n\
                     Please fix these errors and call validate_json again with the corrected JSON.",
                    attempt, self.state.max_attempts, error_list
                )))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::mpsc;

    fn create_test_tool(schema: serde_json::Value) -> ValidateJsonTool {
        let (tx, _rx) = mpsc::channel(1);
        let state = JsonResponseState::new(schema, 8, tx);
        ValidateJsonTool::new(state)
    }

    #[tokio::test]
    async fn test_valid_json() {
        let schema = serde_json::json!({
            "type": "object",
            "required": ["message"],
            "properties": {
                "message": { "type": "string" }
            }
        });

        let tool = create_test_tool(schema);
        let input = serde_json::json!({
            "json_response": r#"{"message": "hello"}"#
        });

        let result = tool.execute(input, &ToolContext::default()).await.unwrap();
        assert_eq!(result.status, strands_core::ToolResultStatus::Success);
        let text = result.content[0].as_text().unwrap();
        assert!(text.contains("PASSED"));
    }

    #[tokio::test]
    async fn test_invalid_json_syntax() {
        let schema = serde_json::json!({"type": "object"});
        let tool = create_test_tool(schema);

        let input = serde_json::json!({
            "json_response": "{ invalid json }"
        });

        let result = tool.execute(input, &ToolContext::default()).await.unwrap();
        let text = result.content[0].as_text().unwrap();
        assert!(text.contains("FAILED"));
        assert!(text.contains("Invalid JSON syntax"));
    }

    #[tokio::test]
    async fn test_schema_validation_failure() {
        let schema = serde_json::json!({
            "type": "object",
            "required": ["name", "age"],
            "properties": {
                "name": { "type": "string" },
                "age": { "type": "integer" }
            }
        });

        let tool = create_test_tool(schema);
        let input = serde_json::json!({
            "json_response": r#"{"name": "test"}"#  // missing "age"
        });

        let result = tool.execute(input, &ToolContext::default()).await.unwrap();
        let text = result.content[0].as_text().unwrap();
        assert!(text.contains("FAILED"));
    }

    #[tokio::test]
    async fn test_max_attempts() {
        let (tx, _rx) = mpsc::channel(1);
        let state = JsonResponseState::new(serde_json::json!({"type": "object"}), 2, tx);

        // Simulate already at max attempts
        state.increment_attempts(); // 1
        state.increment_attempts(); // 2

        let tool = ValidateJsonTool::new(state);
        let input = serde_json::json!({
            "json_response": "{}"
        });

        let result = tool.execute(input, &ToolContext::default()).await.unwrap();
        assert_eq!(result.status, strands_core::ToolResultStatus::Error);
        let text = result.content[0].as_text().unwrap();
        assert!(text.contains("Maximum validation attempts"));
    }
}
