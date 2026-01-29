//! Local memory cache for frequently accessed memories

use serde_json::Value;
use std::collections::HashMap;
use std::time::{Duration, Instant};

/// A cache entry with expiration tracking
#[derive(Clone)]
struct CacheEntry {
    results: Vec<Value>,
    timestamp: Instant,
    namespace: String,
}

/// LRU cache for frequently accessed memories
pub struct MemoryCache {
    max_size: usize,
    ttl: Duration,
    cache: HashMap<String, CacheEntry>,
}

impl MemoryCache {
    /// Create a new cache
    ///
    /// # Arguments
    /// * `max_size` - Maximum number of cache entries
    /// * `ttl_seconds` - Time-to-live in seconds
    pub fn new(max_size: usize, ttl_seconds: u64) -> Self {
        Self {
            max_size,
            ttl: Duration::from_secs(ttl_seconds),
            cache: HashMap::new(),
        }
    }

    /// Create a cache key from query and namespace
    fn make_key(query: &str, namespace: &str) -> String {
        let data = format!("{}:{}", query, namespace);
        format!("{:x}", md5::compute(data.as_bytes()))
    }

    /// Get cached results for a query (updates access time for LRU behavior)
    pub fn get(&mut self, query: &str, namespace: &str) -> Option<Vec<Value>> {
        let key = Self::make_key(query, namespace);

        if let Some(entry) = self.cache.get_mut(&key) {
            if entry.timestamp.elapsed() < self.ttl {
                // Update timestamp for true LRU behavior
                entry.timestamp = Instant::now();
                tracing::debug!("Cache hit for query in namespace {}", namespace);
                return Some(entry.results.clone());
            }
            tracing::debug!("Cache expired for query in namespace {}", namespace);
        }

        None
    }

    /// Cache results for a query
    pub fn set(&mut self, query: &str, namespace: &str, results: Vec<Value>) {
        let key = Self::make_key(query, namespace);

        // Evict oldest if at capacity
        if self.cache.len() >= self.max_size
            && !self.cache.contains_key(&key)
            && let Some(oldest_key) = self
                .cache
                .iter()
                .min_by_key(|(_, entry)| entry.timestamp)
                .map(|(k, _)| k.clone())
        {
            self.cache.remove(&oldest_key);
            tracing::debug!("Evicted oldest cache entry due to size limit");
        }

        self.cache.insert(
            key,
            CacheEntry {
                results,
                timestamp: Instant::now(),
                namespace: namespace.to_string(),
            },
        );
    }

    /// Invalidate cache entries
    ///
    /// # Arguments
    /// * `namespace` - If provided, only invalidate entries for this namespace.
    ///   If None, clears entire cache.
    pub fn invalidate(&mut self, namespace: Option<&str>) -> usize {
        match namespace {
            None => {
                let count = self.cache.len();
                self.cache.clear();
                tracing::debug!("Invalidated entire cache ({} entries)", count);
                count
            }
            Some(ns) => {
                let keys_to_remove: Vec<String> = self
                    .cache
                    .iter()
                    .filter(|(_, entry)| {
                        entry.namespace == ns || entry.namespace.starts_with(&format!("{}/", ns))
                    })
                    .map(|(k, _)| k.clone())
                    .collect();

                let count = keys_to_remove.len();
                for key in keys_to_remove {
                    self.cache.remove(&key);
                }

                if count > 0 {
                    tracing::debug!("Invalidated {} cache entries for namespace {}", count, ns);
                }
                count
            }
        }
    }

    /// Remove all expired entries
    #[allow(dead_code)]
    pub fn cleanup_expired(&mut self) -> usize {
        let now = Instant::now();
        let expired_keys: Vec<String> = self
            .cache
            .iter()
            .filter(|(_, entry)| now.duration_since(entry.timestamp) >= self.ttl)
            .map(|(k, _)| k.clone())
            .collect();

        let count = expired_keys.len();
        for key in expired_keys {
            self.cache.remove(&key);
        }

        if count > 0 {
            tracing::debug!("Cleaned up {} expired cache entries", count);
        }
        count
    }

    /// Get cache statistics
    pub fn get_stats(&self) -> HashMap<String, Value> {
        let now = Instant::now();
        let expired_count = self
            .cache
            .values()
            .filter(|entry| now.duration_since(entry.timestamp) >= self.ttl)
            .count();

        // Count entries by namespace category
        let mut namespace_counts: HashMap<String, usize> = HashMap::new();
        for entry in self.cache.values() {
            let category = entry
                .namespace
                .split('/')
                .next()
                .unwrap_or(&entry.namespace)
                .to_string();
            *namespace_counts.entry(category).or_insert(0) += 1;
        }

        let mut stats = HashMap::new();
        stats.insert("size".to_string(), serde_json::json!(self.cache.len()));
        stats.insert("max_size".to_string(), serde_json::json!(self.max_size));
        stats.insert(
            "ttl_seconds".to_string(),
            serde_json::json!(self.ttl.as_secs()),
        );
        stats.insert(
            "expired_entries".to_string(),
            serde_json::json!(expired_count),
        );
        stats.insert(
            "active_entries".to_string(),
            serde_json::json!(self.cache.len() - expired_count),
        );
        stats.insert(
            "by_namespace_category".to_string(),
            serde_json::json!(namespace_counts),
        );
        stats
    }
}

impl Default for MemoryCache {
    fn default() -> Self {
        Self::new(1000, 300) // 1000 entries, 5 minute TTL
    }
}
