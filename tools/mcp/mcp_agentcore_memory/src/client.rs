//! ChromaDB HTTP client

use crate::sanitize::sanitize_content;
use crate::types::{BatchResult, ChromaDBConfig, MemoryEvent, MemoryRecord, chromadb_api::*};
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};

/// ChromaDB HTTP client
pub struct ChromaDBClient {
    client: Client,
    config: ChromaDBConfig,
    /// Cached collection IDs: collection_name -> collection_id
    collection_cache: Arc<RwLock<HashMap<String, String>>>,
}

impl ChromaDBClient {
    /// Create a new ChromaDB client
    pub fn new(config: ChromaDBConfig) -> Self {
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");

        info!(
            "ChromaDB client configured: {}:{}",
            config.host, config.port
        );

        Self {
            client,
            config,
            collection_cache: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Get the base URL for the ChromaDB API
    fn base_url(&self) -> String {
        self.config.base_url()
    }

    /// Get or create a collection, returning the collection ID
    async fn get_or_create_collection(&self, name: &str) -> Result<String, String> {
        // Check cache first
        {
            let cache = self.collection_cache.read().await;
            if let Some(id) = cache.get(name) {
                return Ok(id.clone());
            }
        }

        let url = format!("{}/api/v1/collections", self.base_url());
        let request = CreateCollectionRequest {
            name: name.to_string(),
            metadata: Some(HashMap::from([(
                "hnsw:space".to_string(),
                "cosine".to_string(),
            )])),
            get_or_create: true,
        };

        let response = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| format!("Failed to create collection: {}", e))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(format!(
                "Failed to create collection: {} - {}",
                status, body
            ));
        }

        let collection: CollectionResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse collection response: {}", e))?;

        // Cache the collection ID
        {
            let mut cache = self.collection_cache.write().await;
            cache.insert(name.to_string(), collection.id.clone());
        }

        debug!("Got collection '{}' with ID: {}", name, collection.id);
        Ok(collection.id)
    }

    /// Get the events collection name
    fn events_collection_name(&self) -> String {
        format!("{}_events", self.config.collection_prefix)
    }

    /// Get the records collection name for a namespace
    /// ChromaDB collection names must be 3-63 characters, alphanumeric with underscores/hyphens
    fn records_collection_name(&self, namespace: &str) -> String {
        // Replace any non-alphanumeric characters (except underscore) with underscore
        let safe_name: String = namespace
            .chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || c == '_' {
                    c
                } else {
                    '_'
                }
            })
            .collect();
        let full_name = format!("{}_records_{}", self.config.collection_prefix, safe_name);
        // Truncate to 63 characters if needed (ChromaDB limit)
        if full_name.len() > 63 {
            full_name[..63].to_string()
        } else {
            full_name
        }
    }

    /// Store a short-term memory event
    pub async fn store_event(
        &self,
        actor_id: &str,
        session_id: &str,
        content: &str,
        metadata: Option<HashMap<String, Value>>,
    ) -> Result<MemoryEvent, String> {
        let collection_name = self.events_collection_name();
        let collection_id = self.get_or_create_collection(&collection_name).await?;

        let event_id = uuid::Uuid::new_v4().to_string();
        let timestamp = Utc::now();
        let sanitized_content = sanitize_content(content);

        let mut meta: HashMap<String, Value> = HashMap::new();
        meta.insert("actor_id".to_string(), json!(actor_id));
        meta.insert("session_id".to_string(), json!(session_id));
        meta.insert("timestamp".to_string(), json!(timestamp.to_rfc3339()));
        if let Some(extra) = metadata.clone() {
            meta.extend(extra);
        }

        let url = format!(
            "{}/api/v1/collections/{}/add",
            self.base_url(),
            collection_id
        );
        let request = AddDocumentsRequest {
            ids: vec![event_id.clone()],
            documents: vec![sanitized_content.clone()],
            metadatas: Some(vec![meta]),
        };

        let response = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| format!("Failed to store event: {}", e))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(format!("Failed to store event: {} - {}", status, body));
        }

        debug!(
            "Stored event {} for actor={} session={}",
            event_id, actor_id, session_id
        );

        Ok(MemoryEvent {
            id: event_id,
            actor_id: actor_id.to_string(),
            session_id: session_id.to_string(),
            content: sanitized_content,
            timestamp,
            metadata: metadata.unwrap_or_default(),
        })
    }

    /// List events from a session
    pub async fn list_events(
        &self,
        actor_id: &str,
        session_id: &str,
        limit: u32,
    ) -> Result<Vec<MemoryEvent>, String> {
        let collection_name = self.events_collection_name();
        let collection_id = self.get_or_create_collection(&collection_name).await?;

        let url = format!(
            "{}/api/v1/collections/{}/get",
            self.base_url(),
            collection_id
        );
        // Don't limit at database level - ChromaDB get doesn't guarantee order,
        // so we need to fetch all matching events, sort by timestamp, then apply limit.
        // Use a large buffer (10000) to prevent unbounded memory usage while still
        // capturing typical session histories. Sessions larger than this may miss
        // some recent events - this is an acceptable tradeoff vs unbounded fetches.
        let fetch_limit = std::cmp::max(limit, 10000);
        let request = GetRequest {
            ids: None,
            limit: Some(fetch_limit),
            where_filter: Some(json!({
                "$and": [
                    {"actor_id": {"$eq": actor_id}},
                    {"session_id": {"$eq": session_id}}
                ]
            })),
            include: Some(vec!["documents".to_string(), "metadatas".to_string()]),
        };

        let response = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| format!("Failed to list events: {}", e))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(format!("Failed to list events: {} - {}", status, body));
        }

        let result: GetResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse events response: {}", e))?;

        let mut events: Vec<MemoryEvent> = Vec::new();
        for (i, id) in result.ids.iter().enumerate() {
            let doc = result
                .documents
                .as_ref()
                .and_then(|d| d.get(i))
                .cloned()
                .unwrap_or_default();
            let meta = result
                .metadatas
                .as_ref()
                .and_then(|m| m.get(i))
                .cloned()
                .unwrap_or_default();

            let timestamp = meta
                .get("timestamp")
                .and_then(|t| t.as_str())
                .and_then(|t| DateTime::parse_from_rfc3339(t).ok())
                .map(|dt| dt.with_timezone(&Utc))
                .unwrap_or_else(Utc::now);

            events.push(MemoryEvent {
                id: id.clone(),
                actor_id: meta
                    .get("actor_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or(actor_id)
                    .to_string(),
                session_id: meta
                    .get("session_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or(session_id)
                    .to_string(),
                content: doc,
                timestamp,
                metadata: meta
                    .into_iter()
                    .filter(|(k, _)| !["actor_id", "session_id", "timestamp"].contains(&k.as_str()))
                    .collect(),
            });
        }

        // Sort by timestamp descending and apply limit after sorting
        events.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
        events.truncate(limit as usize);
        Ok(events)
    }

    /// Store long-term memory records
    pub async fn store_records(
        &self,
        records: Vec<(String, Option<HashMap<String, Value>>)>,
        namespace: &str,
    ) -> Result<BatchResult, String> {
        if records.is_empty() {
            return Ok(BatchResult::success(0));
        }

        let collection_name = self.records_collection_name(namespace);
        let collection_id = self.get_or_create_collection(&collection_name).await?;

        let mut ids = Vec::new();
        let mut documents = Vec::new();
        let mut metadatas = Vec::new();

        for (content, extra_meta) in &records {
            let id = uuid::Uuid::new_v4().to_string();
            let sanitized = sanitize_content(content);

            let mut meta: HashMap<String, Value> = HashMap::new();
            meta.insert("namespace".to_string(), json!(namespace));
            meta.insert("created_at".to_string(), json!(Utc::now().to_rfc3339()));
            if let Some(extra) = extra_meta {
                meta.extend(extra.clone());
            }

            ids.push(id);
            documents.push(sanitized);
            metadatas.push(meta);
        }

        let url = format!(
            "{}/api/v1/collections/{}/add",
            self.base_url(),
            collection_id
        );
        let request = AddDocumentsRequest {
            ids,
            documents,
            metadatas: Some(metadatas),
        };

        let response = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| format!("Failed to store records: {}", e))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            error!("Failed to store records: {} - {}", status, body);
            return Ok(BatchResult::failure(records.len(), body));
        }

        debug!(
            "Stored {} records in namespace {}",
            records.len(),
            namespace
        );
        Ok(BatchResult::success(records.len()))
    }

    /// Search records with semantic similarity
    pub async fn search_records(
        &self,
        query: &str,
        namespace: &str,
        top_k: u32,
    ) -> Result<Vec<MemoryRecord>, String> {
        let collection_name = self.records_collection_name(namespace);
        let collection_id = self.get_or_create_collection(&collection_name).await?;

        let url = format!(
            "{}/api/v1/collections/{}/query",
            self.base_url(),
            collection_id
        );
        let request = QueryRequest {
            query_texts: vec![query.to_string()],
            n_results: top_k,
            include: Some(vec![
                "documents".to_string(),
                "metadatas".to_string(),
                "distances".to_string(),
            ]),
        };

        let response = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| format!("Failed to search records: {}", e))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(format!("Failed to search records: {} - {}", status, body));
        }

        let result: QueryResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse search response: {}", e))?;

        let mut records = Vec::new();
        if !result.ids.is_empty() && !result.ids[0].is_empty() {
            for (i, id) in result.ids[0].iter().enumerate() {
                let doc = result
                    .documents
                    .as_ref()
                    .and_then(|d| d.first())
                    .and_then(|d| d.get(i))
                    .cloned()
                    .unwrap_or_default();
                let meta = result
                    .metadatas
                    .as_ref()
                    .and_then(|m| m.first())
                    .and_then(|m| m.get(i))
                    .cloned()
                    .unwrap_or_default();
                let distance = result
                    .distances
                    .as_ref()
                    .and_then(|d| d.first())
                    .and_then(|d| d.get(i))
                    .copied()
                    .unwrap_or(0.0);

                // Convert distance to similarity (cosine: 1 - distance)
                let relevance = 1.0 - distance;

                let created_at = meta
                    .get("created_at")
                    .and_then(|t| t.as_str())
                    .and_then(|t| DateTime::parse_from_rfc3339(t).ok())
                    .map(|dt| dt.with_timezone(&Utc));

                records.push(MemoryRecord {
                    id: id.clone(),
                    content: doc,
                    namespace: namespace.to_string(),
                    relevance: Some(relevance),
                    created_at,
                    metadata: meta
                        .into_iter()
                        .filter(|(k, _)| !["namespace", "created_at"].contains(&k.as_str()))
                        .collect(),
                });
            }
        }

        Ok(records)
    }

    /// List records in a namespace (no search)
    #[allow(dead_code)]
    pub async fn list_records(
        &self,
        namespace: &str,
        limit: u32,
    ) -> Result<Vec<MemoryRecord>, String> {
        let collection_name = self.records_collection_name(namespace);
        let collection_id = self.get_or_create_collection(&collection_name).await?;

        let url = format!(
            "{}/api/v1/collections/{}/get",
            self.base_url(),
            collection_id
        );
        let request = GetRequest {
            ids: None,
            limit: Some(limit),
            where_filter: None,
            include: Some(vec!["documents".to_string(), "metadatas".to_string()]),
        };

        let response = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| format!("Failed to list records: {}", e))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(format!("Failed to list records: {} - {}", status, body));
        }

        let result: GetResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse records response: {}", e))?;

        let mut records = Vec::new();
        for (i, id) in result.ids.iter().enumerate() {
            let doc = result
                .documents
                .as_ref()
                .and_then(|d| d.get(i))
                .cloned()
                .unwrap_or_default();
            let meta = result
                .metadatas
                .as_ref()
                .and_then(|m| m.get(i))
                .cloned()
                .unwrap_or_default();

            let created_at = meta
                .get("created_at")
                .and_then(|t| t.as_str())
                .and_then(|t| DateTime::parse_from_rfc3339(t).ok())
                .map(|dt| dt.with_timezone(&Utc));

            records.push(MemoryRecord {
                id: id.clone(),
                content: doc,
                namespace: namespace.to_string(),
                relevance: None,
                created_at,
                metadata: meta,
            });
        }

        Ok(records)
    }

    /// Check if ChromaDB is healthy
    pub async fn health_check(&self) -> bool {
        let url = format!("{}/api/v1/heartbeat", self.base_url());

        match self.client.get(&url).send().await {
            Ok(response) => {
                if response.status().is_success() {
                    true
                } else {
                    warn!("ChromaDB health check failed: {}", response.status());
                    false
                }
            }
            Err(e) => {
                warn!("ChromaDB health check error: {}", e);
                false
            }
        }
    }

    /// Get provider info
    pub fn get_info(&self) -> HashMap<String, Value> {
        let mut info = HashMap::new();
        info.insert("provider".to_string(), json!("chromadb"));
        info.insert("host".to_string(), json!(self.config.host));
        info.insert("port".to_string(), json!(self.config.port));
        info.insert(
            "collection_prefix".to_string(),
            json!(self.config.collection_prefix),
        );
        info.insert("rate_limit".to_string(), json!(null));
        info.insert("semantic_search".to_string(), json!(true));
        info.insert("managed_service".to_string(), json!(false));
        info
    }
}
