//! Dashboard HTTP routes.

use std::sync::Arc;

use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::routing::{delete, get, post};
use axum::{Json, Router};
use chrono::Utc;
use tracing::info;

use economic_agents_monitoring::{Event, EventType, LoggedDecision};

use crate::models::*;
use crate::state::DashboardState;
use crate::websocket::ws_handler;

/// Type alias for API results.
type ApiResult<T> = std::result::Result<T, (StatusCode, Json<ApiErrorResponse>)>;

/// Create the dashboard router.
pub fn dashboard_router(state: Arc<DashboardState>) -> Router {
    Router::new()
        // Health & Status
        .route("/health", get(health_handler))
        .route("/status", get(status_handler))
        // Agent Management
        .route("/agents", get(list_agents_handler))
        .route("/agents", post(create_agent_handler))
        .route("/agents/:agent_id", get(get_agent_handler))
        .route("/agents/:agent_id", delete(delete_agent_handler))
        .route("/agents/:agent_id/start", post(start_agent_handler))
        .route("/agents/:agent_id/stop", post(stop_agent_handler))
        .route("/agents/:agent_id/cycles", get(get_agent_cycles_handler))
        // Metrics
        .route("/metrics", get(metrics_handler))
        .route("/metrics/prometheus", get(prometheus_metrics_handler))
        // Events
        .route("/events", get(list_events_handler))
        // Decisions
        .route("/decisions", get(list_decisions_handler))
        // WebSocket
        .route("/ws", get(ws_handler))
        .with_state(state)
}

// ============================================================================
// Health & Status
// ============================================================================

async fn health_handler(State(state): State<Arc<DashboardState>>) -> Json<HealthResponse> {
    Json(HealthResponse::healthy(state.uptime_seconds()))
}

async fn status_handler(State(state): State<Arc<DashboardState>>) -> Json<DashboardStatusResponse> {
    let agents = state.agents.read().await;
    let active_count = agents.values().filter(|a| a.is_running).count();

    Json(DashboardStatusResponse {
        health: HealthResponse::healthy(state.uptime_seconds()),
        agent_count: agents.len(),
        active_agent_count: active_count,
        websocket_clients: state.ws_client_count().await,
        events_processed: state.events_processed().await,
    })
}

// ============================================================================
// Agent Management
// ============================================================================

async fn list_agents_handler(State(state): State<Arc<DashboardState>>) -> Json<AgentListResponse> {
    let agents = state.list_agents().await;
    let total = agents.len();
    Json(AgentListResponse { agents, total })
}

async fn create_agent_handler(
    State(state): State<Arc<DashboardState>>,
    Json(request): Json<CreateAgentRequest>,
) -> ApiResult<(StatusCode, Json<AgentSummary>)> {
    let config = request.to_config();

    // Create agent without backends (they can be attached later)
    let agent_id = state.register_agent(config, None).await;

    // Get the agent summary
    let summary = state.get_agent(&agent_id).await.ok_or_else(|| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ApiErrorResponse::new(
                "Failed to create agent",
                "CREATE_FAILED",
            )),
        )
    })?;

    // Publish event
    state
        .event_bus
        .publish(Event::new(
            EventType::AgentStarted,
            &agent_id,
            serde_json::json!({
                "agent_id": agent_id,
                "config": request,
            }),
        ))
        .await;

    state.increment_events().await;

    info!(agent_id = %agent_id, "Agent created");

    Ok((StatusCode::CREATED, Json(summary)))
}

async fn get_agent_handler(
    State(state): State<Arc<DashboardState>>,
    Path(agent_id): Path<String>,
) -> ApiResult<Json<AgentDetailsResponse>> {
    let agents = state.agents.read().await;

    let managed = agents.get(&agent_id).ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ApiErrorResponse::new(
                format!("Agent {} not found", agent_id),
                "AGENT_NOT_FOUND",
            )),
        )
    })?;

    let response = AgentDetailsResponse {
        agent: managed.summary(),
        recent_cycles: managed.recent_cycles(10),
        stats: managed.stats(),
    };

    Ok(Json(response))
}

async fn delete_agent_handler(
    State(state): State<Arc<DashboardState>>,
    Path(agent_id): Path<String>,
) -> ApiResult<Json<AgentActionResponse>> {
    // First check if agent exists and is running
    {
        let agents = state.agents.read().await;
        if let Some(managed) = agents.get(&agent_id)
            && managed.is_running
        {
            return Err((
                StatusCode::CONFLICT,
                Json(ApiErrorResponse::new(
                    "Cannot delete running agent. Stop it first.",
                    "AGENT_RUNNING",
                )),
            ));
        }
    }

    if state.remove_agent(&agent_id).await {
        // Publish event
        state
            .event_bus
            .publish(Event::new(
                EventType::AgentStopped,
                &agent_id,
                serde_json::json!({
                    "agent_id": agent_id,
                    "reason": "deleted",
                }),
            ))
            .await;

        state.increment_events().await;

        info!(agent_id = %agent_id, "Agent deleted");

        Ok(Json(AgentActionResponse {
            agent_id,
            action: "deleted".to_string(),
            success: true,
            message: "Agent deleted successfully".to_string(),
        }))
    } else {
        Err((
            StatusCode::NOT_FOUND,
            Json(ApiErrorResponse::new(
                format!("Agent {} not found", agent_id),
                "AGENT_NOT_FOUND",
            )),
        ))
    }
}

async fn start_agent_handler(
    State(state): State<Arc<DashboardState>>,
    Path(agent_id): Path<String>,
    Json(request): Json<StartAgentRequest>,
) -> ApiResult<Json<AgentActionResponse>> {
    let mut agents = state.agents.write().await;

    let managed = agents.get_mut(&agent_id).ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ApiErrorResponse::new(
                format!("Agent {} not found", agent_id),
                "AGENT_NOT_FOUND",
            )),
        )
    })?;

    if managed.is_running {
        return Err((
            StatusCode::CONFLICT,
            Json(ApiErrorResponse::new(
                "Agent is already running",
                "AGENT_ALREADY_RUNNING",
            )),
        ));
    }

    // Mark as running (actual run would be in a background task)
    managed.is_running = true;
    managed.last_activity = Utc::now();

    // Update max_cycles if provided
    if let Some(max) = request.max_cycles {
        managed.agent.config.max_cycles = Some(max);
    }

    info!(agent_id = %agent_id, "Agent started");

    // Broadcast update
    state.broadcast(WsMessage::AgentUpdate(managed.summary()));

    Ok(Json(AgentActionResponse {
        agent_id,
        action: "started".to_string(),
        success: true,
        message: "Agent started successfully".to_string(),
    }))
}

async fn stop_agent_handler(
    State(state): State<Arc<DashboardState>>,
    Path(agent_id): Path<String>,
) -> ApiResult<Json<AgentActionResponse>> {
    let mut agents = state.agents.write().await;

    let managed = agents.get_mut(&agent_id).ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ApiErrorResponse::new(
                format!("Agent {} not found", agent_id),
                "AGENT_NOT_FOUND",
            )),
        )
    })?;

    if !managed.is_running {
        return Err((
            StatusCode::CONFLICT,
            Json(ApiErrorResponse::new(
                "Agent is not running",
                "AGENT_NOT_RUNNING",
            )),
        ));
    }

    // Stop the agent
    managed.agent.stop();
    managed.is_running = false;
    managed.last_activity = Utc::now();

    info!(agent_id = %agent_id, "Agent stopped");

    // Broadcast update
    state.broadcast(WsMessage::AgentUpdate(managed.summary()));

    // Publish event
    drop(agents); // Release lock before async operation
    state
        .event_bus
        .publish(Event::new(
            EventType::AgentStopped,
            &agent_id,
            serde_json::json!({
                "agent_id": agent_id,
                "reason": "manual_stop",
            }),
        ))
        .await;

    state.increment_events().await;

    Ok(Json(AgentActionResponse {
        agent_id,
        action: "stopped".to_string(),
        success: true,
        message: "Agent stopped successfully".to_string(),
    }))
}

async fn get_agent_cycles_handler(
    State(state): State<Arc<DashboardState>>,
    Path(agent_id): Path<String>,
    Query(params): Query<ListEventsRequest>,
) -> ApiResult<Json<serde_json::Value>> {
    let agents = state.agents.read().await;

    let managed = agents.get(&agent_id).ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ApiErrorResponse::new(
                format!("Agent {} not found", agent_id),
                "AGENT_NOT_FOUND",
            )),
        )
    })?;

    let cycles = managed.recent_cycles(params.limit);

    Ok(Json(serde_json::json!({
        "agent_id": agent_id,
        "cycles": cycles,
        "count": cycles.len(),
    })))
}

// ============================================================================
// Metrics
// ============================================================================

async fn metrics_handler(State(state): State<Arc<DashboardState>>) -> Json<MetricsResponse> {
    let snapshot = state.metrics.snapshot().await;

    Json(MetricsResponse {
        counters: snapshot.counters,
        gauges: snapshot.gauges,
        timestamp: Utc::now(),
    })
}

async fn prometheus_metrics_handler(
    State(state): State<Arc<DashboardState>>,
) -> (
    StatusCode,
    [(axum::http::header::HeaderName, &'static str); 1],
    String,
) {
    let snapshot = state.metrics.snapshot().await;
    let mut output = String::new();

    // Format counters
    for (name, value) in &snapshot.counters {
        let sanitized = name.replace(['-', '.'], "_");
        output.push_str(&format!(
            "# TYPE {} counter\n{} {}\n",
            sanitized, sanitized, value
        ));
    }

    // Format gauges
    for (name, value) in &snapshot.gauges {
        let sanitized = name.replace(['-', '.'], "_");
        output.push_str(&format!(
            "# TYPE {} gauge\n{} {}\n",
            sanitized, sanitized, value
        ));
    }

    (
        StatusCode::OK,
        [(
            axum::http::header::CONTENT_TYPE,
            "text/plain; charset=utf-8",
        )],
        output,
    )
}

// ============================================================================
// Events
// ============================================================================

async fn list_events_handler(
    State(state): State<Arc<DashboardState>>,
    Query(params): Query<ListEventsRequest>,
) -> Json<EventListResponse> {
    let events = state.event_bus.recent(params.limit).await;

    let summaries: Vec<EventSummary> = events
        .into_iter()
        .filter(|e| {
            // Filter by event type if specified
            if let Some(ref et) = params.event_type
                && !format!("{:?}", e.event_type)
                    .to_lowercase()
                    .contains(&et.to_lowercase())
            {
                return false;
            }
            // Filter by source if specified
            if let Some(ref src) = params.source
                && !e.source.contains(src)
            {
                return false;
            }
            true
        })
        .map(|e| EventSummary {
            id: e.id,
            event_type: format!("{:?}", e.event_type),
            source: e.source,
            payload: e.payload,
            timestamp: e.timestamp,
        })
        .collect();

    let count = summaries.len();
    Json(EventListResponse {
        events: summaries,
        count,
    })
}

// ============================================================================
// Decisions
// ============================================================================

async fn list_decisions_handler(
    State(state): State<Arc<DashboardState>>,
    Query(params): Query<ListDecisionsRequest>,
) -> Json<DecisionListResponse> {
    let decisions: Vec<LoggedDecision> = if let Some(ref agent_id) = params.agent_id {
        state.decision_logger.for_agent(agent_id).await
    } else {
        state.decision_logger.recent(params.limit).await
    };

    let summaries: Vec<DecisionSummary> = decisions
        .into_iter()
        .take(params.limit)
        .map(|d| DecisionSummary {
            id: d.id,
            agent_id: d.agent_id,
            decision_type: d.decision_type,
            reasoning: d.reasoning,
            confidence: d.confidence,
            outcome: d.outcome,
            timestamp: d.timestamp,
        })
        .collect();

    let count = summaries.len();
    Json(DecisionListResponse {
        decisions: summaries,
        count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_health_response() {
        let health = HealthResponse::healthy(100);
        assert_eq!(health.status, "healthy");
        assert_eq!(health.service, "dashboard");
        assert_eq!(health.uptime_seconds, 100);
    }

    #[test]
    fn test_api_error_response() {
        let error = ApiErrorResponse::new("test error", "TEST_ERROR");
        assert_eq!(error.error, "test error");
        assert_eq!(error.code, "TEST_ERROR");
        assert!(error.details.is_none());

        let with_details = error.with_details(serde_json::json!({"key": "value"}));
        assert!(with_details.details.is_some());
    }
}
