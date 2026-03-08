use std::time::Duration;

use reqwest::Client;

use crate::ApiError;
use crate::orchestrator_models::*;

/// Default request timeout for orchestrator HTTP requests (60 seconds).
///
/// Longer than the detection client because job submission may involve
/// Docker image pulls or container startup on the orchestrator side.
const DEFAULT_REQUEST_TIMEOUT: Duration = Duration::from_secs(60);

/// Default port for the GPU orchestrator API.
pub const DEFAULT_ORCHESTRATOR_PORT: u16 = 8000;

/// Client for the GPU Orchestrator API (port 8000).
///
/// This is separate from the detection API (port 8022). The orchestrator
/// manages Docker containers, job queues, and long-running training tasks.
pub struct OrchestratorClient {
    base_url: String,
    client: Client,
    api_key: Option<String>,
}

impl OrchestratorClient {
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

    pub fn localhost() -> Self {
        Self::new(
            &format!("http://localhost:{DEFAULT_ORCHESTRATOR_PORT}"),
            None,
        )
    }

    // -- Job creation --

    pub async fn train_backdoor(
        &self,
        req: &TrainBackdoorJobRequest,
    ) -> Result<JobResponse, ApiError> {
        self.post("/api/jobs/train-backdoor", req).await
    }

    pub async fn train_probes(&self, req: &TrainProbesJobRequest) -> Result<JobResponse, ApiError> {
        self.post("/api/jobs/train-probes", req).await
    }

    pub async fn safety_training(
        &self,
        req: &SafetyTrainingJobRequest,
    ) -> Result<JobResponse, ApiError> {
        self.post("/api/jobs/safety-training", req).await
    }

    // -- Job queries --

    pub async fn list_jobs(
        &self,
        status: Option<&str>,
        job_type: Option<&str>,
        limit: u32,
        offset: u32,
    ) -> Result<JobListResponse, ApiError> {
        let mut query = format!("?limit={limit}&offset={offset}");
        if let Some(s) = status {
            query.push_str(&format!("&status={s}"));
        }
        if let Some(t) = job_type {
            query.push_str(&format!("&job_type={t}"));
        }
        let path = format!("/api/jobs{query}");
        self.get(&path).await
    }

    pub async fn get_job(&self, job_id: &str) -> Result<JobResponse, ApiError> {
        self.get(&format!("/api/jobs/{job_id}")).await
    }

    pub async fn cancel_job(&self, job_id: &str) -> Result<serde_json::Value, ApiError> {
        self.delete(&format!("/api/jobs/{job_id}")).await
    }

    // -- Logs --

    pub async fn get_logs(&self, job_id: &str, tail: u32) -> Result<String, ApiError> {
        let url = format!("{}/api/jobs/{job_id}/logs?tail={tail}", self.base_url);
        let mut request = self.client.get(&url);
        if let Some(key) = &self.api_key {
            request = request.header("X-API-Key", key);
        }
        let resp = request.send().await.map_err(|e| ApiError::Unreachable {
            url: url.clone(),
            source: e,
        })?;
        let status = resp.status();
        if status.is_success() {
            Ok(resp.text().await?)
        } else {
            let body = resp.text().await.unwrap_or_default();
            Err(ApiError::Api {
                status: status.as_u16(),
                body,
            })
        }
    }

    // -- System --

    pub async fn system_status(&self) -> Result<SystemStatusResponse, ApiError> {
        self.get("/api/system/status").await
    }

    pub async fn health(&self) -> Result<serde_json::Value, ApiError> {
        self.get("/health").await
    }

    // -- Internal helpers --

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

    async fn delete<T: serde::de::DeserializeOwned>(&self, path: &str) -> Result<T, ApiError> {
        let url = format!("{}{path}", self.base_url);
        let mut request = self.client.delete(&url);
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
    fn orchestrator_client_construction() {
        let client = OrchestratorClient::localhost();
        assert_eq!(client.base_url, "http://localhost:8000");
    }

    #[test]
    fn orchestrator_with_api_key() {
        let client = OrchestratorClient::new("http://gpu-host:8000", Some("key123".into()));
        assert_eq!(client.api_key.as_deref(), Some("key123"));
    }
}
