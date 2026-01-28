//! HTTP endpoint handler for code review.

use std::sync::Arc;

use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use strands_agent::{
    termination_channel, Agent, AgentConfig, InferenceConfig, LoopTerminationSignal,
};
use strands_core::Message;
use strands_models::BedrockModel;
use strands_tools::{CommitResponseTool, JsonResponseState, ValidateJsonTool};
use tokio::sync::mpsc;
use tracing::{error, info, instrument, warn};
use uuid::Uuid;

use crate::handlers::AppState;
use crate::injection_guard::PatternMatcher;

use super::request::{
    CodeReviewRequest, CodeReviewResponse, ReviewResult, ReviewSeverity, ReviewStatus,
    SecurityDeniedResponse, UsageResponse,
};
use super::schema::{format_user_message, get_schema, get_system_prompt};

/// Maximum JSON validation attempts before failure.
const MAX_JSON_ATTEMPTS: u32 = 8;

/// Error response for code review endpoint.
#[derive(Debug, serde::Serialize)]
pub struct CodeReviewError {
    pub error: String,
    pub code: Option<String>,
    pub retryable: bool,
}

impl IntoResponse for CodeReviewError {
    fn into_response(self) -> Response {
        let status = if self.retryable {
            StatusCode::SERVICE_UNAVAILABLE
        } else {
            StatusCode::BAD_REQUEST
        };
        (status, Json(self)).into_response()
    }
}

/// Code review invocation handler.
///
/// POST /code-review
///
/// This endpoint:
/// 1. Validates the request
/// 2. Checks for prompt injection in the instructions
/// 3. Creates a specialized code review agent with JSON response tools
/// 4. Runs the agent with early termination support
/// 5. Returns the structured review result
#[instrument(skip(state, request), fields(review_id))]
pub async fn invoke_code_review(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CodeReviewRequest>,
) -> Result<Json<CodeReviewResponse>, Response> {
    let review_id = Uuid::new_v4().to_string();
    tracing::Span::current().record("review_id", &review_id);

    info!(
        repository = %request.repository,
        branch = %request.branch,
        commit = %request.commit,
        apply_fixes = request.apply_fixes,
        create_pr = request.create_pr,
        "Code review request received"
    );

    // Step 1: Check for prompt injection in the instructions
    let injection_analysis = check_injection(&state, &request.instructions).await;

    if injection_analysis.is_malicious {
        warn!(
            confidence = injection_analysis.confidence,
            category = ?injection_analysis.attack_category,
            reason = %injection_analysis.reason,
            "Prompt injection detected, denying request"
        );

        let denied_response = SecurityDeniedResponse::new(
            &injection_analysis.reason,
            injection_analysis
                .attack_category
                .map(|c| format!("{:?}", c).to_lowercase()),
            injection_analysis.confidence,
        );

        return Err((StatusCode::FORBIDDEN, Json(denied_response)).into_response());
    }

    // Step 2: Set up the JSON response tools
    let schema = get_schema(request.apply_fixes);
    let (commit_tx, mut commit_rx) = mpsc::channel(1);
    let json_state = JsonResponseState::new(schema, MAX_JSON_ATTEMPTS, commit_tx);

    let validate_tool = ValidateJsonTool::new(json_state.clone());
    let commit_tool = CommitResponseTool::new(json_state.clone());

    // Step 3: Create the termination channel
    let (term_tx, term_rx) = termination_channel();

    // Spawn a task to bridge commit_rx to term_tx
    let term_tx_clone = term_tx.clone();
    tokio::spawn(async move {
        if let Some(committed) = commit_rx.recv().await {
            let _ = term_tx_clone
                .send(LoopTerminationSignal::ToolCompleted {
                    tool_name: "commit_response".to_string(),
                    result: committed.json_response,
                })
                .await;
        }
    });

    // Step 4: Create the code review agent
    let system_prompt = get_system_prompt(request.apply_fixes, request.create_pr);

    // Create a new model instance for this request
    let model = BedrockModel::new(&state.model_id, &state.region).await;

    let agent_config = AgentConfig {
        max_iterations: 20, // Allow enough iterations for JSON retries
        inference_config: InferenceConfig {
            max_tokens: Some(8192), // Large enough for detailed reviews
            ..Default::default()
        },
        ..Default::default()
    };

    let agent = Agent::builder()
        .model(model)
        .config(agent_config)
        .system_prompt(&system_prompt)
        .tool(validate_tool)
        .tool(commit_tool)
        .build()
        .map_err(|e| {
            error!(error = %e, "Failed to build code review agent");
            CodeReviewError {
                error: format!("Failed to initialize agent: {}", e),
                code: Some("AGENT_INIT_ERROR".to_string()),
                retryable: false,
            }
            .into_response()
        })?;

    // Step 5: Format the user message
    let user_message = format_user_message(
        &request.instructions,
        &request.repository,
        &request.branch,
        &request.commit,
        &request.base_branch,
    );

    // Step 6: Run the agent with early termination
    let messages = vec![Message::user(&user_message)];

    let (result, _final_messages, committed_json) = agent
        .run_loop_with_early_termination(messages, term_rx)
        .await
        .map_err(|e| {
            error!(error = %e, "Code review agent failed");
            CodeReviewError {
                error: format!("Agent execution failed: {}", e),
                code: Some("AGENT_ERROR".to_string()),
                retryable: e.to_string().contains("throttl"),
            }
            .into_response()
        })?;

    // Step 7: Parse the committed JSON into ReviewResult
    let (review_result, status) = match committed_json {
        Some(json) => {
            let parsed = parse_review_result(json, request.apply_fixes);
            (parsed, ReviewStatus::Completed)
        }
        None => {
            // No committed result - agent ended without committing
            warn!("Agent ended without committing a response");
            (
                ReviewResult::ReviewOnly {
                    review_markdown: result.text(),
                    severity: ReviewSeverity::Info,
                    findings_count: 0,
                },
                ReviewStatus::Failed,
            )
        }
    };

    info!(
        review_id = %review_id,
        status = ?status,
        iterations = result.iterations,
        validation_attempts = json_state.current_attempts(),
        "Code review completed"
    );

    Ok(Json(CodeReviewResponse {
        review_id,
        status,
        result: review_result,
        usage: UsageResponse {
            input_tokens: result.usage.input_tokens,
            output_tokens: result.usage.output_tokens,
            total_tokens: result.usage.total_tokens,
        },
        validation_attempts: json_state.current_attempts(),
        iterations: result.iterations,
    }))
}

/// Check for prompt injection in the instructions.
async fn check_injection(
    _state: &AppState,
    instructions: &str,
) -> crate::injection_guard::InjectionAnalysis {
    // For now, use pattern-based detection only
    // In production, this would use the InjectionDetector with an LLM
    let matcher = PatternMatcher::new();

    let pattern_matches = matcher.check(instructions);

    if pattern_matches.is_empty() {
        return crate::injection_guard::InjectionAnalysis::safe();
    }

    // Check if any high-confidence matches
    let highest = pattern_matches.first().cloned();
    let confidence = highest.as_ref().map(|m| m.confidence).unwrap_or(0.0);

    if confidence >= 0.85 {
        crate::injection_guard::InjectionAnalysis::from_patterns(pattern_matches)
    } else {
        // For medium-confidence matches, we could invoke LLM analysis here
        // For now, just flag it with lower confidence
        if confidence >= 0.5 {
            crate::injection_guard::InjectionAnalysis::from_patterns(pattern_matches)
        } else {
            crate::injection_guard::InjectionAnalysis::safe()
        }
    }
}

/// Parse the committed JSON into a ReviewResult.
fn parse_review_result(json: serde_json::Value, apply_fixes: bool) -> ReviewResult {
    if apply_fixes {
        // Try to parse as WithFixes
        ReviewResult::WithFixes {
            review_markdown: json
                .get("review_markdown")
                .and_then(|v| v.as_str())
                .unwrap_or("No review provided")
                .to_string(),
            severity: parse_severity(json.get("severity")),
            findings_count: json
                .get("findings_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as u32,
            file_changes: json
                .get("file_changes")
                .and_then(|v| v.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|item| {
                            Some(super::request::FileChange {
                                path: item.get("path")?.as_str()?.to_string(),
                                diff: item.get("diff")?.as_str()?.to_string(),
                                original_sha: item
                                    .get("original_sha")
                                    .and_then(|v| v.as_str())
                                    .map(|s| s.to_string()),
                            })
                        })
                        .collect()
                })
                .unwrap_or_default(),
            pr_title: json
                .get("pr_title")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            pr_description: json
                .get("pr_description")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
        }
    } else {
        ReviewResult::ReviewOnly {
            review_markdown: json
                .get("review_markdown")
                .and_then(|v| v.as_str())
                .unwrap_or("No review provided")
                .to_string(),
            severity: parse_severity(json.get("severity")),
            findings_count: json
                .get("findings_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as u32,
        }
    }
}

/// Parse severity from JSON value.
fn parse_severity(value: Option<&serde_json::Value>) -> ReviewSeverity {
    value
        .and_then(|v| v.as_str())
        .map(|s| match s.to_lowercase().as_str() {
            "critical" => ReviewSeverity::Critical,
            "high" => ReviewSeverity::High,
            "medium" => ReviewSeverity::Medium,
            "low" => ReviewSeverity::Low,
            _ => ReviewSeverity::Info,
        })
        .unwrap_or(ReviewSeverity::Info)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_severity() {
        assert_eq!(
            parse_severity(Some(&serde_json::json!("critical"))),
            ReviewSeverity::Critical
        );
        assert_eq!(
            parse_severity(Some(&serde_json::json!("HIGH"))),
            ReviewSeverity::High
        );
        assert_eq!(parse_severity(None), ReviewSeverity::Info);
    }

    #[test]
    fn test_parse_review_result() {
        let json = serde_json::json!({
            "review_markdown": "# Review\nLooks good",
            "severity": "low",
            "findings_count": 2
        });

        let result = parse_review_result(json, false);
        match result {
            ReviewResult::ReviewOnly {
                review_markdown,
                severity,
                findings_count,
            } => {
                assert!(review_markdown.contains("Looks good"));
                assert_eq!(severity, ReviewSeverity::Low);
                assert_eq!(findings_count, 2);
            }
            _ => panic!("Expected ReviewOnly"),
        }
    }
}
