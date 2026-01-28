//! HTTP request handlers for AgentCore protocol.

use std::sync::Arc;

use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::{Deserialize, Serialize};
use strands_agent::Agent;
use strands_core::StrandsError;
use strands_session::SessionManager;
use tracing::{error, info, instrument};
use uuid::Uuid;

use crate::code_review::{invoke_code_review_internal, CodeReviewRequest};

/// Application state shared across handlers.
pub struct AppState {
    pub agent: Agent,
    pub session_manager: SessionManager,
    /// Model ID for creating additional agents (e.g., code review)
    pub model_id: String,
    /// AWS region for Bedrock
    pub region: String,
}

/// Unified request that can be either a regular invocation or code review.
/// AgentCore HTTP protocol routes all requests to /invocations, so we use
/// field presence to determine request type.
#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum UnifiedRequest {
    /// Code review request (has `repository` and `instructions` fields)
    CodeReview(CodeReviewRequest),
    /// Regular invocation request (has `prompt` field)
    Invoke(InvocationRequest),
}

/// Invocation request body.
#[derive(Debug, Deserialize)]
pub struct InvocationRequest {
    /// The prompt to send to the agent
    pub prompt: String,
    /// Optional session ID for conversation continuity
    pub session_id: Option<String>,
    /// Whether to stream the response
    #[serde(default)]
    pub stream: bool,
}

/// Invocation response body.
#[derive(Debug, Serialize)]
pub struct InvocationResponse {
    /// Unique invocation ID
    pub invocation_id: String,
    /// Session ID used
    pub session_id: String,
    /// Response text
    pub response: String,
    /// Stop reason
    pub stop_reason: String,
    /// Token usage
    pub usage: UsageResponse,
    /// Number of agent iterations
    pub iterations: u32,
}

/// Token usage information.
#[derive(Debug, Serialize)]
pub struct UsageResponse {
    pub input_tokens: u32,
    pub output_tokens: u32,
    pub total_tokens: u32,
}

/// Health check response.
/// Must match AgentCore protocol: status = "Healthy" or "HealthyBusy"
#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub time_of_last_update: u64,
}

/// Error response body.
#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
    pub code: Option<String>,
    pub retryable: bool,
}

impl IntoResponse for ErrorResponse {
    fn into_response(self) -> Response {
        let status = if self.retryable {
            StatusCode::SERVICE_UNAVAILABLE
        } else {
            StatusCode::BAD_REQUEST
        };

        (status, Json(self)).into_response()
    }
}

/// Health check handler.
///
/// GET /ping
/// Returns AgentCore-compatible health status.
pub async fn health_check() -> Json<HealthResponse> {
    use std::time::{SystemTime, UNIX_EPOCH};

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    Json(HealthResponse {
        status: "Healthy".to_string(),
        time_of_last_update: timestamp,
    })
}

/// Unified invocation handler that routes based on request type.
///
/// POST /invocations (and POST /)
///
/// AgentCore HTTP protocol routes all requests to /invocations, so we use
/// field presence to determine if this is a regular invoke or code review:
/// - If request has `repository` and `instructions` fields -> code review
/// - If request has `prompt` field -> regular invocation
#[instrument(skip(state, request))]
pub async fn invoke(
    State(state): State<Arc<AppState>>,
    Json(request): Json<UnifiedRequest>,
) -> Response {
    match request {
        UnifiedRequest::CodeReview(code_review_request) => {
            info!(
                repository = %code_review_request.repository,
                "Routing to code review handler"
            );
            invoke_code_review_internal(state, code_review_request)
                .await
                .into_response()
        }
        UnifiedRequest::Invoke(invoke_request) => {
            invoke_regular(state, invoke_request).await.into_response()
        }
    }
}

/// Regular invocation handler for conversational prompts.
#[instrument(skip(state, request), fields(session_id, invocation_id))]
async fn invoke_regular(
    state: Arc<AppState>,
    request: InvocationRequest,
) -> Result<Json<InvocationResponse>, ErrorResponse> {
    let invocation_id = Uuid::new_v4().to_string();

    // Get or create session
    let session_id = request
        .session_id
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    let mut session = state
        .session_manager
        .get_or_create(&session_id)
        .await
        .map_err(|e| ErrorResponse {
            error: format!("Session error: {}", e),
            code: Some("SESSION_ERROR".to_string()),
            retryable: true,
        })?;

    info!(
        invocation_id = %invocation_id,
        session_id = %session_id,
        "Processing invocation"
    );

    // Mark session as processing
    session.set_processing();

    // Invoke with an isolated copy of the session's conversation history.
    // This avoids shared mutex state and prevents cross-session data leakage.
    let (result, updated_messages) = state
        .agent
        .invoke_with_messages(&request.prompt, session.messages.clone())
        .await
        .map_err(|e| {
            error!(error = %e, "Agent invocation failed");
            map_strands_error(e)
        })?;

    // Extract response text (Text blocks only; Reasoning blocks are internal model
    // thinking and not included in the response string)
    let response_text = result.text();

    // Update session with the final conversation state from the agent
    session.messages = updated_messages;
    session.add_usage(&result.usage);
    session.set_active();

    // Persist session
    state
        .session_manager
        .update_session(&session)
        .await
        .map_err(|e| ErrorResponse {
            error: format!("Session update error: {}", e),
            code: Some("SESSION_ERROR".to_string()),
            retryable: true,
        })?;

    info!(
        invocation_id = %invocation_id,
        iterations = result.iterations,
        input_tokens = result.usage.input_tokens,
        output_tokens = result.usage.output_tokens,
        "Invocation completed"
    );

    Ok(Json(InvocationResponse {
        invocation_id,
        session_id,
        response: response_text,
        stop_reason: format!("{:?}", result.stop_reason),
        usage: UsageResponse {
            input_tokens: result.usage.input_tokens,
            output_tokens: result.usage.output_tokens,
            total_tokens: result.usage.total_tokens,
        },
        iterations: result.iterations,
    }))
}

/// Map StrandsError to ErrorResponse.
fn map_strands_error(error: StrandsError) -> ErrorResponse {
    match &error {
        StrandsError::ModelThrottled { .. } => ErrorResponse {
            error: error.to_string(),
            code: Some("THROTTLED".to_string()),
            retryable: true,
        },
        StrandsError::ContextWindowOverflow { .. } => ErrorResponse {
            error: error.to_string(),
            code: Some("CONTEXT_OVERFLOW".to_string()),
            retryable: false,
        },
        StrandsError::Model { message, .. } => ErrorResponse {
            error: message.clone(),
            code: Some("MODEL_ERROR".to_string()),
            retryable: false,
        },
        StrandsError::ToolNotFound { tool_name } => ErrorResponse {
            error: format!("Tool not found: {}", tool_name),
            code: Some("TOOL_NOT_FOUND".to_string()),
            retryable: false,
        },
        StrandsError::Tool {
            tool_name, message, ..
        } => ErrorResponse {
            error: format!("Tool '{}' failed: {}", tool_name, message),
            code: Some("TOOL_ERROR".to_string()),
            retryable: false,
        },
        StrandsError::MaxIterationsExceeded { max } => ErrorResponse {
            error: format!("Max iterations ({}) exceeded", max),
            code: Some("MAX_ITERATIONS".to_string()),
            retryable: false,
        },
        _ => ErrorResponse {
            error: error.to_string(),
            code: None,
            retryable: false,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_health_response_serialization() {
        let response = HealthResponse {
            status: "Healthy".to_string(),
            time_of_last_update: 1234567890,
        };
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("Healthy"));
        assert!(json.contains("time_of_last_update"));
    }

    #[test]
    fn test_error_response_retryable() {
        let error = ErrorResponse {
            error: "Throttled".to_string(),
            code: Some("THROTTLED".to_string()),
            retryable: true,
        };
        assert!(error.retryable);
    }
}
