//! Memory service: the logic behind every MCP tool.
//!
//! Responsibilities: input validation, secret sanitization, embedding,
//! collection naming, fact deduplication, search caching and translating
//! store results into tool responses. The vector store and embedder are
//! injected as trait objects so the full behaviour is unit-testable offline.
//!
//! ## Storage layout (compatible with earlier releases)
//!
//! * Session events: one collection `{prefix}_events`; each event carries
//!   `actor_id`, `session_id`, `timestamp` (RFC 3339) and `timestamp_ms`.
//! * Facts: one collection per namespace, `{prefix}_rec_{h}` where `h` is the
//!   first 8 bytes (16 hex chars) of SHA-256(namespace). Each fact carries
//!   `namespace`, `created_at` and optionally `source`.
//!
//! New collections are created with cosine distance and record the embedder
//! (`embedder`, `embedding_dim`) plus the namespace in their metadata.

use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::{Map, Value, json};
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashSet};
use std::sync::{Arc, Mutex};
use tracing::{debug, warn};

use crate::cache::MemoryCache;
use crate::config::Config;
use crate::embedding::Embedder;
use crate::namespaces::{self, validate_namespace};
use crate::sanitize::sanitize;
use crate::store::{Filter, Item, Metadata, StoreError, UpsertBatch, VectorStore};

/// Maximum size of one event or fact, in bytes.
pub const MAX_CONTENT_BYTES: usize = 32 * 1024;
/// Maximum facts per `store_facts` call.
pub const MAX_FACTS_PER_CALL: usize = 100;
/// Maximum ids per `delete_memories` call.
pub const MAX_IDS_PER_CALL: usize = 100;
/// Upper bound for `search_memories.top_k`.
pub const MAX_TOP_K: u32 = 50;
/// Upper bound for list limits.
pub const MAX_LIST_LIMIT: u32 = 1000;
/// Maximum events scanned when listing a session (they must be sorted
/// client-side because ChromaDB `get` has no ordering).
pub const MAX_EVENT_SCAN: usize = 50_000;
/// Maximum records processed by one `reindex_namespace` call.
pub const MAX_REINDEX: usize = 100_000;
/// Maximum identifier (actor/session/id) length in bytes.
pub const MAX_ID_LEN: usize = 256;
/// Maximum user metadata entries per event.
pub const MAX_METADATA_KEYS: usize = 32;

const PAGE: usize = 1000;
const EMBED_CHUNK: usize = 64;
const EVENT_RESERVED: &[&str] = &["actor_id", "session_id", "timestamp", "timestamp_ms"];
const RECORD_RESERVED: &[&str] = &["namespace", "created_at", "source"];

/// Errors surfaced to tool callers.
#[derive(Debug, thiserror::Error)]
pub enum ServiceError {
    /// Bad caller input.
    #[error("{0}")]
    Invalid(String),
    /// Vector store failure.
    #[error(transparent)]
    Store(#[from] StoreError),
    /// Embedding backend failure.
    #[error("embedding error: {0}")]
    Embedding(String),
    /// Collection was built with a different embedder.
    #[error("{0}")]
    Incompatible(String),
}

impl ServiceError {
    /// Short machine-readable category.
    pub fn kind(&self) -> &'static str {
        match self {
            Self::Invalid(_) => "invalid_input",
            Self::Store(StoreError::Unavailable(_)) => "store_unavailable",
            Self::Store(_) => "store_error",
            Self::Embedding(_) => "embedding_error",
            Self::Incompatible(_) => "incompatible_collection",
        }
    }
}

type SResult<T> = Result<T, ServiceError>;

/// Result of `store_event`.
#[derive(Debug, Serialize)]
pub struct EventStored {
    /// Always true (failures are errors).
    pub success: bool,
    /// New event id.
    pub event_id: String,
    /// Backend name.
    pub provider: &'static str,
    /// Event timestamp (RFC 3339).
    pub timestamp: String,
    /// Whether any secrets were redacted from content or metadata.
    pub redacted: bool,
    /// Which detectors fired.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub redactions: Vec<&'static str>,
    /// User metadata keys dropped because they are reserved.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub ignored_metadata_keys: Vec<String>,
}

/// Result of `store_facts`.
#[derive(Debug, Serialize)]
pub struct FactsStored {
    /// True unless nothing could be stored.
    pub success: bool,
    /// Newly stored facts.
    pub created: usize,
    /// Facts already present in the namespace or repeated within the call.
    pub duplicates: usize,
    /// Kept for backward compatibility (always 0: failures are errors).
    pub failed: usize,
    /// Canonical namespace.
    pub namespace: String,
    /// Record id for each input fact, in input order.
    pub ids: Vec<String>,
    /// Number of facts that had secrets redacted.
    pub redacted: usize,
}

/// The memory service.
pub struct MemoryService {
    store: Arc<dyn VectorStore>,
    embedder: Arc<dyn Embedder>,
    cache: Mutex<MemoryCache>,
    prefix: String,
    /// Collections whose embedder metadata has been checked.
    verified: Mutex<HashSet<String>>,
}

/// Validate a free-text field (non-empty after trim, bounded size).
fn validate_text(field: &str, s: &str) -> SResult<()> {
    if s.trim().is_empty() {
        return Err(ServiceError::Invalid(format!("{field} must not be empty")));
    }
    if s.len() > MAX_CONTENT_BYTES {
        return Err(ServiceError::Invalid(format!(
            "{field} is {} bytes; the maximum is {MAX_CONTENT_BYTES}",
            s.len()
        )));
    }
    Ok(())
}

/// Validate an identifier and return it trimmed.
fn validate_id(field: &str, s: &str) -> SResult<String> {
    let t = s.trim();
    if t.is_empty() {
        return Err(ServiceError::Invalid(format!("{field} must not be empty")));
    }
    if t.len() > MAX_ID_LEN {
        return Err(ServiceError::Invalid(format!(
            "{field} is {} bytes; the maximum is {MAX_ID_LEN}",
            t.len()
        )));
    }
    if t.chars().any(char::is_control) {
        return Err(ServiceError::Invalid(format!(
            "{field} must not contain control characters"
        )));
    }
    Ok(t.to_string())
}

/// ChromaDB metadata values must be scalars: nested values become JSON
/// strings, nulls are dropped, strings are sanitized.
fn flatten_value(value: Value, redactions: &mut BTreeSet<&'static str>) -> Option<Value> {
    let s = match value {
        Value::Null => return None,
        Value::Bool(_) | Value::Number(_) => return Some(value),
        Value::String(s) => s,
        other => other.to_string(),
    };
    let clean = sanitize(&s);
    redactions.extend(clean.detections.iter().copied());
    Some(Value::String(clean.text))
}

fn parse_time(meta: &Metadata, key: &str) -> Option<DateTime<Utc>> {
    meta.get(key)
        .and_then(Value::as_str)
        .and_then(|t| DateTime::parse_from_rfc3339(t).ok())
        .map(|dt| dt.with_timezone(&Utc))
}

fn user_metadata(meta: &Metadata, reserved: &[&str]) -> Map<String, Value> {
    meta.iter()
        .filter(|(k, _)| !reserved.contains(&k.as_str()))
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect()
}

/// Cosine distance to a 0..1-ish relevance score, rounded to 4 places.
fn relevance(distance: Option<f64>) -> Option<f64> {
    distance
        .filter(|d| d.is_finite())
        .map(|d| ((1.0 - d) * 10_000.0).round() / 10_000.0)
}

/// Deterministic fact id: identical text in the same namespace always maps to
/// the same record, which is what makes `store_facts` idempotent.
pub fn fact_id(namespace: &str, content: &str) -> String {
    let digest = Sha256::digest(format!("{namespace}\n{content}").as_bytes());
    let hex: String = digest.iter().take(16).map(|b| format!("{b:02x}")).collect();
    format!("fact-{hex}")
}

impl MemoryService {
    /// Create a service over the given store and embedder.
    pub fn new(config: &Config, store: Arc<dyn VectorStore>, embedder: Arc<dyn Embedder>) -> Self {
        Self {
            store,
            embedder,
            cache: Mutex::new(MemoryCache::new(config.cache_max_entries, config.cache_ttl)),
            prefix: config.collection_prefix.clone(),
            verified: Mutex::new(HashSet::new()),
        }
    }

    fn cache(&self) -> std::sync::MutexGuard<'_, MemoryCache> {
        self.cache.lock().unwrap_or_else(|p| p.into_inner())
    }

    /// Name of the events collection.
    pub fn events_collection(&self) -> String {
        format!("{}_events", self.prefix)
    }

    fn records_prefix(&self) -> String {
        format!("{}_rec_", self.prefix)
    }

    /// Collection name for a namespace (stable across releases).
    pub fn records_collection(&self, namespace: &str) -> String {
        let hash = Sha256::digest(namespace.as_bytes());
        let hex: String = hash.iter().take(8).map(|b| format!("{b:02x}")).collect();
        format!("{}{hex}", self.records_prefix())
    }

    fn collection_metadata(&self, kind: &str, namespace: Option<&str>) -> Metadata {
        let mut m = Metadata::new();
        m.insert("hnsw:space".into(), json!("cosine"));
        m.insert("embedder".into(), json!(self.embedder.id()));
        m.insert("embedding_dim".into(), json!(self.embedder.dimension()));
        m.insert("kind".into(), json!(kind));
        m.insert("created_by".into(), json!("mcp-agentcore-memory"));
        if let Some(ns) = namespace {
            m.insert("namespace".into(), json!(ns));
        }
        m
    }

    /// Refuse to mix embedders within one collection. Legacy collections
    /// without an `embedder` entry are accepted.
    async fn ensure_compatible(&self, collection: &str) -> SResult<()> {
        if self
            .verified
            .lock()
            .unwrap_or_else(|p| p.into_inner())
            .contains(collection)
        {
            return Ok(());
        }
        if let Some(meta) = self.store.collection_metadata(collection).await? {
            if let Some(existing) = meta.get("embedder").and_then(Value::as_str)
                && existing != self.embedder.id()
            {
                return Err(ServiceError::Incompatible(format!(
                    "collection '{collection}' was built with embedder '{existing}' but this \
                     server uses '{}'. Set MEMORY_EMBEDDER to match, or use a different \
                     CHROMADB_COLLECTION prefix for the new embedder.",
                    self.embedder.id()
                )));
            }
            self.verified
                .lock()
                .unwrap_or_else(|p| p.into_inner())
                .insert(collection.to_string());
        }
        Ok(())
    }

    async fn embed(&self, texts: Vec<String>) -> SResult<Vec<Vec<f32>>> {
        let n = texts.len();
        let mut out = Vec::with_capacity(n);
        let mut texts = texts.into_iter().peekable();
        while texts.peek().is_some() {
            let chunk: Vec<String> = texts.by_ref().take(EMBED_CHUNK).collect();
            let vecs = self
                .embedder
                .embed(chunk)
                .await
                .map_err(ServiceError::Embedding)?;
            out.extend(vecs);
        }
        if out.len() != n {
            return Err(ServiceError::Embedding(format!(
                "embedder returned {} vectors for {n} inputs",
                out.len()
            )));
        }
        Ok(out)
    }

    async fn embed_one(&self, text: &str) -> SResult<Vec<f32>> {
        self.embed(vec![text.to_string()])
            .await?
            .pop()
            .ok_or_else(|| ServiceError::Embedding("embedder returned no vector".into()))
    }

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    /// Store a short-term session event.
    pub async fn store_event(
        &self,
        actor_id: &str,
        session_id: &str,
        content: &str,
        metadata: Option<Map<String, Value>>,
    ) -> SResult<EventStored> {
        let actor_id = validate_id("actor_id", actor_id)?;
        let session_id = validate_id("session_id", session_id)?;
        validate_text("content", content)?;
        let metadata = metadata.unwrap_or_default();
        if metadata.len() > MAX_METADATA_KEYS {
            return Err(ServiceError::Invalid(format!(
                "metadata has {} keys; the maximum is {MAX_METADATA_KEYS}",
                metadata.len()
            )));
        }

        let clean = sanitize(content);
        let mut redactions: BTreeSet<&'static str> = clean.detections.clone();
        let mut meta = Metadata::new();
        let mut ignored = Vec::new();
        for (k, v) in metadata {
            if EVENT_RESERVED.contains(&k.as_str()) {
                ignored.push(k);
            } else if k.trim().is_empty() || k.len() > 64 {
                return Err(ServiceError::Invalid(format!(
                    "metadata key {k:?} must be 1-64 bytes"
                )));
            } else if let Some(v) = flatten_value(v, &mut redactions) {
                meta.insert(k, v);
            }
        }
        let timestamp = Utc::now();
        meta.insert("actor_id".into(), json!(actor_id));
        meta.insert("session_id".into(), json!(session_id));
        meta.insert("timestamp".into(), json!(timestamp.to_rfc3339()));
        meta.insert("timestamp_ms".into(), json!(timestamp.timestamp_millis()));

        let collection = self.events_collection();
        self.ensure_compatible(&collection).await?;
        let embedding = self.embed_one(&clean.text).await?;
        let event_id = uuid::Uuid::new_v4().to_string();
        self.store
            .upsert(
                &collection,
                &self.collection_metadata("events", None),
                UpsertBatch {
                    ids: vec![event_id.clone()],
                    embeddings: vec![embedding],
                    documents: vec![clean.text],
                    metadatas: vec![meta],
                },
            )
            .await?;
        debug!("stored event {event_id} actor={actor_id} session={session_id}");

        Ok(EventStored {
            success: true,
            event_id,
            provider: "chromadb",
            timestamp: timestamp.to_rfc3339(),
            redacted: !redactions.is_empty(),
            redactions: redactions.into_iter().collect(),
            ignored_metadata_keys: ignored,
        })
    }

    /// List a session's events, newest first.
    pub async fn list_events(
        &self,
        actor_id: &str,
        session_id: &str,
        limit: u32,
    ) -> SResult<Value> {
        let actor_id = validate_id("actor_id", actor_id)?;
        let session_id = validate_id("session_id", session_id)?;
        if limit == 0 {
            return Err(ServiceError::Invalid("limit must be at least 1".into()));
        }
        let limit = limit.min(MAX_LIST_LIMIT) as usize;
        let filter = Filter::default()
            .eq("actor_id", actor_id.as_str())
            .eq("session_id", session_id.as_str());

        // ChromaDB `get` has no ordering, so scan the session then sort.
        let collection = self.events_collection();
        let mut items: Vec<Item> = Vec::new();
        let mut truncated = false;
        loop {
            let page = self
                .store
                .get(&collection, None, &filter, Some(PAGE), items.len())
                .await?;
            let n = page.len();
            items.extend(page);
            if n < PAGE {
                break;
            }
            if items.len() >= MAX_EVENT_SCAN {
                truncated = true;
                warn!("session {actor_id}/{session_id} has more than {MAX_EVENT_SCAN} events");
                break;
            }
        }
        let total = items.len();

        let mut events: Vec<(Option<DateTime<Utc>>, Value)> = items
            .into_iter()
            .map(|item| {
                let ts = parse_time(&item.metadata, "timestamp");
                let v = json!({
                    "id": item.id,
                    "content": item.document.unwrap_or_default(),
                    "timestamp": ts.map(|t| t.to_rfc3339()),
                    "metadata": user_metadata(&item.metadata, EVENT_RESERVED),
                });
                (ts, v)
            })
            .collect();
        // Newest first; events with unparseable timestamps sort last.
        events.sort_by_key(|e| std::cmp::Reverse(e.0));
        events.truncate(limit);
        let events: Vec<Value> = events.into_iter().map(|(_, v)| v).collect();

        let mut response = json!({
            "actor_id": actor_id,
            "session_id": session_id,
            "count": events.len(),
            "total": total,
            "events": events,
        });
        if truncated {
            response["truncated_scan"] = json!(true);
        }
        Ok(response)
    }

    // -----------------------------------------------------------------------
    // Facts
    // -----------------------------------------------------------------------

    /// Store facts in a namespace. Identical facts are deduplicated.
    pub async fn store_facts(
        &self,
        facts: Vec<String>,
        namespace: &str,
        source: Option<&str>,
    ) -> SResult<FactsStored> {
        let namespace = validate_namespace(namespace).map_err(ServiceError::Invalid)?;
        if facts.is_empty() {
            return Err(ServiceError::Invalid(
                "facts must contain at least one fact".into(),
            ));
        }
        if facts.len() > MAX_FACTS_PER_CALL {
            return Err(ServiceError::Invalid(format!(
                "{} facts given; the maximum per call is {MAX_FACTS_PER_CALL}",
                facts.len()
            )));
        }
        for (i, f) in facts.iter().enumerate() {
            validate_text(&format!("facts[{i}]"), f)?;
        }
        let mut src_redactions = BTreeSet::new();
        let source = match source.map(str::trim).filter(|s| !s.is_empty()) {
            Some(s) if s.len() > MAX_ID_LEN => {
                return Err(ServiceError::Invalid(format!(
                    "source is {} bytes; the maximum is {MAX_ID_LEN}",
                    s.len()
                )));
            },
            Some(s) => flatten_value(json!(s), &mut src_redactions),
            None => None,
        };

        // Sanitize, derive ids, dedupe within the call.
        let mut ids = Vec::with_capacity(facts.len());
        let mut unique: Vec<(String, String)> = Vec::new();
        let mut seen = HashSet::new();
        let mut redacted = 0;
        for fact in &facts {
            let clean = sanitize(fact.trim());
            if clean.redacted() {
                redacted += 1;
            }
            let id = fact_id(&namespace, &clean.text);
            if seen.insert(id.clone()) {
                unique.push((id.clone(), clean.text));
            }
            ids.push(id);
        }

        let collection = self.records_collection(&namespace);
        self.ensure_compatible(&collection).await?;

        // Skip facts that already exist (keeps their original created_at).
        let unique_ids: Vec<String> = unique.iter().map(|(id, _)| id.clone()).collect();
        let existing: HashSet<String> = self
            .store
            .get(&collection, Some(unique_ids), &Filter::default(), None, 0)
            .await?
            .into_iter()
            .map(|i| i.id)
            .collect();
        let new: Vec<(String, String)> = unique
            .into_iter()
            .filter(|(id, _)| !existing.contains(id))
            .collect();

        if !new.is_empty() {
            let embeddings = self
                .embed(new.iter().map(|(_, t)| t.clone()).collect())
                .await?;
            let now = Utc::now().to_rfc3339();
            let mut batch = UpsertBatch::default();
            for ((id, text), emb) in new.iter().cloned().zip(embeddings) {
                let mut meta = Metadata::new();
                meta.insert("namespace".into(), json!(namespace));
                meta.insert("created_at".into(), json!(now));
                if let Some(s) = &source {
                    meta.insert("source".into(), s.clone());
                }
                batch.ids.push(id);
                batch.embeddings.push(emb);
                batch.documents.push(text);
                batch.metadatas.push(meta);
            }
            self.store
                .upsert(
                    &collection,
                    &self.collection_metadata("records", Some(&namespace)),
                    batch,
                )
                .await?;
            self.verified
                .lock()
                .unwrap_or_else(|p| p.into_inner())
                .insert(collection.clone());
        }
        self.cache().invalidate(Some(&namespace));

        Ok(FactsStored {
            success: true,
            created: new.len(),
            duplicates: facts.len() - new.len(),
            failed: 0,
            namespace,
            ids,
            redacted,
        })
    }

    fn record_json(namespace: &str, item: Item, distance: Option<Option<f64>>) -> Value {
        let mut v = json!({
            "id": item.id,
            "content": item.document.unwrap_or_default(),
            "namespace": namespace,
            "created_at": parse_time(&item.metadata, "created_at").map(|t| t.to_rfc3339()),
            "source": item.metadata.get("source").cloned(),
            "metadata": user_metadata(&item.metadata, RECORD_RESERVED),
        });
        if let Some(d) = distance {
            v["relevance"] = json!(relevance(d));
        }
        v
    }

    /// Semantic search within one namespace.
    pub async fn search(
        &self,
        query: &str,
        namespace: &str,
        top_k: u32,
        min_relevance: Option<f64>,
    ) -> SResult<Value> {
        validate_text("query", query)?;
        let namespace = validate_namespace(namespace).map_err(ServiceError::Invalid)?;
        if top_k == 0 {
            return Err(ServiceError::Invalid("top_k must be at least 1".into()));
        }
        let top_k = top_k.min(MAX_TOP_K);
        if let Some(m) = min_relevance
            && !(m.is_finite() && (-1.0..=1.0).contains(&m))
        {
            return Err(ServiceError::Invalid(
                "min_relevance must be between -1.0 and 1.0".into(),
            ));
        }
        let query = query.trim();

        let cached = self.cache().get(query, &namespace, top_k);
        let (memories, was_cached) = match cached {
            Some(m) => (m, true),
            None => {
                let collection = self.records_collection(&namespace);
                self.ensure_compatible(&collection).await?;
                let embedding = self.embed_one(query).await?;
                let hits = self
                    .store
                    .query(&collection, embedding, top_k as usize, &Filter::default())
                    .await?;
                let memories: Vec<Value> = hits
                    .into_iter()
                    .map(|h| Self::record_json(&namespace, h.item, Some(h.distance)))
                    .collect();
                self.cache().set(query, &namespace, top_k, memories.clone());
                (memories, false)
            },
        };

        let memories: Vec<Value> = match min_relevance {
            Some(min) => memories
                .into_iter()
                .filter(|m| m["relevance"].as_f64().is_some_and(|r| r >= min))
                .collect(),
            None => memories,
        };

        Ok(json!({
            "query": query,
            "namespace": namespace,
            "count": memories.len(),
            "cached": was_cached,
            "memories": memories,
        }))
    }

    /// Browse a namespace without a query.
    pub async fn list_memories(&self, namespace: &str, limit: u32, offset: u32) -> SResult<Value> {
        let namespace = validate_namespace(namespace).map_err(ServiceError::Invalid)?;
        if limit == 0 {
            return Err(ServiceError::Invalid("limit must be at least 1".into()));
        }
        let limit = limit.min(MAX_LIST_LIMIT);
        let collection = self.records_collection(&namespace);
        let total = self.store.count(&collection).await?;
        let items = self
            .store
            .get(
                &collection,
                None,
                &Filter::default(),
                Some(limit as usize),
                offset as usize,
            )
            .await?;
        let memories: Vec<Value> = items
            .into_iter()
            .map(|i| Self::record_json(&namespace, i, None))
            .collect();
        Ok(json!({
            "namespace": namespace,
            "total": total,
            "offset": offset,
            "count": memories.len(),
            "memories": memories,
        }))
    }

    /// Delete facts by id from a namespace.
    pub async fn delete_memories(&self, namespace: &str, ids: Vec<String>) -> SResult<Value> {
        let namespace = validate_namespace(namespace).map_err(ServiceError::Invalid)?;
        if ids.is_empty() {
            return Err(ServiceError::Invalid(
                "ids must contain at least one id".into(),
            ));
        }
        if ids.len() > MAX_IDS_PER_CALL {
            return Err(ServiceError::Invalid(format!(
                "{} ids given; the maximum per call is {MAX_IDS_PER_CALL}",
                ids.len()
            )));
        }
        let mut wanted = Vec::new();
        for id in &ids {
            let id = validate_id("id", id)?;
            if !wanted.contains(&id) {
                wanted.push(id);
            }
        }
        let collection = self.records_collection(&namespace);
        let found: HashSet<String> = self
            .store
            .get(
                &collection,
                Some(wanted.clone()),
                &Filter::default(),
                None,
                0,
            )
            .await?
            .into_iter()
            .map(|i| i.id)
            .collect();
        let (deleted, not_found): (Vec<String>, Vec<String>) =
            wanted.into_iter().partition(|id| found.contains(id));
        self.store.delete(&collection, deleted.clone()).await?;
        self.cache().invalidate(Some(&namespace));
        Ok(json!({
            "success": true,
            "namespace": namespace,
            "deleted": deleted,
            "not_found": not_found,
        }))
    }

    /// Recompute embeddings for every fact in a namespace (e.g. facts written
    /// by releases that stored documents without vectors).
    pub async fn reindex_namespace(&self, namespace: &str) -> SResult<Value> {
        let namespace = validate_namespace(namespace).map_err(ServiceError::Invalid)?;
        let collection = self.records_collection(&namespace);
        self.ensure_compatible(&collection).await?;

        let mut items: Vec<Item> = Vec::new();
        loop {
            let page = self
                .store
                .get(
                    &collection,
                    None,
                    &Filter::default(),
                    Some(PAGE),
                    items.len(),
                )
                .await?;
            let n = page.len();
            items.extend(page);
            if n < PAGE || items.len() >= MAX_REINDEX {
                break;
            }
        }
        let scanned = items.len();
        let (with_doc, without_doc): (Vec<Item>, Vec<Item>) =
            items.into_iter().partition(|i| i.document.is_some());

        let create_meta = self.collection_metadata("records", Some(&namespace));
        for chunk in with_doc.chunks(EMBED_CHUNK) {
            let docs: Vec<String> = chunk
                .iter()
                .map(|i| i.document.clone().unwrap_or_default())
                .collect();
            let embeddings = self.embed(docs.clone()).await?;
            let mut batch = UpsertBatch {
                ids: chunk.iter().map(|i| i.id.clone()).collect(),
                embeddings,
                documents: docs,
                metadatas: Vec::with_capacity(chunk.len()),
            };
            for item in chunk {
                let mut meta = item.metadata.clone();
                meta.entry("namespace").or_insert_with(|| json!(namespace));
                batch.metadatas.push(meta);
            }
            self.store.upsert(&collection, &create_meta, batch).await?;
        }
        self.cache().invalidate(Some(&namespace));

        Ok(json!({
            "success": true,
            "namespace": namespace,
            "reindexed": with_doc.len(),
            "skipped_without_document": without_doc.len(),
            "limit_reached": scanned >= MAX_REINDEX,
            "embedder": self.embedder.id(),
        }))
    }

    // -----------------------------------------------------------------------
    // Discovery and status
    // -----------------------------------------------------------------------

    /// Predefined namespaces, optionally plus those that actually hold data.
    pub async fn list_namespaces(&self, include_stored: bool) -> Value {
        let mut response = json!({
            "namespaces": namespaces::predefined_tree(),
            "note": "Use hierarchical namespaces with '/' separator for organization. \
                     Any valid namespace may be used; each is searched independently.",
        });
        if include_stored {
            match self.stored_namespaces().await {
                Ok(stored) => response["stored"] = json!(stored),
                Err(e) => {
                    response["stored"] = Value::Null;
                    response["stored_error"] = json!(e.to_string());
                },
            }
        }
        response
    }

    async fn stored_namespaces(&self) -> SResult<Vec<Value>> {
        let collections = self.store.list_collections(&self.records_prefix()).await?;
        let mut out = Vec::new();
        for c in collections {
            let mut namespace = c
                .metadata
                .get("namespace")
                .and_then(Value::as_str)
                .map(String::from);
            if namespace.is_none() {
                // Legacy collection: read the namespace from a record.
                namespace = self
                    .store
                    .get(&c.name, None, &Filter::default(), Some(1), 0)
                    .await?
                    .into_iter()
                    .next()
                    .and_then(|i| {
                        i.metadata
                            .get("namespace")
                            .and_then(Value::as_str)
                            .map(String::from)
                    });
            }
            let count = self.store.count(&c.name).await?;
            // Only report collections that really belong to the namespace we
            // think they do (guards against foreign collections sharing the
            // prefix).
            let ns_ok = namespace
                .as_deref()
                .is_some_and(|ns| self.records_collection(ns) == c.name);
            out.push(json!({
                "namespace": if ns_ok { namespace.clone() } else { None },
                "collection": c.name,
                "count": count,
                "predefined": namespace.as_deref().is_some_and(namespaces::is_predefined),
                "embedder": c.metadata.get("embedder").cloned(),
            }));
        }
        out.sort_by(|a, b| {
            a["namespace"]
                .as_str()
                .unwrap_or("~")
                .cmp(b["namespace"].as_str().unwrap_or("~"))
        });
        Ok(out)
    }

    /// Connectivity, embedder and cache status.
    pub async fn status(&self) -> Value {
        let (status, version, error) = match self.store.heartbeat().await {
            Ok(v) => ("connected", v, None),
            Err(e) => ("disconnected", None, Some(e.to_string())),
        };
        let mut provider = self.store.describe();
        provider["server_version"] = json!(version);
        provider["collection_prefix"] = json!(self.prefix);
        provider["events_collection"] = json!(self.events_collection());
        provider["semantic_search"] = json!(true);
        provider["managed_service"] = json!(false);
        provider["rate_limit"] = Value::Null;
        let mut response = json!({
            "status": status,
            "provider": provider,
            "embedder": {
                "id": self.embedder.id(),
                "dimension": self.embedder.dimension(),
                "loaded": self.embedder.is_ready(),
            },
            "cache": self.cache().stats(),
        });
        if let Some(e) = error {
            response["error"] = json!(e);
        }
        response
    }

    /// Expose cache-relevant stats keyed by namespace (test helper).
    #[cfg(test)]
    pub fn cache_size(&self) -> usize {
        self.cache().stats()["size"].as_u64().unwrap_or(0) as usize
    }
}

/// Helper used by tests to build metadata maps.
#[cfg(test)]
pub fn meta(pairs: &[(&str, Value)]) -> Metadata {
    pairs
        .iter()
        .map(|(k, v)| (k.to_string(), v.clone()))
        .collect()
}
