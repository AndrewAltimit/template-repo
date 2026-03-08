mod models;
pub mod orchestrator;
pub mod orchestrator_models;

pub use models::*;
pub use orchestrator::OrchestratorClient;
pub use orchestrator_models::*;

use std::time::Duration;

use reqwest::Client;
use thiserror::Error;

/// Default request timeout for HTTP clients (30 seconds).
const DEFAULT_REQUEST_TIMEOUT: Duration = Duration::from_secs(30);

/// Default port for the sleeper agents FastAPI server inside the container.
pub const DEFAULT_API_PORT: u16 = 8022;

#[derive(Debug, Error)]
pub enum ApiError {
    #[error("HTTP request failed: {0}")]
    Request(#[from] reqwest::Error),

    #[error("API returned error {status}: {body}")]
    Api { status: u16, body: String },

    #[error("API server not reachable at {url}: {source}")]
    Unreachable { url: String, source: reqwest::Error },
}

/// Typed client for the sleeper agents detection API.
///
/// Communicates with the FastAPI server running inside the GPU container
/// on the configured port (default 8022).
pub struct SleeperClient {
    base_url: String,
    client: Client,
    api_key: Option<String>,
}

impl SleeperClient {
    /// Create a new client pointing at the given base URL.
    ///
    /// Example: `SleeperClient::new("http://localhost:8022", None)`
    pub fn new(base_url: &str, api_key: Option<String>) -> Self {
        let base_url = base_url.trim_end_matches('/').to_string();
        let client = Client::builder()
            .timeout(DEFAULT_REQUEST_TIMEOUT)
            .build()
            .unwrap_or_default();
        Self {
            base_url,
            client,
            api_key,
        }
    }

    /// Create a client for localhost on the default port.
    pub fn localhost() -> Self {
        Self::new(&format!("http://localhost:{DEFAULT_API_PORT}"), None)
    }

    /// Check if the API server is reachable.
    pub async fn health(&self) -> Result<HealthResponse, ApiError> {
        self.get("/health").await
    }

    /// Get system status (model loaded, GPU info, etc.).
    pub async fn status(&self) -> Result<StatusResponse, ApiError> {
        self.get("/status").await
    }

    /// Initialize the detector with a model.
    pub async fn initialize(&self, req: &InitRequest) -> Result<serde_json::Value, ApiError> {
        self.post("/initialize", req).await
    }

    /// Run backdoor detection on text.
    pub async fn detect(&self, req: &DetectRequest) -> Result<serde_json::Value, ApiError> {
        self.post("/detect", req).await
    }

    /// Train probes on the loaded model.
    pub async fn train_probes(&self, n_samples: u32) -> Result<serde_json::Value, ApiError> {
        let url = format!("{}/train_probes?n_samples={n_samples}", self.base_url);
        let mut request = self.client.post(&url);
        if let Some(key) = &self.api_key {
            request = request.header("X-API-Key", key);
        }
        let resp = request.send().await?;
        self.handle_response(resp).await
    }

    /// Sweep layers for optimal probe placement.
    pub async fn layer_sweep(&self, n_samples: u32) -> Result<serde_json::Value, ApiError> {
        self.post("/layer_sweep", &SweepRequest { n_samples }).await
    }

    /// Train a backdoored model for testing.
    pub async fn train_backdoor(&self, req: &TrainRequest) -> Result<serde_json::Value, ApiError> {
        self.post("/train_backdoor", req).await
    }

    /// Run honeypot tests.
    pub async fn honeypot_test(
        &self,
        req: &HoneypotRequest,
    ) -> Result<serde_json::Value, ApiError> {
        self.post("/honeypot_test", req).await
    }

    // -- internal helpers --

    async fn get<T: serde::de::DeserializeOwned>(&self, path: &str) -> Result<T, ApiError> {
        let url = format!("{}{path}", self.base_url);
        let mut request = self.client.get(&url);
        if let Some(key) = &self.api_key {
            request = request.header("X-API-Key", key);
        }
        let resp = request.send().await.map_err(|e| ApiError::Unreachable {
            url: url.clone(),
            source: e,
        })?;
        self.handle_response(resp).await
    }

    async fn post<T: serde::Serialize, R: serde::de::DeserializeOwned>(
        &self,
        path: &str,
        body: &T,
    ) -> Result<R, ApiError> {
        let url = format!("{}{path}", self.base_url);
        let mut request = self.client.post(&url).json(body);
        if let Some(key) = &self.api_key {
            request = request.header("X-API-Key", key);
        }
        let resp = request.send().await?;
        self.handle_response(resp).await
    }

    async fn handle_response<T: serde::de::DeserializeOwned>(
        &self,
        resp: reqwest::Response,
    ) -> Result<T, ApiError> {
        let status = resp.status();
        if status.is_success() {
            Ok(resp.json().await?)
        } else {
            let body = resp.text().await.unwrap_or_default();
            Err(ApiError::Api {
                status: status.as_u16(),
                body,
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn client_construction() {
        let client = SleeperClient::localhost();
        assert_eq!(client.base_url, "http://localhost:8022");
        assert!(client.api_key.is_none());
    }

    #[test]
    fn client_with_trailing_slash() {
        let client = SleeperClient::new("http://example.com:8022/", None);
        assert_eq!(client.base_url, "http://example.com:8022");
    }

    #[test]
    fn client_with_api_key() {
        let client = SleeperClient::new("http://localhost:8022", Some("secret".into()));
        assert_eq!(client.api_key.as_deref(), Some("secret"));
    }

    #[test]
    fn status_response_effective_model() {
        let status: StatusResponse =
            serde_json::from_str(r#"{"initialized": true, "model": "gpt2", "cpu_mode": false}"#)
                .unwrap();
        assert_eq!(status.effective_model(), Some("gpt2"));
        assert!(status.is_model_loaded());
    }

    #[test]
    fn status_response_not_initialized() {
        let status: StatusResponse =
            serde_json::from_str(r#"{"initialized": false, "model": null}"#).unwrap();
        assert_eq!(status.effective_model(), None);
        assert!(!status.is_model_loaded());
    }

    #[test]
    fn status_response_legacy_fields() {
        // Test backward compat with model_loaded/model_name fields
        let status: StatusResponse = serde_json::from_str(
            r#"{"model_loaded": true, "model_name": "mistral-7b", "status": "ok"}"#,
        )
        .unwrap();
        assert_eq!(status.effective_model(), Some("mistral-7b"));
        assert!(status.is_model_loaded());
    }

    #[test]
    fn detect_request_serialization() {
        let req = DetectRequest {
            text: "test input".to_string(),
            use_ensemble: Some(true),
            run_interventions: None,
            check_attention: None,
        };
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["text"], "test input");
        assert_eq!(json["use_ensemble"], true);
        // None fields should be omitted
        assert!(json.get("run_interventions").is_none());
        assert!(json.get("check_attention").is_none());
    }
}
