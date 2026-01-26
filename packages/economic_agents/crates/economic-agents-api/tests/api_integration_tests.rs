//! Integration tests for API clients and services.
//!
//! These tests verify that the HTTP clients correctly communicate
//! with the Axum services.

use std::sync::Arc;
use tokio::sync::RwLock;

use axum_test::TestServer;

use economic_agents_api::services::{
    ComputeServiceState, MarketplaceServiceState, WalletServiceState, compute_router,
    marketplace_router, wallet_router,
};
use economic_agents_mock::{MockBackendConfig, MockBackendFactory};

/// Create a test server for the wallet service.
async fn create_wallet_test_server() -> TestServer {
    let backends = MockBackendFactory::create_with_config(MockBackendConfig {
        initial_balance: 100.0,
        initial_compute_hours: 48.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 10,
    })
    .await;

    let state = Arc::new(WalletServiceState {
        wallet: Arc::new(RwLock::new(backends.wallet)),
    });

    let app = wallet_router(state);
    TestServer::new(app).unwrap()
}

/// Create a test server for the compute service.
async fn create_compute_test_server() -> TestServer {
    let backends = MockBackendFactory::create_with_config(MockBackendConfig {
        initial_balance: 100.0,
        initial_compute_hours: 48.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 10,
    })
    .await;

    let state = Arc::new(ComputeServiceState {
        compute: Arc::new(RwLock::new(backends.compute)),
    });

    let app = compute_router(state);
    TestServer::new(app).unwrap()
}

/// Create a test server for the marketplace service.
async fn create_marketplace_test_server() -> TestServer {
    let backends = MockBackendFactory::create_with_config(MockBackendConfig {
        initial_balance: 100.0,
        initial_compute_hours: 48.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 10,
    })
    .await;

    let state = Arc::new(MarketplaceServiceState {
        marketplace: Arc::new(RwLock::new(backends.marketplace)),
    });

    let app = marketplace_router(state);
    TestServer::new(app).unwrap()
}

// ============================================================================
// Wallet Service Tests
// ============================================================================

#[tokio::test]
async fn test_wallet_health() {
    let server = create_wallet_test_server().await;

    let response = server.get("/health").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["status"], "healthy");
    assert_eq!(body["service"], "wallet");
}

#[tokio::test]
async fn test_wallet_get_balance() {
    let server = create_wallet_test_server().await;

    let response = server.get("/balance").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["balance"], 100.0);
    assert!(body["address"].is_string());
}

#[tokio::test]
async fn test_wallet_send_payment() {
    let server = create_wallet_test_server().await;

    let response = server
        .post("/send")
        .json(&serde_json::json!({
            "to": "recipient-address",
            "amount": 10.0,
            "memo": "Test payment"
        }))
        .await;

    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert!(body["transaction"]["id"].is_string());
    assert_eq!(body["transaction"]["amount"], 10.0);
    assert_eq!(body["transaction"]["to"], "recipient-address");
}

#[tokio::test]
async fn test_wallet_receive_payment() {
    let server = create_wallet_test_server().await;

    let response = server
        .post("/receive")
        .json(&serde_json::json!({
            "from": "sender-address",
            "amount": 50.0
        }))
        .await;

    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["transaction"]["amount"], 50.0);
}

#[tokio::test]
async fn test_wallet_transaction_history() {
    let server = create_wallet_test_server().await;

    // First, make some transactions
    server
        .post("/send")
        .json(&serde_json::json!({
            "to": "recipient",
            "amount": 5.0
        }))
        .await;

    server
        .post("/receive")
        .json(&serde_json::json!({
            "amount": 10.0
        }))
        .await;

    // Get history
    let response = server.get("/transactions?limit=10").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert!(body["transactions"].is_array());
    assert_eq!(body["transactions"].as_array().unwrap().len(), 2);
}

// ============================================================================
// Compute Service Tests
// ============================================================================

#[tokio::test]
async fn test_compute_health() {
    let server = create_compute_test_server().await;

    let response = server.get("/health").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["status"], "healthy");
    assert_eq!(body["service"], "compute");
}

#[tokio::test]
async fn test_compute_status() {
    let server = create_compute_test_server().await;

    let response = server.get("/status").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["status"]["hours_remaining"], 48.0);
    assert_eq!(body["status"]["cost_per_hour"], 0.10);
}

#[tokio::test]
async fn test_compute_add_funds() {
    let server = create_compute_test_server().await;

    let response = server
        .post("/funds")
        .json(&serde_json::json!({"amount": 10.0}))
        .await;

    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    // Adding $10 at $0.10/hour = 100 more hours
    assert_eq!(body["status"]["hours_remaining"], 148.0);
}

#[tokio::test]
async fn test_compute_consume_time() {
    let server = create_compute_test_server().await;

    let response = server
        .post("/consume")
        .json(&serde_json::json!({"hours": 8.0}))
        .await;

    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["status"]["hours_remaining"], 40.0);
}

#[tokio::test]
async fn test_compute_hours_remaining() {
    let server = create_compute_test_server().await;

    let response = server.get("/hours").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["hours"], 48.0);
    assert_eq!(body["cost_per_hour"], 0.10);
}

// ============================================================================
// Marketplace Service Tests
// ============================================================================

#[tokio::test]
async fn test_marketplace_health() {
    let server = create_marketplace_test_server().await;

    let response = server.get("/health").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert_eq!(body["status"], "healthy");
    assert_eq!(body["service"], "marketplace");
}

#[tokio::test]
async fn test_marketplace_list_tasks() {
    let server = create_marketplace_test_server().await;

    let response = server.get("/tasks").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert!(body["tasks"].is_array());
    assert_eq!(body["total"], 10);
}

#[tokio::test]
async fn test_marketplace_list_tasks_with_filter() {
    let server = create_marketplace_test_server().await;

    let response = server.get("/tasks?limit=5&min_reward=10.0").await;
    response.assert_status_ok();

    let body: serde_json::Value = response.json();
    assert!(body["tasks"].is_array());
    let tasks = body["tasks"].as_array().unwrap();
    assert!(tasks.len() <= 5);
}

#[tokio::test]
async fn test_marketplace_claim_and_submit() {
    let server = create_marketplace_test_server().await;

    // First, get available tasks
    let response = server.get("/tasks?limit=1").await;
    let body: serde_json::Value = response.json();
    let tasks = body["tasks"].as_array().unwrap();

    if tasks.is_empty() {
        // Skip if no tasks available
        return;
    }

    let task_id = tasks[0]["id"].as_str().unwrap();

    // Claim the task
    let claim_response = server
        .post(&format!("/tasks/{}/claim", task_id))
        .json(&serde_json::json!({"agent_id": "test-agent"}))
        .await;

    claim_response.assert_status_ok();

    let claim_body: serde_json::Value = claim_response.json();
    assert_eq!(claim_body["task"]["status"], "claimed");

    // Submit a solution
    let submit_response = server
        .post(&format!("/tasks/{}/submit", task_id))
        .json(&serde_json::json!({
            "agent_id": "test-agent",
            "content": "Here is my solution"
        }))
        .await;

    submit_response.assert_status_ok();

    let submit_body: serde_json::Value = submit_response.json();
    assert!(submit_body["submission"]["id"].is_string());
}
