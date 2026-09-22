//! Runtime configuration, read from environment variables.
//!
//! Every setting has a safe default so the server starts with no environment
//! at all (pointing at a ChromaDB on `localhost:8000`). Invalid values are
//! logged and replaced by the default rather than aborting startup, because an
//! MCP server that dies on launch is much harder to diagnose from an agent
//! client than one that reports a clear error from `memory_status`.

use std::path::PathBuf;
use std::time::Duration;

use tracing::warn;

/// Which embedding backend turns text into vectors.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EmbedderKind {
    /// Local ONNX sentence-transformer (all-MiniLM-L6-v2). Real semantic search.
    FastEmbed,
    /// Deterministic feature-hashing of words and character trigrams. Lexical
    /// similarity only, but needs no model download.
    Hash,
}

impl EmbedderKind {
    /// Parse a user-supplied embedder name (case-insensitive).
    pub fn parse(s: &str) -> Option<Self> {
        match s.trim().to_ascii_lowercase().as_str() {
            "fastembed" | "minilm" | "all-minilm-l6-v2" | "onnx" => Some(Self::FastEmbed),
            "hash" | "hashing" | "lexical" => Some(Self::Hash),
            _ => None,
        }
    }

    /// The embedder used when `MEMORY_EMBEDDER` is unset.
    pub fn default_kind() -> Self {
        if cfg!(feature = "fastembed") {
            Self::FastEmbed
        } else {
            Self::Hash
        }
    }
}

/// Server configuration.
#[derive(Debug, Clone)]
pub struct Config {
    /// Base URL of the ChromaDB server, without a trailing slash.
    pub chroma_url: String,
    /// ChromaDB tenant (v2 API only).
    pub tenant: String,
    /// ChromaDB database (v2 API only).
    pub database: String,
    /// Prefix for every collection this server creates.
    pub collection_prefix: String,
    /// Total timeout for a single ChromaDB request.
    pub request_timeout: Duration,
    /// Search-result cache capacity (entries). 0 disables the cache.
    pub cache_max_entries: usize,
    /// Search-result cache time-to-live. Zero disables the cache.
    pub cache_ttl: Duration,
    /// Embedding backend.
    pub embedder: EmbedderKind,
    /// Where the fastembed model files are cached.
    pub model_cache_dir: PathBuf,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            chroma_url: "http://localhost:8000".to_string(),
            tenant: "default_tenant".to_string(),
            database: "default_database".to_string(),
            collection_prefix: "agent_memory".to_string(),
            request_timeout: Duration::from_secs(30),
            cache_max_entries: 1000,
            cache_ttl: Duration::from_secs(300),
            embedder: EmbedderKind::default_kind(),
            model_cache_dir: default_model_cache_dir(),
        }
    }
}

impl Config {
    /// Build the configuration from the process environment.
    pub fn from_env() -> Self {
        Self::from_lookup(|k| std::env::var(k).ok())
    }

    /// Build the configuration from an arbitrary key lookup (testable).
    pub fn from_lookup(get: impl Fn(&str) -> Option<String>) -> Self {
        let d = Self::default();
        let non_empty = |k: &str| {
            get(k)
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty())
        };

        let chroma_url = match non_empty("CHROMADB_URL") {
            Some(url) => normalize_url(&url),
            None => {
                let host = non_empty("CHROMADB_HOST").unwrap_or_else(|| "localhost".to_string());
                let port = parse_or(&non_empty("CHROMADB_PORT"), "CHROMADB_PORT", 8000u16);
                normalize_url(&format!("{host}:{port}"))
            },
        };

        let collection_prefix = match non_empty("CHROMADB_COLLECTION") {
            Some(p) if is_valid_prefix(&p) => p,
            Some(p) => {
                warn!(
                    "CHROMADB_COLLECTION='{p}' is invalid (use 1-40 chars of [A-Za-z0-9_-], \
                     starting with a letter or digit); using '{}'",
                    d.collection_prefix
                );
                d.collection_prefix.clone()
            },
            None => d.collection_prefix.clone(),
        };

        let embedder = match non_empty("MEMORY_EMBEDDER") {
            Some(v) => match EmbedderKind::parse(&v) {
                Some(EmbedderKind::FastEmbed) if !cfg!(feature = "fastembed") => {
                    warn!(
                        "MEMORY_EMBEDDER=fastembed but this binary was built without the \
                         'fastembed' feature; falling back to 'hash'"
                    );
                    EmbedderKind::Hash
                },
                Some(k) => k,
                None => {
                    warn!("Unknown MEMORY_EMBEDDER='{v}' (expected fastembed|hash); using default");
                    d.embedder
                },
            },
            None => d.embedder,
        };

        let model_cache_dir = non_empty("MEMORY_MODEL_CACHE_DIR")
            .or_else(|| non_empty("FASTEMBED_CACHE_DIR"))
            .map(PathBuf::from)
            .unwrap_or_else(|| d.model_cache_dir.clone());

        Self {
            chroma_url,
            tenant: non_empty("CHROMADB_TENANT").unwrap_or(d.tenant),
            database: non_empty("CHROMADB_DATABASE").unwrap_or(d.database),
            collection_prefix,
            request_timeout: Duration::from_secs(
                parse_or(
                    &non_empty("CHROMADB_TIMEOUT_SECS"),
                    "CHROMADB_TIMEOUT_SECS",
                    d.request_timeout.as_secs(),
                )
                .clamp(1, 600),
            ),
            cache_max_entries: parse_or(
                &non_empty("MEMORY_CACHE_MAX_ENTRIES"),
                "MEMORY_CACHE_MAX_ENTRIES",
                d.cache_max_entries,
            ),
            cache_ttl: Duration::from_secs(parse_or(
                &non_empty("MEMORY_CACHE_TTL_SECS"),
                "MEMORY_CACHE_TTL_SECS",
                d.cache_ttl.as_secs(),
            )),
            embedder,
            model_cache_dir,
        }
    }
}

/// Parse `value` or warn and fall back to `default`.
fn parse_or<T: std::str::FromStr + Copy>(value: &Option<String>, key: &str, default: T) -> T {
    match value {
        None => default,
        Some(v) => v.parse().unwrap_or_else(|_| {
            warn!("Ignoring invalid {key}='{v}'");
            default
        }),
    }
}

/// Ensure a scheme is present and strip trailing slashes.
fn normalize_url(raw: &str) -> String {
    let with_scheme = if raw.starts_with("http://") || raw.starts_with("https://") {
        raw.to_string()
    } else {
        format!("http://{raw}")
    };
    with_scheme.trim_end_matches('/').to_string()
}

/// Collection prefixes end up inside ChromaDB collection names, which must be
/// 3-63 chars of `[A-Za-z0-9._-]` starting and ending with an alphanumeric.
/// The longest suffix we append is `_rec_` + 16 hex chars (21 chars).
fn is_valid_prefix(p: &str) -> bool {
    (1..=40).contains(&p.len())
        && p.chars().next().is_some_and(|c| c.is_ascii_alphanumeric())
        && p.chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
}

/// `$XDG_CACHE_HOME` or `$HOME/.cache` (or the temp dir), plus our subdir.
fn default_model_cache_dir() -> PathBuf {
    let base = std::env::var_os("XDG_CACHE_HOME")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("HOME")
                .or_else(|| std::env::var_os("USERPROFILE"))
                .map(|h| PathBuf::from(h).join(".cache"))
        })
        .unwrap_or_else(std::env::temp_dir);
    base.join("mcp-agentcore-memory").join("models")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn cfg(pairs: &[(&str, &str)]) -> Config {
        let map: HashMap<String, String> = pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        Config::from_lookup(|k| map.get(k).cloned())
    }

    #[test]
    fn defaults_when_env_empty() {
        let c = cfg(&[]);
        assert_eq!(c.chroma_url, "http://localhost:8000");
        assert_eq!(c.collection_prefix, "agent_memory");
        assert_eq!(c.tenant, "default_tenant");
        assert_eq!(c.cache_ttl, Duration::from_secs(300));
    }

    #[test]
    fn host_and_port() {
        let c = cfg(&[("CHROMADB_HOST", "chromadb"), ("CHROMADB_PORT", "9000")]);
        assert_eq!(c.chroma_url, "http://chromadb:9000");
    }

    #[test]
    fn url_takes_precedence_and_is_normalized() {
        let c = cfg(&[
            ("CHROMADB_URL", "https://db.example:8443/"),
            ("CHROMADB_HOST", "ignored"),
        ]);
        assert_eq!(c.chroma_url, "https://db.example:8443");
    }

    #[test]
    fn invalid_values_fall_back() {
        let c = cfg(&[
            ("CHROMADB_PORT", "not-a-port"),
            ("CHROMADB_COLLECTION", "bad name!"),
            ("MEMORY_CACHE_TTL_SECS", "-5"),
            ("MEMORY_EMBEDDER", "nonsense"),
        ]);
        assert_eq!(c.chroma_url, "http://localhost:8000");
        assert_eq!(c.collection_prefix, "agent_memory");
        assert_eq!(c.cache_ttl, Duration::from_secs(300));
        assert_eq!(c.embedder, EmbedderKind::default_kind());
    }

    #[test]
    fn embedder_selection() {
        assert_eq!(
            cfg(&[("MEMORY_EMBEDDER", "HASH")]).embedder,
            EmbedderKind::Hash
        );
    }

    #[test]
    fn timeout_is_clamped() {
        let c = cfg(&[("CHROMADB_TIMEOUT_SECS", "0")]);
        assert_eq!(c.request_timeout, Duration::from_secs(1));
    }

    #[test]
    fn prefix_validation() {
        assert!(is_valid_prefix("agent_memory"));
        assert!(is_valid_prefix("team-a"));
        assert!(!is_valid_prefix("_leading"));
        assert!(!is_valid_prefix("has space"));
        assert!(!is_valid_prefix(&"x".repeat(41)));
    }
}
