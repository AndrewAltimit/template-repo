//! Reaction search service: owns the loaded catalog, the embedding model
//! lifecycle, and the semantic index, and exposes async operations to the
//! MCP tools.
//!
//! Design notes:
//! - State is published as an immutable [`Snapshot`] behind an `Arc`, so a
//!   search only holds a lock long enough to clone the pointer. Refreshes
//!   build a new snapshot off to the side and swap it in; in-flight searches
//!   keep using the old one.
//! - The catalog (config) and the model load independently. Id lookups,
//!   listings, and tag browsing never wait for the model.
//! - The model loads on a blocking thread in the background. A search waits
//!   at most `model_wait` for it and otherwise answers with lexical ranking
//!   (and says so), instead of hanging on a first-time 90 MB download or
//!   failing outright when offline. A failed load is retried after
//!   `model_retry`, or immediately on `refresh_reactions`.
//! - All ONNX work (model load, corpus and query embedding) runs in
//!   `spawn_blocking`, never on the async runtime threads.

use std::collections::HashSet;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::{Value, json};
use tokio::sync::{Mutex, RwLock, watch};
use tracing::{info, warn};

use crate::config::{ConfigLoader, ConfigSettings, ConfigSource};
use crate::embed::{Embedder, FastEmbedder, MODEL_NAME};
use crate::engine::{Catalog, SearchMode, SearchOptions, SemanticIndex, rank};
use crate::types::ReactionResult;

/// Factory that loads the embedding model (blocking).
pub type EmbedderFactory = Arc<dyn Fn() -> Result<Arc<dyn Embedder>, String> + Send + Sync>;

/// Settings for [`ReactionService`].
#[derive(Debug, Clone)]
pub struct ServiceSettings {
    /// Config source and cache settings.
    pub config: ConfigSettings,
    /// Where the ONNX model is cached.
    pub model_cache_dir: PathBuf,
    /// How long a search waits for a loading model before answering
    /// lexically.
    pub model_wait: Duration,
    /// Minimum delay before retrying a failed model load.
    pub model_retry: Duration,
}

impl Default for ServiceSettings {
    fn default() -> Self {
        let config = ConfigSettings::default();
        Self {
            model_cache_dir: config.cache_dir.join("models"),
            config,
            model_wait: Duration::from_secs(30),
            model_retry: Duration::from_secs(300),
        }
    }
}

/// Embedding model lifecycle.
#[derive(Clone)]
enum ModelState {
    Idle,
    Loading {
        since: Instant,
    },
    Ready {
        embedder: Arc<dyn Embedder>,
        load_secs: f64,
    },
    Failed {
        error: String,
        at: Instant,
    },
}

impl ModelState {
    fn label(&self) -> &'static str {
        match self {
            Self::Idle => "not_loaded",
            Self::Loading { .. } => "loading",
            Self::Ready { .. } => "ready",
            Self::Failed { .. } => "failed",
        }
    }
}

/// Immutable view of the loaded data.
struct Snapshot {
    catalog: Arc<Catalog>,
    semantic: Option<Arc<SemanticIndex>>,
    source: ConfigSource,
    loaded_at: DateTime<Utc>,
    warnings: Vec<String>,
}

/// Outcome of a search.
#[derive(Debug, Serialize)]
pub struct SearchOutcome {
    /// How results were ranked.
    pub mode: SearchMode,
    /// Ranked results.
    pub results: Vec<ReactionResult>,
    /// Why the search fell back to lexical ranking, if it did.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
}

/// Outcome of a refresh.
#[derive(Debug, Serialize)]
pub struct RefreshOutcome {
    /// Reactions now loaded.
    pub reaction_count: usize,
    /// Reactions loaded before the refresh.
    pub previous_count: usize,
    /// Ids that are new in this refresh.
    pub added: Vec<String>,
    /// Ids that disappeared in this refresh.
    pub removed: Vec<String>,
    /// Where the data came from.
    pub source: ConfigSource,
    /// Whether the semantic index is ready for the new data.
    pub semantic_ready: bool,
    /// Validation warnings for the new document.
    pub warnings: Vec<String>,
}

/// The reaction search service shared by all tools.
pub struct ReactionService {
    loader: ConfigLoader,
    settings: ServiceSettings,
    factory: EmbedderFactory,
    snapshot: RwLock<Option<Arc<Snapshot>>>,
    /// Serializes config loads and refreshes.
    load_lock: Mutex<()>,
    /// Serializes semantic index builds.
    index_lock: Mutex<()>,
    model: Arc<watch::Sender<ModelState>>,
    index_error: RwLock<Option<String>>,
}

impl ReactionService {
    /// Service using the real fastembed model.
    pub fn new(settings: ServiceSettings) -> Arc<Self> {
        let dir = settings.model_cache_dir.clone();
        let factory: EmbedderFactory = Arc::new(move || {
            FastEmbedder::load(dir.clone()).map(|m| Arc::new(m) as Arc<dyn Embedder>)
        });
        Self::with_embedder_factory(settings, factory)
    }

    /// Service with a custom model factory (used by tests).
    pub fn with_embedder_factory(settings: ServiceSettings, factory: EmbedderFactory) -> Arc<Self> {
        Arc::new(Self {
            loader: ConfigLoader::new(settings.config.clone()),
            settings,
            factory,
            snapshot: RwLock::new(None),
            load_lock: Mutex::new(()),
            index_lock: Mutex::new(()),
            model: Arc::new(watch::channel(ModelState::Idle).0),
            index_error: RwLock::new(None),
        })
    }

    /// Start loading config and model in the background so the first search
    /// is fast. Errors are logged, not fatal: tools retry on demand.
    pub fn preload(self: &Arc<Self>) {
        let this = Arc::clone(self);
        tokio::spawn(async move {
            this.start_model_load();
            match this.snapshot().await {
                Ok(snap) => {
                    let _ = this.semantic_index(Duration::from_secs(3600)).await;
                    info!("Preload complete ({} reactions)", snap.catalog.len());
                },
                Err(e) => warn!("Preload could not load reactions: {e}"),
            }
        });
    }

    /// Current snapshot, loading the config on first use.
    async fn snapshot(&self) -> Result<Arc<Snapshot>, String> {
        if let Some(s) = self.snapshot.read().await.as_ref() {
            return Ok(Arc::clone(s));
        }
        let _guard = self.load_lock.lock().await;
        if let Some(s) = self.snapshot.read().await.as_ref() {
            return Ok(Arc::clone(s));
        }
        let loaded = self.loader.load().await.map_err(|e| e.to_string())?;
        let snap = Arc::new(Snapshot {
            catalog: Arc::new(Catalog::new(loaded.reactions)),
            semantic: None,
            source: loaded.source,
            loaded_at: Utc::now(),
            warnings: loaded.warnings,
        });
        *self.snapshot.write().await = Some(Arc::clone(&snap));
        Ok(snap)
    }

    /// The loaded catalog (loads config on first use; never waits for the
    /// model).
    pub async fn catalog(&self) -> Result<Arc<Catalog>, String> {
        Ok(Arc::clone(&self.snapshot().await?.catalog))
    }

    /// Kick off a background model load if none is loaded, loading, or
    /// recently failed.
    fn start_model_load(&self) {
        let retry = self.settings.model_retry;
        let started = self.model.send_if_modified(|state| {
            let start = match state {
                ModelState::Idle => true,
                ModelState::Failed { at, .. } => at.elapsed() >= retry,
                _ => false,
            };
            if start {
                *state = ModelState::Loading {
                    since: Instant::now(),
                };
            }
            start
        });
        if !started {
            return;
        }
        let factory = Arc::clone(&self.factory);
        let model = Arc::clone(&self.model);
        tokio::spawn(async move {
            let started = Instant::now();
            let result = tokio::task::spawn_blocking(move || factory())
                .await
                .unwrap_or_else(|e| Err(format!("model loader task failed: {e}")));
            let next = match result {
                Ok(embedder) => ModelState::Ready {
                    embedder,
                    load_secs: started.elapsed().as_secs_f64(),
                },
                Err(error) => {
                    warn!("Embedding model unavailable, using lexical search: {error}");
                    ModelState::Failed {
                        error,
                        at: Instant::now(),
                    }
                },
            };
            model.send_replace(next);
        });
    }

    /// Wait up to `wait` for the model; `None` if it is not ready by then.
    async fn embedder(&self, wait: Duration) -> Option<Arc<dyn Embedder>> {
        self.start_model_load();
        let mut rx = self.model.subscribe();
        let _ = tokio::time::timeout(
            wait,
            rx.wait_for(|s| !matches!(s, ModelState::Loading { .. })),
        )
        .await;
        match &*rx.borrow() {
            ModelState::Ready { embedder, .. } => Some(Arc::clone(embedder)),
            _ => None,
        }
    }

    /// Semantic index for the current catalog, building it if needed.
    /// Returns the catalog the index belongs to (a refresh may have swapped
    /// it), or `None` when the model is unavailable or the build failed.
    async fn semantic_index(
        &self,
        wait: Duration,
    ) -> Option<(Arc<Catalog>, Arc<SemanticIndex>, Arc<dyn Embedder>)> {
        let embedder = self.embedder(wait).await?;
        let snap = self.snapshot.read().await.clone()?;
        if let Some(idx) = &snap.semantic {
            return Some((Arc::clone(&snap.catalog), Arc::clone(idx), embedder));
        }

        let _guard = self.index_lock.lock().await;
        // Another task may have built it (or refreshed) while we waited.
        let current = self.snapshot.read().await.clone()?;
        if let Some(idx) = &current.semantic {
            return Some((Arc::clone(&current.catalog), Arc::clone(idx), embedder));
        }

        let idx = self.build_index(&current.catalog, &embedder).await?;
        let mut slot = self.snapshot.write().await;
        if let Some(latest) = slot.as_ref()
            && Arc::ptr_eq(&latest.catalog, &current.catalog)
        {
            *slot = Some(Arc::new(Snapshot {
                catalog: Arc::clone(&latest.catalog),
                semantic: Some(Arc::clone(&idx)),
                source: latest.source,
                loaded_at: latest.loaded_at,
                warnings: latest.warnings.clone(),
            }));
        }
        Some((Arc::clone(&current.catalog), idx, embedder))
    }

    async fn build_index(
        &self,
        catalog: &Arc<Catalog>,
        embedder: &Arc<dyn Embedder>,
    ) -> Option<Arc<SemanticIndex>> {
        let (c, e) = (Arc::clone(catalog), Arc::clone(embedder));
        let started = Instant::now();
        let result = tokio::task::spawn_blocking(move || SemanticIndex::build(&c, e.as_ref()))
            .await
            .map_err(|e| format!("index task failed: {e}"))
            .and_then(|r| r.map_err(|e| e.to_string()));
        match result {
            Ok(idx) => {
                info!(
                    "Semantic index built: {} reactions, {} field texts in {:.2}s",
                    catalog.len(),
                    idx.field_count(),
                    started.elapsed().as_secs_f64()
                );
                *self.index_error.write().await = None;
                Some(Arc::new(idx))
            },
            Err(e) => {
                warn!("Semantic index build failed, using lexical search: {e}");
                *self.index_error.write().await = Some(e);
                None
            },
        }
    }

    /// Search the catalog. Uses semantic ranking when the model is available
    /// and lexical ranking otherwise.
    pub async fn search(&self, query: &str, opts: &SearchOptions) -> Result<SearchOutcome, String> {
        let snap = self.snapshot().await?;
        let mut note = None;

        if let Some((catalog, idx, embedder)) = self.semantic_index(self.settings.model_wait).await
        {
            let q = vec![query.to_string()];
            let embedded = tokio::task::spawn_blocking(move || embedder.embed(&q))
                .await
                .map_err(|e| format!("query embedding task failed: {e}"))
                .and_then(|r| r);
            match embedded.and_then(|mut v| {
                v.pop()
                    .ok_or_else(|| "embedder returned no vector".to_string())
                    .and_then(|q| idx.similarities(q).map_err(|e| e.to_string()))
            }) {
                Ok(sims) => {
                    return Ok(SearchOutcome {
                        mode: SearchMode::Semantic,
                        results: rank(&catalog, Some(&sims), query, opts),
                        note: None,
                    });
                },
                Err(e) => {
                    warn!("Query embedding failed, falling back to lexical: {e}");
                    note = Some(format!(
                        "semantic search failed ({e}); used keyword matching"
                    ));
                },
            }
        }

        let note = note.unwrap_or_else(|| match &*self.model.borrow() {
            ModelState::Loading { since } => format!(
                "embedding model still loading ({:.0}s so far); used keyword matching",
                since.elapsed().as_secs_f64()
            ),
            ModelState::Failed { error, .. } => {
                format!("embedding model unavailable ({error}); used keyword matching")
            },
            _ => "semantic index unavailable; used keyword matching".to_string(),
        });
        Ok(SearchOutcome {
            mode: SearchMode::Lexical,
            results: rank(&snap.catalog, None, query, opts),
            note: Some(note),
        })
    }

    /// Re-fetch the config from its source, bypassing the cache TTL. On
    /// failure the previously loaded data (and on-disk cache) stay in use.
    /// Also retries a failed model load.
    pub async fn refresh(&self) -> Result<RefreshOutcome, String> {
        let _guard = self.load_lock.lock().await;
        let previous = self.snapshot.read().await.clone();

        let loaded = self.loader.refresh().await.map_err(|e| match &previous {
            Some(p) => format!(
                "{e}. Keeping the {} previously loaded reactions.",
                p.catalog.len()
            ),
            None => e.to_string(),
        })?;

        let catalog = Arc::new(Catalog::new(loaded.reactions));
        let (added, removed) = match &previous {
            Some(p) => diff_ids(&p.catalog, &catalog),
            None => (Vec::new(), Vec::new()),
        };

        // Retry a failed model immediately on an explicit refresh.
        self.model.send_if_modified(|s| {
            if matches!(s, ModelState::Failed { .. }) {
                *s = ModelState::Idle;
                true
            } else {
                false
            }
        });
        self.start_model_load();

        // Re-index now if the model is already loaded so the next search is
        // fast; otherwise the index is built lazily.
        let ready = match &*self.model.borrow() {
            ModelState::Ready { embedder, .. } => Some(Arc::clone(embedder)),
            _ => None,
        };
        let semantic = match ready {
            Some(embedder) => {
                let _g = self.index_lock.lock().await;
                self.build_index(&catalog, &embedder).await
            },
            None => None,
        };

        let outcome = RefreshOutcome {
            reaction_count: catalog.len(),
            previous_count: previous.as_ref().map_or(0, |p| p.catalog.len()),
            added,
            removed,
            source: loaded.source,
            semantic_ready: semantic.is_some(),
            warnings: loaded.warnings.clone(),
        };
        *self.snapshot.write().await = Some(Arc::new(Snapshot {
            catalog,
            semantic,
            source: loaded.source,
            loaded_at: Utc::now(),
            warnings: loaded.warnings,
        }));
        Ok(outcome)
    }

    /// Status report. Never blocks on loading.
    pub async fn status(&self) -> Value {
        let snap = self.snapshot.read().await.clone();
        let model_state = self.model.borrow().clone();
        let index_error = self.index_error.read().await.clone();

        let mut model = json!({
            "name": MODEL_NAME,
            "state": model_state.label(),
            "cache_dir": self.settings.model_cache_dir.display().to_string(),
        });
        match &model_state {
            ModelState::Loading { since } => {
                model["loading_secs"] = json!(since.elapsed().as_secs());
            },
            ModelState::Ready {
                load_secs,
                embedder,
            } => {
                model["name"] = json!(embedder.model_name());
                model["load_secs"] = json!((load_secs * 100.0).round() / 100.0);
            },
            ModelState::Failed { error, at } => {
                model["error"] = json!(error);
                let retry_in = self.settings.model_retry.saturating_sub(at.elapsed());
                model["retry_in_secs"] = json!(retry_in.as_secs());
            },
            ModelState::Idle => {},
        }

        let search_mode = match &snap {
            None => "not_loaded",
            Some(s) if s.semantic.is_some() => "semantic",
            Some(_) => "lexical",
        };

        let mut response = json!({
            "server": "reaction-search",
            "version": env!("CARGO_PKG_VERSION"),
            "initialized": snap.is_some(),
            "search_mode": search_mode,
            "model": model,
            "cache": self.loader.cache_info().await,
        });
        if let Some(e) = index_error {
            response["index_error"] = json!(e);
        }
        match &snap {
            Some(s) => {
                response["engine"] = json!({
                    "initialized": s.semantic.is_some(),
                    "model_name": model["name"],
                    "reaction_count": s.catalog.len(),
                    "unique_tags": s.catalog.tag_counts().len(),
                    "embeddings_shape": s.semantic.as_ref().map_or([0, 0], |i| i.shape()),
                });
                response["catalog"] = json!({
                    "reaction_count": s.catalog.len(),
                    "unique_tags": s.catalog.tag_counts().len(),
                    "source": s.source,
                    "loaded_at": s.loaded_at.to_rfc3339(),
                    "warnings": s.warnings,
                });
            },
            None => {
                response["note"] =
                    json!("Reactions load on first use (or at startup with preload)");
            },
        }
        response
    }
}

fn diff_ids(old: &Catalog, new: &Catalog) -> (Vec<String>, Vec<String>) {
    let old_ids: HashSet<&str> = old.reactions().iter().map(|r| r.id.as_str()).collect();
    let new_ids: HashSet<&str> = new.reactions().iter().map(|r| r.id.as_str()).collect();
    let mut added: Vec<String> = new_ids
        .difference(&old_ids)
        .map(|s| s.to_string())
        .collect();
    let mut removed: Vec<String> = old_ids
        .difference(&new_ids)
        .map(|s| s.to_string())
        .collect();
    added.sort();
    removed.sort();
    (added, removed)
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::embed::HashEmbedder;
    use std::sync::atomic::{AtomicUsize, Ordering};

    pub const SAMPLE: &str = r#"
reaction_images:
  - id: "felix"
    description: "Happy cheerful excited expression"
    usage_scenarios: ["Celebrating good news"]
    tags: ["happy", "excited"]
  - id: "confused"
    description: "Confused questioning expression"
    usage_scenarios: ["When you do not understand the error"]
    tags: ["confused"]
  - id: "kagami_annoyed"
    description: "Annoyed irritated glare"
    usage_scenarios: ["When tests keep failing"]
    tags: ["annoyed"]
"#;

    /// Service reading `yaml` from a temp file, with a controllable model.
    pub fn test_service(
        name: &str,
        yaml: &str,
        factory: EmbedderFactory,
    ) -> (Arc<ReactionService>, PathBuf) {
        let dir = std::env::temp_dir().join(format!(
            "mcp_reaction_search_svc_{name}_{}_{}",
            std::process::id(),
            Utc::now().timestamp_nanos_opt().unwrap_or_default()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("config.yaml");
        std::fs::write(&path, yaml).unwrap();
        let settings = ServiceSettings {
            config: ConfigSettings {
                config_url: path.display().to_string(),
                cache_dir: dir.join("cache"),
                cache_ttl: Duration::from_secs(60),
                fetch_timeout: Duration::from_secs(1),
            },
            model_cache_dir: dir.join("models"),
            model_wait: Duration::from_secs(5),
            model_retry: Duration::from_secs(3600),
        };
        (
            ReactionService::with_embedder_factory(settings, factory),
            path,
        )
    }

    pub fn hash_factory() -> EmbedderFactory {
        Arc::new(|| Ok(Arc::new(HashEmbedder) as Arc<dyn Embedder>))
    }

    pub fn failing_factory(calls: Arc<AtomicUsize>) -> EmbedderFactory {
        Arc::new(move || {
            calls.fetch_add(1, Ordering::SeqCst);
            Err("offline".to_string())
        })
    }

    #[tokio::test]
    async fn semantic_search_with_working_model() {
        let (svc, _) = test_service("semantic", SAMPLE, hash_factory());
        let out = svc
            .search("confused about the error", &SearchOptions::default())
            .await
            .unwrap();
        assert_eq!(out.mode, SearchMode::Semantic);
        assert!(out.note.is_none());
        assert_eq!(out.results[0].id, "confused");
        let status = svc.status().await;
        assert_eq!(status["search_mode"], "semantic");
        assert_eq!(status["model"]["state"], "ready");
        assert_eq!(status["engine"]["reaction_count"], 3);
    }

    #[tokio::test]
    async fn model_failure_falls_back_to_lexical_and_is_not_retried_immediately() {
        let calls = Arc::new(AtomicUsize::new(0));
        let (svc, _) = test_service("lexical", SAMPLE, failing_factory(calls.clone()));
        let out = svc
            .search("annoyed", &SearchOptions::default())
            .await
            .unwrap();
        assert_eq!(out.mode, SearchMode::Lexical);
        assert!(out.note.as_deref().unwrap().contains("offline"));
        assert_eq!(out.results[0].id, "kagami_annoyed");

        svc.search("happy", &SearchOptions::default())
            .await
            .unwrap();
        assert_eq!(calls.load(Ordering::SeqCst), 1, "retry backoff respected");

        let status = svc.status().await;
        assert_eq!(status["model"]["state"], "failed");
        assert_eq!(status["search_mode"], "lexical");

        // An explicit refresh retries the model.
        svc.refresh().await.unwrap();
        tokio::time::sleep(Duration::from_millis(200)).await;
        assert_eq!(calls.load(Ordering::SeqCst), 2);
    }

    #[tokio::test]
    async fn slow_model_does_not_block_search() {
        let slow: EmbedderFactory = Arc::new(|| {
            std::thread::sleep(Duration::from_millis(1500));
            Ok(Arc::new(HashEmbedder) as Arc<dyn Embedder>)
        });
        let (svc, _) = test_service("slow", SAMPLE, slow);
        let svc = {
            // Shorten the wait so the first search answers lexically.
            let mut s = svc.settings.clone();
            s.model_wait = Duration::from_millis(100);
            ReactionService::with_embedder_factory(s, Arc::clone(&svc.factory))
        };
        let out = svc
            .search("happy", &SearchOptions::default())
            .await
            .unwrap();
        assert_eq!(out.mode, SearchMode::Lexical);
        assert!(out.note.unwrap().contains("still loading"));
        assert_eq!(svc.status().await["model"]["state"], "loading");
    }

    #[tokio::test]
    async fn catalog_does_not_need_model() {
        let calls = Arc::new(AtomicUsize::new(0));
        let (svc, _) = test_service("catalog", SAMPLE, failing_factory(calls.clone()));
        let catalog = svc.catalog().await.unwrap();
        assert_eq!(catalog.len(), 3);
        assert_eq!(calls.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn refresh_reports_diff_and_keeps_data_on_failure() {
        let (svc, path) = test_service("refresh", SAMPLE, hash_factory());
        svc.search("happy", &SearchOptions::default())
            .await
            .unwrap();

        let updated = SAMPLE.replace("kagami_annoyed", "nao_annoyed");
        std::fs::write(&path, updated).unwrap();
        let out = svc.refresh().await.unwrap();
        assert_eq!(out.added, vec!["nao_annoyed"]);
        assert_eq!(out.removed, vec!["kagami_annoyed"]);
        assert_eq!(out.reaction_count, 3);
        assert!(out.semantic_ready);
        assert!(svc.catalog().await.unwrap().get("nao_annoyed").is_some());

        // Broken source: refresh fails, old data stays.
        std::fs::write(&path, "reaction_images: []").unwrap();
        let err = svc.refresh().await.unwrap_err();
        assert!(err.contains("Keeping the 3 previously loaded"), "{err}");
        assert!(svc.catalog().await.unwrap().get("nao_annoyed").is_some());
    }

    #[tokio::test]
    async fn missing_config_is_a_clear_error() {
        let (svc, path) = test_service("missing", SAMPLE, hash_factory());
        std::fs::remove_file(&path).unwrap();
        let err = svc.catalog().await.unwrap_err();
        assert!(err.contains("cannot read"), "{err}");
        let status = svc.status().await;
        assert_eq!(status["initialized"], false);
    }
}
