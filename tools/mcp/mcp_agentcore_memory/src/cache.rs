//! In-process LRU + TTL cache for `search_memories` results.
//!
//! The key is `(namespace, top_k, query)`, so asking for more results than a
//! cached call returned is a miss rather than a silently truncated hit. Writes
//! and deletes through this server invalidate the affected namespace; writes by
//! *other* processes sharing the same ChromaDB are only picked up once the TTL
//! expires (default 5 minutes, `MEMORY_CACHE_TTL_SECS=0` disables caching).

use serde_json::{Value, json};
use std::collections::HashMap;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct CacheKey {
    namespace: String,
    top_k: u32,
    query: String,
}

#[derive(Clone)]
struct CacheEntry {
    results: Vec<Value>,
    inserted: Instant,
    last_used: Instant,
}

/// Bounded search-result cache.
pub struct MemoryCache {
    max_size: usize,
    ttl: Duration,
    entries: HashMap<CacheKey, CacheEntry>,
    hits: u64,
    misses: u64,
}

impl MemoryCache {
    /// Create a cache holding at most `max_size` entries for `ttl` each.
    /// Either value being zero disables caching.
    pub fn new(max_size: usize, ttl: Duration) -> Self {
        Self {
            max_size,
            ttl,
            entries: HashMap::new(),
            hits: 0,
            misses: 0,
        }
    }

    /// Whether the cache stores anything at all.
    pub fn enabled(&self) -> bool {
        self.max_size > 0 && !self.ttl.is_zero()
    }

    fn key(query: &str, namespace: &str, top_k: u32) -> CacheKey {
        CacheKey {
            namespace: namespace.to_string(),
            top_k,
            query: query.to_string(),
        }
    }

    /// Look up cached results. Expiry is measured from insertion (a hit does
    /// not extend the TTL, so hot entries still refresh periodically); a hit
    /// refreshes the LRU position.
    pub fn get(&mut self, query: &str, namespace: &str, top_k: u32) -> Option<Vec<Value>> {
        if !self.enabled() {
            return None;
        }
        let key = Self::key(query, namespace, top_k);
        let ttl = self.ttl;
        match self.entries.get_mut(&key) {
            Some(entry) if entry.inserted.elapsed() < ttl => {
                entry.last_used = Instant::now();
                self.hits += 1;
                Some(entry.results.clone())
            },
            Some(_) => {
                self.entries.remove(&key);
                self.misses += 1;
                None
            },
            None => {
                self.misses += 1;
                None
            },
        }
    }

    /// Store results, evicting expired entries and then the least recently
    /// used one if the cache is full.
    pub fn set(&mut self, query: &str, namespace: &str, top_k: u32, results: Vec<Value>) {
        if !self.enabled() {
            return;
        }
        let key = Self::key(query, namespace, top_k);
        if self.entries.len() >= self.max_size && !self.entries.contains_key(&key) {
            self.cleanup_expired();
            if self.entries.len() >= self.max_size
                && let Some(oldest) = self
                    .entries
                    .iter()
                    .min_by_key(|(_, e)| e.last_used)
                    .map(|(k, _)| k.clone())
            {
                self.entries.remove(&oldest);
            }
        }
        let now = Instant::now();
        self.entries.insert(
            key,
            CacheEntry {
                results,
                inserted: now,
                last_used: now,
            },
        );
    }

    /// Drop entries for exactly `namespace` (not its children: each namespace
    /// is a separate collection, so writing to `a/b` cannot change `a`), or
    /// everything when `namespace` is `None`. Returns the number removed.
    pub fn invalidate(&mut self, namespace: Option<&str>) -> usize {
        let before = self.entries.len();
        match namespace {
            None => self.entries.clear(),
            Some(ns) => self.entries.retain(|k, _| k.namespace != ns),
        }
        before - self.entries.len()
    }

    /// Remove expired entries, returning how many were dropped.
    pub fn cleanup_expired(&mut self) -> usize {
        let ttl = self.ttl;
        let before = self.entries.len();
        self.entries.retain(|_, e| e.inserted.elapsed() < ttl);
        before - self.entries.len()
    }

    /// Statistics for `memory_status`.
    pub fn stats(&self) -> Value {
        let expired = self
            .entries
            .values()
            .filter(|e| e.inserted.elapsed() >= self.ttl)
            .count();
        let mut by_category: HashMap<&str, usize> = HashMap::new();
        for key in self.entries.keys() {
            let category = key.namespace.split('/').next().unwrap_or(&key.namespace);
            *by_category.entry(category).or_insert(0) += 1;
        }
        json!({
            "enabled": self.enabled(),
            "size": self.entries.len(),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl.as_secs(),
            "expired_entries": expired,
            "active_entries": self.entries.len() - expired,
            "hits": self.hits,
            "misses": self.misses,
            "by_namespace_category": by_category,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vals(n: usize) -> Vec<Value> {
        (0..n).map(|i| json!(i)).collect()
    }

    #[test]
    fn hit_and_miss() {
        let mut c = MemoryCache::new(10, Duration::from_secs(60));
        assert!(c.get("q", "ns", 5).is_none());
        c.set("q", "ns", 5, vals(2));
        assert_eq!(c.get("q", "ns", 5).unwrap().len(), 2);
        assert_eq!(c.stats()["hits"], 1);
        assert_eq!(c.stats()["misses"], 1);
    }

    #[test]
    fn top_k_is_part_of_key() {
        let mut c = MemoryCache::new(10, Duration::from_secs(60));
        c.set("q", "ns", 2, vals(2));
        assert!(c.get("q", "ns", 10).is_none());
    }

    #[test]
    fn no_key_collision_on_separator() {
        let mut c = MemoryCache::new(10, Duration::from_secs(60));
        c.set("a:b", "c", 5, vals(1));
        assert!(c.get("a", "b:c", 5).is_none());
    }

    #[test]
    fn expiry() {
        let mut c = MemoryCache::new(10, Duration::from_millis(1));
        c.set("q", "ns", 5, vals(1));
        std::thread::sleep(Duration::from_millis(5));
        assert!(c.get("q", "ns", 5).is_none());
        assert_eq!(c.stats()["size"], 0, "expired entry removed on access");
    }

    #[test]
    fn lru_eviction() {
        let mut c = MemoryCache::new(2, Duration::from_secs(60));
        c.set("a", "ns", 5, vals(1));
        std::thread::sleep(Duration::from_millis(2));
        c.set("b", "ns", 5, vals(1));
        std::thread::sleep(Duration::from_millis(2));
        // Touch "a" so "b" becomes least recently used.
        assert!(c.get("a", "ns", 5).is_some());
        c.set("c", "ns", 5, vals(1));
        assert!(c.get("a", "ns", 5).is_some());
        assert!(c.get("b", "ns", 5).is_none());
        assert!(c.get("c", "ns", 5).is_some());
    }

    #[test]
    fn invalidate_exact_namespace_only() {
        let mut c = MemoryCache::new(10, Duration::from_secs(60));
        c.set("q", "codebase", 5, vals(1));
        c.set("q", "codebase/patterns", 5, vals(1));
        assert_eq!(c.invalidate(Some("codebase/patterns")), 1);
        assert!(c.get("q", "codebase", 5).is_some());
        assert_eq!(c.invalidate(None), 1);
    }

    #[test]
    fn disabled_cache_stores_nothing() {
        let mut c = MemoryCache::new(10, Duration::ZERO);
        c.set("q", "ns", 5, vals(1));
        assert!(c.get("q", "ns", 5).is_none());
        assert_eq!(c.stats()["enabled"], false);
        let mut c = MemoryCache::new(0, Duration::from_secs(1));
        c.set("q", "ns", 5, vals(1));
        assert!(c.get("q", "ns", 5).is_none());
    }
}
