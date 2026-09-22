//! Sentence-embedding backend.
//!
//! The [`Embedder`] trait isolates the ONNX model so the ranking logic can be
//! unit-tested offline with a deterministic fake, and so the service can keep
//! working (lexically) when the model cannot be downloaded.

use std::path::PathBuf;

use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
use tracing::info;

/// Embedding model used for semantic search: all-MiniLM-L6-v2 (384 dims,
/// ~90 MB ONNX download from Hugging Face on first use).
pub const MODEL: EmbeddingModel = EmbeddingModel::AllMiniLML6V2;

/// Human-readable model name reported in status output.
pub const MODEL_NAME: &str = "sentence-transformers/all-MiniLM-L6-v2";

/// A synchronous text embedder. Calls are CPU-bound and must be run on a
/// blocking thread (`tokio::task::spawn_blocking`), never directly in async
/// code.
pub trait Embedder: Send + Sync {
    /// Model identifier for diagnostics.
    fn model_name(&self) -> &str;

    /// Embed each text into a vector. All vectors share one dimension.
    fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>, String>;
}

/// [`Embedder`] backed by fastembed / ONNX Runtime.
pub struct FastEmbedder {
    model: TextEmbedding,
}

impl FastEmbedder {
    /// Load (downloading on first use) the model into `cache_dir`.
    ///
    /// Blocking: performs network and disk I/O and ONNX session setup.
    /// `HF_HOME`, if set, overrides `cache_dir` (fastembed behaviour) and
    /// `HF_ENDPOINT` overrides the Hugging Face host.
    pub fn load(cache_dir: PathBuf) -> Result<Self, String> {
        info!(
            "Loading embedding model {MODEL_NAME} (cache: {})",
            cache_dir.display()
        );
        let started = std::time::Instant::now();
        let model = TextEmbedding::try_new(
            InitOptions::new(MODEL)
                .with_cache_dir(cache_dir)
                // The progress bar is terminal noise in docker logs and
                // useless over MCP; download progress is logged instead.
                .with_show_download_progress(false),
        )
        .map_err(|e| format!("failed to load embedding model {MODEL_NAME}: {e:#}"))?;
        info!(
            "Embedding model loaded in {:.2}s",
            started.elapsed().as_secs_f64()
        );
        Ok(Self { model })
    }
}

impl Embedder for FastEmbedder {
    fn model_name(&self) -> &str {
        MODEL_NAME
    }

    fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>, String> {
        self.model
            .embed(texts.to_vec(), None)
            .map_err(|e| format!("embedding failed: {e:#}"))
    }
}

/// Deterministic bag-of-words embedder for tests: each token is hashed into
/// one of `DIM` buckets. Texts sharing words get high cosine similarity,
/// which is enough to exercise ranking without the real model.
#[cfg(test)]
pub struct HashEmbedder;

#[cfg(test)]
impl HashEmbedder {
    const DIM: usize = 64;
}

#[cfg(test)]
impl Embedder for HashEmbedder {
    fn model_name(&self) -> &str {
        "test-hash-embedder"
    }

    fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>, String> {
        use std::hash::{Hash, Hasher};
        Ok(texts
            .iter()
            .map(|t| {
                let mut v = vec![0.0f32; Self::DIM];
                for tok in crate::text::tokenize(t) {
                    let mut h = std::collections::hash_map::DefaultHasher::new();
                    tok.hash(&mut h);
                    v[(h.finish() as usize) % Self::DIM] += 1.0;
                }
                v
            })
            .collect())
    }
}
