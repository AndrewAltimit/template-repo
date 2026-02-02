//! Axum-based API services.
//!
//! These services provide HTTP endpoints for the backend interfaces,
//! allowing agents to connect via the API clients.

use axum::{
    Json, Router,
    extract::{Path, Query, State},
    http::StatusCode,
    routing::{get, post},
};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;
use uuid::Uuid;

use economic_agents_interfaces::{Compute, EconomicAgentError, Marketplace, TaskFilter, Wallet};
use economic_agents_mock::{
    MockBackendConfig, MockBackendFactory, MockCompute, MockMarketplace, MockWallet,
};

use crate::middleware::{AuthConfig, RateLimitConfig};
use crate::models::*;

/// Type alias for API results to avoid conflict with interfaces::Result
type ApiResult<T> = std::result::Result<T, (StatusCode, Json<ApiErrorResponse>)>;

// ============================================================================
// Service State
// ============================================================================

/// Shared state for wallet service.
pub struct WalletServiceState {
    pub wallet: Arc<RwLock<MockWallet>>,
}

/// Shared state for compute service.
pub struct ComputeServiceState {
    pub compute: Arc<RwLock<MockCompute>>,
}

/// Shared state for marketplace service.
pub struct MarketplaceServiceState {
    pub marketplace: Arc<RwLock<MockMarketplace>>,
}

// ============================================================================
// Wallet Service
// ============================================================================

/// Create the wallet service router.
pub fn wallet_router(state: Arc<WalletServiceState>) -> Router {
    Router::new()
        .route("/health", get(wallet_health))
        .route("/balance", get(get_balance))
        .route("/send", post(send_payment))
        .route("/receive", post(receive_payment))
        .route("/transactions", get(get_transactions))
        .with_state(state)
}

async fn wallet_health() -> Json<HealthResponse> {
    Json(HealthResponse::healthy("wallet"))
}

async fn get_balance(
    State(state): State<Arc<WalletServiceState>>,
) -> ApiResult<Json<BalanceResponse>> {
    let wallet = state.wallet.read().await;

    let balance = wallet.get_balance().await.map_err(to_api_error)?;
    let address = wallet.get_address().await.map_err(to_api_error)?;

    Ok(Json(BalanceResponse { balance, address }))
}

async fn send_payment(
    State(state): State<Arc<WalletServiceState>>,
    Json(request): Json<SendPaymentRequest>,
) -> ApiResult<Json<TransactionResponse>> {
    let wallet = state.wallet.read().await;

    let transaction = wallet
        .send_payment(&request.to, request.amount, request.memo.as_deref())
        .await
        .map_err(to_api_error)?;

    Ok(Json(TransactionResponse { transaction }))
}

async fn receive_payment(
    State(state): State<Arc<WalletServiceState>>,
    Json(request): Json<ReceivePaymentRequest>,
) -> ApiResult<Json<TransactionResponse>> {
    let wallet = state.wallet.read().await;

    let transaction = wallet
        .receive_payment(
            request.from.as_deref(),
            request.amount,
            request.memo.as_deref(),
        )
        .await
        .map_err(to_api_error)?;

    Ok(Json(TransactionResponse { transaction }))
}

#[derive(Debug, serde::Deserialize)]
struct TransactionQuery {
    #[serde(default = "default_limit")]
    limit: usize,
}

fn default_limit() -> usize {
    100
}

async fn get_transactions(
    State(state): State<Arc<WalletServiceState>>,
    Query(query): Query<TransactionQuery>,
) -> ApiResult<Json<TransactionHistoryResponse>> {
    let wallet = state.wallet.read().await;

    let transactions = wallet
        .get_transaction_history(query.limit)
        .await
        .map_err(to_api_error)?;

    let total = transactions.len();

    Ok(Json(TransactionHistoryResponse {
        transactions,
        total,
    }))
}

// ============================================================================
// Compute Service
// ============================================================================

/// Create the compute service router.
pub fn compute_router(state: Arc<ComputeServiceState>) -> Router {
    Router::new()
        .route("/health", get(compute_health))
        .route("/status", get(get_compute_status))
        .route("/funds", post(add_compute_funds))
        .route("/consume", post(consume_compute_time))
        .route("/hours", get(get_hours_remaining))
        .with_state(state)
}

async fn compute_health() -> Json<HealthResponse> {
    Json(HealthResponse::healthy("compute"))
}

async fn get_compute_status(
    State(state): State<Arc<ComputeServiceState>>,
) -> ApiResult<Json<ComputeStatusResponse>> {
    let compute = state.compute.read().await;

    let status = compute.get_status().await.map_err(to_api_error)?;

    Ok(Json(ComputeStatusResponse { status }))
}

async fn add_compute_funds(
    State(state): State<Arc<ComputeServiceState>>,
    Json(request): Json<AddFundsRequest>,
) -> ApiResult<Json<ComputeStatusResponse>> {
    let compute = state.compute.read().await;

    let status = compute
        .add_funds(request.amount)
        .await
        .map_err(to_api_error)?;

    Ok(Json(ComputeStatusResponse { status }))
}

async fn consume_compute_time(
    State(state): State<Arc<ComputeServiceState>>,
    Json(request): Json<ConsumeTimeRequest>,
) -> ApiResult<Json<ComputeStatusResponse>> {
    let compute = state.compute.read().await;

    let status = compute
        .consume_time(request.hours)
        .await
        .map_err(to_api_error)?;

    Ok(Json(ComputeStatusResponse { status }))
}

async fn get_hours_remaining(
    State(state): State<Arc<ComputeServiceState>>,
) -> ApiResult<Json<HoursRemainingResponse>> {
    let compute = state.compute.read().await;

    let hours = compute.get_hours_remaining().await.map_err(to_api_error)?;
    let cost_per_hour = compute.get_cost_per_hour().await.map_err(to_api_error)?;

    Ok(Json(HoursRemainingResponse {
        hours,
        cost_per_hour,
    }))
}

// ============================================================================
// Marketplace Service
// ============================================================================

/// Create the marketplace service router.
pub fn marketplace_router(state: Arc<MarketplaceServiceState>) -> Router {
    Router::new()
        .route("/health", get(marketplace_health))
        .route("/tasks", get(list_tasks))
        .route("/tasks/:task_id", get(get_task))
        .route("/tasks/:task_id/claim", post(claim_task))
        .route("/tasks/:task_id/submit", post(submit_solution))
        .route("/tasks/:task_id/release", post(release_task))
        .route("/submissions/:submission_id", get(get_submission))
        .with_state(state)
}

async fn marketplace_health() -> Json<HealthResponse> {
    Json(HealthResponse::healthy("marketplace"))
}

async fn list_tasks(
    State(state): State<Arc<MarketplaceServiceState>>,
    Query(query): Query<ListTasksRequest>,
) -> ApiResult<Json<TaskListResponse>> {
    let marketplace = state.marketplace.read().await;

    let filter = if query.category.is_some()
        || query.min_reward.is_some()
        || query.max_reward.is_some()
        || query.max_difficulty.is_some()
        || query.max_hours.is_some()
        || query.limit.is_some()
    {
        Some(TaskFilter {
            category: query.category,
            min_reward: query.min_reward,
            max_reward: query.max_reward,
            max_difficulty: query.max_difficulty,
            max_hours: query.max_hours,
            limit: query.limit,
        })
    } else {
        None
    };

    let tasks = marketplace
        .list_available_tasks(filter)
        .await
        .map_err(to_api_error)?;

    let total = tasks.len();

    Ok(Json(TaskListResponse { tasks, total }))
}

async fn get_task(
    State(state): State<Arc<MarketplaceServiceState>>,
    Path(task_id): Path<Uuid>,
) -> ApiResult<Json<TaskResponse>> {
    let marketplace = state.marketplace.read().await;

    let task = marketplace.get_task(task_id).await.map_err(to_api_error)?;

    Ok(Json(TaskResponse { task }))
}

async fn claim_task(
    State(state): State<Arc<MarketplaceServiceState>>,
    Path(task_id): Path<Uuid>,
    Json(request): Json<ClaimTaskRequest>,
) -> ApiResult<Json<TaskResponse>> {
    let marketplace = state.marketplace.read().await;

    let task = marketplace
        .claim_task(task_id, &request.agent_id)
        .await
        .map_err(to_api_error)?;

    Ok(Json(TaskResponse { task }))
}

async fn submit_solution(
    State(state): State<Arc<MarketplaceServiceState>>,
    Path(task_id): Path<Uuid>,
    Json(request): Json<SubmitSolutionRequest>,
) -> ApiResult<Json<SubmissionResponse>> {
    let marketplace = state.marketplace.read().await;

    let submission = marketplace
        .submit_solution(task_id, &request.agent_id, &request.content)
        .await
        .map_err(to_api_error)?;

    Ok(Json(SubmissionResponse { submission }))
}

async fn release_task(
    State(state): State<Arc<MarketplaceServiceState>>,
    Path(task_id): Path<Uuid>,
    Json(request): Json<ReleaseTaskRequest>,
) -> ApiResult<Json<serde_json::Value>> {
    let marketplace = state.marketplace.read().await;

    marketplace
        .release_task(task_id, &request.agent_id)
        .await
        .map_err(to_api_error)?;

    Ok(Json(serde_json::json!({"status": "released"})))
}

async fn get_submission(
    State(state): State<Arc<MarketplaceServiceState>>,
    Path(submission_id): Path<Uuid>,
) -> ApiResult<Json<SubmissionResponse>> {
    let marketplace = state.marketplace.read().await;

    let submission = marketplace
        .check_submission_status(submission_id)
        .await
        .map_err(to_api_error)?;

    Ok(Json(SubmissionResponse { submission }))
}

// ============================================================================
// Error Conversion
// ============================================================================

fn to_api_error(err: EconomicAgentError) -> (StatusCode, Json<ApiErrorResponse>) {
    let (status, code) = match &err {
        EconomicAgentError::NotInitialized => (StatusCode::BAD_REQUEST, "NOT_INITIALIZED"),
        EconomicAgentError::InsufficientCapital { .. } => {
            (StatusCode::BAD_REQUEST, "INSUFFICIENT_CAPITAL")
        },
        EconomicAgentError::InsufficientInvestorCapital { .. } => {
            (StatusCode::BAD_REQUEST, "INSUFFICIENT_INVESTOR_CAPITAL")
        },
        EconomicAgentError::CompanyBankrupt { .. } => (StatusCode::BAD_REQUEST, "COMPANY_BANKRUPT"),
        EconomicAgentError::InvalidStageTransition { .. } => {
            (StatusCode::BAD_REQUEST, "INVALID_STAGE_TRANSITION")
        },
        EconomicAgentError::CompanyNotFound { .. } => (StatusCode::NOT_FOUND, "COMPANY_NOT_FOUND"),
        EconomicAgentError::ProductDevelopmentFailed { .. } => {
            (StatusCode::BAD_REQUEST, "PRODUCT_DEVELOPMENT_FAILED")
        },
        EconomicAgentError::StageRegression { .. } => {
            (StatusCode::INTERNAL_SERVER_ERROR, "STAGE_REGRESSION")
        },
        EconomicAgentError::InvestmentRejected { .. } => {
            (StatusCode::BAD_REQUEST, "INVESTMENT_REJECTED")
        },
        EconomicAgentError::TaskNotFound { .. } => (StatusCode::NOT_FOUND, "TASK_NOT_FOUND"),
        EconomicAgentError::TaskAlreadyClaimed { .. } => {
            (StatusCode::CONFLICT, "TASK_ALREADY_CLAIMED")
        },
        EconomicAgentError::SubmissionRejected { .. } => {
            (StatusCode::BAD_REQUEST, "SUBMISSION_REJECTED")
        },
        EconomicAgentError::Network(_) => (StatusCode::BAD_GATEWAY, "NETWORK_ERROR"),
        EconomicAgentError::Timeout { .. } => (StatusCode::GATEWAY_TIMEOUT, "TIMEOUT"),
        EconomicAgentError::Serialization(_) => {
            (StatusCode::INTERNAL_SERVER_ERROR, "SERIALIZATION_ERROR")
        },
        EconomicAgentError::Configuration(_) => (StatusCode::INTERNAL_SERVER_ERROR, "CONFIG_ERROR"),
        EconomicAgentError::Internal(_) => (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR"),
    };

    (status, Json(ApiErrorResponse::new(err.to_string(), code)))
}

// ============================================================================
// Server Builder
// ============================================================================

/// Configuration for running API services.
#[derive(Debug, Clone)]
pub struct ServiceConfig {
    /// Port for wallet service.
    pub wallet_port: u16,
    /// Port for compute service.
    pub compute_port: u16,
    /// Port for marketplace service.
    pub marketplace_port: u16,
    /// Backend configuration.
    pub backend_config: MockBackendConfig,
    /// Authentication configuration.
    pub auth_config: AuthConfig,
    /// Rate limiting configuration.
    pub rate_limit_config: RateLimitConfig,
}

impl Default for ServiceConfig {
    fn default() -> Self {
        Self {
            wallet_port: 8001,
            compute_port: 8002,
            marketplace_port: 8003,
            backend_config: MockBackendConfig::default(),
            auth_config: AuthConfig::default(),
            rate_limit_config: RateLimitConfig::default(),
        }
    }
}

/// Builder for creating and running API services.
pub struct ServiceBuilder {
    config: ServiceConfig,
}

impl ServiceBuilder {
    /// Create a new service builder with default configuration.
    pub fn new() -> Self {
        Self {
            config: ServiceConfig::default(),
        }
    }

    /// Set the backend configuration.
    pub fn with_backend_config(mut self, config: MockBackendConfig) -> Self {
        self.config.backend_config = config;
        self
    }

    /// Set the wallet service port.
    pub fn with_wallet_port(mut self, port: u16) -> Self {
        self.config.wallet_port = port;
        self
    }

    /// Set the compute service port.
    pub fn with_compute_port(mut self, port: u16) -> Self {
        self.config.compute_port = port;
        self
    }

    /// Set the marketplace service port.
    pub fn with_marketplace_port(mut self, port: u16) -> Self {
        self.config.marketplace_port = port;
        self
    }

    /// Set authentication configuration.
    pub fn with_auth(mut self, config: AuthConfig) -> Self {
        self.config.auth_config = config;
        self
    }

    /// Set rate limiting configuration.
    pub fn with_rate_limit(mut self, config: RateLimitConfig) -> Self {
        self.config.rate_limit_config = config;
        self
    }

    /// Build and return the service states and routers.
    pub async fn build(self) -> ServiceBundle {
        let mock_backends =
            MockBackendFactory::create_with_config(self.config.backend_config.clone()).await;

        let wallet_state = Arc::new(WalletServiceState {
            wallet: Arc::new(RwLock::new(mock_backends.wallet)),
        });
        let compute_state = Arc::new(ComputeServiceState {
            compute: Arc::new(RwLock::new(mock_backends.compute)),
        });
        let marketplace_state = Arc::new(MarketplaceServiceState {
            marketplace: Arc::new(RwLock::new(mock_backends.marketplace)),
        });

        ServiceBundle {
            wallet_router: wallet_router(wallet_state),
            compute_router: compute_router(compute_state),
            marketplace_router: marketplace_router(marketplace_state),
            config: self.config,
        }
    }
}

impl Default for ServiceBuilder {
    fn default() -> Self {
        Self::new()
    }
}

/// Bundle of service routers ready to run.
pub struct ServiceBundle {
    pub wallet_router: Router,
    pub compute_router: Router,
    pub marketplace_router: Router,
    pub config: ServiceConfig,
}

impl ServiceBundle {
    /// Run all services concurrently.
    pub async fn run(self) -> std::io::Result<()> {
        let wallet_addr = format!("0.0.0.0:{}", self.config.wallet_port);
        let compute_addr = format!("0.0.0.0:{}", self.config.compute_port);
        let marketplace_addr = format!("0.0.0.0:{}", self.config.marketplace_port);

        info!("Starting wallet service on {}", wallet_addr);
        info!("Starting compute service on {}", compute_addr);
        info!("Starting marketplace service on {}", marketplace_addr);

        let wallet_listener = tokio::net::TcpListener::bind(&wallet_addr).await?;
        let compute_listener = tokio::net::TcpListener::bind(&compute_addr).await?;
        let marketplace_listener = tokio::net::TcpListener::bind(&marketplace_addr).await?;

        tokio::try_join!(
            axum::serve(wallet_listener, self.wallet_router),
            axum::serve(compute_listener, self.compute_router),
            axum::serve(marketplace_listener, self.marketplace_router),
        )?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_service_config_default() {
        let config = ServiceConfig::default();
        assert_eq!(config.wallet_port, 8001);
        assert_eq!(config.compute_port, 8002);
        assert_eq!(config.marketplace_port, 8003);
    }

    #[test]
    fn test_service_builder() {
        let builder = ServiceBuilder::new()
            .with_wallet_port(9001)
            .with_compute_port(9002)
            .with_marketplace_port(9003);

        assert_eq!(builder.config.wallet_port, 9001);
        assert_eq!(builder.config.compute_port, 9002);
        assert_eq!(builder.config.marketplace_port, 9003);
    }
}
