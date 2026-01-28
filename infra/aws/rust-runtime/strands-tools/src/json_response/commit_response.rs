//! Commit response tool.
//!
//! Finalizes the JSON response and signals the agent loop to terminate.
//! This implements the "transaction commit" pattern - once called successfully,
//! the response is locked and no more changes are allowed.

use async_trait::async_trait;
use strands_core::{InputSchema, Result, Tool, ToolContext, ToolExecutionResult, ToolSpec};
use tracing::{debug, info, warn};

use super::state::{CommittedResponse, JsonResponseState};

/// Tool for committing the final JSON response.
///
/// When this tool succeeds, it signals the agent loop to terminate immediately.
/// The committed JSON response is sent through a channel for retrieval.
pub struct CommitResponseTool {
    state: JsonResponseState,
}

impl CommitResponseTool {
    /// Create a new commit tool with the given state.
    pub fn new(state: JsonResponseState) -> Self {
        Self { state }
    }
}

#[async_trait]
impl Tool for CommitResponseTool {
    fn spec(&self) -> ToolSpec {
        ToolSpec {
            name: "commit_response".to_string(),
            description: "Finalize and commit your JSON response. \
                IMPORTANT: Only call this AFTER validate_json has returned 'PASSED'. \
                Once committed, the response cannot be changed and the review is complete."
                .to_string(),
            input_schema: InputSchema::builder()
                .string(
                    "json_response",
                    "The validated JSON response to commit. \
                     This must be the same JSON that passed validation.",
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
        // Try to commit (idempotent - only first call succeeds)
        if !self.state.try_commit() {
            warn!("Attempted to commit response when already committed");
            return Ok(ToolExecutionResult::error(
                "Response has already been committed. The review is complete.",
            ));
        }

        // Extract json_response parameter
        let json_str = match input.get("json_response").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => {
                // Reset commit state since we failed
                // Note: In production, you might want to handle this differently
                return Ok(ToolExecutionResult::error(
                    "Missing required parameter 'json_response'. \
                     Please provide the JSON response to commit.",
                ));
            }
        };

        // Parse the JSON
        let json_value: serde_json::Value = match serde_json::from_str(json_str) {
            Ok(v) => v,
            Err(e) => {
                return Ok(ToolExecutionResult::error(format!(
                    "Invalid JSON: {}. \
                     Please ensure you're committing valid JSON that passed validation.",
                    e
                )));
            }
        };

        debug!(json_len = json_str.len(), "Committing JSON response");

        // Send the committed response through the channel
        let committed = CommittedResponse {
            json_response: json_value,
            validation_attempts: self.state.current_attempts(),
        };

        if let Err(e) = self.state.commit_tx.send(committed).await {
            warn!(error = %e, "Failed to send committed response");
            return Ok(ToolExecutionResult::error(
                "Internal error: Failed to commit response. Please try again.",
            ));
        }

        info!(
            attempts = self.state.current_attempts(),
            "Response committed successfully"
        );

        Ok(ToolExecutionResult::success_text(
            "Response committed successfully. The code review is now complete.",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::mpsc;

    #[tokio::test]
    async fn test_commit_success() {
        let (tx, mut rx) = mpsc::channel(1);
        let state = JsonResponseState::new(serde_json::json!({}), 8, tx);
        let tool = CommitResponseTool::new(state);

        let input = serde_json::json!({
            "json_response": r#"{"result": "success"}"#
        });

        let result = tool.execute(input, &ToolContext::default()).await.unwrap();
        assert_eq!(result.status, strands_core::ToolResultStatus::Success);

        // Check that the response was sent through the channel
        let committed = rx
            .try_recv()
            .expect("Should have received committed response");
        assert_eq!(committed.json_response["result"], "success");
    }

    #[tokio::test]
    async fn test_commit_idempotent() {
        let (tx, _rx) = mpsc::channel(1);
        let state = JsonResponseState::new(serde_json::json!({}), 8, tx);
        let tool = CommitResponseTool::new(state);

        let input = serde_json::json!({
            "json_response": r#"{"result": "success"}"#
        });

        // First commit succeeds
        let result1 = tool
            .execute(input.clone(), &ToolContext::default())
            .await
            .unwrap();
        assert_eq!(result1.status, strands_core::ToolResultStatus::Success);

        // Second commit fails
        let result2 = tool.execute(input, &ToolContext::default()).await.unwrap();
        assert_eq!(result2.status, strands_core::ToolResultStatus::Error);
        let text = result2.content[0].as_text().unwrap();
        assert!(text.contains("already been committed"));
    }

    #[tokio::test]
    async fn test_commit_invalid_json() {
        let (tx, _rx) = mpsc::channel(1);
        let state = JsonResponseState::new(serde_json::json!({}), 8, tx);
        let tool = CommitResponseTool::new(state);

        let input = serde_json::json!({
            "json_response": "{ invalid }"
        });

        let result = tool.execute(input, &ToolContext::default()).await.unwrap();
        assert_eq!(result.status, strands_core::ToolResultStatus::Error);
        let text = result.content[0].as_text().unwrap();
        assert!(text.contains("Invalid JSON"));
    }

    #[tokio::test]
    async fn test_commit_missing_param() {
        let (tx, _rx) = mpsc::channel(1);
        let state = JsonResponseState::new(serde_json::json!({}), 8, tx);
        let tool = CommitResponseTool::new(state);

        let input = serde_json::json!({});

        let result = tool.execute(input, &ToolContext::default()).await.unwrap();
        assert_eq!(result.status, strands_core::ToolResultStatus::Error);
        let text = result.content[0].as_text().unwrap();
        assert!(text.contains("Missing required parameter"));
    }
}
