//! Text embedding backends.
//!
//! ChromaDB's HTTP API does **not** compute embeddings: that is done by the
//! (Python/JS) client library. This server therefore embeds every document and
//! query itself before talking to ChromaDB.
//!
//! * [`FastEmbedder`] (feature `fastembed`, the default) runs
//!   `all-MiniLM-L6-v2` locally via ONNX Runtime - the same model ChromaDB's
//!   Python client uses by default, so vectors are interchangeable with
//!   collections written by Python tooling. The model (~90 MB) is downloaded
//!   from Hugging Face on first use into `MEMORY_MODEL_CACHE_DIR` (the Docker
//!   image ships it pre-downloaded).
//! * [`HashEmbedder`] is a dependency-free, deterministic feature-hashing
//!   embedder over words and character trigrams. It captures lexical overlap
//!   only (no synonyms), but works fully offline and is used by the tests.
//!
//! The two produce vectors of different dimensions (384 vs 256), so ChromaDB
//! rejects writes that would mix them in one collection instead of silently
//! returning meaningless similarities.

use async_trait::async_trait;
use sha2::{Digest, Sha256};

use crate::config::{Config, EmbedderKind};

/// Something that turns text into fixed-size vectors.
#[async_trait]
pub trait Embedder: Send + Sync {
    /// Stable identifier stored in collection metadata (e.g. `hash-v1-256`).
    fn id(&self) -> &str;
    /// Output vector dimension.
    fn dimension(&self) -> usize;
    /// Whether the backend is ready without further downloads or loading.
    fn is_ready(&self) -> bool;
    /// Embed a batch of texts, returning one vector per input, in order.
    async fn embed(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>, String>;
}

/// Build the embedder selected by the configuration.
pub fn from_config(config: &Config) -> std::sync::Arc<dyn Embedder> {
    match config.embedder {
        #[cfg(feature = "fastembed")]
        EmbedderKind::FastEmbed => {
            std::sync::Arc::new(FastEmbedder::new(config.model_cache_dir.clone()))
        },
        #[cfg(not(feature = "fastembed"))]
        EmbedderKind::FastEmbed => std::sync::Arc::new(HashEmbedder::default()),
        EmbedderKind::Hash => std::sync::Arc::new(HashEmbedder::default()),
    }
}

// ---------------------------------------------------------------------------
// Hash embedder
// ---------------------------------------------------------------------------

/// Deterministic feature-hashing embedder (lexical similarity only).
///
/// Each lowercase word contributes weight 1.0 and each character trigram of
/// the padded word 0.5 to a signed bucket chosen by SHA-256, then the vector is
/// L2-normalized. Stable across platforms and releases (the hash is fixed), so
/// stored vectors stay valid.
pub struct HashEmbedder {
    dim: usize,
    id: String,
}

impl HashEmbedder {
    /// Dimension used by default; deliberately different from MiniLM's 384.
    pub const DEFAULT_DIM: usize = 256;

    /// Create a hash embedder with `dim` buckets (minimum 8).
    pub fn new(dim: usize) -> Self {
        let dim = dim.max(8);
        Self {
            dim,
            id: format!("hash-v1-{dim}"),
        }
    }

    fn add_feature(&self, v: &mut [f32], feature: &str, weight: f32) {
        let digest = Sha256::digest(feature.as_bytes());
        let mut idx_bytes = [0u8; 8];
        idx_bytes.copy_from_slice(&digest[..8]);
        let idx = (u64::from_le_bytes(idx_bytes) % self.dim as u64) as usize;
        let sign = if digest[8] & 1 == 0 { 1.0 } else { -1.0 };
        v[idx] += sign * weight;
    }

    /// Embed one text synchronously.
    pub fn embed_one(&self, text: &str) -> Vec<f32> {
        let mut v = vec![0.0f32; self.dim];
        let lower = text.to_lowercase();
        for word in lower
            .split(|c: char| !c.is_alphanumeric())
            .filter(|w| !w.is_empty())
        {
            self.add_feature(&mut v, &format!("w:{word}"), 1.0);
            let padded: Vec<char> = format!(" {word} ").chars().collect();
            for tri in padded.windows(3) {
                let tri: String = tri.iter().collect();
                self.add_feature(&mut v, &format!("t:{tri}"), 0.5);
            }
        }
        let norm = v.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 0.0 {
            v.iter_mut().for_each(|x| *x /= norm);
        } else {
            // Empty/punctuation-only text: a fixed unit vector keeps cosine
            // distance well-defined (zero vectors make it NaN).
            v[0] = 1.0;
        }
        v
    }
}

impl Default for HashEmbedder {
    fn default() -> Self {
        Self::new(Self::DEFAULT_DIM)
    }
}

#[async_trait]
impl Embedder for HashEmbedder {
    fn id(&self) -> &str {
        &self.id
    }

    fn dimension(&self) -> usize {
        self.dim
    }

    fn is_ready(&self) -> bool {
        true
    }

    async fn embed(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>, String> {
        Ok(texts.iter().map(|t| self.embed_one(t)).collect())
    }
}

// ---------------------------------------------------------------------------
// FastEmbed (ONNX) embedder
// ---------------------------------------------------------------------------

#[cfg(feature = "fastembed")]
pub use fast::FastEmbedder;

#[cfg(feature = "fastembed")]
mod fast {
    use super::Embedder;
    use async_trait::async_trait;
    use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
    use std::path::PathBuf;
    use std::sync::Arc;
    use tokio::sync::OnceCell;

    /// Local all-MiniLM-L6-v2 embedder, loaded lazily on first use.
    pub struct FastEmbedder {
        cache_dir: PathBuf,
        model: OnceCell<Arc<TextEmbedding>>,
    }

    impl FastEmbedder {
        /// Output dimension of all-MiniLM-L6-v2.
        pub const DIM: usize = 384;

        /// Create an embedder that caches model files under `cache_dir`.
        pub fn new(cache_dir: PathBuf) -> Self {
            Self {
                cache_dir,
                model: OnceCell::new(),
            }
        }

        /// Load (downloading if necessary) the model. Blocking work runs on
        /// the blocking thread pool. Concurrent callers share one load; a
        /// failed load is retried on the next call.
        pub async fn load(&self) -> Result<Arc<TextEmbedding>, String> {
            self.model
                .get_or_try_init(|| async {
                    let dir = self.cache_dir.clone();
                    tracing::info!(
                        "Loading embedding model all-MiniLM-L6-v2 (cache: {})",
                        dir.display()
                    );
                    tokio::task::spawn_blocking(move || {
                        if let Err(e) = std::fs::create_dir_all(&dir) {
                            return Err(format!(
                                "cannot create model cache dir {}: {e}",
                                dir.display()
                            ));
                        }
                        // Progress bars must stay off: in stdio mode stdout is
                        // the JSON-RPC channel.
                        TextEmbedding::try_new(
                            InitOptions::new(EmbeddingModel::AllMiniLML6V2)
                                .with_cache_dir(dir)
                                .with_show_download_progress(false),
                        )
                        .map(Arc::new)
                        .map_err(|e| format!("failed to load embedding model: {e}"))
                    })
                    .await
                    .map_err(|e| format!("embedding model loader task failed: {e}"))?
                })
                .await
                .cloned()
        }
    }

    #[async_trait]
    impl Embedder for FastEmbedder {
        fn id(&self) -> &str {
            "fastembed-all-minilm-l6-v2"
        }

        fn dimension(&self) -> usize {
            Self::DIM
        }

        fn is_ready(&self) -> bool {
            self.model.initialized()
        }

        async fn embed(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>, String> {
            if texts.is_empty() {
                return Ok(Vec::new());
            }
            let model = self.load().await?;
            tokio::task::spawn_blocking(move || {
                model
                    .embed(texts, None)
                    .map_err(|e| format!("embedding failed: {e}"))
            })
            .await
            .map_err(|e| format!("embedding task failed: {e}"))?
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cosine(a: &[f32], b: &[f32]) -> f32 {
        a.iter().zip(b).map(|(x, y)| x * y).sum()
    }

    #[tokio::test]
    async fn hash_embedder_is_deterministic_and_normalized() {
        let e = HashEmbedder::default();
        let v = e
            .embed(vec!["Rust MCP servers".into(), "Rust MCP servers".into()])
            .await
            .unwrap();
        assert_eq!(v.len(), 2);
        assert_eq!(v[0], v[1]);
        assert_eq!(v[0].len(), HashEmbedder::DEFAULT_DIM);
        let norm: f32 = v[0].iter().map(|x| x * x).sum::<f32>().sqrt();
        assert!((norm - 1.0).abs() < 1e-5);
        assert_eq!(e.id(), "hash-v1-256");
    }

    #[test]
    fn hash_embedder_ranks_lexical_overlap() {
        let e = HashEmbedder::default();
        let q = e.embed_one("how are MCP servers structured");
        let near = e.embed_one("All MCP servers are structured around the mcp-core crate");
        let far = e.embed_one("Bananas are yellow fruit");
        assert!(cosine(&q, &near) > cosine(&q, &far));
    }

    #[test]
    fn hash_embedder_handles_empty_text() {
        let e = HashEmbedder::new(16);
        let v = e.embed_one("  ... ");
        assert_eq!(v.len(), 16);
        assert_eq!(v[0], 1.0);
        assert!(v.iter().all(|x| x.is_finite()));
    }

    #[test]
    fn hash_dimension_differs_from_minilm() {
        assert_ne!(HashEmbedder::DEFAULT_DIM, 384);
    }
}
