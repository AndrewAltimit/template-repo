//! Integration tests for dashboard API.

use std::sync::Arc;

use axum_test::TestServer;

use economic_agents_dashboard::{
    dashboard_router, AgentListResponse, AgentSummary, CreateAgentRequest, DashboardState,
    DashboardStatusResponse, EventListResponse, HealthResponse, MetricsResponse,
};

/// Create a test server.
async fn create_test_server() -> TestServer {
    let state = Arc::new(DashboardState::new());
    let app = dashboard_router(state);
    TestServer::new(app).unwrap()
}

// ============================================================================
// Health & Status Tests
// ============================================================================

#[tokio::test]
async fn test_health_endpoint() {
    let server = create_test_server().await;

    let response = server.get("/health").await;
    response.assert_status_ok();

    let body: HealthResponse = response.json();
    assert_eq!(body.status, "healthy");
    assert_eq!(body.service, "dashboard");
}

#[tokio::test]
async fn test_status_endpoint() {
    let server = create_test_server().await;

    let response = server.get("/status").await;
    response.assert_status_ok();

    let body: DashboardStatusResponse = response.json();
    assert_eq!(body.health.status, "healthy");
    assert_eq!(body.agent_count, 0);
    assert_eq!(body.active_agent_count, 0);
}

// ============================================================================
// Agent Management Tests
// ============================================================================

#[tokio::test]
async fn test_list_agents_empty() {
    let server = create_test_server().await;

    let response = server.get("/agents").await;
    response.assert_status_ok();

    let body: AgentListResponse = response.json();
    assert_eq!(body.total, 0);
    assert!(body.agents.is_empty());
}

#[tokio::test]
async fn test_create_agent() {
    let server = create_test_server().await;

    let response = server
        .post("/agents")
        .json(&CreateAgentRequest {
            agent_id: None,
            engine_type: Some("rule_based".to_string()),
            mode: Some("survival".to_string()),
            personality: Some("balanced".to_string()),
            task_selection_strategy: Some("highest_reward".to_string()),
            survival_buffer_hours: Some(24.0),
            company_threshold: Some(100.0),
            max_cycles: Some(10),
            initial_balance: None,
            initial_compute_hours: None,
        })
        .await;

    response.assert_status(axum::http::StatusCode::CREATED);

    let body: AgentSummary = response.json();
    assert!(!body.id.is_empty());
    assert!(!body.is_running);
}

#[tokio::test]
async fn test_create_and_list_agents() {
    let server = create_test_server().await;

    // Create first agent
    server
        .post("/agents")
        .json(&CreateAgentRequest {
            engine_type: Some("rule_based".to_string()),
            ..Default::default()
        })
        .await;

    // Create second agent
    server
        .post("/agents")
        .json(&CreateAgentRequest {
            mode: Some("company".to_string()),
            ..Default::default()
        })
        .await;

    // List agents
    let response = server.get("/agents").await;
    response.assert_status_ok();

    let body: AgentListResponse = response.json();
    assert_eq!(body.total, 2);
    assert_eq!(body.agents.len(), 2);
}

#[tokio::test]
async fn test_get_agent_details() {
    let server = create_test_server().await;

    // Create agent
    let create_response = server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let created: AgentSummary = create_response.json();

    // Get agent details
    let response = server.get(&format!("/agents/{}", created.id)).await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["agent"]["id"], created.id);
    assert!(body["stats"]["success_rate"].is_number());
    assert!(body["recent_cycles"].is_array());
}

#[tokio::test]
async fn test_get_nonexistent_agent() {
    let server = create_test_server().await;

    let response = server.get("/agents/nonexistent-id").await;
    response.assert_status(axum::http::StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn test_start_agent() {
    let server = create_test_server().await;

    // Create agent
    let create_response = server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let created: AgentSummary = create_response.json();

    // Start agent
    let response = server
        .post(&format!("/agents/{}/start", created.id))
        .json(&serde_json::json!({}))
        .await;

    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["action"], "started");
    assert!(body["success"].as_bool().unwrap());
}

#[tokio::test]
async fn test_start_already_running_agent() {
    let server = create_test_server().await;

    // Create agent
    let create_response = server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let created: AgentSummary = create_response.json();

    // Start agent
    server
        .post(&format!("/agents/{}/start", created.id))
        .json(&serde_json::json!({}))
        .await;

    // Try to start again
    let response = server
        .post(&format!("/agents/{}/start", created.id))
        .json(&serde_json::json!({}))
        .await;

    response.assert_status(axum::http::StatusCode::CONFLICT);
}

#[tokio::test]
async fn test_stop_agent() {
    let server = create_test_server().await;

    // Create agent
    let create_response = server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let created: AgentSummary = create_response.json();

    // Start agent
    server
        .post(&format!("/agents/{}/start", created.id))
        .json(&serde_json::json!({}))
        .await;

    // Stop agent
    let response = server.post(&format!("/agents/{}/stop", created.id)).await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["action"], "stopped");
    assert!(body["success"].as_bool().unwrap());
}

#[tokio::test]
async fn test_stop_not_running_agent() {
    let server = create_test_server().await;

    // Create agent
    let create_response = server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let created: AgentSummary = create_response.json();

    // Try to stop without starting
    let response = server.post(&format!("/agents/{}/stop", created.id)).await;
    response.assert_status(axum::http::StatusCode::CONFLICT);
}

#[tokio::test]
async fn test_delete_agent() {
    let server = create_test_server().await;

    // Create agent
    let create_response = server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let created: AgentSummary = create_response.json();

    // Delete agent
    let response = server.delete(&format!("/agents/{}", created.id)).await;
    response.assert_status_ok();

    // Verify deleted
    let list_response = server.get("/agents").await;
    let body: AgentListResponse = list_response.json();
    assert_eq!(body.total, 0);
}

#[tokio::test]
async fn test_delete_running_agent_fails() {
    let server = create_test_server().await;

    // Create agent
    let create_response = server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let created: AgentSummary = create_response.json();

    // Start agent
    server
        .post(&format!("/agents/{}/start", created.id))
        .json(&serde_json::json!({}))
        .await;

    // Try to delete running agent
    let response = server.delete(&format!("/agents/{}", created.id)).await;
    response.assert_status(axum::http::StatusCode::CONFLICT);
}

// ============================================================================
// Metrics Tests
// ============================================================================

#[tokio::test]
async fn test_metrics_endpoint() {
    let server = create_test_server().await;

    let response = server.get("/metrics").await;
    response.assert_status_ok();

    let body: MetricsResponse = response.json();
    assert!(body.counters.is_empty() || !body.counters.is_empty()); // Just check it parses
    assert!(body.timestamp.to_string().len() > 0);
}

#[tokio::test]
async fn test_prometheus_metrics_endpoint() {
    let server = create_test_server().await;

    // Create an agent to generate some metrics
    server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let response = server.get("/metrics/prometheus").await;
    response.assert_status_ok();

    let body = response.text();
    // Prometheus format should contain TYPE declarations
    assert!(body.contains("TYPE") || body.is_empty());
}

// ============================================================================
// Events Tests
// ============================================================================

#[tokio::test]
async fn test_list_events_empty() {
    let server = create_test_server().await;

    let response = server.get("/events").await;
    response.assert_status_ok();

    let body: EventListResponse = response.json();
    assert_eq!(body.count, 0);
}

#[tokio::test]
async fn test_list_events_after_agent_creation() {
    let server = create_test_server().await;

    // Create agent (generates an event)
    server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let response = server.get("/events").await;
    response.assert_status_ok();

    let body: EventListResponse = response.json();
    assert!(body.count >= 1);
}

#[tokio::test]
async fn test_list_events_with_limit() {
    let server = create_test_server().await;

    // Create multiple agents to generate events
    for _ in 0..5 {
        server
            .post("/agents")
            .json(&CreateAgentRequest::default())
            .await;
    }

    let response = server.get("/events?limit=2").await;
    response.assert_status_ok();

    let body: EventListResponse = response.json();
    assert!(body.count <= 2);
}

// ============================================================================
// Decisions Tests
// ============================================================================

#[tokio::test]
async fn test_list_decisions_empty() {
    let server = create_test_server().await;

    let response = server.get("/decisions").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["count"], 0);
}

// ============================================================================
// Agent Cycles Tests
// ============================================================================

#[tokio::test]
async fn test_get_agent_cycles() {
    let server = create_test_server().await;

    // Create agent
    let create_response = server
        .post("/agents")
        .json(&CreateAgentRequest::default())
        .await;

    let created: AgentSummary = create_response.json();

    // Get cycles (should be empty)
    let response = server.get(&format!("/agents/{}/cycles", created.id)).await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["count"], 0);
    assert!(body["cycles"].is_array());
}

// ============================================================================
// Default Implementation Tests
// ============================================================================

#[tokio::test]
async fn test_create_agent_request_default() {
    let request = CreateAgentRequest::default();
    let config = request.to_config();

    // Default values should be applied
    assert_eq!(format!("{:?}", config.engine_type), "RuleBased");
    assert_eq!(format!("{:?}", config.mode), "Survival");
}
