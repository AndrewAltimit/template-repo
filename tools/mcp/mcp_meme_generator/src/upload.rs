//! Image upload utilities for sharing memes online.
//!
//! Supports multiple free hosting services without authentication.

use reqwest::multipart;
use std::path::Path;
use tracing::{info, warn};

use crate::types::UploadResult;

/// Upload a meme to free hosting services
pub struct MemeUploader;

impl MemeUploader {
    /// Upload to 0x0.st - simple, no-auth file hosting
    ///
    /// Files expire based on size (365 days for <512KB, less for larger)
    pub async fn upload_to_0x0st(file_path: &Path) -> UploadResult {
        if !file_path.exists() {
            return UploadResult {
                success: false,
                error: Some(format!("File not found: {}", file_path.display())),
                ..Default::default()
            };
        }

        let file_name = file_path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("image.png")
            .to_string();

        let file_bytes = match tokio::fs::read(file_path).await {
            Ok(bytes) => bytes,
            Err(e) => {
                return UploadResult {
                    success: false,
                    error: Some(format!("Failed to read file: {}", e)),
                    ..Default::default()
                };
            },
        };

        let part = multipart::Part::bytes(file_bytes)
            .file_name(file_name)
            .mime_str("application/octet-stream")
            .unwrap();

        let form = multipart::Form::new().part("file", part);

        let client = reqwest::Client::new();
        let response = client
            .post("https://0x0.st")
            .header("User-Agent", "curl/8.0.0") // 0x0.st blocks some user agents
            .multipart(form)
            .timeout(std::time::Duration::from_secs(30))
            .send()
            .await;

        match response {
            Ok(resp) if resp.status().is_success() => {
                let text = resp.text().await.unwrap_or_default();
                let url = text.trim().to_string();
                if url.starts_with("https://0x0.st/") {
                    UploadResult {
                        success: true,
                        url: Some(url.clone()),
                        embed_url: Some(url),
                        service: Some("0x0.st".to_string()),
                        note: Some(
                            "Link expires based on file size (365 days for <512KB)".to_string(),
                        ),
                        error: None,
                    }
                } else {
                    UploadResult {
                        success: false,
                        error: Some(format!("Unexpected response: {}", url)),
                        ..Default::default()
                    }
                }
            },
            Ok(resp) => UploadResult {
                success: false,
                error: Some(format!("Upload failed with status {}", resp.status())),
                ..Default::default()
            },
            Err(e) => {
                if e.is_timeout() {
                    UploadResult {
                        success: false,
                        error: Some("Upload timed out after 30 seconds".to_string()),
                        ..Default::default()
                    }
                } else {
                    UploadResult {
                        success: false,
                        error: Some(format!("Upload error: {}", e)),
                        ..Default::default()
                    }
                }
            },
        }
    }

    /// Upload to tmpfiles.org - reliable free hosting
    ///
    /// Files expire after 1 hour of no downloads, or max 30 days
    pub async fn upload_to_tmpfiles(file_path: &Path) -> UploadResult {
        if !file_path.exists() {
            return UploadResult {
                success: false,
                error: Some(format!("File not found: {}", file_path.display())),
                ..Default::default()
            };
        }

        let file_name = file_path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("image.png")
            .to_string();

        let file_bytes = match tokio::fs::read(file_path).await {
            Ok(bytes) => bytes,
            Err(e) => {
                return UploadResult {
                    success: false,
                    error: Some(format!("Failed to read file: {}", e)),
                    ..Default::default()
                };
            },
        };

        let part = multipart::Part::bytes(file_bytes)
            .file_name(file_name)
            .mime_str("application/octet-stream")
            .unwrap();

        let form = multipart::Form::new().part("file", part);

        let client = reqwest::Client::new();
        let response = client
            .post("https://tmpfiles.org/api/v1/upload")
            .multipart(form)
            .timeout(std::time::Duration::from_secs(30))
            .send()
            .await;

        match response {
            Ok(resp) if resp.status().is_success() => {
                let json: Result<serde_json::Value, _> = resp.json().await;
                match json {
                    Ok(data) => {
                        if data.get("status").and_then(|s| s.as_str()) == Some("success") {
                            if let Some(url) = data
                                .get("data")
                                .and_then(|d| d.get("url"))
                                .and_then(|u| u.as_str())
                            {
                                // Convert to direct download link
                                let embed_url = url.replace("http://", "https://");
                                UploadResult {
                                    success: true,
                                    url: Some(url.to_string()),
                                    embed_url: Some(embed_url),
                                    service: Some("tmpfiles.org".to_string()),
                                    note: Some(
                                        "Link expires after 1 hour of inactivity or max 30 days"
                                            .to_string(),
                                    ),
                                    error: None,
                                }
                            } else {
                                UploadResult {
                                    success: false,
                                    error: Some("No URL in response".to_string()),
                                    ..Default::default()
                                }
                            }
                        } else {
                            let msg = data
                                .get("message")
                                .and_then(|m| m.as_str())
                                .unwrap_or("Upload failed");
                            UploadResult {
                                success: false,
                                error: Some(msg.to_string()),
                                ..Default::default()
                            }
                        }
                    },
                    Err(e) => UploadResult {
                        success: false,
                        error: Some(format!("Invalid JSON response: {}", e)),
                        ..Default::default()
                    },
                }
            },
            Ok(resp) => {
                let status = resp.status();
                if status.as_u16() == 403 {
                    UploadResult {
                        success: false,
                        error: Some(
                            "Access forbidden - service may be blocking automated uploads"
                                .to_string(),
                        ),
                        ..Default::default()
                    }
                } else {
                    UploadResult {
                        success: false,
                        error: Some(format!("Upload failed with status {}", status)),
                        ..Default::default()
                    }
                }
            },
            Err(e) => {
                if e.is_timeout() {
                    UploadResult {
                        success: false,
                        error: Some("Upload timed out after 30 seconds".to_string()),
                        ..Default::default()
                    }
                } else {
                    UploadResult {
                        success: false,
                        error: Some(format!("Upload error: {}", e)),
                        ..Default::default()
                    }
                }
            },
        }
    }

    /// Upload to file.io - another free, no-auth service
    pub async fn upload_to_fileio(file_path: &Path, expires: &str) -> UploadResult {
        if !file_path.exists() {
            return UploadResult {
                success: false,
                error: Some(format!("File not found: {}", file_path.display())),
                ..Default::default()
            };
        }

        let file_name = file_path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("image.png")
            .to_string();

        let file_bytes = match tokio::fs::read(file_path).await {
            Ok(bytes) => bytes,
            Err(e) => {
                return UploadResult {
                    success: false,
                    error: Some(format!("Failed to read file: {}", e)),
                    ..Default::default()
                };
            },
        };

        let part = multipart::Part::bytes(file_bytes)
            .file_name(file_name)
            .mime_str("application/octet-stream")
            .unwrap();

        let form = multipart::Form::new().part("file", part);

        let client = reqwest::Client::new();
        let response = client
            .post(format!("https://file.io/?expires={}", expires))
            .multipart(form)
            .timeout(std::time::Duration::from_secs(30))
            .send()
            .await;

        match response {
            Ok(resp) if resp.status().is_success() => {
                let json: Result<serde_json::Value, _> = resp.json().await;
                match json {
                    Ok(data) => {
                        if data.get("success").and_then(|s| s.as_bool()) == Some(true) {
                            if let Some(link) = data.get("link").and_then(|l| l.as_str()) {
                                UploadResult {
                                    success: true,
                                    url: Some(link.to_string()),
                                    embed_url: Some(link.to_string()),
                                    service: Some("file.io".to_string()),
                                    note: Some(format!("Link expires after {}", expires)),
                                    error: None,
                                }
                            } else {
                                UploadResult {
                                    success: false,
                                    error: Some("No link in response".to_string()),
                                    ..Default::default()
                                }
                            }
                        } else {
                            let msg = data
                                .get("message")
                                .and_then(|m| m.as_str())
                                .unwrap_or("Upload failed");
                            UploadResult {
                                success: false,
                                error: Some(msg.to_string()),
                                ..Default::default()
                            }
                        }
                    },
                    Err(e) => UploadResult {
                        success: false,
                        error: Some(format!("Invalid JSON response: {}", e)),
                        ..Default::default()
                    },
                }
            },
            Ok(resp) => UploadResult {
                success: false,
                error: Some(format!("Upload failed with status {}", resp.status())),
                ..Default::default()
            },
            Err(e) => {
                if e.is_timeout() {
                    UploadResult {
                        success: false,
                        error: Some("Upload timed out after 30 seconds".to_string()),
                        ..Default::default()
                    }
                } else {
                    UploadResult {
                        success: false,
                        error: Some(format!("Upload error: {}", e)),
                        ..Default::default()
                    }
                }
            },
        }
    }

    /// Upload a meme to a hosting service
    ///
    /// Tries multiple services in order: 0x0.st, tmpfiles.org, file.io
    pub async fn upload(file_path: &Path, service: &str) -> UploadResult {
        if !file_path.exists() {
            return UploadResult {
                success: false,
                error: Some(format!("File not found: {}", file_path.display())),
                ..Default::default()
            };
        }

        // Check file size
        let metadata = match tokio::fs::metadata(file_path).await {
            Ok(m) => m,
            Err(e) => {
                return UploadResult {
                    success: false,
                    error: Some(format!("Failed to read file metadata: {}", e)),
                    ..Default::default()
                };
            },
        };

        let size_mb = metadata.len() as f64 / (1024.0 * 1024.0);
        if size_mb > 512.0 {
            return UploadResult {
                success: false,
                error: Some(format!("File too large: {:.1}MB (max 512MB)", size_mb)),
                ..Default::default()
            };
        }

        match service {
            "0x0st" => Self::upload_to_0x0st(file_path).await,
            "tmpfiles" => Self::upload_to_tmpfiles(file_path).await,
            "fileio" => Self::upload_to_fileio(file_path, "1d").await,
            "auto" => {
                // Try 0x0.st first (better retention)
                info!("Trying 0x0.st...");
                let result = Self::upload_to_0x0st(file_path).await;
                if result.success {
                    info!("Successfully uploaded to 0x0.st");
                    return result;
                }
                warn!("0x0.st failed: {:?}", result.error);

                // Try tmpfiles.org second
                info!("Trying tmpfiles.org...");
                let result = Self::upload_to_tmpfiles(file_path).await;
                if result.success {
                    info!("Successfully uploaded to tmpfiles.org");
                    return result;
                }
                warn!("tmpfiles.org failed: {:?}", result.error);

                // Try file.io last
                info!("Trying file.io...");
                let result = Self::upload_to_fileio(file_path, "1d").await;
                if result.success {
                    info!("Successfully uploaded to file.io");
                    return result;
                }
                warn!("file.io failed: {:?}", result.error);

                UploadResult {
                    success: false,
                    error: Some("All upload services failed".to_string()),
                    ..Default::default()
                }
            },
            _ => UploadResult {
                success: false,
                error: Some(format!(
                    "Unknown service: {}. Available: 0x0st, tmpfiles, fileio, auto",
                    service
                )),
                ..Default::default()
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_upload_result_default() {
        let result = UploadResult::default();
        assert!(!result.success);
        assert!(result.url.is_none());
    }
}
