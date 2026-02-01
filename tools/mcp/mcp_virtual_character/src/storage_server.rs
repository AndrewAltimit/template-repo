//! Storage HTTP Server for file upload/download.
//!
//! Provides HTTP endpoints for temporary file storage, enabling cross-machine
//! transfer of audio files and other virtual character data.

use axum::{
    body::Body,
    extract::{Path, State},
    http::{header, HeaderMap, StatusCode},
    response::{IntoResponse, Json, Response},
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info, warn};

use crate::storage::StorageService;

/// Shared state for the HTTP server.
pub type SharedStorage = Arc<RwLock<StorageService>>;

/// Response from file upload.
#[derive(Debug, Serialize)]
pub struct UploadResponse {
    pub file_id: String,
    pub url: String,
    pub expires_at: String,
    pub size_bytes: usize,
}

/// Request for base64 upload.
#[derive(Debug, Deserialize)]
pub struct Base64UploadRequest {
    pub audio_data: String,
    #[serde(default = "default_filename")]
    pub filename: String,
}

fn default_filename() -> String {
    "audio.mp3".to_string()
}

/// Health check response.
#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub files_stored: usize,
    pub storage_path: String,
    pub nonces_tracked: usize,
}

/// Token response.
#[derive(Debug, Serialize)]
pub struct TokenResponse {
    pub token: String,
    pub expires_in_seconds: u64,
}

/// Error response.
#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
}

impl IntoResponse for ErrorResponse {
    fn into_response(self) -> Response {
        let body = serde_json::to_string(&self).unwrap_or_default();
        Response::builder()
            .status(StatusCode::INTERNAL_SERVER_ERROR)
            .header(header::CONTENT_TYPE, "application/json")
            .body(Body::from(body))
            .unwrap()
    }
}

/// Extract and verify authorization header.
fn verify_auth(headers: &HeaderMap, storage: &StorageService) -> Result<(), (StatusCode, Json<ErrorResponse>)> {
    let auth_header = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok());

    match auth_header {
        Some(auth) if auth.starts_with("Bearer ") => {
            let token = auth.trim_start_matches("Bearer ");
            if storage.verify_token_sync(token) {
                Ok(())
            } else {
                Err((
                    StatusCode::UNAUTHORIZED,
                    Json(ErrorResponse {
                        error: "Invalid or expired token".to_string(),
                    }),
                ))
            }
        }
        _ => Err((
            StatusCode::UNAUTHORIZED,
            Json(ErrorResponse {
                error: "Missing or invalid authorization header".to_string(),
            }),
        )),
    }
}

/// Health check endpoint (no auth required).
async fn health(State(storage): State<SharedStorage>) -> impl IntoResponse {
    let storage = storage.read().await;
    let (files_stored, nonces_tracked) = storage.get_stats();

    Json(HealthResponse {
        status: "healthy".to_string(),
        files_stored,
        storage_path: storage.storage_path().to_string_lossy().to_string(),
        nonces_tracked,
    })
}

/// Generate a new authentication token.
async fn generate_token(
    State(storage): State<SharedStorage>,
    headers: HeaderMap,
) -> Result<Json<TokenResponse>, (StatusCode, Json<ErrorResponse>)> {
    let storage = storage.read().await;
    verify_auth(&headers, &storage)?;

    let token = storage.generate_token();
    Ok(Json(TokenResponse {
        token,
        expires_in_seconds: 300, // 5 minutes
    }))
}

/// Upload a file via multipart form.
async fn upload_file(
    State(storage): State<SharedStorage>,
    headers: HeaderMap,
    body: axum::body::Bytes,
) -> Result<Json<UploadResponse>, (StatusCode, Json<ErrorResponse>)> {
    let storage = storage.read().await;
    verify_auth(&headers, &storage)?;

    let filename = headers
        .get("x-filename")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("audio.mp3")
        .to_string();

    match storage.store_file(&body, &filename).await {
        Ok(response) => {
            info!("Stored file: {} ({} bytes)", response.file_id, body.len());
            Ok(Json(UploadResponse {
                file_id: response.file_id.clone(),
                url: response.url,
                expires_at: response.expires_at,
                size_bytes: body.len(),
            }))
        }
        Err(e) => {
            error!("Failed to store file: {}", e);
            Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    error: format!("Failed to store file: {}", e),
                }),
            ))
        }
    }
}

/// Upload base64-encoded audio.
async fn upload_base64(
    State(storage): State<SharedStorage>,
    headers: HeaderMap,
    Json(request): Json<Base64UploadRequest>,
) -> Result<Json<UploadResponse>, (StatusCode, Json<ErrorResponse>)> {
    let storage = storage.read().await;
    verify_auth(&headers, &storage)?;

    let content = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, &request.audio_data)
        .map_err(|e| {
            (
                StatusCode::BAD_REQUEST,
                Json(ErrorResponse {
                    error: format!("Invalid base64: {}", e),
                }),
            )
        })?;

    match storage.store_file(&content, &request.filename).await {
        Ok(response) => {
            info!(
                "Stored base64 file: {} ({} bytes)",
                response.file_id,
                content.len()
            );
            Ok(Json(UploadResponse {
                file_id: response.file_id.clone(),
                url: response.url,
                expires_at: response.expires_at,
                size_bytes: content.len(),
            }))
        }
        Err(e) => {
            error!("Failed to store file: {}", e);
            Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    error: format!("Failed to store file: {}", e),
                }),
            ))
        }
    }
}

/// Download a stored file.
async fn download_file(
    State(storage): State<SharedStorage>,
    headers: HeaderMap,
    Path(file_id): Path<String>,
) -> Result<Response, (StatusCode, Json<ErrorResponse>)> {
    let storage = storage.read().await;
    verify_auth(&headers, &storage)?;

    match storage.get_file_content(&file_id).await {
        Ok(Some((content, filename))) => {
            info!("Downloaded file: {} ({} bytes)", file_id, content.len());

            let content_type = if filename.ends_with(".mp3") {
                "audio/mpeg"
            } else if filename.ends_with(".wav") {
                "audio/wav"
            } else if filename.ends_with(".ogg") {
                "audio/ogg"
            } else {
                "application/octet-stream"
            };

            Ok(Response::builder()
                .status(StatusCode::OK)
                .header(header::CONTENT_TYPE, content_type)
                .header(
                    header::CONTENT_DISPOSITION,
                    format!("attachment; filename=\"{}\"", filename),
                )
                .body(Body::from(content))
                .unwrap())
        }
        Ok(None) => {
            warn!("File not found or expired: {}", file_id);
            Err((
                StatusCode::NOT_FOUND,
                Json(ErrorResponse {
                    error: "File not found or expired".to_string(),
                }),
            ))
        }
        Err(e) => {
            error!("Failed to get file: {}", e);
            Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    error: format!("Failed to get file: {}", e),
                }),
            ))
        }
    }
}

/// Create the storage HTTP router.
pub fn create_storage_router(storage: SharedStorage) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/token", post(generate_token))
        .route("/upload", post(upload_file))
        .route("/upload_base64", post(upload_base64))
        .route("/download/{file_id}", get(download_file))
        .with_state(storage)
}

/// Start the storage HTTP server.
pub async fn start_storage_server(storage: SharedStorage, port: u16) -> Result<(), std::io::Error> {
    let app = create_storage_router(storage);
    let addr = std::net::SocketAddr::from(([0, 0, 0, 0], port));

    info!("Starting storage HTTP server on port {}", port);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_storage_router() {
        let storage = Arc::new(RwLock::new(
            StorageService::new_with_secret("/tmp/test_storage_router", 1.0, "test_secret").unwrap(),
        ));

        // Just verify router creation doesn't panic
        let _app = create_storage_router(storage);
    }

    #[test]
    fn test_verify_auth_missing_header() {
        let headers = HeaderMap::new();
        let storage = StorageService::new_with_secret("/tmp/test_auth", 1.0, "test_secret").unwrap();

        let result = verify_auth(&headers, &storage);
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_auth_invalid_token() {
        let mut headers = HeaderMap::new();
        headers.insert(header::AUTHORIZATION, "Bearer invalid_token".parse().unwrap());
        let storage = StorageService::new_with_secret("/tmp/test_auth2", 1.0, "test_secret").unwrap();

        let result = verify_auth(&headers, &storage);
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_auth_valid_token() {
        let storage = StorageService::new_with_secret("/tmp/test_auth3", 1.0, "test_secret").unwrap();
        let token = storage.generate_token();

        let mut headers = HeaderMap::new();
        headers.insert(header::AUTHORIZATION, format!("Bearer {}", token).parse().unwrap());

        let result = verify_auth(&headers, &storage);
        assert!(result.is_ok());
    }
}
