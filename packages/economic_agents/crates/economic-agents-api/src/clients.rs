//! HTTP API clients for backend services.
//!
//! These clients implement the core interface traits using HTTP requests
//! to connect to the backend API services.

use async_trait::async_trait;
use reqwest::Client;
use std::time::Duration;

use economic_agents_interfaces::{
    Compute, ComputeStatus, Currency, EconomicAgentError, Hours, Marketplace, Result, Task,
    TaskFilter, TaskSubmission, Transaction, Wallet,
};

use crate::models::*;

/// Configuration for an API client.
#[derive(Debug, Clone)]
pub struct ApiClientConfig {
    /// Base URL of the service.
    pub base_url: String,
    /// API key for authentication.
    pub api_key: Option<String>,
    /// Request timeout.
    pub timeout: Duration,
    /// Agent ID for identifying requests.
    pub agent_id: Option<String>,
}

impl ApiClientConfig {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into(),
            api_key: None,
            timeout: Duration::from_secs(30),
            agent_id: None,
        }
    }

    pub fn with_api_key(mut self, key: impl Into<String>) -> Self {
        self.api_key = Some(key.into());
        self
    }

    pub fn with_timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    pub fn with_agent_id(mut self, agent_id: impl Into<String>) -> Self {
        self.agent_id = Some(agent_id.into());
        self
    }
}

/// Shared client implementation with common HTTP logic.
#[derive(Clone)]
struct HttpClient {
    client: Client,
    base_url: String,
    api_key: Option<String>,
}

impl HttpClient {
    fn new(config: &ApiClientConfig) -> Result<Self> {
        let client = Client::builder()
            .timeout(config.timeout)
            .build()
            .map_err(|e| EconomicAgentError::Network(e.to_string()))?;

        Ok(Self {
            client,
            base_url: config.base_url.clone(),
            api_key: config.api_key.clone(),
        })
    }

    fn request(&self, method: reqwest::Method, path: &str) -> reqwest::RequestBuilder {
        let url = format!("{}{}", self.base_url, path);
        let mut req = self.client.request(method, &url);

        if let Some(ref key) = self.api_key {
            req = req.header("X-API-Key", key);
        }

        req.header("Content-Type", "application/json")
    }

    async fn get<T: serde::de::DeserializeOwned>(&self, path: &str) -> Result<T> {
        let response = self
            .request(reqwest::Method::GET, path)
            .send()
            .await
            .map_err(|e| EconomicAgentError::Network(e.to_string()))?;

        self.handle_response(response).await
    }

    async fn post<T: serde::de::DeserializeOwned, B: serde::Serialize>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T> {
        let response = self
            .request(reqwest::Method::POST, path)
            .json(body)
            .send()
            .await
            .map_err(|e| EconomicAgentError::Network(e.to_string()))?;

        self.handle_response(response).await
    }

    #[allow(dead_code)]
    async fn delete(&self, path: &str) -> Result<()> {
        let response = self
            .request(reqwest::Method::DELETE, path)
            .send()
            .await
            .map_err(|e| EconomicAgentError::Network(e.to_string()))?;

        if response.status().is_success() {
            Ok(())
        } else {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            Err(EconomicAgentError::Network(format!(
                "HTTP {} - {}",
                status, body
            )))
        }
    }

    async fn handle_response<T: serde::de::DeserializeOwned>(
        &self,
        response: reqwest::Response,
    ) -> Result<T> {
        let status = response.status();

        if status.is_success() {
            response.json().await.map_err(|e| {
                EconomicAgentError::Internal(format!("Failed to parse response: {}", e))
            })
        } else {
            let body = response.text().await.unwrap_or_default();

            // Try to parse as API error response
            if let Ok(error_response) = serde_json::from_str::<ApiErrorResponse>(&body) {
                Err(EconomicAgentError::Network(format!(
                    "{}: {}",
                    error_response.code, error_response.error
                )))
            } else {
                Err(EconomicAgentError::Network(format!(
                    "HTTP {} - {}",
                    status, body
                )))
            }
        }
    }
}

// ============================================================================
// Wallet API Client
// ============================================================================

/// HTTP client for the Wallet API service.
#[derive(Clone)]
pub struct WalletApiClient {
    http: HttpClient,
}

impl WalletApiClient {
    /// Create a new wallet API client.
    pub fn new(config: ApiClientConfig) -> Result<Self> {
        Ok(Self {
            http: HttpClient::new(&config)?,
        })
    }
}

#[async_trait]
impl Wallet for WalletApiClient {
    async fn get_balance(&self) -> Result<Currency> {
        let response: BalanceResponse = self.http.get("/balance").await?;
        Ok(response.balance)
    }

    async fn get_address(&self) -> Result<String> {
        let response: BalanceResponse = self.http.get("/balance").await?;
        Ok(response.address)
    }

    async fn send_payment(
        &self,
        to: &str,
        amount: Currency,
        memo: Option<&str>,
    ) -> Result<Transaction> {
        let request = SendPaymentRequest {
            to: to.to_string(),
            amount,
            memo: memo.map(|s| s.to_string()),
        };
        let response: TransactionResponse = self.http.post("/send", &request).await?;
        Ok(response.transaction)
    }

    async fn receive_payment(
        &self,
        from: Option<&str>,
        amount: Currency,
        memo: Option<&str>,
    ) -> Result<Transaction> {
        let request = ReceivePaymentRequest {
            from: from.map(|s| s.to_string()),
            amount,
            memo: memo.map(|s| s.to_string()),
        };
        let response: TransactionResponse = self.http.post("/receive", &request).await?;
        Ok(response.transaction)
    }

    async fn get_transaction_history(&self, limit: usize) -> Result<Vec<Transaction>> {
        let response: TransactionHistoryResponse = self
            .http
            .get(&format!("/transactions?limit={}", limit))
            .await?;
        Ok(response.transactions)
    }
}

// ============================================================================
// Compute API Client
// ============================================================================

/// HTTP client for the Compute API service.
#[derive(Clone)]
pub struct ComputeApiClient {
    http: HttpClient,
}

impl ComputeApiClient {
    /// Create a new compute API client.
    pub fn new(config: ApiClientConfig) -> Result<Self> {
        Ok(Self {
            http: HttpClient::new(&config)?,
        })
    }
}

#[async_trait]
impl Compute for ComputeApiClient {
    async fn get_status(&self) -> Result<ComputeStatus> {
        let response: ComputeStatusResponse = self.http.get("/status").await?;
        Ok(response.status)
    }

    async fn add_funds(&self, amount: Currency) -> Result<ComputeStatus> {
        let request = AddFundsRequest { amount };
        let response: ComputeStatusResponse = self.http.post("/funds", &request).await?;
        Ok(response.status)
    }

    async fn consume_time(&self, hours: Hours) -> Result<ComputeStatus> {
        let request = ConsumeTimeRequest { hours };
        let response: ComputeStatusResponse = self.http.post("/consume", &request).await?;
        Ok(response.status)
    }

    async fn get_cost_per_hour(&self) -> Result<Currency> {
        let response: ComputeStatusResponse = self.http.get("/status").await?;
        Ok(response.status.cost_per_hour)
    }

    async fn get_hours_remaining(&self) -> Result<Hours> {
        let response: HoursRemainingResponse = self.http.get("/hours").await?;
        Ok(response.hours)
    }
}

// ============================================================================
// Marketplace API Client
// ============================================================================

/// HTTP client for the Marketplace API service.
#[derive(Clone)]
pub struct MarketplaceApiClient {
    http: HttpClient,
}

impl MarketplaceApiClient {
    /// Create a new marketplace API client.
    pub fn new(config: ApiClientConfig) -> Result<Self> {
        Ok(Self {
            http: HttpClient::new(&config)?,
        })
    }
}

#[async_trait]
impl Marketplace for MarketplaceApiClient {
    async fn list_available_tasks(&self, filter: Option<TaskFilter>) -> Result<Vec<Task>> {
        let mut path = "/tasks".to_string();

        if let Some(f) = filter {
            let mut params = Vec::new();

            if let Some(cat) = f.category {
                params.push(format!(
                    "category={}",
                    serde_json::to_string(&cat)
                        .unwrap_or_default()
                        .trim_matches('"')
                ));
            }
            if let Some(min) = f.min_reward {
                params.push(format!("min_reward={}", min));
            }
            if let Some(max) = f.max_reward {
                params.push(format!("max_reward={}", max));
            }
            if let Some(diff) = f.max_difficulty {
                params.push(format!("max_difficulty={}", diff));
            }
            if let Some(hours) = f.max_hours {
                params.push(format!("max_hours={}", hours));
            }
            if let Some(limit) = f.limit {
                params.push(format!("limit={}", limit));
            }

            if !params.is_empty() {
                path = format!("{}?{}", path, params.join("&"));
            }
        }

        let response: TaskListResponse = self.http.get(&path).await?;
        Ok(response.tasks)
    }

    async fn claim_task(
        &self,
        task_id: economic_agents_interfaces::EntityId,
        agent_id: &str,
    ) -> Result<Task> {
        let request = ClaimTaskRequest {
            agent_id: agent_id.to_string(),
        };
        let response: TaskResponse = self
            .http
            .post(&format!("/tasks/{}/claim", task_id), &request)
            .await?;
        Ok(response.task)
    }

    async fn submit_solution(
        &self,
        task_id: economic_agents_interfaces::EntityId,
        agent_id: &str,
        content: &str,
    ) -> Result<TaskSubmission> {
        let request = SubmitSolutionRequest {
            agent_id: agent_id.to_string(),
            content: content.to_string(),
        };
        let response: SubmissionResponse = self
            .http
            .post(&format!("/tasks/{}/submit", task_id), &request)
            .await?;
        Ok(response.submission)
    }

    async fn check_submission_status(
        &self,
        submission_id: economic_agents_interfaces::EntityId,
    ) -> Result<TaskSubmission> {
        let response: SubmissionResponse = self
            .http
            .get(&format!("/submissions/{}", submission_id))
            .await?;
        Ok(response.submission)
    }

    async fn get_task(&self, task_id: economic_agents_interfaces::EntityId) -> Result<Task> {
        let response: TaskResponse = self.http.get(&format!("/tasks/{}", task_id)).await?;
        Ok(response.task)
    }

    async fn release_task(
        &self,
        task_id: economic_agents_interfaces::EntityId,
        agent_id: &str,
    ) -> Result<()> {
        let request = ReleaseTaskRequest {
            agent_id: agent_id.to_string(),
        };
        let _: serde_json::Value = self
            .http
            .post(&format!("/tasks/{}/release", task_id), &request)
            .await?;
        Ok(())
    }
}

// ============================================================================
// API Client Factory
// ============================================================================

/// Factory for creating API clients.
pub struct ApiClientFactory;

impl ApiClientFactory {
    /// Create all API clients with a common configuration base.
    pub fn create_all(
        endpoints: &crate::config::ApiEndpointConfig,
        api_key: Option<&str>,
    ) -> Result<ApiClients> {
        let wallet_config = ApiClientConfig::new(&endpoints.wallet_url);
        let compute_config = ApiClientConfig::new(&endpoints.compute_url);
        let marketplace_config = ApiClientConfig::new(&endpoints.marketplace_url);

        let wallet_config = if let Some(key) = api_key {
            wallet_config.with_api_key(key)
        } else {
            wallet_config
        };
        let compute_config = if let Some(key) = api_key {
            compute_config.with_api_key(key)
        } else {
            compute_config
        };
        let marketplace_config = if let Some(key) = api_key {
            marketplace_config.with_api_key(key)
        } else {
            marketplace_config
        };

        Ok(ApiClients {
            wallet: WalletApiClient::new(wallet_config)?,
            compute: ComputeApiClient::new(compute_config)?,
            marketplace: MarketplaceApiClient::new(marketplace_config)?,
        })
    }
}

/// Collection of all API clients.
pub struct ApiClients {
    pub wallet: WalletApiClient,
    pub compute: ComputeApiClient,
    pub marketplace: MarketplaceApiClient,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_api_client_config() {
        let config = ApiClientConfig::new("http://localhost:8001")
            .with_api_key("test-key")
            .with_timeout(Duration::from_secs(60))
            .with_agent_id("agent-1");

        assert_eq!(config.base_url, "http://localhost:8001");
        assert_eq!(config.api_key, Some("test-key".to_string()));
        assert_eq!(config.timeout, Duration::from_secs(60));
        assert_eq!(config.agent_id, Some("agent-1".to_string()));
    }

    #[test]
    fn test_api_error_response() {
        let error = ApiErrorResponse::new("Not found", "NOT_FOUND")
            .with_details(serde_json::json!({"id": "123"}));

        assert_eq!(error.error, "Not found");
        assert_eq!(error.code, "NOT_FOUND");
        assert!(error.details.is_some());
    }
}
