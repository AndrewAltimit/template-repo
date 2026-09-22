//! Upload memes to free, no-auth image hosts for a shareable URL.
//!
//! Hosts (tried in this order by [`UploadService::Auto`]):
//!
//! | Service      | Direct/embed URL | Retention                                   |
//! |--------------|------------------|---------------------------------------------|
//! | 0x0.st       | yes              | 30 days to 1 year depending on file size    |
//! | tmpfiles.org | yes (`/dl/` URL) | deleted after 60 minutes                    |
//! | file.io      | no (one-time download page) | deleted after first download     |
//!
//! Third-party availability changes often; every attempt is bounded by a
//! request timeout plus a connect timeout, and the combined per-service errors
//! are returned when all hosts fail so the caller can see *why*.
//!
//! The response parsers are pure functions so they are unit tested without
//! network access; [`Uploader::with_endpoints`] lets tests point the client at
//! a local mock server.

use reqwest::multipart;
use serde::Deserialize;
use std::time::Duration;
use tracing::{info, warn};

use crate::types::UploadResult;

/// Default total request timeout per upload attempt.
pub const DEFAULT_UPLOAD_TIMEOUT: Duration = Duration::from_secs(30);

/// Largest file `upload_meme` will send.
pub const MAX_UPLOAD_BYTES: u64 = 20 * 1024 * 1024;

/// How much of an unexpected response body to echo back in errors.
const BODY_SNIPPET_CHARS: usize = 200;

/// Which host to upload to.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize)]
pub enum UploadService {
    /// Try every host in order until one succeeds.
    #[default]
    #[serde(rename = "auto")]
    Auto,
    /// <https://0x0.st>
    #[serde(rename = "0x0st", alias = "0x0.st")]
    ZeroXZero,
    /// <https://tmpfiles.org>
    #[serde(rename = "tmpfiles", alias = "tmpfiles.org")]
    Tmpfiles,
    /// <https://file.io>
    #[serde(rename = "fileio", alias = "file.io")]
    FileIo,
}

impl UploadService {
    /// Concrete services in fallback order.
    const ORDER: [UploadService; 3] = [Self::ZeroXZero, Self::Tmpfiles, Self::FileIo];

    /// Display name.
    pub fn name(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::ZeroXZero => "0x0.st",
            Self::Tmpfiles => "tmpfiles.org",
            Self::FileIo => "file.io",
        }
    }
}

/// Upload endpoints (overridable for tests).
#[derive(Debug, Clone)]
pub struct Endpoints {
    /// 0x0.st POST URL.
    pub zero_x_zero: String,
    /// tmpfiles.org upload API URL.
    pub tmpfiles: String,
    /// file.io upload URL.
    pub fileio: String,
}

impl Default for Endpoints {
    fn default() -> Self {
        Self {
            zero_x_zero: "https://0x0.st".to_string(),
            tmpfiles: "https://tmpfiles.org/api/v1/upload".to_string(),
            fileio: "https://file.io/?expires=1d".to_string(),
        }
    }
}

/// HTTP uploader with a shared, timeout-bounded client.
#[derive(Clone)]
pub struct Uploader {
    client: reqwest::Client,
    endpoints: Endpoints,
    timeout: Duration,
}

impl Uploader {
    /// Uploader for the real hosts with the given per-attempt timeout.
    pub fn new(timeout: Duration) -> Self {
        Self::with_endpoints(timeout, Endpoints::default())
    }

    /// Uploader for custom endpoints (used by tests).
    pub fn with_endpoints(timeout: Duration, endpoints: Endpoints) -> Self {
        Self {
            client: mcp_core::http::build_client_or_default(timeout),
            endpoints,
            timeout,
        }
    }

    /// Upload `bytes` as `file_name` to `service` (or each host in turn for
    /// [`UploadService::Auto`]).
    pub async fn upload(
        &self,
        bytes: &[u8],
        file_name: &str,
        mime: &str,
        service: UploadService,
    ) -> UploadResult {
        if service != UploadService::Auto {
            return self.upload_one(bytes, file_name, mime, service).await;
        }
        let mut failures = Vec::new();
        for svc in UploadService::ORDER {
            info!("Uploading meme to {}", svc.name());
            let result = self.upload_one(bytes, file_name, mime, svc).await;
            if result.success {
                return result;
            }
            let err = result.error.unwrap_or_else(|| "unknown error".into());
            warn!("{} upload failed: {err}", svc.name());
            failures.push(format!("{}: {err}", svc.name()));
        }
        UploadResult::failure(format!(
            "All upload services failed ({})",
            failures.join("; ")
        ))
    }

    async fn upload_one(
        &self,
        bytes: &[u8],
        file_name: &str,
        mime: &str,
        service: UploadService,
    ) -> UploadResult {
        let part = match multipart::Part::bytes(bytes.to_vec())
            .file_name(file_name.to_string())
            .mime_str(mime)
        {
            Ok(p) => p,
            Err(e) => return UploadResult::failure(format!("Failed to build upload body: {e}")),
        };
        let form = multipart::Form::new().part("file", part);

        let (url, parse): (&str, fn(u16, &str) -> UploadResult) = match service {
            UploadService::ZeroXZero => (&self.endpoints.zero_x_zero, parse_0x0),
            UploadService::Tmpfiles => (&self.endpoints.tmpfiles, parse_tmpfiles),
            UploadService::FileIo => (&self.endpoints.fileio, parse_fileio),
            UploadService::Auto => return UploadResult::failure("auto is not a concrete service"),
        };

        let mut request = self.client.post(url).multipart(form);
        if service == UploadService::ZeroXZero {
            // 0x0.st rejects many generic/browser user agents but accepts curl's.
            request = request.header(reqwest::header::USER_AGENT, "curl/8.5.0");
        }

        let response = match request.send().await {
            Ok(r) => r,
            Err(e) => return UploadResult::failure(describe_error(&e, self.timeout)),
        };
        let status = response.status().as_u16();
        match response.text().await {
            Ok(body) => parse(status, &body),
            Err(e) => UploadResult::failure(describe_error(&e, self.timeout)),
        }
    }
}

fn describe_error(e: &reqwest::Error, timeout: Duration) -> String {
    if e.is_timeout() {
        format!("timed out after {}s", timeout.as_secs_f32())
    } else if e.is_connect() {
        format!("connection failed: {e}")
    } else {
        format!("request failed: {e}")
    }
}

fn snippet(body: &str) -> String {
    let trimmed = body.trim();
    let mut s: String = trimmed.chars().take(BODY_SNIPPET_CHARS).collect();
    if trimmed.chars().count() > BODY_SNIPPET_CHARS {
        s.push_str("...");
    }
    s
}

fn status_error(status: u16, body: &str) -> UploadResult {
    let hint = match status {
        403 => " (service is blocking automated uploads)",
        413 => " (file too large for this service)",
        429 => " (rate limited)",
        _ => "",
    };
    UploadResult::failure(format!("HTTP {status}{hint}: {}", snippet(body)))
}

fn looks_like_url(s: &str) -> bool {
    (s.starts_with("https://") || s.starts_with("http://"))
        && !s.chars().any(char::is_whitespace)
        && s.len() > "https://".len()
}

/// 0x0.st answers with the file URL as plain text.
pub fn parse_0x0(status: u16, body: &str) -> UploadResult {
    if !(200..300).contains(&status) {
        return status_error(status, body);
    }
    let url = body.trim();
    if !looks_like_url(url) {
        return UploadResult::failure(format!("unexpected response: {}", snippet(body)));
    }
    UploadResult {
        success: true,
        url: Some(url.to_string()),
        embed_url: Some(url.to_string()),
        service: Some(UploadService::ZeroXZero.name().to_string()),
        note: Some("Retention depends on file size (30 days up to 1 year)".to_string()),
        error: None,
    }
}

/// tmpfiles.org returns `{"status":"success","data":{"url":"http://tmpfiles.org/<id>/<name>"}}`.
/// That URL is an HTML landing page; the embeddable file lives at
/// `https://tmpfiles.org/dl/<id>/<name>`.
pub fn parse_tmpfiles(status: u16, body: &str) -> UploadResult {
    if !(200..300).contains(&status) {
        return status_error(status, body);
    }
    let data: serde_json::Value = match serde_json::from_str(body) {
        Ok(v) => v,
        Err(_) => {
            return UploadResult::failure(format!("invalid JSON response: {}", snippet(body)));
        },
    };
    if data.get("status").and_then(|s| s.as_str()) != Some("success") {
        let msg = data
            .get("message")
            .and_then(|m| m.as_str())
            .unwrap_or("upload rejected");
        return UploadResult::failure(msg.to_string());
    }
    let Some(url) = data
        .pointer("/data/url")
        .and_then(|u| u.as_str())
        .filter(|u| looks_like_url(u))
    else {
        return UploadResult::failure("response did not contain a URL");
    };
    let page = url.replacen("http://", "https://", 1);
    let embed = tmpfiles_direct_url(&page).unwrap_or_else(|| page.clone());
    UploadResult {
        success: true,
        url: Some(page),
        embed_url: Some(embed),
        service: Some(UploadService::Tmpfiles.name().to_string()),
        note: Some("tmpfiles.org deletes uploads after 60 minutes".to_string()),
        error: None,
    }
}

/// `https://tmpfiles.org/123/x.png` -> `https://tmpfiles.org/dl/123/x.png`.
fn tmpfiles_direct_url(page: &str) -> Option<String> {
    let rest = page.strip_prefix("https://tmpfiles.org/")?;
    if rest.starts_with("dl/") {
        return Some(page.to_string());
    }
    Some(format!("https://tmpfiles.org/dl/{rest}"))
}

/// file.io returns `{"success":true,"link":"https://file.io/<key>"}`. The link
/// is a download page that is deleted after its first download, so it is not
/// offered as an embed URL.
pub fn parse_fileio(status: u16, body: &str) -> UploadResult {
    let data: Option<serde_json::Value> = serde_json::from_str(body).ok();
    if !(200..300).contains(&status) {
        if let Some(msg) = data
            .as_ref()
            .and_then(|d| d.get("message"))
            .and_then(|m| m.as_str())
        {
            return UploadResult::failure(format!("HTTP {status}: {msg}"));
        }
        return status_error(status, body);
    }
    let Some(data) = data else {
        return UploadResult::failure(format!("invalid JSON response: {}", snippet(body)));
    };
    if data.get("success").and_then(|s| s.as_bool()) != Some(true) {
        let msg = data
            .get("message")
            .and_then(|m| m.as_str())
            .unwrap_or("upload rejected");
        return UploadResult::failure(msg.to_string());
    }
    let Some(link) = data
        .get("link")
        .and_then(|l| l.as_str())
        .filter(|l| looks_like_url(l))
    else {
        return UploadResult::failure("response did not contain a link");
    };
    UploadResult {
        success: true,
        url: Some(link.to_string()),
        embed_url: None,
        service: Some(UploadService::FileIo.name().to_string()),
        note: Some(
            "file.io links are download pages deleted after the first download; not embeddable"
                .to_string(),
        ),
        error: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpListener;

    #[test]
    fn parses_0x0_success_and_failures() {
        let ok = parse_0x0(200, "https://0x0.st/abc.png\n");
        assert!(ok.success);
        assert_eq!(ok.embed_url.as_deref(), Some("https://0x0.st/abc.png"));
        assert_eq!(ok.service.as_deref(), Some("0x0.st"));

        let html = parse_0x0(200, "<html>blocked</html>");
        assert!(!html.success);
        assert!(html.error.unwrap().contains("unexpected response"));

        let forbidden = parse_0x0(403, "nope");
        assert!(
            forbidden
                .error
                .unwrap()
                .contains("HTTP 403 (service is blocking")
        );
    }

    #[test]
    fn parses_tmpfiles_and_builds_direct_url() {
        let body = r#"{"status":"success","data":{"url":"http://tmpfiles.org/12345/meme.png"}}"#;
        let r = parse_tmpfiles(200, body);
        assert!(r.success);
        assert_eq!(
            r.url.as_deref(),
            Some("https://tmpfiles.org/12345/meme.png")
        );
        assert_eq!(
            r.embed_url.as_deref(),
            Some("https://tmpfiles.org/dl/12345/meme.png")
        );

        let rejected = parse_tmpfiles(200, r#"{"status":"error","message":"too big"}"#);
        assert_eq!(rejected.error.as_deref(), Some("too big"));
        assert!(!parse_tmpfiles(200, "not json").success);
        assert!(!parse_tmpfiles(200, r#"{"status":"success","data":{}}"#).success);
        assert!(!parse_tmpfiles(500, "oops").success);
    }

    #[test]
    fn parses_fileio_without_embed_url() {
        let r = parse_fileio(200, r#"{"success":true,"link":"https://file.io/xyz"}"#);
        assert!(r.success);
        assert_eq!(r.url.as_deref(), Some("https://file.io/xyz"));
        assert!(r.embed_url.is_none());

        let r = parse_fileio(400, r#"{"success":false,"message":"bad"}"#);
        assert_eq!(r.error.as_deref(), Some("HTTP 400: bad"));
        assert!(!parse_fileio(200, r#"{"success":false}"#).success);
    }

    #[test]
    fn long_error_bodies_are_truncated() {
        let r = parse_0x0(500, &"x".repeat(5000));
        let err = r.error.unwrap();
        assert!(err.len() < 300);
        assert!(err.ends_with("..."));
    }

    #[test]
    fn service_names_deserialize() {
        for (s, want) in [
            ("auto", UploadService::Auto),
            ("0x0st", UploadService::ZeroXZero),
            ("0x0.st", UploadService::ZeroXZero),
            ("tmpfiles", UploadService::Tmpfiles),
            ("fileio", UploadService::FileIo),
        ] {
            let got: UploadService = serde_json::from_value(serde_json::json!(s)).unwrap();
            assert_eq!(got, want);
        }
        assert!(serde_json::from_value::<UploadService>(serde_json::json!("imgur")).is_err());
    }

    /// Minimal one-shot HTTP server: serves `responses` in order (one per
    /// connection) and returns its base URL. A `None` response never replies.
    async fn mock_server(responses: Vec<Option<(u16, &'static str)>>) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            for response in responses {
                let Ok((mut sock, _)) = listener.accept().await else {
                    return;
                };
                tokio::spawn(async move {
                    // Read headers + body (Content-Length) before replying.
                    let mut buf = Vec::new();
                    let mut chunk = [0u8; 8192];
                    loop {
                        let n = sock.read(&mut chunk).await.unwrap_or(0);
                        if n == 0 {
                            break;
                        }
                        buf.extend_from_slice(&chunk[..n]);
                        let text = String::from_utf8_lossy(&buf);
                        if let Some(end) = text.find("\r\n\r\n") {
                            let len = text[..end]
                                .lines()
                                .find_map(|l| {
                                    let l = l.to_ascii_lowercase();
                                    l.strip_prefix("content-length:")
                                        .and_then(|v| v.trim().parse::<usize>().ok())
                                })
                                .unwrap_or(0);
                            if buf.len() >= end + 4 + len {
                                break;
                            }
                        }
                    }
                    match response {
                        Some((status, body)) => {
                            let reply = format!(
                                "HTTP/1.1 {status} X\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                                body.len()
                            );
                            let _ = sock.write_all(reply.as_bytes()).await;
                        },
                        None => tokio::time::sleep(Duration::from_secs(30)).await,
                    }
                });
            }
        });
        format!("http://{addr}")
    }

    #[tokio::test]
    async fn auto_falls_back_to_next_service() {
        let base = mock_server(vec![
            Some((503, "down for maintenance")),
            Some((
                200,
                r#"{"status":"success","data":{"url":"http://tmpfiles.org/9/m.png"}}"#,
            )),
        ])
        .await;
        let uploader = Uploader::with_endpoints(
            Duration::from_secs(5),
            Endpoints {
                zero_x_zero: base.clone(),
                tmpfiles: base.clone(),
                fileio: base,
            },
        );
        let r = uploader
            .upload(b"png-bytes", "m.png", "image/png", UploadService::Auto)
            .await;
        assert!(r.success, "{r:?}");
        assert_eq!(r.service.as_deref(), Some("tmpfiles.org"));
        assert_eq!(
            r.embed_url.as_deref(),
            Some("https://tmpfiles.org/dl/9/m.png")
        );
    }

    #[tokio::test]
    async fn all_failures_are_reported_together() {
        let base = mock_server(vec![Some((500, "a")), Some((500, "b")), Some((500, "c"))]).await;
        let uploader = Uploader::with_endpoints(
            Duration::from_secs(5),
            Endpoints {
                zero_x_zero: base.clone(),
                tmpfiles: base.clone(),
                fileio: base,
            },
        );
        let r = uploader
            .upload(b"x", "m.png", "image/png", UploadService::Auto)
            .await;
        assert!(!r.success);
        let err = r.error.unwrap();
        assert!(err.contains("0x0.st: HTTP 500"), "{err}");
        assert!(err.contains("tmpfiles.org: HTTP 500"), "{err}");
        assert!(err.contains("file.io: HTTP 500"), "{err}");
    }

    #[tokio::test]
    async fn slow_service_times_out() {
        let base = mock_server(vec![None]).await;
        let uploader = Uploader::with_endpoints(
            Duration::from_millis(300),
            Endpoints {
                zero_x_zero: base.clone(),
                tmpfiles: base.clone(),
                fileio: base,
            },
        );
        let r = uploader
            .upload(b"x", "m.png", "image/png", UploadService::ZeroXZero)
            .await;
        assert!(!r.success);
        assert!(r.error.unwrap().contains("timed out"));
    }
}
