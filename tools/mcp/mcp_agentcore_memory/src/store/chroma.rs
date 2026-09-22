//! ChromaDB HTTP implementation of [`VectorStore`].
//!
//! Supports both REST API generations:
//!
//! * **v2** (`/api/v2/tenants/{tenant}/databases/{database}/collections/...`),
//!   served by ChromaDB 0.5.x/0.6.x and the only API in ChromaDB 1.x;
//! * **v1** (`/api/v1/collections/...`) for older 0.4/0.5 servers.
//!
//! The version is detected on first use via the heartbeat endpoints and
//! cached. Collection name to id lookups are cached as well; if a cached id
//! goes stale (collection deleted/recreated behind our back) the entry is
//! dropped and the operation retried once.

use async_trait::async_trait;
use reqwest::{Client, Method, StatusCode, Url};
use serde::Deserialize;
use serde_json::{Value, json};
use std::collections::HashMap;
use tokio::sync::{OnceCell, RwLock};
use tracing::{debug, info};

use super::{CollectionInfo, Filter, Hit, Item, Metadata, StoreError, UpsertBatch, VectorStore};
use crate::config::Config;

/// Maximum characters of an upstream error body echoed back to the caller.
const MAX_ERROR_BODY: usize = 500;
/// Page size used when listing collections.
const LIST_PAGE: usize = 100;
/// Hard cap on collections scanned by `list_collections`.
const LIST_MAX: usize = 10_000;

/// Which ChromaDB REST API generation the server speaks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ApiVersion {
    /// Legacy `/api/v1` API.
    V1,
    /// Tenant/database-scoped `/api/v2` API.
    V2,
}

/// ChromaDB-backed vector store.
pub struct ChromaStore {
    client: Client,
    base: Url,
    tenant: String,
    database: String,
    api: OnceCell<ApiVersion>,
    ids: RwLock<HashMap<String, String>>,
}

#[derive(Debug, Deserialize)]
struct CollectionResponse {
    id: String,
    name: String,
    #[serde(default)]
    metadata: Option<Metadata>,
}

#[derive(Debug, Deserialize)]
struct GetResponse {
    ids: Vec<String>,
    #[serde(default)]
    documents: Option<Vec<Option<String>>>,
    #[serde(default)]
    metadatas: Option<Vec<Option<Metadata>>>,
}

#[derive(Debug, Deserialize)]
struct QueryResponse {
    ids: Vec<Vec<String>>,
    #[serde(default)]
    documents: Option<Vec<Vec<Option<String>>>>,
    #[serde(default)]
    metadatas: Option<Vec<Vec<Option<Metadata>>>>,
    #[serde(default)]
    distances: Option<Vec<Vec<Option<f64>>>>,
}

/// Outcome of a collection-scoped request.
enum Outcome {
    Ok(Value),
    Missing,
}

impl ChromaStore {
    /// Create a store from the configuration. Fails only if the URL is invalid.
    pub fn new(config: &Config) -> Result<Self, String> {
        let base = Url::parse(&config.chroma_url)
            .map_err(|e| format!("invalid ChromaDB URL '{}': {e}", config.chroma_url))?;
        if base.cannot_be_a_base() {
            return Err(format!("invalid ChromaDB URL '{}'", config.chroma_url));
        }
        info!("ChromaDB endpoint: {}", config.chroma_url);
        Ok(Self {
            client: mcp_core::http::build_client_or_default(config.request_timeout),
            base,
            tenant: config.tenant.clone(),
            database: config.database.clone(),
            api: OnceCell::new(),
            ids: RwLock::new(HashMap::new()),
        })
    }

    /// Build a URL from path segments (each segment is percent-encoded).
    fn url(&self, segments: &[&str]) -> Url {
        let mut url = self.base.clone();
        if let Ok(mut path) = url.path_segments_mut() {
            path.pop_if_empty();
            path.extend(segments);
        }
        url
    }

    fn collections_url(&self, api: ApiVersion, extra: &[&str]) -> Url {
        let mut segs: Vec<&str> = match api {
            ApiVersion::V1 => vec!["api", "v1", "collections"],
            ApiVersion::V2 => vec![
                "api",
                "v2",
                "tenants",
                &self.tenant,
                "databases",
                &self.database,
                "collections",
            ],
        };
        segs.extend_from_slice(extra);
        self.url(&segs)
    }

    /// Detect (once) which API generation the server speaks.
    async fn api(&self) -> Result<ApiVersion, StoreError> {
        self.api
            .get_or_try_init(|| async {
                let v2 = self.url(&["api", "v2", "heartbeat"]);
                let resp = self.client.get(v2).send().await.map_err(unavailable)?;
                if resp.status().is_success() {
                    debug!("ChromaDB speaks API v2");
                    return Ok(ApiVersion::V2);
                }
                let v1 = self.url(&["api", "v1", "heartbeat"]);
                let resp = self.client.get(v1).send().await.map_err(unavailable)?;
                if resp.status().is_success() {
                    debug!("ChromaDB speaks API v1");
                    return Ok(ApiVersion::V1);
                }
                Err(api_error(resp).await)
            })
            .await
            .copied()
    }

    /// Send a request and decode the JSON body, mapping HTTP errors.
    async fn send(
        &self,
        method: Method,
        url: Url,
        body: Option<&Value>,
    ) -> Result<Outcome, StoreError> {
        let mut req = self.client.request(method, url);
        if let Some(b) = body {
            req = req.json(b);
        }
        let resp = req.send().await.map_err(unavailable)?;
        if resp.status().is_success() {
            let text = resp.text().await.map_err(unavailable)?;
            if text.trim().is_empty() {
                return Ok(Outcome::Ok(Value::Null));
            }
            return serde_json::from_str(&text)
                .map(Outcome::Ok)
                .map_err(|e| StoreError::Protocol(format!("invalid JSON: {e}")));
        }
        let err = api_error(resp).await;
        if is_missing_collection(&err) {
            return Ok(Outcome::Missing);
        }
        Err(err)
    }

    /// Resolve a collection name to its id, optionally creating it.
    async fn resolve(
        &self,
        name: &str,
        create: Option<&Metadata>,
    ) -> Result<Option<String>, StoreError> {
        if let Some(id) = self.ids.read().await.get(name) {
            return Ok(Some(id.clone()));
        }
        let api = self.api().await?;
        let collection = match create {
            Some(meta) => {
                let mut body = json!({"name": name, "get_or_create": true});
                if !meta.is_empty() {
                    body["metadata"] = Value::Object(meta.clone());
                }
                let url = self.collections_url(api, &[]);
                match self.send(Method::POST, url, Some(&body)).await? {
                    Outcome::Ok(v) => Some(v),
                    Outcome::Missing => {
                        return Err(StoreError::Protocol(format!(
                            "ChromaDB reported collection '{name}' missing while creating it"
                        )));
                    },
                }
            },
            None => match self
                .send(Method::GET, self.collections_url(api, &[name]), None)
                .await?
            {
                Outcome::Ok(v) => Some(v),
                Outcome::Missing => None,
            },
        };
        let Some(value) = collection else {
            return Ok(None);
        };
        let parsed: CollectionResponse = serde_json::from_value(value)
            .map_err(|e| StoreError::Protocol(format!("collection response: {e}")))?;
        self.ids
            .write()
            .await
            .insert(name.to_string(), parsed.id.clone());
        Ok(Some(parsed.id))
    }

    /// Run `POST|GET collections/{id}/{op}`, retrying once on a stale id.
    /// Returns `None` if the collection does not exist and `create` is `None`.
    async fn collection_op(
        &self,
        name: &str,
        create: Option<&Metadata>,
        method: Method,
        op: &str,
        body: Option<&Value>,
    ) -> Result<Option<Value>, StoreError> {
        let api = self.api().await?;
        for attempt in 0..2 {
            let Some(id) = self.resolve(name, create).await? else {
                return Ok(None);
            };
            let url = self.collections_url(api, &[&id, op]);
            match self.send(method.clone(), url, body).await? {
                Outcome::Ok(v) => return Ok(Some(v)),
                Outcome::Missing => {
                    debug!("collection '{name}' id {id} is stale (attempt {attempt})");
                    self.ids.write().await.remove(name);
                },
            }
        }
        if create.is_some() {
            Err(StoreError::Protocol(format!(
                "collection '{name}' disappeared while writing to it"
            )))
        } else {
            Ok(None)
        }
    }
}

fn unavailable(e: reqwest::Error) -> StoreError {
    let kind = if e.is_timeout() {
        "timed out"
    } else if e.is_connect() {
        "connection failed"
    } else {
        "request failed"
    };
    StoreError::Unavailable(format!("{kind}: {e}"))
}

async fn api_error(resp: reqwest::Response) -> StoreError {
    let status = resp.status();
    let body = resp.text().await.unwrap_or_default();
    StoreError::Api {
        status: status.as_u16(),
        message: truncate(&body, MAX_ERROR_BODY),
    }
}

/// Shorten `s` to at most `max` chars, respecting UTF-8 boundaries.
pub(crate) fn truncate(s: &str, max: usize) -> String {
    let s = s.trim();
    match s.char_indices().nth(max) {
        Some((idx, _)) => format!("{}...", &s[..idx]),
        None => s.to_string(),
    }
}

/// ChromaDB reports a missing collection as 404 (v2) or as a 400/500 whose
/// body says the collection "does not exist" (v1 / 0.5.x).
fn is_missing_collection(err: &StoreError) -> bool {
    match err {
        StoreError::Api { status, message } => {
            let m = message.to_ascii_lowercase();
            *status == StatusCode::NOT_FOUND.as_u16()
                || m.contains("does not exist")
                || m.contains("invalidcollection")
                || m.contains("notfounderror")
        },
        _ => false,
    }
}

/// Convert a flat `get` response into items.
fn items_from_get(v: Value) -> Result<Vec<Item>, StoreError> {
    let r: GetResponse =
        serde_json::from_value(v).map_err(|e| StoreError::Protocol(format!("get: {e}")))?;
    let mut docs = r.documents.unwrap_or_default().into_iter();
    let mut metas = r.metadatas.unwrap_or_default().into_iter();
    Ok(r.ids
        .into_iter()
        .map(|id| Item {
            id,
            document: docs.next().flatten(),
            metadata: metas.next().flatten().unwrap_or_default(),
        })
        .collect())
}

/// Convert a (single-query) `query` response into hits.
fn hits_from_query(v: Value) -> Result<Vec<Hit>, StoreError> {
    let r: QueryResponse =
        serde_json::from_value(v).map_err(|e| StoreError::Protocol(format!("query: {e}")))?;
    fn first<T>(o: Option<Vec<Vec<T>>>) -> Vec<T> {
        o.and_then(|v| v.into_iter().next()).unwrap_or_default()
    }
    let ids = r.ids.into_iter().next().unwrap_or_default();
    let mut docs = first(r.documents).into_iter();
    let mut metas = first(r.metadatas).into_iter();
    let mut dists = first(r.distances).into_iter();
    Ok(ids
        .into_iter()
        .map(|id| Hit {
            item: Item {
                id,
                document: docs.next().flatten(),
                metadata: metas.next().flatten().unwrap_or_default(),
            },
            distance: dists.next().flatten(),
        })
        .collect())
}

#[async_trait]
impl VectorStore for ChromaStore {
    fn describe(&self) -> Value {
        // Never echo credentials embedded in the URL.
        let mut shown = self.base.clone();
        let _ = shown.set_username("");
        let _ = shown.set_password(None);
        json!({
            "provider": "chromadb",
            "url": shown.as_str().trim_end_matches('/'),
            "api_version": self.api.get().map(|v| match v {
                ApiVersion::V1 => "v1",
                ApiVersion::V2 => "v2",
            }),
            "tenant": self.tenant,
            "database": self.database,
        })
    }

    async fn heartbeat(&self) -> Result<Option<String>, StoreError> {
        let api = self.api().await?;
        let prefix = match api {
            ApiVersion::V1 => "v1",
            ApiVersion::V2 => "v2",
        };
        self.send(Method::GET, self.url(&["api", prefix, "heartbeat"]), None)
            .await?;
        let version = match self
            .send(Method::GET, self.url(&["api", prefix, "version"]), None)
            .await
        {
            Ok(Outcome::Ok(Value::String(s))) => Some(s),
            _ => None,
        };
        Ok(version)
    }

    async fn collection_metadata(&self, name: &str) -> Result<Option<Metadata>, StoreError> {
        let api = self.api().await?;
        match self
            .send(Method::GET, self.collections_url(api, &[name]), None)
            .await?
        {
            Outcome::Missing => Ok(None),
            Outcome::Ok(v) => {
                let c: CollectionResponse = serde_json::from_value(v)
                    .map_err(|e| StoreError::Protocol(format!("collection response: {e}")))?;
                self.ids.write().await.insert(c.name, c.id);
                Ok(Some(c.metadata.unwrap_or_default()))
            },
        }
    }

    async fn list_collections(&self, prefix: &str) -> Result<Vec<CollectionInfo>, StoreError> {
        let api = self.api().await?;
        let mut out = Vec::new();
        let mut offset = 0;
        while offset < LIST_MAX {
            let mut url = self.collections_url(api, &[]);
            url.query_pairs_mut()
                .append_pair("limit", &LIST_PAGE.to_string())
                .append_pair("offset", &offset.to_string());
            let page = match self.send(Method::GET, url, None).await? {
                Outcome::Ok(v) => serde_json::from_value::<Vec<CollectionResponse>>(v)
                    .map_err(|e| StoreError::Protocol(format!("collection list: {e}")))?,
                Outcome::Missing => Vec::new(),
            };
            let n = page.len();
            let mut ids = self.ids.write().await;
            for c in page {
                if c.name.starts_with(prefix) {
                    ids.insert(c.name.clone(), c.id);
                    out.push(CollectionInfo {
                        name: c.name,
                        metadata: c.metadata.unwrap_or_default(),
                    });
                }
            }
            if n < LIST_PAGE {
                break;
            }
            offset += n;
        }
        Ok(out)
    }

    async fn upsert(
        &self,
        collection: &str,
        create_metadata: &Metadata,
        batch: UpsertBatch,
    ) -> Result<(), StoreError> {
        if batch.is_empty() {
            return Ok(());
        }
        let body = json!({
            "ids": batch.ids,
            "embeddings": batch.embeddings,
            "documents": batch.documents,
            "metadatas": batch.metadatas,
        });
        self.collection_op(
            collection,
            Some(create_metadata),
            Method::POST,
            "upsert",
            Some(&body),
        )
        .await?;
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
        let mut body = json!({"include": ["documents", "metadatas"], "offset": offset});
        if let Some(ids) = ids {
            body["ids"] = json!(ids);
        }
        if let Some(w) = filter.to_chroma() {
            body["where"] = w;
        }
        if let Some(l) = limit {
            body["limit"] = json!(l);
        }
        match self
            .collection_op(collection, None, Method::POST, "get", Some(&body))
            .await?
        {
            Some(v) => items_from_get(v),
            None => Ok(Vec::new()),
        }
    }

    async fn query(
        &self,
        collection: &str,
        embedding: Vec<f32>,
        n_results: usize,
        filter: &Filter,
    ) -> Result<Vec<Hit>, StoreError> {
        let mut body = json!({
            "query_embeddings": [embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        });
        if let Some(w) = filter.to_chroma() {
            body["where"] = w;
        }
        match self
            .collection_op(collection, None, Method::POST, "query", Some(&body))
            .await?
        {
            Some(v) => hits_from_query(v),
            None => Ok(Vec::new()),
        }
    }

    async fn delete(&self, collection: &str, ids: Vec<String>) -> Result<(), StoreError> {
        if ids.is_empty() {
            return Ok(());
        }
        let body = json!({ "ids": ids });
        self.collection_op(collection, None, Method::POST, "delete", Some(&body))
            .await?;
        Ok(())
    }

    async fn count(&self, collection: &str) -> Result<usize, StoreError> {
        match self
            .collection_op(collection, None, Method::GET, "count", None)
            .await?
        {
            Some(v) => v
                .as_u64()
                .map(|n| n as usize)
                .ok_or_else(|| StoreError::Protocol(format!("count: expected integer, got {v}"))),
            None => Ok(0),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn store(url: &str) -> ChromaStore {
        let config = Config {
            chroma_url: url.to_string(),
            tenant: "my tenant".into(),
            ..Config::default()
        };
        ChromaStore::new(&config).unwrap()
    }

    #[test]
    fn builds_v1_and_v2_urls() {
        let s = store("http://chroma:8000");
        assert_eq!(
            s.collections_url(ApiVersion::V1, &["abc", "get"]).as_str(),
            "http://chroma:8000/api/v1/collections/abc/get"
        );
        assert_eq!(
            s.collections_url(ApiVersion::V2, &["abc", "query"])
                .as_str(),
            "http://chroma:8000/api/v2/tenants/my%20tenant/databases/default_database/collections/abc/query"
        );
    }

    #[test]
    fn preserves_base_path() {
        let s = store("http://proxy/chroma/");
        assert_eq!(
            s.url(&["api", "v2", "heartbeat"]).as_str(),
            "http://proxy/chroma/api/v2/heartbeat"
        );
    }

    #[test]
    fn describe_hides_credentials() {
        let d = store("http://user:hunter2@chroma:8000").describe();
        assert_eq!(d["url"], "http://chroma:8000");
        assert!(!d.to_string().contains("hunter2"));
    }

    #[test]
    fn rejects_invalid_url() {
        let config = Config {
            chroma_url: "not a url".into(),
            ..Config::default()
        };
        assert!(ChromaStore::new(&config).is_err());
    }

    #[test]
    fn missing_collection_detection() {
        let e = |status, m: &str| StoreError::Api {
            status,
            message: m.into(),
        };
        assert!(is_missing_collection(&e(404, "")));
        assert!(is_missing_collection(&e(
            400,
            r#"{"error":"InvalidCollection","message":"Collection x does not exist."}"#
        )));
        assert!(is_missing_collection(&e(
            500,
            "Collection foo does not exist."
        )));
        assert!(!is_missing_collection(&e(400, "dimension mismatch")));
        assert!(!is_missing_collection(&StoreError::Unavailable("x".into())));
    }

    #[test]
    fn parses_get_response_with_nulls() {
        let v = json!({
            "ids": ["a", "b"],
            "documents": ["doc a", null],
            "metadatas": [{"k": 1}, null],
            "embeddings": null
        });
        let items = items_from_get(v).unwrap();
        assert_eq!(items.len(), 2);
        assert_eq!(items[0].document.as_deref(), Some("doc a"));
        assert_eq!(items[0].metadata["k"], 1);
        assert_eq!(items[1].document, None);
        assert!(items[1].metadata.is_empty());
    }

    #[test]
    fn parses_get_response_without_optional_fields() {
        let items = items_from_get(json!({"ids": ["a"]})).unwrap();
        assert_eq!(items[0].document, None);
    }

    #[test]
    fn parses_query_response() {
        let v = json!({
            "ids": [["b", "a"]],
            "documents": [["x", "hello"]],
            "metadatas": [[{"n": 1}, {"n": 2}]],
            "distances": [[0.0, 0.25]],
        });
        let hits = hits_from_query(v).unwrap();
        assert_eq!(hits.len(), 2);
        assert_eq!(hits[1].item.id, "a");
        assert_eq!(hits[1].distance, Some(0.25));
        assert_eq!(hits[1].item.metadata["n"], 2);
    }

    #[test]
    fn parses_empty_query_response() {
        let hits = hits_from_query(json!({"ids": [[]], "distances": [[]]})).unwrap();
        assert!(hits.is_empty());
        let hits = hits_from_query(json!({"ids": []})).unwrap();
        assert!(hits.is_empty());
    }

    #[test]
    fn rejects_malformed_response() {
        assert!(matches!(
            items_from_get(json!({"nope": 1})),
            Err(StoreError::Protocol(_))
        ));
    }

    #[test]
    fn truncate_respects_char_boundaries() {
        assert_eq!(truncate("abc", 5), "abc");
        assert_eq!(truncate("abcdef", 3), "abc...");
        assert_eq!(
            truncate("\u{00e9}\u{00e9}\u{00e9}", 2),
            "\u{00e9}\u{00e9}..."
        );
    }

    #[tokio::test]
    async fn unreachable_server_is_unavailable_error() {
        // Port 9 (discard) on localhost is essentially never listening.
        let config = Config {
            chroma_url: "http://127.0.0.1:9".into(),
            request_timeout: std::time::Duration::from_secs(2),
            ..Config::default()
        };
        let s = ChromaStore::new(&config).unwrap();
        match s.heartbeat().await {
            Err(StoreError::Unavailable(_)) => {},
            other => panic!("expected Unavailable, got {other:?}"),
        }
        // The failed detection must not be cached.
        assert!(s.api.get().is_none());
    }
}
