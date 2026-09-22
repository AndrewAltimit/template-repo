//! In-memory [`VectorStore`] used by the unit tests.
//!
//! Mirrors the ChromaDB semantics the service relies on: collections are
//! created on upsert only, reads of missing collections are empty, upserts
//! overwrite by id, the embedding dimension is fixed by the first write, and
//! query distances are cosine distances.

use async_trait::async_trait;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};

use super::{CollectionInfo, Filter, Hit, Item, Metadata, StoreError, UpsertBatch, VectorStore};

#[derive(Default)]
struct Collection {
    metadata: Metadata,
    dim: Option<usize>,
    /// id -> (embedding, document, metadata); BTreeMap for stable ordering.
    records: BTreeMap<String, (Vec<f32>, String, Metadata)>,
}

/// Thread-safe in-memory vector store.
#[derive(Default)]
pub struct InMemoryStore {
    collections: Mutex<BTreeMap<String, Collection>>,
    offline: AtomicBool,
}

impl InMemoryStore {
    /// Simulate the database going away (every call fails as unavailable).
    pub fn set_offline(&self, offline: bool) {
        self.offline.store(offline, Ordering::SeqCst);
    }

    fn check(&self) -> Result<(), StoreError> {
        if self.offline.load(Ordering::SeqCst) {
            Err(StoreError::Unavailable(
                "connection refused (simulated)".into(),
            ))
        } else {
            Ok(())
        }
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, BTreeMap<String, Collection>> {
        self.collections
            .lock()
            .unwrap_or_else(|poison| poison.into_inner())
    }

    /// Insert a record directly, bypassing the service (simulates legacy data).
    pub fn insert_raw(&self, collection: &str, id: &str, doc: &str, meta: Metadata, emb: Vec<f32>) {
        let mut cols = self.lock();
        let c = cols.entry(collection.to_string()).or_default();
        c.records
            .insert(id.to_string(), (emb, doc.to_string(), meta));
    }

    /// Stored embedding of a record, if any.
    pub fn embedding_of(&self, collection: &str, id: &str) -> Option<Vec<f32>> {
        self.lock()
            .get(collection)
            .and_then(|c| c.records.get(id))
            .map(|r| r.0.clone())
    }
}

fn cosine_distance(a: &[f32], b: &[f32]) -> Option<f64> {
    let dot: f32 = a.iter().zip(b).map(|(x, y)| x * y).sum();
    let na: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if na == 0.0 || nb == 0.0 {
        return None;
    }
    Some(1.0 - f64::from(dot / (na * nb)))
}

#[async_trait]
impl VectorStore for InMemoryStore {
    fn describe(&self) -> Value {
        json!({"provider": "in-memory"})
    }

    async fn heartbeat(&self) -> Result<Option<String>, StoreError> {
        self.check()?;
        Ok(Some("test".into()))
    }

    async fn collection_metadata(&self, name: &str) -> Result<Option<Metadata>, StoreError> {
        self.check()?;
        Ok(self.lock().get(name).map(|c| c.metadata.clone()))
    }

    async fn list_collections(&self, prefix: &str) -> Result<Vec<CollectionInfo>, StoreError> {
        self.check()?;
        Ok(self
            .lock()
            .iter()
            .filter(|(n, _)| n.starts_with(prefix))
            .map(|(n, c)| CollectionInfo {
                name: n.clone(),
                metadata: c.metadata.clone(),
            })
            .collect())
    }

    async fn upsert(
        &self,
        collection: &str,
        create_metadata: &Metadata,
        batch: UpsertBatch,
    ) -> Result<(), StoreError> {
        self.check()?;
        let n = batch.len();
        if batch.embeddings.len() != n || batch.documents.len() != n || batch.metadatas.len() != n {
            return Err(StoreError::Api {
                status: 400,
                message: "batch vectors have different lengths".into(),
            });
        }
        let mut cols = self.lock();
        let c = cols
            .entry(collection.to_string())
            .or_insert_with(|| Collection {
                metadata: create_metadata.clone(),
                ..Collection::default()
            });
        for e in &batch.embeddings {
            match c.dim {
                None => c.dim = Some(e.len()),
                Some(d) if d != e.len() => {
                    return Err(StoreError::Api {
                        status: 400,
                        message: format!(
                            "Collection expecting embedding with dimension of {d}, got {}",
                            e.len()
                        ),
                    });
                },
                _ => {},
            }
        }
        for (((id, emb), doc), meta) in batch
            .ids
            .into_iter()
            .zip(batch.embeddings)
            .zip(batch.documents)
            .zip(batch.metadatas)
        {
            c.records.insert(id, (emb, doc, meta));
        }
        Ok(())
    }

    async fn get(
        &self,
        collection: &str,
        ids: Option<Vec<String>>,
        filter: &Filter,
        limit: Option<usize>,
        offset: usize,
    ) -> Result<Vec<Item>, StoreError> {
        self.check()?;
        let cols = self.lock();
        let Some(c) = cols.get(collection) else {
            return Ok(Vec::new());
        };
        Ok(c.records
            .iter()
            .filter(|(id, _)| ids.as_ref().is_none_or(|want| want.contains(id)))
            .filter(|(_, (_, _, m))| filter.matches(m))
            .skip(offset)
            .take(limit.unwrap_or(usize::MAX))
            .map(|(id, (_, doc, meta))| Item {
                id: id.clone(),
                document: Some(doc.clone()),
                metadata: meta.clone(),
            })
            .collect())
    }

    async fn query(
        &self,
        collection: &str,
        embedding: Vec<f32>,
        n_results: usize,
        filter: &Filter,
    ) -> Result<Vec<Hit>, StoreError> {
        self.check()?;
        let cols = self.lock();
        let Some(c) = cols.get(collection) else {
            return Ok(Vec::new());
        };
        let mut hits: Vec<Hit> = c
            .records
            .iter()
            .filter(|(_, (emb, _, m))| !emb.is_empty() && filter.matches(m))
            .map(|(id, (emb, doc, meta))| Hit {
                item: Item {
                    id: id.clone(),
                    document: Some(doc.clone()),
                    metadata: meta.clone(),
                },
                distance: cosine_distance(&embedding, emb),
            })
            .collect();
        hits.sort_by(|a, b| {
            a.distance
                .unwrap_or(f64::MAX)
                .total_cmp(&b.distance.unwrap_or(f64::MAX))
        });
        hits.truncate(n_results);
        Ok(hits)
    }

    async fn delete(&self, collection: &str, ids: Vec<String>) -> Result<(), StoreError> {
        self.check()?;
        if let Some(c) = self.lock().get_mut(collection) {
            for id in ids {
                c.records.remove(&id);
            }
        }
        Ok(())
    }

    async fn count(&self, collection: &str) -> Result<usize, StoreError> {
        self.check()?;
        Ok(self.lock().get(collection).map_or(0, |c| c.records.len()))
    }
}
