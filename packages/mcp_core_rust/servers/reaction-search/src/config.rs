//! Config loader with caching for reaction search.

use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use thiserror::Error;
use tracing::{debug, info, warn};

use crate::types::{CacheMeta, CacheStatus, Reaction, ReactionConfig};

/// Default config URL
const CONFIG_URL: &str =
    "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml";

/// Default cache TTL: 1 week in seconds
const CACHE_TTL_SECONDS: u64 = 7 * 24 * 60 * 60;

/// HTTP request timeout in seconds
const REQUEST_TIMEOUT_SECS: u64 = 30;

/// Errors that can occur during config loading
#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Failed to fetch config: {0}")]
    FetchError(String),

    #[error("Failed to parse config: {0}")]
    ParseError(String),

    #[error("Cache error: {0}")]
    CacheError(String),

    #[error("No config available")]
    NoConfig,
}

/// Config loader with GitHub fetching and local caching
pub struct ConfigLoader {
    config_url: String,
    cache_dir: PathBuf,
    cache_ttl: u64,
    config: Option<ReactionConfig>,
}

impl ConfigLoader {
    /// Create a new config loader with defaults
    pub fn new() -> Self {
        let cache_dir = dirs::cache_dir()
            .unwrap_or_else(|| PathBuf::from(".cache"))
            .join("mcp_reaction_search");

        Self {
            config_url: CONFIG_URL.to_string(),
            cache_dir,
            cache_ttl: CACHE_TTL_SECONDS,
            config: None,
        }
    }

    /// Create with custom settings
    pub fn with_options(config_url: String, cache_dir: PathBuf, cache_ttl: u64) -> Self {
        Self {
            config_url,
            cache_dir,
            cache_ttl,
            config: None,
        }
    }

    /// Get the cache file path
    fn cache_file(&self) -> PathBuf {
        self.cache_dir.join("reaction_config.json")
    }

    /// Get the cache metadata file path
    fn cache_meta_file(&self) -> PathBuf {
        self.cache_dir.join("cache_meta.json")
    }

    /// Get current unix timestamp
    fn now_timestamp() -> f64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0)
    }

    /// Check if cache is valid (exists and within TTL)
    fn is_cache_valid(&self) -> bool {
        let meta_path = self.cache_meta_file();
        if !meta_path.exists() || !self.cache_file().exists() {
            return false;
        }

        match fs::read_to_string(&meta_path) {
            Ok(content) => match serde_json::from_str::<CacheMeta>(&content) {
                Ok(meta) => {
                    let age = Self::now_timestamp() - meta.cached_at;
                    age < self.cache_ttl as f64
                }
                Err(_) => false,
            },
            Err(_) => false,
        }
    }

    /// Load config from cache
    fn load_from_cache(&self) -> Result<ReactionConfig, ConfigError> {
        let cache_path = self.cache_file();
        let content = fs::read_to_string(&cache_path)
            .map_err(|e| ConfigError::CacheError(format!("Failed to read cache: {}", e)))?;

        serde_json::from_str(&content)
            .map_err(|e| ConfigError::ParseError(format!("Failed to parse cached config: {}", e)))
    }

    /// Save config to cache
    fn save_to_cache(&self, config: &ReactionConfig) -> Result<(), ConfigError> {
        // Ensure cache directory exists
        fs::create_dir_all(&self.cache_dir)
            .map_err(|e| ConfigError::CacheError(format!("Failed to create cache dir: {}", e)))?;

        // Save config as JSON
        let config_json = serde_json::to_string_pretty(config)
            .map_err(|e| ConfigError::CacheError(format!("Failed to serialize config: {}", e)))?;

        fs::write(self.cache_file(), config_json)
            .map_err(|e| ConfigError::CacheError(format!("Failed to write cache: {}", e)))?;

        // Save metadata
        let meta = CacheMeta {
            cached_at: Self::now_timestamp(),
            source_url: self.config_url.clone(),
            reaction_count: config.reaction_images.len(),
        };

        let meta_json = serde_json::to_string_pretty(&meta)
            .map_err(|e| ConfigError::CacheError(format!("Failed to serialize meta: {}", e)))?;

        fs::write(self.cache_meta_file(), meta_json)
            .map_err(|e| ConfigError::CacheError(format!("Failed to write meta: {}", e)))?;

        debug!("Saved {} reactions to cache", config.reaction_images.len());
        Ok(())
    }

    /// Fetch config from GitHub
    async fn fetch_from_github(&self) -> Result<ReactionConfig, ConfigError> {
        info!("Fetching config from {}", self.config_url);

        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(REQUEST_TIMEOUT_SECS))
            .build()
            .map_err(|e| ConfigError::FetchError(format!("Failed to create client: {}", e)))?;

        let response = client
            .get(&self.config_url)
            .send()
            .await
            .map_err(|e| ConfigError::FetchError(format!("Request failed: {}", e)))?;

        if !response.status().is_success() {
            return Err(ConfigError::FetchError(format!(
                "HTTP {}: {}",
                response.status(),
                response.status().canonical_reason().unwrap_or("Unknown")
            )));
        }

        let yaml_content = response
            .text()
            .await
            .map_err(|e| ConfigError::FetchError(format!("Failed to read response: {}", e)))?;

        let config: ReactionConfig = serde_yaml::from_str(&yaml_content)
            .map_err(|e| ConfigError::ParseError(format!("Failed to parse YAML: {}", e)))?;

        info!("Fetched {} reactions from GitHub", config.reaction_images.len());
        Ok(config)
    }

    /// Load config (from cache or GitHub)
    pub async fn load(&mut self, force_refresh: bool) -> Result<&ReactionConfig, ConfigError> {
        // Return cached if available and not forcing refresh
        if !force_refresh && self.config.is_some() {
            return Ok(self.config.as_ref().unwrap());
        }

        // Try cache first (if not forcing refresh)
        if !force_refresh && self.is_cache_valid() {
            debug!("Loading config from cache");
            match self.load_from_cache() {
                Ok(config) => {
                    info!("Loaded {} reactions from cache", config.reaction_images.len());
                    self.config = Some(config);
                    return Ok(self.config.as_ref().unwrap());
                }
                Err(e) => {
                    warn!("Cache load failed, will fetch: {}", e);
                }
            }
        }

        // Fetch from GitHub
        match self.fetch_from_github().await {
            Ok(config) => {
                // Save to cache (ignore errors)
                if let Err(e) = self.save_to_cache(&config) {
                    warn!("Failed to save cache: {}", e);
                }
                self.config = Some(config);
                Ok(self.config.as_ref().unwrap())
            }
            Err(e) => {
                // Try expired cache as fallback
                warn!("GitHub fetch failed: {}", e);
                if self.cache_file().exists() {
                    warn!("Falling back to expired cache");
                    match self.load_from_cache() {
                        Ok(config) => {
                            self.config = Some(config);
                            Ok(self.config.as_ref().unwrap())
                        }
                        Err(_) => Err(ConfigError::NoConfig),
                    }
                } else {
                    Err(ConfigError::NoConfig)
                }
            }
        }
    }

    /// Get reactions from loaded config
    pub async fn get_reactions(&mut self) -> Result<Vec<Reaction>, ConfigError> {
        let config = self.load(false).await?;
        Ok(config.reaction_images.clone())
    }

    /// Clear the cache
    pub fn clear_cache(&mut self) -> bool {
        self.config = None;

        let cache_removed = fs::remove_file(self.cache_file()).is_ok();
        let meta_removed = fs::remove_file(self.cache_meta_file()).is_ok();

        cache_removed || meta_removed
    }

    /// Get cache status information
    pub fn get_cache_info(&self) -> CacheStatus {
        let cache_file = self.cache_file();
        let meta_file = self.cache_meta_file();
        let cache_exists = cache_file.exists();

        let mut status = CacheStatus {
            cache_dir: self.cache_dir.display().to_string(),
            cache_file_exists: cache_exists,
            cache_valid: self.is_cache_valid(),
            cache_ttl_seconds: self.cache_ttl,
            config_url: self.config_url.clone(),
            cached_at: None,
            reaction_count: None,
            cache_age_hours: None,
            cache_expires_in_hours: None,
        };

        if meta_file.exists() {
            if let Ok(content) = fs::read_to_string(&meta_file) {
                if let Ok(meta) = serde_json::from_str::<CacheMeta>(&content) {
                    let now = Self::now_timestamp();
                    let age_secs = now - meta.cached_at;
                    let ttl_secs = self.cache_ttl as f64;

                    status.cached_at = Some(meta.cached_at);
                    status.reaction_count = Some(meta.reaction_count);
                    status.cache_age_hours = Some(age_secs / 3600.0);
                    status.cache_expires_in_hours = Some((ttl_secs - age_secs) / 3600.0);
                }
            }
        }

        status
    }
}

impl Default for ConfigLoader {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_loader_creation() {
        let loader = ConfigLoader::new();
        assert!(!loader.config_url.is_empty());
        assert!(loader.cache_ttl > 0);
    }

    #[test]
    fn test_cache_info() {
        let loader = ConfigLoader::new();
        let info = loader.get_cache_info();
        assert!(!info.cache_dir.is_empty());
        assert!(!info.config_url.is_empty());
    }
}
