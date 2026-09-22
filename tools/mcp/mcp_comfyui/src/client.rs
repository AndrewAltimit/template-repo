//! HTTP client for the ComfyUI REST API.
//!
//! Endpoints used: `POST /prompt`, `GET /history/{id}`, `GET /queue`,
//! `POST /queue` (delete), `POST /interrupt`, `GET /object_info[/{class}]`,
//! `GET /system_stats`, `GET /view`, `POST /upload/image`.

use std::time::{Duration, Instant};

use reqwest::{Client, Response, StatusCode};
use serde_json::{Value, json};
use tracing::{debug, info, warn};

use crate::types::{JobState, JobStatus, QueueSnapshot, parse_history_entry};

/// Maximum characters of an upstream error body echoed back to the caller.
const MAX_ERROR_BODY: usize = 1500;
/// Consecutive poll failures tolerated before giving up on a wait.
const MAX_POLL_FAILURES: u32 = 5;
/// Every Nth poll without a history entry also checks the queue so a prompt
/// that vanished (ComfyUI restart) is detected instead of waiting forever.
const QUEUE_CHECK_EVERY: u32 = 5;

/// Errors talking to ComfyUI.
#[derive(Debug, thiserror::Error)]
pub enum ClientError {
    /// Network-level failure (connection refused, timeout, DNS, ...).
    #[error("cannot reach ComfyUI at {url}: {detail}")]
    Unreachable {
        /// Request URL.
        url: String,
        /// Error chain.
        detail: String,
    },
    /// Non-success HTTP status.
    #[error("ComfyUI returned HTTP {status} for {endpoint}: {body}")]
    Status {
        /// Endpoint path.
        endpoint: String,
        /// HTTP status code.
        status: u16,
        /// (Truncated) response body.
        body: String,
    },
    /// `/prompt` rejected the workflow (validation errors).
    #[error("ComfyUI rejected the workflow: {0}")]
    Rejected(String),
    /// Response body did not have the expected shape.
    #[error("unexpected response from ComfyUI {endpoint}: {detail}")]
    BadResponse {
        /// Endpoint path.
        endpoint: String,
        /// What was wrong.
        detail: String,
    },
    /// Requested resource does not exist.
    #[error("{0}")]
    NotFound(String),
    /// Response exceeded a configured size cap.
    #[error("{0}")]
    TooLarge(String),
}

/// Model categories exposed by `list_models`, mapped to the loader node and
/// input whose combo options enumerate the files ComfyUI can see.
pub const MODEL_KINDS: &[(&str, &str, &str)] = &[
    ("checkpoint", "CheckpointLoaderSimple", "ckpt_name"),
    ("lora", "LoraLoader", "lora_name"),
    ("vae", "VAELoader", "vae_name"),
    ("upscale_model", "UpscaleModelLoader", "model_name"),
    ("controlnet", "ControlNetLoader", "control_net_name"),
    ("unet", "UNETLoader", "unet_name"),
    ("clip", "CLIPLoader", "clip_name"),
];

/// ComfyUI HTTP API client.
pub struct ComfyUIClient {
    client: Client,
    base_url: String,
    client_id: String,
    poll_interval: Duration,
}

fn error_chain(err: &dyn std::error::Error) -> String {
    let mut out = err.to_string();
    let mut source = err.source();
    while let Some(s) = source {
        let msg = s.to_string();
        if !out.contains(&msg) {
            out.push_str(": ");
            out.push_str(&msg);
        }
        source = s.source();
    }
    out
}

fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let head: String = s.chars().take(max).collect();
        format!("{head}... (truncated)")
    }
}

/// Turn a `/prompt` validation error body into a compact readable message.
pub fn describe_prompt_error(body: &Value) -> String {
    let mut parts = Vec::new();
    if let Some(err) = body.get("error") {
        let msg = err
            .get("message")
            .and_then(Value::as_str)
            .or_else(|| err.as_str())
            .unwrap_or("validation failed");
        let details = err.get("details").and_then(Value::as_str).unwrap_or("");
        if details.is_empty() {
            parts.push(msg.to_string());
        } else {
            parts.push(format!("{msg}: {}", truncate(details, 300)));
        }
    }
    if let Some(nodes) = body.get("node_errors").and_then(Value::as_object) {
        let mut ids: Vec<&String> = nodes.keys().collect();
        ids.sort();
        for id in ids {
            let node = &nodes[id];
            let class = node
                .get("class_type")
                .and_then(Value::as_str)
                .unwrap_or("?");
            let errors = node
                .get("errors")
                .and_then(Value::as_array)
                .map(|errs| {
                    errs.iter()
                        .map(|e| {
                            let m = e.get("message").and_then(Value::as_str).unwrap_or("error");
                            match e.get("details").and_then(Value::as_str) {
                                Some(d) if !d.is_empty() => format!("{m}: {}", truncate(d, 300)),
                                _ => m.to_string(),
                            }
                        })
                        .collect::<Vec<_>>()
                        .join("; ")
                })
                .unwrap_or_default();
            parts.push(format!("node {id} ({class}): {errors}"));
        }
    }
    if parts.is_empty() {
        truncate(&body.to_string(), MAX_ERROR_BODY)
    } else {
        parts.join(" | ")
    }
}

/// Extract the options of a combo input from an `/object_info` node spec.
///
/// Handles both the classic `[[opt, ...], {...}]` shape and the newer
/// `["COMBO", {"options": [...]}]` shape.
pub fn combo_options(node_info: &Value, input: &str) -> Option<Vec<String>> {
    let spec = ["required", "optional"]
        .iter()
        .find_map(|section| node_info.get("input")?.get(*section)?.get(input))?;
    let first = spec.get(0)?;
    let list = match first {
        Value::Array(items) => items,
        Value::String(s) if s == "COMBO" => spec.get(1)?.get("options")?.as_array()?,
        _ => return None,
    };
    Some(
        list.iter()
            .filter_map(|v| v.as_str().map(String::from))
            .collect(),
    )
}

impl ComfyUIClient {
    /// Create a client for `base_url` (no trailing slash) with a per-request
    /// timeout. `client_id` identifies this server's prompts to ComfyUI.
    pub fn new(base_url: &str, request_timeout: Duration, client_id: String) -> Self {
        Self {
            client: mcp_core::http::build_client_or_default(request_timeout),
            base_url: base_url.trim_end_matches('/').to_string(),
            client_id,
            poll_interval: Duration::from_secs(1),
        }
    }

    /// Override the completion polling interval (used by tests).
    pub fn with_poll_interval(mut self, interval: Duration) -> Self {
        self.poll_interval = interval;
        self
    }

    /// Base URL this client talks to.
    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    fn url(&self, path: &str) -> String {
        format!("{}{}", self.base_url, path)
    }

    async fn send(&self, req: reqwest::RequestBuilder, url: &str) -> Result<Response, ClientError> {
        req.send().await.map_err(|e| ClientError::Unreachable {
            url: url.to_string(),
            detail: if e.is_timeout() {
                format!("request timed out ({})", error_chain(&e))
            } else {
                error_chain(&e)
            },
        })
    }

    async fn check(resp: Response, endpoint: &str) -> Result<Response, ClientError> {
        if resp.status().is_success() {
            return Ok(resp);
        }
        let status = resp.status().as_u16();
        let body = resp.text().await.unwrap_or_default();
        Err(ClientError::Status {
            endpoint: endpoint.to_string(),
            status,
            body: truncate(body.trim(), MAX_ERROR_BODY),
        })
    }

    async fn json(resp: Response, endpoint: &str) -> Result<Value, ClientError> {
        resp.json().await.map_err(|e| ClientError::BadResponse {
            endpoint: endpoint.to_string(),
            detail: error_chain(&e),
        })
    }

    async fn get_json(&self, path: &str) -> Result<Value, ClientError> {
        let url = self.url(path);
        let resp = self.send(self.client.get(&url), &url).await?;
        let resp = Self::check(resp, path).await?;
        Self::json(resp, path).await
    }

    async fn post_json(&self, path: &str, body: &Value) -> Result<Response, ClientError> {
        let url = self.url(path);
        let resp = self.send(self.client.post(&url).json(body), &url).await?;
        Self::check(resp, path).await
    }

    /// Queue an API-format workflow; returns ComfyUI's prompt id.
    pub async fn queue_prompt(&self, workflow: &Value) -> Result<String, ClientError> {
        let url = self.url("/prompt");
        let payload = json!({"prompt": workflow, "client_id": self.client_id});
        let resp = self
            .send(self.client.post(&url).json(&payload), &url)
            .await?;

        let status = resp.status();
        if status == StatusCode::BAD_REQUEST {
            let text = resp.text().await.unwrap_or_default();
            let msg = serde_json::from_str::<Value>(&text)
                .map(|v| describe_prompt_error(&v))
                .unwrap_or_else(|_| truncate(text.trim(), MAX_ERROR_BODY));
            return Err(ClientError::Rejected(msg));
        }
        let resp = Self::check(resp, "/prompt").await?;
        let body = Self::json(resp, "/prompt").await?;

        if let Some(errors) = body.get("node_errors").and_then(Value::as_object)
            && !errors.is_empty()
        {
            return Err(ClientError::Rejected(describe_prompt_error(&body)));
        }
        let prompt_id = body
            .get("prompt_id")
            .and_then(Value::as_str)
            .ok_or_else(|| ClientError::BadResponse {
                endpoint: "/prompt".into(),
                detail: "missing 'prompt_id'".into(),
            })?
            .to_string();
        info!("Queued prompt {prompt_id}");
        Ok(prompt_id)
    }

    /// Raw history entry for a prompt, or `None` if ComfyUI has no record yet.
    pub async fn history(&self, prompt_id: &str) -> Result<Option<Value>, ClientError> {
        let path = format!("/history/{prompt_id}");
        let body = self.get_json(&path).await?;
        Ok(body.get(prompt_id).cloned())
    }

    /// Current queue contents.
    pub async fn queue(&self) -> Result<QueueSnapshot, ClientError> {
        Ok(QueueSnapshot::parse(&self.get_json("/queue").await?))
    }

    /// Current state of a prompt (history first, then the queue).
    pub async fn job_state(&self, prompt_id: &str) -> Result<JobState, ClientError> {
        if let Some(entry) = self.history(prompt_id).await? {
            return Ok(parse_history_entry(&entry));
        }
        if let Some(state) = self.queue().await?.state_of(prompt_id) {
            return Ok(state);
        }
        // The prompt may have finished between the two calls.
        if let Some(entry) = self.history(prompt_id).await? {
            return Ok(parse_history_entry(&entry));
        }
        Ok(JobState::bare(JobStatus::Unknown))
    }

    /// Poll until the prompt reaches a terminal state or `timeout` elapses.
    ///
    /// Returns [`JobStatus::Timeout`] (not an error) when time runs out and
    /// [`JobStatus::Unknown`] if the prompt disappears from both queue and
    /// history. Up to [`MAX_POLL_FAILURES`] consecutive transient errors are
    /// tolerated.
    pub async fn wait_for_completion(
        &self,
        prompt_id: &str,
        timeout: Duration,
    ) -> Result<JobState, ClientError> {
        let deadline = Instant::now() + timeout;
        let mut failures = 0u32;
        let mut polls = 0u32;
        let mut last_state = JobState::bare(JobStatus::Queued);

        loop {
            polls += 1;
            let poll = async {
                if let Some(entry) = self.history(prompt_id).await? {
                    return Ok::<_, ClientError>(parse_history_entry(&entry));
                }
                if polls.is_multiple_of(QUEUE_CHECK_EVERY) {
                    return self.job_state(prompt_id).await;
                }
                Ok(last_state.clone())
            };
            match poll.await {
                Ok(state) if state.status.is_terminal() || state.status == JobStatus::Unknown => {
                    debug!("Prompt {prompt_id} finished: {:?}", state.status);
                    return Ok(state);
                },
                Ok(state) => {
                    failures = 0;
                    last_state = state;
                },
                Err(e) => {
                    failures += 1;
                    warn!(
                        "Polling prompt {prompt_id} failed ({failures}/{MAX_POLL_FAILURES}): {e}"
                    );
                    if failures >= MAX_POLL_FAILURES {
                        return Err(e);
                    }
                },
            }

            let now = Instant::now();
            if now >= deadline {
                // Report where it is stuck (queued vs running) if we can.
                if let Ok(state) = self.job_state(prompt_id).await {
                    if state.status.is_terminal() {
                        return Ok(state);
                    }
                    last_state = state;
                }
                return Ok(JobState {
                    status: JobStatus::Timeout,
                    queue_position: last_state.queue_position,
                    images: Vec::new(),
                    error: Some(format!(
                        "not finished after {}s (last seen: {:?})",
                        timeout.as_secs(),
                        last_state.status
                    )),
                });
            }
            tokio::time::sleep(self.poll_interval.min(deadline - now)).await;
        }
    }

    /// Remove a pending prompt from the queue.
    pub async fn delete_from_queue(&self, prompt_id: &str) -> Result<(), ClientError> {
        self.post_json("/queue", &json!({"delete": [prompt_id]}))
            .await
            .map(|_| ())
    }

    /// Interrupt execution. Recent ComfyUI builds honor `prompt_id` and only
    /// interrupt that prompt; callers should only invoke this for a prompt
    /// known to be running, since older builds interrupt whatever is running.
    pub async fn interrupt(&self, prompt_id: &str) -> Result<(), ClientError> {
        self.post_json("/interrupt", &json!({"prompt_id": prompt_id}))
            .await
            .map(|_| ())
    }

    /// `/object_info`, optionally for a single node class. Unknown classes
    /// yield [`ClientError::NotFound`].
    pub async fn object_info(&self, node_class: Option<&str>) -> Result<Value, ClientError> {
        match node_class {
            None => self.get_json("/object_info").await,
            Some(class) => {
                let encoded: String = url_path_escape(class);
                let body = self.get_json(&format!("/object_info/{encoded}")).await?;
                body.get(class).cloned().ok_or_else(|| {
                    ClientError::NotFound(format!(
                        "node class {class:?} is not available on this ComfyUI instance"
                    ))
                })
            },
        }
    }

    /// Model file names ComfyUI can load for `kind` (see [`MODEL_KINDS`]).
    pub async fn models(&self, kind: &str) -> Result<Vec<String>, ClientError> {
        let (_, node, input) =
            MODEL_KINDS
                .iter()
                .find(|(k, _, _)| *k == kind)
                .ok_or_else(|| {
                    ClientError::NotFound(format!(
                        "unknown model type {kind:?}; expected one of: {}",
                        MODEL_KINDS
                            .iter()
                            .map(|m| m.0)
                            .collect::<Vec<_>>()
                            .join(", ")
                    ))
                })?;
        let info = self.object_info(Some(node)).await?;
        combo_options(&info, input).ok_or_else(|| ClientError::BadResponse {
            endpoint: format!("/object_info/{node}"),
            detail: format!("input {input:?} has no option list"),
        })
    }

    /// `/system_stats` passthrough.
    pub async fn system_stats(&self) -> Result<Value, ClientError> {
        self.get_json("/system_stats").await
    }

    /// Fetch a file via `/view`, refusing anything larger than `max_bytes`.
    /// Returns `(bytes, content_type)`.
    pub async fn view(
        &self,
        filename: &str,
        subfolder: &str,
        kind: &str,
        max_bytes: u64,
    ) -> Result<(Vec<u8>, Option<String>), ClientError> {
        let url = self.url("/view");
        let req = self.client.get(&url).query(&[
            ("filename", filename),
            ("subfolder", subfolder),
            ("type", kind),
        ]);
        let resp = self.send(req, &url).await?;
        if resp.status() == StatusCode::NOT_FOUND {
            return Err(ClientError::NotFound(format!(
                "image {filename:?} not found in {kind}/{subfolder}"
            )));
        }
        let mut resp = Self::check(resp, "/view").await?;
        let too_large = || {
            ClientError::TooLarge(format!(
                "image {filename:?} exceeds the {max_bytes}-byte limit (COMFYUI_MAX_IMAGE_BYTES)"
            ))
        };
        if resp.content_length().is_some_and(|len| len > max_bytes) {
            return Err(too_large());
        }
        let content_type = resp
            .headers()
            .get(reqwest::header::CONTENT_TYPE)
            .and_then(|v| v.to_str().ok())
            .map(String::from);
        let mut data = Vec::new();
        while let Some(chunk) = resp.chunk().await.map_err(|e| ClientError::Unreachable {
            url: url.clone(),
            detail: error_chain(&e),
        })? {
            if data.len() as u64 + chunk.len() as u64 > max_bytes {
                return Err(too_large());
            }
            data.extend_from_slice(&chunk);
        }
        Ok((data, content_type))
    }

    /// Upload an image into ComfyUI's input directory (`/upload/image`).
    /// Returns ComfyUI's `{name, subfolder, type}` response; `name` may differ
    /// from `filename` when `overwrite` is false and the name was taken.
    pub async fn upload_image(
        &self,
        filename: &str,
        data: &[u8],
        mime: &str,
        subfolder: &str,
        overwrite: bool,
    ) -> Result<Value, ClientError> {
        let boundary = format!("----mcp-comfyui-{}", uuid::Uuid::new_v4().simple());
        let body = multipart_body(&boundary, filename, mime, data, subfolder, overwrite);
        let url = self.url("/upload/image");
        let req = self
            .client
            .post(&url)
            .header(
                reqwest::header::CONTENT_TYPE,
                format!("multipart/form-data; boundary={boundary}"),
            )
            .body(body);
        let resp = self.send(req, &url).await?;
        let resp = Self::check(resp, "/upload/image").await?;
        let value = Self::json(resp, "/upload/image").await?;
        if value.get("name").and_then(Value::as_str).is_none() {
            return Err(ClientError::BadResponse {
                endpoint: "/upload/image".into(),
                detail: "missing 'name'".into(),
            });
        }
        Ok(value)
    }
}

/// Percent-encode a single URL path segment.
fn url_path_escape(segment: &str) -> String {
    let mut out = String::with_capacity(segment.len());
    for b in segment.bytes() {
        if b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.' | b'~') {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

/// Build a `multipart/form-data` body for `/upload/image`. `filename` must
/// already be validated (no quotes or control characters).
pub fn multipart_body(
    boundary: &str,
    filename: &str,
    mime: &str,
    data: &[u8],
    subfolder: &str,
    overwrite: bool,
) -> Vec<u8> {
    let mut body = Vec::with_capacity(data.len() + 512);
    body.extend_from_slice(
        format!(
            "--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n"
        )
        .as_bytes(),
    );
    body.extend_from_slice(data);
    body.extend_from_slice(b"\r\n");
    for (name, value) in [
        ("type", "input"),
        ("subfolder", subfolder),
        ("overwrite", if overwrite { "true" } else { "false" }),
    ] {
        body.extend_from_slice(
            format!(
                "--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
            )
            .as_bytes(),
        );
    }
    body.extend_from_slice(format!("--{boundary}--\r\n").as_bytes());
    body
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prompt_error_is_readable() {
        let body = json!({
            "error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation", "details": ""},
            "node_errors": {
                "1": {
                    "class_type": "CheckpointLoaderSimple",
                    "errors": [{"message": "Value not in list", "details": "ckpt_name: 'x.safetensors' not in []"}]
                }
            }
        });
        let msg = describe_prompt_error(&body);
        assert!(msg.starts_with("Prompt outputs failed validation"), "{msg}");
        assert!(
            msg.contains("node 1 (CheckpointLoaderSimple): Value not in list: ckpt_name"),
            "{msg}"
        );
        assert_eq!(describe_prompt_error(&json!({"x": 1})), "{\"x\":1}");
    }

    #[test]
    fn combo_option_shapes() {
        let classic =
            json!({"input": {"required": {"ckpt_name": [["a.safetensors", "b.ckpt"], {}]}}});
        assert_eq!(
            combo_options(&classic, "ckpt_name").unwrap(),
            ["a.safetensors", "b.ckpt"]
        );
        let v3 = json!({"input": {"optional": {"model_name": ["COMBO", {"options": ["4x.pth"]}]}}});
        assert_eq!(combo_options(&v3, "model_name").unwrap(), ["4x.pth"]);
        assert!(combo_options(&classic, "missing").is_none());
        let not_combo = json!({"input": {"required": {"steps": ["INT", {"default": 20}]}}});
        assert!(combo_options(&not_combo, "steps").is_none());
    }

    #[test]
    fn multipart_layout() {
        let body = multipart_body("B", "a.png", "image/png", b"PNGDATA", "sub", false);
        let text = String::from_utf8(body).unwrap();
        assert!(text.starts_with("--B\r\nContent-Disposition: form-data; name=\"image\"; filename=\"a.png\"\r\nContent-Type: image/png\r\n\r\nPNGDATA\r\n"));
        assert!(text.contains("name=\"type\"\r\n\r\ninput\r\n"));
        assert!(text.contains("name=\"subfolder\"\r\n\r\nsub\r\n"));
        assert!(text.contains("name=\"overwrite\"\r\n\r\nfalse\r\n"));
        assert!(text.ends_with("--B--\r\n"));
    }

    #[test]
    fn path_escape() {
        assert_eq!(url_path_escape("KSampler"), "KSampler");
        assert_eq!(url_path_escape("a b/c"), "a%20b%2Fc");
    }

    #[test]
    fn truncation() {
        assert_eq!(truncate("abc", 5), "abc");
        assert_eq!(truncate("abcdef", 3), "abc... (truncated)");
    }
}
