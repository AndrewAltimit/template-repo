//! Reaction config loading: remote fetch, local-file source, on-disk cache,
//! validation, and offline fallback.
//!
//! Resolution order for [`ConfigLoader::load`]:
//!
//! 1. A local-file source (`file://...` or a plain path) is always read
//!    directly; nothing is cached.
//! 2. A fresh on-disk cache (within TTL and written for the same source URL).
//! 3. A network fetch (bounded by `fetch_timeout` and [`MAX_CONFIG_BYTES`]);
//!    on success the cache is rewritten atomically.
//! 4. A stale cache, if the fetch failed. This is the offline fallback.
//!
//! [`ConfigLoader::refresh`] only performs step 3 and never deletes the
//! existing cache, so a failed refresh cannot strand the server without data.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::Serialize;
use thiserror::Error;
use tracing::{debug, info, warn};

use crate::types::{CacheMeta, CacheStatus, Reaction, ReactionConfig};

/// Default config URL.
pub const DEFAULT_CONFIG_URL: &str =
    "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml";

/// Default cache TTL: 1 week.
pub const DEFAULT_CACHE_TTL: Duration = Duration::from_secs(7 * 24 * 60 * 60);

/// Default total timeout for the config fetch.
pub const DEFAULT_FETCH_TIMEOUT: Duration = Duration::from_secs(15);

/// Upper bound on the config document size. The real file is ~50 KB; this
/// guards against a misconfigured URL streaming something huge into memory.
pub const MAX_CONFIG_BYTES: usize = 8 * 1024 * 1024;

const CACHE_FILE: &str = "reaction_config.json";
const CACHE_META_FILE: &str = "cache_meta.json";

/// Errors that can occur during config loading.
#[derive(Error, Debug)]
pub enum ConfigError {
    /// Network or file read failure.
    #[error("failed to fetch config: {0}")]
    Fetch(String),

    /// The document could not be parsed or contained no usable reactions.
    #[error("failed to parse config: {0}")]
    Parse(String),

    /// Reading or writing the local cache failed.
    #[error("cache error: {0}")]
    Cache(String),

    /// Neither the source nor any cache produced a config.
    #[error("no reaction config available (fetch failed: {0}; no usable cache)")]
    NoConfig(String),
}

/// Where a loaded config came from.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ConfigSource {
    /// Read from a local file source.
    LocalFile,
    /// Read from a fresh on-disk cache.
    Cache,
    /// Fetched from the network.
    Network,
    /// Network fetch failed; fell back to an expired cache.
    StaleCache,
}

/// Settings for [`ConfigLoader`].
#[derive(Debug, Clone)]
pub struct ConfigSettings {
    /// `http(s)://` URL, `file://` URL, or local filesystem path.
    pub config_url: String,
    /// Directory for the cached config and metadata.
    pub cache_dir: PathBuf,
    /// Maximum age before the cache is considered stale.
    pub cache_ttl: Duration,
    /// Total timeout for a network fetch.
    pub fetch_timeout: Duration,
}

impl Default for ConfigSettings {
    fn default() -> Self {
        Self {
            config_url: DEFAULT_CONFIG_URL.to_string(),
            cache_dir: default_cache_root().join("mcp_reaction_search"),
            cache_ttl: DEFAULT_CACHE_TTL,
            fetch_timeout: DEFAULT_FETCH_TIMEOUT,
        }
    }
}

/// Platform cache root (`~/.cache` on Linux), or `./.cache` if unknown.
pub fn default_cache_root() -> PathBuf {
    dirs::cache_dir().unwrap_or_else(|| PathBuf::from(".cache"))
}

/// Result of a successful load.
#[derive(Debug, Clone)]
pub struct LoadedConfig {
    /// Validated, de-duplicated reactions (never empty).
    pub reactions: Vec<Reaction>,
    /// Where they came from.
    pub source: ConfigSource,
    /// Non-fatal problems found while validating the document.
    pub warnings: Vec<String>,
}

/// Config loader with remote fetching and local caching.
pub struct ConfigLoader {
    settings: ConfigSettings,
    client: reqwest::Client,
}

impl ConfigLoader {
    /// Create a loader from settings.
    pub fn new(settings: ConfigSettings) -> Self {
        let client = mcp_core::http::build_client_or_default(settings.fetch_timeout);
        Self { settings, client }
    }

    fn cache_file(&self) -> PathBuf {
        self.settings.cache_dir.join(CACHE_FILE)
    }

    fn cache_meta_file(&self) -> PathBuf {
        self.settings.cache_dir.join(CACHE_META_FILE)
    }

    /// Local path if the source is a file rather than an HTTP(S) URL.
    fn local_source_path(&self) -> Option<PathBuf> {
        local_path_for(&self.settings.config_url)
    }

    async fn read_meta(&self) -> Option<CacheMeta> {
        let content = tokio::fs::read_to_string(self.cache_meta_file())
            .await
            .ok()?;
        serde_json::from_str(&content).ok()
    }

    /// A cache is valid if it exists, was written for the configured source
    /// URL, and is younger than the TTL.
    async fn is_cache_valid(&self) -> bool {
        if !tokio::fs::try_exists(self.cache_file())
            .await
            .unwrap_or(false)
        {
            return false;
        }
        match self.read_meta().await {
            Some(meta) => {
                meta.source_url == self.settings.config_url
                    && cache_age_secs(&meta) < self.settings.cache_ttl.as_secs_f64()
            },
            None => false,
        }
    }

    async fn load_from_cache(&self) -> Result<Vec<Reaction>, ConfigError> {
        let content = tokio::fs::read_to_string(self.cache_file())
            .await
            .map_err(|e| ConfigError::Cache(format!("failed to read cache: {e}")))?;
        let config: ReactionConfig = serde_json::from_str(&content)
            .map_err(|e| ConfigError::Parse(format!("corrupt cache file: {e}")))?;
        Ok(config.reaction_images)
    }

    /// Write the cache atomically (temp file + rename) so a crash mid-write
    /// never leaves a truncated cache behind.
    async fn save_to_cache(&self, reactions: &[Reaction]) -> Result<(), ConfigError> {
        let dir = &self.settings.cache_dir;
        tokio::fs::create_dir_all(dir)
            .await
            .map_err(|e| ConfigError::Cache(format!("failed to create {}: {e}", dir.display())))?;

        let config = ReactionConfig {
            reaction_images: reactions.to_vec(),
        };
        let config_json = serde_json::to_string(&config)
            .map_err(|e| ConfigError::Cache(format!("failed to serialize config: {e}")))?;
        let meta = CacheMeta {
            cached_at: now_timestamp(),
            source_url: self.settings.config_url.clone(),
            reaction_count: reactions.len(),
        };
        let meta_json = serde_json::to_string_pretty(&meta)
            .map_err(|e| ConfigError::Cache(format!("failed to serialize meta: {e}")))?;

        write_atomic(&self.cache_file(), config_json.as_bytes()).await?;
        write_atomic(&self.cache_meta_file(), meta_json.as_bytes()).await?;
        debug!("Saved {} reactions to cache", reactions.len());
        Ok(())
    }

    /// Fetch the raw document from the network with a size cap.
    async fn fetch_remote(&self) -> Result<String, ConfigError> {
        let url = &self.settings.config_url;
        info!("Fetching reaction config from {url}");

        let mut response = self.client.get(url).send().await.map_err(|e| {
            ConfigError::Fetch(describe_reqwest_error(&e, self.settings.fetch_timeout))
        })?;

        let status = response.status();
        if !status.is_success() {
            return Err(ConfigError::Fetch(format!("HTTP {status} from {url}")));
        }
        if let Some(len) = response.content_length()
            && len > MAX_CONFIG_BYTES as u64
        {
            return Err(ConfigError::Fetch(format!(
                "config is {len} bytes, exceeds limit of {MAX_CONFIG_BYTES}"
            )));
        }

        let mut body = Vec::new();
        while let Some(chunk) = response.chunk().await.map_err(|e| {
            ConfigError::Fetch(describe_reqwest_error(&e, self.settings.fetch_timeout))
        })? {
            if body.len() + chunk.len() > MAX_CONFIG_BYTES {
                return Err(ConfigError::Fetch(format!(
                    "config exceeds limit of {MAX_CONFIG_BYTES} bytes"
                )));
            }
            body.extend_from_slice(&chunk);
        }
        String::from_utf8(body).map_err(|_| ConfigError::Parse("config is not valid UTF-8".into()))
    }

    /// Read the document from a local file source.
    async fn read_local(&self, path: &Path) -> Result<String, ConfigError> {
        let meta = tokio::fs::metadata(path)
            .await
            .map_err(|e| ConfigError::Fetch(format!("cannot read {}: {e}", path.display())))?;
        if meta.len() > MAX_CONFIG_BYTES as u64 {
            return Err(ConfigError::Fetch(format!(
                "{} is {} bytes, exceeds limit of {MAX_CONFIG_BYTES}",
                path.display(),
                meta.len()
            )));
        }
        tokio::fs::read_to_string(path)
            .await
            .map_err(|e| ConfigError::Fetch(format!("cannot read {}: {e}", path.display())))
    }

    /// Fetch from the configured source (bypassing the cache), validate, and
    /// rewrite the cache on success. The existing cache is untouched on
    /// failure.
    pub async fn refresh(&self) -> Result<LoadedConfig, ConfigError> {
        if let Some(path) = self.local_source_path() {
            let raw = self.read_local(&path).await?;
            let (reactions, warnings) = parse_config(&raw)?;
            return Ok(LoadedConfig {
                reactions,
                source: ConfigSource::LocalFile,
                warnings,
            });
        }

        let raw = self.fetch_remote().await?;
        let (reactions, warnings) = parse_config(&raw)?;
        info!("Fetched {} reactions", reactions.len());
        if let Err(e) = self.save_to_cache(&reactions).await {
            warn!("Failed to save reaction cache: {e}");
        }
        Ok(LoadedConfig {
            reactions,
            source: ConfigSource::Network,
            warnings,
        })
    }

    /// Load the config: fresh cache, else network, else stale cache.
    pub async fn load(&self) -> Result<LoadedConfig, ConfigError> {
        if self.local_source_path().is_none() && self.is_cache_valid().await {
            match self.load_from_cache().await {
                Ok(raw) => {
                    let (reactions, warnings) = sanitize_reactions(raw);
                    if !reactions.is_empty() {
                        info!("Loaded {} reactions from cache", reactions.len());
                        return Ok(LoadedConfig {
                            reactions,
                            source: ConfigSource::Cache,
                            warnings,
                        });
                    }
                    warn!("Cache contained no usable reactions; fetching");
                },
                Err(e) => warn!("Cache load failed, fetching instead: {e}"),
            }
        }

        let fetch_err = match self.refresh().await {
            Ok(loaded) => return Ok(loaded),
            Err(e) => e,
        };
        if self.local_source_path().is_some() {
            return Err(fetch_err);
        }

        warn!("Config fetch failed: {fetch_err}");
        match self.load_from_cache().await {
            Ok(raw) => {
                let (reactions, warnings) = sanitize_reactions(raw);
                if reactions.is_empty() {
                    return Err(ConfigError::NoConfig(fetch_err.to_string()));
                }
                warn!(
                    "Falling back to stale cache with {} reactions",
                    reactions.len()
                );
                Ok(LoadedConfig {
                    reactions,
                    source: ConfigSource::StaleCache,
                    warnings,
                })
            },
            Err(_) => Err(ConfigError::NoConfig(fetch_err.to_string())),
        }
    }

    /// Cache status for diagnostics.
    pub async fn cache_info(&self) -> CacheStatus {
        let cache_exists = tokio::fs::try_exists(self.cache_file())
            .await
            .unwrap_or(false);
        let mut status = CacheStatus {
            cache_dir: self.settings.cache_dir.display().to_string(),
            cache_file_exists: cache_exists,
            cache_valid: self.is_cache_valid().await,
            cache_ttl_seconds: self.settings.cache_ttl.as_secs(),
            config_url: self.settings.config_url.clone(),
            cached_at: None,
            reaction_count: None,
            cache_age_hours: None,
            cache_expires_in_hours: None,
        };
        if let Some(meta) = self.read_meta().await {
            let age = cache_age_secs(&meta);
            status.cached_at = Some(meta.cached_at);
            status.reaction_count = Some(meta.reaction_count);
            status.cache_age_hours = Some(age / 3600.0);
            status.cache_expires_in_hours =
                Some((self.settings.cache_ttl.as_secs_f64() - age) / 3600.0);
        }
        status
    }
}

/// Map a config source string to a local path if it is not an HTTP(S) URL.
fn local_path_for(source: &str) -> Option<PathBuf> {
    let lower = source.to_ascii_lowercase();
    if lower.starts_with("http://") || lower.starts_with("https://") {
        None
    } else if let Some(rest) = source.strip_prefix("file://") {
        Some(PathBuf::from(rest))
    } else {
        Some(PathBuf::from(source))
    }
}

fn now_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn cache_age_secs(meta: &CacheMeta) -> f64 {
    (now_timestamp() - meta.cached_at).max(0.0)
}

async fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), ConfigError> {
    let tmp = path.with_extension("tmp");
    tokio::fs::write(&tmp, bytes)
        .await
        .map_err(|e| ConfigError::Cache(format!("failed to write {}: {e}", tmp.display())))?;
    tokio::fs::rename(&tmp, path)
        .await
        .map_err(|e| ConfigError::Cache(format!("failed to replace {}: {e}", path.display())))
}

fn describe_reqwest_error(e: &reqwest::Error, timeout: Duration) -> String {
    if e.is_timeout() {
        format!("request timed out after {}s: {e}", timeout.as_secs())
    } else if e.is_connect() {
        format!("connection failed (offline?): {e}")
    } else {
        format!("request failed: {e}")
    }
}

/// Parse a YAML (or JSON) config document and validate its reactions.
///
/// Fails if the document is malformed or contains no usable reactions, so a
/// bad upstream push can never overwrite a good cache.
pub fn parse_config(raw: &str) -> Result<(Vec<Reaction>, Vec<String>), ConfigError> {
    let config: ReactionConfig =
        serde_yaml::from_str(raw).map_err(|e| ConfigError::Parse(format!("invalid YAML: {e}")))?;
    let (reactions, warnings) = sanitize_reactions(config.reaction_images);
    for w in &warnings {
        warn!("Reaction config: {w}");
    }
    if reactions.is_empty() {
        return Err(ConfigError::Parse(
            "config contains no valid reaction_images entries".into(),
        ));
    }
    Ok((reactions, warnings))
}

/// Whether an id is safe to use as a URL path segment and lookup key.
fn is_valid_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 128
        && id
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
        && !id.starts_with('.')
}

/// Validate and normalize reactions.
///
/// - trims ids and drops entries with empty or unsafe ids (they would produce
///   broken image URLs);
/// - de-duplicates ids: a later entry replaces an earlier one in place;
/// - trims tags, drops empty ones, and removes case-insensitive duplicates.
///
/// Returns the cleaned list and human-readable warnings.
pub fn sanitize_reactions(raw: Vec<Reaction>) -> (Vec<Reaction>, Vec<String>) {
    let mut out: Vec<Reaction> = Vec::with_capacity(raw.len());
    let mut positions: HashMap<String, usize> = HashMap::new();
    let mut warnings = Vec::new();

    for (i, mut r) in raw.into_iter().enumerate() {
        r.id = r.id.trim().to_string();
        if !is_valid_id(&r.id) {
            warnings.push(format!(
                "entry #{i} skipped: invalid id {:?} (allowed: A-Z a-z 0-9 _ - .)",
                r.id
            ));
            continue;
        }
        let mut seen = std::collections::HashSet::new();
        r.tags = r
            .tags
            .into_iter()
            .map(|t| t.trim().to_string())
            .filter(|t| !t.is_empty() && seen.insert(t.to_lowercase()))
            .collect();

        if let Some(&pos) = positions.get(&r.id) {
            warnings.push(format!(
                "duplicate id {:?}: entry #{i} replaces the earlier definition",
                r.id
            ));
            out[pos] = r;
        } else {
            positions.insert(r.id.clone(), out.len());
            out.push(r);
        }
    }
    (out, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = r#"
reaction_images:
  - id: "felix"
    description: "Happy, cheerful, or excited expression"
    usage_scenarios: ["Celebrating something pleasant"]
    tags: ["happy", "Happy", " excited ", ""]
  - id: "confused"
    description: "Confused expression"
    tags: ["confused"]
"#;

    fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "mcp_reaction_search_test_{name}_{}_{}",
            std::process::id(),
            now_timestamp() as u64
        ));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn settings(url: &str, cache_dir: PathBuf) -> ConfigSettings {
        ConfigSettings {
            config_url: url.to_string(),
            cache_dir,
            cache_ttl: DEFAULT_CACHE_TTL,
            fetch_timeout: Duration::from_millis(500),
        }
    }

    #[test]
    fn parse_config_normalizes_tags() {
        let (reactions, warnings) = parse_config(SAMPLE).unwrap();
        assert_eq!(reactions.len(), 2);
        assert_eq!(reactions[0].tags, vec!["happy", "excited"]);
        assert!(warnings.is_empty());
    }

    #[test]
    fn parse_config_rejects_empty_and_malformed() {
        assert!(matches!(
            parse_config("reaction_images: []"),
            Err(ConfigError::Parse(_))
        ));
        assert!(matches!(
            parse_config("reaction_images: [: bad"),
            Err(ConfigError::Parse(_))
        ));
    }

    #[test]
    fn sanitize_drops_invalid_ids_and_dedupes_last_wins() {
        use crate::types::reaction;
        let raw = vec![
            reaction("a", "first", &[], &[]),
            reaction("", "empty", &[], &[]),
            reaction("../etc/passwd", "traversal", &[], &[]),
            reaction("b", "b", &[], &[]),
            reaction(" a ", "second", &[], &[]),
        ];
        let (out, warnings) = sanitize_reactions(raw);
        let ids: Vec<&str> = out.iter().map(|r| r.id.as_str()).collect();
        assert_eq!(ids, vec!["a", "b"]);
        assert_eq!(out[0].description, "second");
        assert_eq!(warnings.len(), 3);
    }

    #[test]
    fn local_path_detection() {
        assert!(local_path_for("https://example.com/x.yaml").is_none());
        assert!(local_path_for("HTTP://example.com/x.yaml").is_none());
        assert_eq!(
            local_path_for("file:///tmp/x.yaml"),
            Some(PathBuf::from("/tmp/x.yaml"))
        );
        assert_eq!(local_path_for("./x.yaml"), Some(PathBuf::from("./x.yaml")));
    }

    #[tokio::test]
    async fn local_file_source_loads_without_cache() {
        let dir = temp_dir("local");
        let path = dir.join("config.yaml");
        std::fs::write(&path, SAMPLE).unwrap();
        let loader = ConfigLoader::new(settings(path.to_str().unwrap(), dir.join("cache")));
        let loaded = loader.load().await.unwrap();
        assert_eq!(loaded.source, ConfigSource::LocalFile);
        assert_eq!(loaded.reactions.len(), 2);
        assert!(!dir.join("cache").join(CACHE_FILE).exists());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[tokio::test]
    async fn fresh_cache_is_used_and_stale_cache_is_offline_fallback() {
        let dir = temp_dir("cache");
        // Unroutable source: fetches fail fast (connection refused on port 9).
        let url = "http://127.0.0.1:9/config.yaml";
        let loader = ConfigLoader::new(settings(url, dir.clone()));

        // No cache and no network: clear error naming the fetch failure.
        let err = loader.load().await.unwrap_err();
        assert!(matches!(err, ConfigError::NoConfig(_)), "{err}");

        // Seed a fresh cache.
        let (reactions, _) = parse_config(SAMPLE).unwrap();
        loader.save_to_cache(&reactions).await.unwrap();
        assert!(loader.is_cache_valid().await);
        let loaded = loader.load().await.unwrap();
        assert_eq!(loaded.source, ConfigSource::Cache);

        // A failed refresh must not destroy the cache.
        assert!(loader.refresh().await.is_err());
        assert!(dir.join(CACHE_FILE).exists());

        // Expire the cache: load falls back to it after the fetch fails.
        let stale = CacheMeta {
            cached_at: now_timestamp() - DEFAULT_CACHE_TTL.as_secs_f64() - 60.0,
            source_url: url.to_string(),
            reaction_count: reactions.len(),
        };
        std::fs::write(
            dir.join(CACHE_META_FILE),
            serde_json::to_string(&stale).unwrap(),
        )
        .unwrap();
        assert!(!loader.is_cache_valid().await);
        let loaded = loader.load().await.unwrap();
        assert_eq!(loaded.source, ConfigSource::StaleCache);
        assert_eq!(loaded.reactions.len(), 2);

        let info = loader.cache_info().await;
        assert!(info.cache_file_exists);
        assert!(!info.cache_valid);
        assert!(info.cache_expires_in_hours.unwrap() < 0.0);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[tokio::test]
    async fn cache_for_different_source_is_not_fresh() {
        let dir = temp_dir("source");
        let a = ConfigLoader::new(settings("http://127.0.0.1:9/a.yaml", dir.clone()));
        let (reactions, _) = parse_config(SAMPLE).unwrap();
        a.save_to_cache(&reactions).await.unwrap();
        assert!(a.is_cache_valid().await);
        let b = ConfigLoader::new(settings("http://127.0.0.1:9/b.yaml", dir.clone()));
        assert!(!b.is_cache_valid().await);
        let _ = std::fs::remove_dir_all(&dir);
    }
}
