//! Semantic search engine using sentence embeddings.

use std::collections::HashMap;

use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
use ndarray::{Array1, Array2};
use thiserror::Error;
use tracing::{debug, info};

use crate::types::{EngineStatus, Reaction, ReactionResult};

/// Default model - all-MiniLM-L6-v2 is fast and good quality
/// Note: fastembed uses slightly different model names than sentence-transformers
const DEFAULT_MODEL: EmbeddingModel = EmbeddingModel::AllMiniLML6V2;

/// Errors from the search engine
#[derive(Error, Debug)]
pub enum EngineError {
    #[error("Engine not initialized")]
    NotInitialized,

    #[error("Failed to load model: {0}")]
    ModelError(String),

    #[error("Failed to encode text: {0}")]
    EncodingError(String),

    #[error("Reaction not found: {0}")]
    NotFound(String),
}

/// Semantic search engine for reactions
pub struct ReactionSearchEngine {
    model: Option<TextEmbedding>,
    model_name: String,
    reactions: Vec<Reaction>,
    embeddings: Option<Array2<f32>>,
    id_to_index: HashMap<String, usize>,
    tag_counts: HashMap<String, usize>,
    initialized: bool,
}

impl ReactionSearchEngine {
    /// Create a new search engine
    pub fn new() -> Self {
        Self {
            model: None,
            model_name: format!("{:?}", DEFAULT_MODEL),
            reactions: Vec::new(),
            embeddings: None,
            id_to_index: HashMap::new(),
            tag_counts: HashMap::new(),
            initialized: false,
        }
    }

    /// Initialize the engine with reactions
    pub fn initialize(&mut self, reactions: Vec<Reaction>) -> Result<(), EngineError> {
        info!("Initializing search engine with {} reactions", reactions.len());

        // Build ID to index mapping
        self.id_to_index.clear();
        for (i, reaction) in reactions.iter().enumerate() {
            self.id_to_index.insert(reaction.id.clone(), i);
        }

        // Build tag counts
        self.tag_counts.clear();
        for reaction in &reactions {
            for tag in &reaction.tags {
                *self.tag_counts.entry(tag.clone()).or_insert(0) += 1;
            }
        }

        // Store reactions
        self.reactions = reactions;

        // Load model (lazy - only on first search if needed)
        if self.model.is_none() {
            debug!("Loading embedding model...");
            let model = TextEmbedding::try_new(InitOptions::new(DEFAULT_MODEL).with_show_download_progress(true))
                .map_err(|e| EngineError::ModelError(e.to_string()))?;
            self.model = Some(model);
            info!("Embedding model loaded");
        }

        // Compute embeddings for all reactions
        let texts: Vec<String> = self.reactions.iter().map(|r| r.searchable_text()).collect();

        debug!("Computing embeddings for {} texts", texts.len());
        let model = self.model.as_ref().unwrap();

        let embeddings_vec = model
            .embed(texts, None)
            .map_err(|e| EngineError::EncodingError(e.to_string()))?;

        // Convert to ndarray
        if embeddings_vec.is_empty() {
            self.embeddings = Some(Array2::zeros((0, 384)));
        } else {
            let dim = embeddings_vec[0].len();
            let n = embeddings_vec.len();
            let flat: Vec<f32> = embeddings_vec.into_iter().flatten().collect();
            self.embeddings = Some(
                Array2::from_shape_vec((n, dim), flat)
                    .map_err(|e| EngineError::EncodingError(e.to_string()))?,
            );
        }

        self.initialized = true;
        info!(
            "Search engine initialized: {} reactions, {} unique tags",
            self.reactions.len(),
            self.tag_counts.len()
        );

        Ok(())
    }

    /// Check if engine is initialized
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }

    /// Get engine status
    pub fn get_status(&self) -> EngineStatus {
        let shape = self
            .embeddings
            .as_ref()
            .map(|e| [e.nrows(), e.ncols()])
            .unwrap_or([0, 0]);

        EngineStatus {
            initialized: self.initialized,
            model_name: self.model_name.clone(),
            reaction_count: self.reactions.len(),
            unique_tags: self.tag_counts.len(),
            embeddings_shape: shape,
        }
    }

    /// Search for reactions matching a query
    pub fn search(
        &self,
        query: &str,
        limit: usize,
        tags: Option<&[String]>,
        min_similarity: f32,
    ) -> Result<Vec<ReactionResult>, EngineError> {
        if !self.initialized {
            return Err(EngineError::NotInitialized);
        }

        let model = self.model.as_ref().ok_or(EngineError::NotInitialized)?;
        let embeddings = self.embeddings.as_ref().ok_or(EngineError::NotInitialized)?;

        // Encode query
        let query_embeddings = model
            .embed(vec![query.to_string()], None)
            .map_err(|e| EngineError::EncodingError(e.to_string()))?;

        if query_embeddings.is_empty() {
            return Ok(Vec::new());
        }

        let query_vec = Array1::from_vec(query_embeddings.into_iter().next().unwrap());

        // Compute cosine similarities
        let similarities = self.cosine_similarity(&query_vec, embeddings);

        // Filter and sort
        let mut results: Vec<(usize, f32)> = similarities
            .iter()
            .enumerate()
            .filter(|(_, sim)| **sim >= min_similarity)
            .filter(|(idx, _)| {
                // Tag filter (if provided)
                if let Some(filter_tags) = tags {
                    let reaction = &self.reactions[*idx];
                    // Check if reaction has at least one matching tag
                    reaction.tags.iter().any(|t| filter_tags.contains(t))
                } else {
                    true
                }
            })
            .map(|(idx, sim)| (idx, *sim))
            .collect();

        // Sort by similarity descending
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        // Take top N and convert to ReactionResult
        let results: Vec<ReactionResult> = results
            .into_iter()
            .take(limit)
            .map(|(idx, sim)| ReactionResult::from_reaction(&self.reactions[idx], sim))
            .collect();

        Ok(results)
    }

    /// Get a reaction by ID
    pub fn get_by_id(&self, id: &str) -> Option<ReactionResult> {
        self.id_to_index.get(id).map(|&idx| {
            ReactionResult::from_reaction(&self.reactions[idx], 1.0) // Perfect match
        })
    }

    /// List all tags with counts
    pub fn list_tags(&self) -> &HashMap<String, usize> {
        &self.tag_counts
    }

    /// Get reaction count
    pub fn reaction_count(&self) -> usize {
        self.reactions.len()
    }

    /// Compute cosine similarity between query and all embeddings
    fn cosine_similarity(&self, query: &Array1<f32>, embeddings: &Array2<f32>) -> Vec<f32> {
        const EPSILON: f32 = 1e-8;

        // Normalize query
        let query_norm = query.mapv(|x| x * x).sum().sqrt() + EPSILON;
        let query_normalized: Array1<f32> = query.mapv(|x| x / query_norm);

        // Compute similarities for each embedding
        embeddings
            .outer_iter()
            .map(|emb| {
                // Normalize embedding
                let emb_norm = emb.mapv(|x| x * x).sum().sqrt() + EPSILON;
                let emb_normalized: Array1<f32> = emb.mapv(|x| x / emb_norm);

                // Dot product of normalized vectors
                query_normalized.dot(&emb_normalized)
            })
            .collect()
    }
}

impl Default for ReactionSearchEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_test_reaction(id: &str, description: &str, tags: Vec<&str>) -> Reaction {
        Reaction {
            id: id.to_string(),
            source_url: None,
            description: description.to_string(),
            tags: tags.into_iter().map(String::from).collect(),
            usage_scenarios: vec![],
            character_appearance: String::new(),
        }
    }

    #[test]
    fn test_engine_creation() {
        let engine = ReactionSearchEngine::new();
        assert!(!engine.is_initialized());
    }

    #[test]
    fn test_get_status_uninitialized() {
        let engine = ReactionSearchEngine::new();
        let status = engine.get_status();
        assert!(!status.initialized);
        assert_eq!(status.reaction_count, 0);
    }

    // Integration tests that require model download are marked ignore
    #[test]
    #[ignore]
    fn test_engine_initialization() {
        let mut engine = ReactionSearchEngine::new();
        let reactions = vec![
            make_test_reaction("happy", "Happy anime girl", vec!["happy"]),
            make_test_reaction("sad", "Sad anime girl", vec!["sad"]),
        ];

        engine.initialize(reactions).unwrap();
        assert!(engine.is_initialized());
        assert_eq!(engine.reaction_count(), 2);
    }

    #[test]
    #[ignore]
    fn test_search() {
        let mut engine = ReactionSearchEngine::new();
        let reactions = vec![
            make_test_reaction("happy", "Happy cheerful excited anime girl", vec!["happy"]),
            make_test_reaction("sad", "Sad crying depressed anime girl", vec!["sad"]),
        ];

        engine.initialize(reactions).unwrap();

        let results = engine.search("excited happy", 5, None, 0.0).unwrap();
        assert!(!results.is_empty());
        assert_eq!(results[0].id, "happy"); // Happy should be most similar
    }
}
