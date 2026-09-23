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
            .expect("failed to build HTTP client");
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

    /// Cancel a queued or running job (`DELETE /api/jobs/{id}`).
    ///
    /// The orchestrator rejects this with 400 for jobs that already finished;
    /// use [`Self::delete_job_permanent`] to remove finished jobs.
    pub async fn cancel_job(&self, job_id: &str) -> Result<serde_json::Value, ApiError> {
        self.delete(&format!("/api/jobs/{job_id}")).await
    }

    /// Permanently delete a job (`DELETE /api/jobs/{id}/permanent`). Works for
    /// jobs in any status.
    ///
    /// Removes the job record and its saved log. With `keep_outputs == false`
    /// the orchestrator also deletes the outputs only this job wrote on the
    /// results volume (its per-job directory or explicit output file); shared
    /// evaluation databases and locations other jobs reference are never
    /// deleted.
    pub async fn delete_job_permanent(
        &self,
        job_id: &str,
        keep_outputs: bool,
    ) -> Result<serde_json::Value, ApiError> {
        let query = if keep_outputs {
            "?keep_outputs=true"
        } else {
            ""
        };
        self.delete(&format!("/api/jobs/{job_id}/permanent{query}"))
            .await
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

    /// Fetch log text appended after character offset `since_offset`
    /// (`GET /api/jobs/{id}/logs?since_offset=N`).
    ///
    /// Pass the returned `next_offset` on the next call to receive only new
    /// text. `next_offset` is `None` when the orchestrator does not support
    /// incremental polling.
    pub async fn get_logs_since(
        &self,
        job_id: &str,
        since_offset: u64,
    ) -> Result<LogChunk, ApiError> {
        let url = format!(
            "{}/api/jobs/{job_id}/logs?since_offset={since_offset}",
            self.base_url
        );
        let mut request = self.client.get(&url);
        if let Some(key) = &self.api_key {
            request = request.header("X-API-Key", key);
        }
        let resp = request.send().await.map_err(|e| ApiError::Unreachable {
            url: url.clone(),
            source: e,
        })?;
        let status = resp.status();
        if !status.is_success() {
            let body = resp.text().await.unwrap_or_default();
            return Err(ApiError::Api {
                status: status.as_u16(),
                body,
            });
        }
        let header = |name: &str| {
            resp.headers()
                .get(name)
                .and_then(|v| v.to_str().ok())
                .map(str::to_owned)
        };
        let next_offset = header("x-log-next-offset").and_then(|v| v.parse().ok());
        let reset = header("x-log-reset").as_deref() == Some("true");
        let truncated = header("x-log-truncated").as_deref() == Some("true");
        let complete = header("x-log-complete").as_deref() == Some("true");
        Ok(LogChunk {
            text: resp.text().await?,
            next_offset,
            reset,
            truncated,
            complete,
        })
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

    /// Serve exactly one HTTP request and return its request line.
    fn one_shot_server(
        status_line: &'static str,
        body: &'static str,
    ) -> (String, std::thread::JoinHandle<String>) {
        one_shot_server_with_headers(status_line, "Content-Type: application/json\r\n", body)
    }

    /// Like `one_shot_server`, with extra response header lines (each ending in CRLF).
    fn one_shot_server_with_headers(
        status_line: &'static str,
        headers: &'static str,
        body: &'static str,
    ) -> (String, std::thread::JoinHandle<String>) {
        use std::io::{BufRead, BufReader, Write};

        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let handle = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut reader = BufReader::new(stream.try_clone().unwrap());
            let mut request_line = String::new();
            reader.read_line(&mut request_line).unwrap();
            // Drain headers
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).unwrap();
                if line == "\r\n" || line.is_empty() {
                    break;
                }
            }
            let response = format!(
                "{status_line}\r\n{headers}Content-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            );
            stream.write_all(response.as_bytes()).unwrap();
            request_line.trim_end().to_string()
        });
        (base_url, handle)
    }

    #[tokio::test]
    async fn delete_job_permanent_uses_permanent_endpoint() {
        let (base_url, server) = one_shot_server("HTTP/1.1 200 OK", r#"{"message":"deleted"}"#);
        let client = OrchestratorClient::new(&base_url, Some("k".into()));

        let resp = client.delete_job_permanent("abc", false).await.unwrap();

        assert_eq!(resp["message"], "deleted");
        assert_eq!(
            server.join().unwrap(),
            "DELETE /api/jobs/abc/permanent HTTP/1.1"
        );
    }

    #[tokio::test]
    async fn delete_job_permanent_can_keep_outputs() {
        let (base_url, server) = one_shot_server("HTTP/1.1 200 OK", r#"{"message":"deleted"}"#);
        let client = OrchestratorClient::new(&base_url, None);

        client.delete_job_permanent("abc", true).await.unwrap();

        assert_eq!(
            server.join().unwrap(),
            "DELETE /api/jobs/abc/permanent?keep_outputs=true HTTP/1.1"
        );
    }

    #[tokio::test]
    async fn get_logs_since_reads_offset_headers() {
        let (base_url, server) = one_shot_server_with_headers(
            "HTTP/1.1 200 OK",
            "Content-Type: text/plain\r\nX-Log-Next-Offset: 42\r\nX-Log-Reset: false\r\nX-Log-Truncated: true\r\nX-Log-Complete: true\r\n",
            "new text\n",
        );
        let client = OrchestratorClient::new(&base_url, None);

        let chunk = client.get_logs_since("abc", 7).await.unwrap();

        assert_eq!(
            chunk,
            LogChunk {
                text: "new text\n".into(),
                next_offset: Some(42),
                reset: false,
                truncated: true,
                complete: true,
            }
        );
        assert_eq!(
            server.join().unwrap(),
            "GET /api/jobs/abc/logs?since_offset=7 HTTP/1.1"
        );
    }

    #[tokio::test]
    async fn get_logs_since_without_offset_header_reports_none() {
        let (base_url, server) = one_shot_server_with_headers(
            "HTTP/1.1 200 OK",
            "Content-Type: text/plain\r\n",
            "tail\n",
        );
        let client = OrchestratorClient::new(&base_url, None);

        let chunk = client.get_logs_since("abc", 0).await.unwrap();

        assert_eq!(chunk.next_offset, None);
        server.join().unwrap();
    }

    #[tokio::test]
    async fn cancel_job_reports_api_error_for_finished_jobs() {
        let (base_url, server) = one_shot_server(
            "HTTP/1.1 400 Bad Request",
            r#"{"detail":"Cannot cancel job in status completed"}"#,
        );
        let client = OrchestratorClient::new(&base_url, None);

        let err = client.cancel_job("abc").await.unwrap_err();

        assert!(matches!(err, ApiError::Api { status: 400, .. }));
        assert_eq!(server.join().unwrap(), "DELETE /api/jobs/abc HTTP/1.1");
    }
}
