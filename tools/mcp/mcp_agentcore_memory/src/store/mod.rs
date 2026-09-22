//! Vector-store abstraction.
//!
//! [`VectorStore`] is the narrow set of operations the memory service needs,
//! keyed by collection *name*. [`chroma::ChromaStore`] implements it over the
//! ChromaDB HTTP API; tests use the in-memory implementation in
//! [`memory::InMemoryStore`] so the whole tool surface can be exercised
//! without a database.

pub mod chroma;
#[cfg(test)]
pub mod memory;

use async_trait::async_trait;
use serde_json::{Map, Value, json};

/// Flat metadata map (ChromaDB accepts string/number/bool values only).
pub type Metadata = Map<String, Value>;

/// A stored document.
#[derive(Debug, Clone, PartialEq)]
pub struct Item {
    /// Record id.
    pub id: String,
    /// Document text (may be absent for records written by other tools).
    pub document: Option<String>,
    /// Record metadata.
    pub metadata: Metadata,
}

/// A similarity-search hit.
#[derive(Debug, Clone, PartialEq)]
pub struct Hit {
    /// The matching record.
    pub item: Item,
    /// Cosine distance (0 = identical), if the store reported one.
    pub distance: Option<f64>,
}

/// A collection and its metadata.
#[derive(Debug, Clone, PartialEq)]
pub struct CollectionInfo {
    /// Collection name.
    pub name: String,
    /// Collection metadata.
    pub metadata: Metadata,
}

/// Records to insert or overwrite (parallel vectors, equal length).
#[derive(Debug, Clone, Default)]
pub struct UpsertBatch {
    /// Record ids (unique within the batch).
    pub ids: Vec<String>,
    /// One embedding per record.
    pub embeddings: Vec<Vec<f32>>,
    /// One document per record.
    pub documents: Vec<String>,
    /// One metadata map per record.
    pub metadatas: Vec<Metadata>,
}

impl UpsertBatch {
    /// Number of records.
    #[cfg(test)]
    pub fn len(&self) -> usize {
        self.ids.len()
    }

    /// True when the batch holds no records.
    pub fn is_empty(&self) -> bool {
        self.ids.is_empty()
    }
}

/// Metadata filter: a conjunction of equality tests.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Filter(pub Vec<(String, Value)>);

impl Filter {
    /// Add an equality condition.
    pub fn eq(mut self, key: &str, value: impl Into<Value>) -> Self {
        self.0.push((key.to_string(), value.into()));
        self
    }

    /// ChromaDB `where` clause, or `None` for an empty filter.
    pub fn to_chroma(&self) -> Option<Value> {
        let clauses: Vec<Value> = self
            .0
            .iter()
            .map(|(k, v)| json!({ k: { "$eq": v } }))
            .collect();
        match clauses.len() {
            0 => None,
            1 => clauses.into_iter().next(),
            _ => Some(json!({ "$and": clauses })),
        }
    }

    /// Evaluate the filter against metadata (used by the in-memory store).
    #[cfg(test)]
    pub fn matches(&self, meta: &Metadata) -> bool {
        self.0.iter().all(|(k, v)| meta.get(k) == Some(v))
    }
}

/// Errors from a vector store.
#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    /// The store could not be reached (connection refused, timeout, ...).
    #[error("cannot reach vector store: {0}")]
    Unavailable(String),
    /// The store answered with an error.
    #[error("vector store error ({status}): {message}")]
    Api {
        /// HTTP status code.
        status: u16,
        /// Error detail (truncated).
        message: String,
    },
    /// The store answered with something we could not parse.
    #[error("unexpected vector store response: {0}")]
    Protocol(String),
}

/// The operations the memory service needs from a vector database.
///
/// Read operations on a collection that does not exist return empty results
/// instead of creating it; only [`VectorStore::upsert`] creates collections.
#[async_trait]
pub trait VectorStore: Send + Sync {
    /// Short description for status output (e.g. provider, URL, API version).
    fn describe(&self) -> Value;

    /// Check connectivity, returning a server version string if known.
    async fn heartbeat(&self) -> Result<Option<String>, StoreError>;

    /// Metadata of a collection, or `None` if it does not exist.
    async fn collection_metadata(&self, name: &str) -> Result<Option<Metadata>, StoreError>;

    /// All collections whose name starts with `prefix`.
    async fn list_collections(&self, prefix: &str) -> Result<Vec<CollectionInfo>, StoreError>;

    /// Insert or overwrite records, creating the collection (with
    /// `create_metadata`) if needed.
    async fn upsert(
        &self,
        collection: &str,
        create_metadata: &Metadata,
        batch: UpsertBatch,
    ) -> Result<(), StoreError>;

    /// Fetch records by id and/or filter, with pagination. Order is unspecified.
    async fn get(
        &self,
        collection: &str,
        ids: Option<Vec<String>>,
        filter: &Filter,
        limit: Option<usize>,
        offset: usize,
    ) -> Result<Vec<Item>, StoreError>;

    /// Nearest-neighbour search, best match first.
    async fn query(
        &self,
        collection: &str,
        embedding: Vec<f32>,
        n_results: usize,
        filter: &Filter,
    ) -> Result<Vec<Hit>, StoreError>;

    /// Delete records by id (unknown ids are ignored).
    async fn delete(&self, collection: &str, ids: Vec<String>) -> Result<(), StoreError>;

    /// Number of records in a collection (0 if it does not exist).
    async fn count(&self, collection: &str) -> Result<usize, StoreError>;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn filter_to_chroma() {
        assert_eq!(Filter::default().to_chroma(), None);
        assert_eq!(
            Filter::default().eq("a", "x").to_chroma(),
            Some(json!({"a": {"$eq": "x"}}))
        );
        assert_eq!(
            Filter::default().eq("a", "x").eq("b", 2).to_chroma(),
            Some(json!({"$and": [{"a": {"$eq": "x"}}, {"b": {"$eq": 2}}]}))
        );
    }

    #[test]
    fn filter_matches() {
        let mut m = Metadata::new();
        m.insert("a".into(), json!("x"));
        assert!(Filter::default().eq("a", "x").matches(&m));
        assert!(!Filter::default().eq("a", "y").matches(&m));
        assert!(Filter::default().matches(&m));
    }
}
