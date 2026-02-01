//! Storage service for Virtual Character MCP Server.
//!
//! Provides secure temporary file exchange for:
//! - Audio files (TTS output, sound effects, music)
//! - Animation sequences and motion data
//! - Avatar textures and assets
//! - Configuration files
//!
//! Files are automatically deleted after TTL to prevent accumulation.
//! Designed for cross-machine transfer (VM to host, remote servers, containers).

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use base64::Engine;
use hmac::{Hmac, Mac};
use rand::Rng;
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use tokio::fs;
use tokio::sync::RwLock;
use tracing::{info, warn};

type HmacSha256 = Hmac<Sha256>;

/// Token validity window (5 minutes).
const TOKEN_VALIDITY_SECONDS: u64 = 300;

/// Allow clock skew of 30 seconds.
const CLOCK_SKEW_SECONDS: u64 = 30;

/// Default TTL in hours.
const DEFAULT_TTL_HOURS: f64 = 1.0;

/// Token payload for authentication.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenPayload {
    pub issued_at: f64,
    pub expires_at: f64,
    pub nonce: String,
}

/// File metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileMetadata {
    pub path: String,
    pub filename: String,
    pub size: usize,
    pub created_at: u64,
    pub expires_at: u64,
}

/// Upload response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UploadResponse {
    pub file_id: String,
    pub url: String,
    pub expires_at: String,
    pub size_bytes: usize,
}

/// Storage service error.
#[derive(Debug, thiserror::Error)]
pub enum StorageError {
    #[error("Storage not initialized: {0}")]
    NotInitialized(String),

    #[error("Authentication failed: {0}")]
    AuthFailed(String),

    #[error("File not found: {0}")]
    NotFound(String),

    #[error("File expired: {0}")]
    Expired(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Invalid data: {0}")]
    InvalidData(String),
}

/// Result type for storage operations.
pub type StorageResult<T> = Result<T, StorageError>;

/// Secure temporary storage with automatic cleanup.
pub struct StorageService {
    storage_path: PathBuf,
    ttl_seconds: u64,
    files: Arc<RwLock<HashMap<String, FileMetadata>>>,
    secret_key: String,
    used_nonces: Arc<RwLock<HashMap<String, f64>>>,
    base_url: String,
}

impl StorageService {
    /// Create a new storage service.
    pub fn new(
        storage_path: Option<PathBuf>,
        ttl_hours: Option<f64>,
        secret_key: Option<String>,
        base_url: Option<String>,
    ) -> StorageResult<Self> {
        let path = storage_path.unwrap_or_else(|| PathBuf::from("/tmp/audio_storage"));
        let ttl = (ttl_hours.unwrap_or(DEFAULT_TTL_HOURS) * 3600.0) as u64;

        let key = secret_key
            .or_else(|| std::env::var("STORAGE_SECRET_KEY").ok())
            .ok_or_else(|| {
                StorageError::NotInitialized("STORAGE_SECRET_KEY must be set".to_string())
            })?;

        let url = base_url
            .or_else(|| std::env::var("STORAGE_BASE_URL").ok())
            .unwrap_or_else(|| "http://localhost:8021".to_string());

        // Create storage directory
        std::fs::create_dir_all(&path)?;

        info!(
            "Storage service initialized: path={:?}, ttl={}s, base_url={}",
            path, ttl, url
        );

        Ok(Self {
            storage_path: path,
            ttl_seconds: ttl,
            files: Arc::new(RwLock::new(HashMap::new())),
            secret_key: key,
            used_nonces: Arc::new(RwLock::new(HashMap::new())),
            base_url: url,
        })
    }

    /// Generate a time-limited authentication token with nonce.
    pub fn generate_token(&self) -> String {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();

        let nonce: String = rand::thread_rng()
            .sample_iter(&rand::distributions::Alphanumeric)
            .take(22)
            .map(char::from)
            .collect();

        let payload = TokenPayload {
            issued_at: now,
            expires_at: now + TOKEN_VALIDITY_SECONDS as f64,
            nonce,
        };

        // Encode payload
        let payload_json = serde_json::to_string(&payload).unwrap_or_default();
        let payload_b64 = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(payload_json);

        // Generate signature
        let mut mac =
            HmacSha256::new_from_slice(self.secret_key.as_bytes()).expect("HMAC key error");
        mac.update(payload_b64.as_bytes());
        let signature = hex::encode(mac.finalize().into_bytes());

        format!("{}.{}", payload_b64, signature)
    }

    /// Verify authentication token.
    pub async fn verify_token(&self, token: &str) -> bool {
        let parts: Vec<&str> = token.split('.').collect();

        if parts.len() != 2 {
            // Try legacy token
            return self.verify_legacy_token(token);
        }

        let (payload_b64, provided_signature) = (parts[0], parts[1]);

        // Verify signature
        let mut mac =
            HmacSha256::new_from_slice(self.secret_key.as_bytes()).expect("HMAC key error");
        mac.update(payload_b64.as_bytes());
        let expected_signature = hex::encode(mac.finalize().into_bytes());

        if provided_signature != expected_signature {
            warn!("Token signature verification failed");
            return false;
        }

        // Decode payload
        let payload_json = match base64::engine::general_purpose::URL_SAFE_NO_PAD.decode(payload_b64)
        {
            Ok(bytes) => match String::from_utf8(bytes) {
                Ok(s) => s,
                Err(_) => return self.verify_legacy_token(token),
            },
            Err(_) => return self.verify_legacy_token(token),
        };

        let payload: TokenPayload = match serde_json::from_str(&payload_json) {
            Ok(p) => p,
            Err(_) => return self.verify_legacy_token(token),
        };

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();

        // Check expiration
        if now > payload.expires_at + CLOCK_SKEW_SECONDS as f64 {
            warn!("Token expired");
            return false;
        }

        // Check not issued in the future
        if payload.issued_at > now + CLOCK_SKEW_SECONDS as f64 {
            warn!("Token issued in the future");
            return false;
        }

        // Check nonce hasn't been used
        {
            let nonces = self.used_nonces.read().await;
            if nonces.contains_key(&payload.nonce) {
                warn!("Token nonce already used (replay attack?)");
                return false;
            }
        }

        // Mark nonce as used
        {
            let mut nonces = self.used_nonces.write().await;
            nonces.insert(payload.nonce.clone(), now);
        }

        true
    }

    fn verify_legacy_token(&self, token: &str) -> bool {
        let mut mac =
            HmacSha256::new_from_slice(self.secret_key.as_bytes()).expect("HMAC key error");
        mac.update(b"audio_storage_token");
        let expected = hex::encode(mac.finalize().into_bytes());
        token == expected
    }

    /// Generate a secure random file ID.
    fn generate_file_id() -> String {
        let bytes: [u8; 24] = rand::random();
        base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(bytes)
    }

    /// Store a file with TTL.
    pub async fn store_file(&self, content: &[u8], filename: &str) -> StorageResult<UploadResponse> {
        let file_id = Self::generate_file_id();
        let file_path = self.storage_path.join(&file_id);

        // Write file
        fs::write(&file_path, content).await?;

        // Track metadata
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let expires_at = now + self.ttl_seconds;

        let metadata = FileMetadata {
            path: file_path.to_string_lossy().to_string(),
            filename: filename.to_string(),
            size: content.len(),
            created_at: now,
            expires_at,
        };

        {
            let mut files = self.files.write().await;
            files.insert(file_id.clone(), metadata);
        }

        let url = format!("{}/download/{}", self.base_url, file_id);
        let expires_str =
            chrono::DateTime::from_timestamp(expires_at as i64, 0)
                .map(|dt| dt.to_rfc3339())
                .unwrap_or_else(|| expires_at.to_string());

        Ok(UploadResponse {
            file_id,
            url,
            expires_at: expires_str,
            size_bytes: content.len(),
        })
    }

    /// Get a file if it exists and hasn't expired.
    pub async fn get_file(&self, file_id: &str) -> StorageResult<(PathBuf, String)> {
        let metadata = {
            let files = self.files.read().await;
            files.get(file_id).cloned()
        };

        let metadata = match metadata {
            Some(m) => m,
            None => return Err(StorageError::NotFound(file_id.to_string())),
        };

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        if now > metadata.expires_at {
            // File expired, delete it
            self.delete_file(file_id).await?;
            return Err(StorageError::Expired(file_id.to_string()));
        }

        let file_path = PathBuf::from(&metadata.path);
        if !file_path.exists() {
            // File missing, clean up metadata
            let mut files = self.files.write().await;
            files.remove(file_id);
            return Err(StorageError::NotFound(file_id.to_string()));
        }

        Ok((file_path, metadata.filename))
    }

    /// Delete a file and its metadata.
    pub async fn delete_file(&self, file_id: &str) -> StorageResult<bool> {
        let metadata = {
            let mut files = self.files.write().await;
            files.remove(file_id)
        };

        if let Some(metadata) = metadata {
            let file_path = PathBuf::from(&metadata.path);
            if file_path.exists() {
                fs::remove_file(&file_path).await?;
            }
            Ok(true)
        } else {
            Ok(false)
        }
    }

    /// Clean up expired files and nonces.
    pub async fn cleanup_expired(&self) -> (usize, usize) {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Find expired files
        let expired_ids: Vec<String> = {
            let files = self.files.read().await;
            files
                .iter()
                .filter(|(_, meta)| now > meta.expires_at)
                .map(|(id, _)| id.clone())
                .collect()
        };

        // Delete expired files
        for file_id in &expired_ids {
            let _ = self.delete_file(file_id).await;
        }

        // Clean up expired nonces
        let cutoff = (now - TOKEN_VALIDITY_SECONDS - CLOCK_SKEW_SECONDS) as f64;
        let nonces_cleaned = {
            let mut nonces = self.used_nonces.write().await;
            let expired: Vec<String> = nonces
                .iter()
                .filter(|(_, &used_at)| used_at < cutoff)
                .map(|(nonce, _)| nonce.clone())
                .collect();

            for nonce in &expired {
                nonces.remove(nonce);
            }
            expired.len()
        };

        (expired_ids.len(), nonces_cleaned)
    }

    /// Start periodic cleanup task.
    pub fn start_cleanup_task(self: Arc<Self>) -> tokio::task::JoinHandle<()> {
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(Duration::from_secs(300)).await;
                let (files, nonces) = self.cleanup_expired().await;
                if files > 0 || nonces > 0 {
                    info!("Cleanup: {} expired files, {} expired nonces", files, nonces);
                }
            }
        })
    }

    /// Get health status.
    pub async fn health(&self) -> serde_json::Value {
        let files = self.files.read().await;
        let nonces = self.used_nonces.read().await;

        serde_json::json!({
            "status": "healthy",
            "files_stored": files.len(),
            "storage_path": self.storage_path.to_string_lossy(),
            "nonces_tracked": nonces.len(),
        })
    }

    /// Get the base URL for this storage service.
    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    /// Get the storage path.
    pub fn storage_path(&self) -> &PathBuf {
        &self.storage_path
    }

    /// Get stats (files stored, nonces tracked).
    pub fn get_stats(&self) -> (usize, usize) {
        // Synchronous version for quick stats
        let files = self.files.blocking_read();
        let nonces = self.used_nonces.blocking_read();
        (files.len(), nonces.len())
    }

    /// Create with explicit secret (for testing).
    pub fn new_with_secret(
        storage_path: &str,
        ttl_hours: f64,
        secret_key: &str,
    ) -> StorageResult<Self> {
        let path = PathBuf::from(storage_path);
        let ttl = (ttl_hours * 3600.0) as u64;

        std::fs::create_dir_all(&path)?;

        Ok(Self {
            storage_path: path,
            ttl_seconds: ttl,
            files: Arc::new(RwLock::new(HashMap::new())),
            secret_key: secret_key.to_string(),
            used_nonces: Arc::new(RwLock::new(HashMap::new())),
            base_url: "http://localhost:8021".to_string(),
        })
    }

    /// Synchronous token verification (for HTTP handler).
    pub fn verify_token_sync(&self, token: &str) -> bool {
        let parts: Vec<&str> = token.split('.').collect();

        if parts.len() != 2 {
            return self.verify_legacy_token(token);
        }

        let (payload_b64, provided_signature) = (parts[0], parts[1]);

        // Verify signature
        let mut mac =
            HmacSha256::new_from_slice(self.secret_key.as_bytes()).expect("HMAC key error");
        mac.update(payload_b64.as_bytes());
        let expected_signature = hex::encode(mac.finalize().into_bytes());

        if provided_signature != expected_signature {
            warn!("Token signature verification failed");
            return false;
        }

        // Decode payload
        let payload_json = match base64::engine::general_purpose::URL_SAFE_NO_PAD.decode(payload_b64)
        {
            Ok(bytes) => match String::from_utf8(bytes) {
                Ok(s) => s,
                Err(_) => return self.verify_legacy_token(token),
            },
            Err(_) => return self.verify_legacy_token(token),
        };

        let payload: TokenPayload = match serde_json::from_str(&payload_json) {
            Ok(p) => p,
            Err(_) => return self.verify_legacy_token(token),
        };

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();

        // Check expiration
        if now > payload.expires_at + CLOCK_SKEW_SECONDS as f64 {
            warn!("Token expired");
            return false;
        }

        // Check not issued in the future
        if payload.issued_at > now + CLOCK_SKEW_SECONDS as f64 {
            warn!("Token issued in the future");
            return false;
        }

        // Check nonce hasn't been used (use try_read to avoid blocking)
        if let Ok(nonces) = self.used_nonces.try_read() {
            if nonces.contains_key(&payload.nonce) {
                warn!("Token nonce already used (replay attack?)");
                return false;
            }
        }

        // Mark nonce as used
        if let Ok(mut nonces) = self.used_nonces.try_write() {
            nonces.insert(payload.nonce.clone(), now);
        }

        true
    }

    /// Get file content and filename (for HTTP server).
    pub async fn get_file_content(&self, file_id: &str) -> StorageResult<Option<(Vec<u8>, String)>> {
        let metadata = {
            let files = self.files.read().await;
            files.get(file_id).cloned()
        };

        let metadata = match metadata {
            Some(m) => m,
            None => return Ok(None),
        };

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        if now > metadata.expires_at {
            return Ok(None);
        }

        let file_path = PathBuf::from(&metadata.path);
        if !file_path.exists() {
            return Ok(None);
        }

        let content = fs::read(&file_path).await?;
        Ok(Some((content, metadata.filename)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_storage_service_creation() {
        // Set up a temporary secret key for testing
        std::env::set_var("STORAGE_SECRET_KEY", "test_secret_key_12345");

        let service = StorageService::new(
            Some(PathBuf::from("/tmp/test_storage")),
            Some(0.1),
            None,
            None,
        );

        assert!(service.is_ok());
    }

    #[tokio::test]
    async fn test_token_generation_and_verification() {
        std::env::set_var("STORAGE_SECRET_KEY", "test_secret_key_12345");

        let service = StorageService::new(
            Some(PathBuf::from("/tmp/test_storage_token")),
            Some(0.1),
            None,
            None,
        )
        .unwrap();

        let token = service.generate_token();
        assert!(!token.is_empty());
        assert!(token.contains('.'));

        let is_valid = service.verify_token(&token).await;
        assert!(is_valid);

        // Token should not be reusable (nonce protection)
        let is_valid_again = service.verify_token(&token).await;
        assert!(!is_valid_again);
    }

    #[tokio::test]
    async fn test_file_storage() {
        std::env::set_var("STORAGE_SECRET_KEY", "test_secret_key_12345");

        let service = StorageService::new(
            Some(PathBuf::from("/tmp/test_storage_files")),
            Some(0.1),
            None,
            None,
        )
        .unwrap();

        let content = b"test audio content";
        let response = service.store_file(content, "test.mp3").await.unwrap();

        assert!(!response.file_id.is_empty());
        assert!(response.url.contains("/download/"));
        assert_eq!(response.size_bytes, content.len());

        // Retrieve the file
        let (path, filename) = service.get_file(&response.file_id).await.unwrap();
        assert!(path.exists());
        assert_eq!(filename, "test.mp3");

        // Delete the file
        let deleted = service.delete_file(&response.file_id).await.unwrap();
        assert!(deleted);

        // File should not be found now
        let result = service.get_file(&response.file_id).await;
        assert!(result.is_err());
    }
}
