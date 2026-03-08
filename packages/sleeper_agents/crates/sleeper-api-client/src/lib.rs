mod models;

pub use models::*;

use reqwest::Client;
use thiserror::Error;

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
        Self {
            base_url,
            client: Client::new(),
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
}
