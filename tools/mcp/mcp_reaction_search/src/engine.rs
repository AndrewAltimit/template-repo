//! Search engine: the reaction catalog, the semantic (embedding) index, and
//! the hybrid ranking function.
//!
//! Everything here is synchronous and free of I/O; embedding calls go through
//! the [`Embedder`] trait and are expected to run on a blocking thread.

use std::collections::{BTreeMap, HashMap};

use ndarray::{Array1, Array2, ArrayView1};
use serde::Serialize;
use thiserror::Error;

use crate::embed::Embedder;
use crate::text::{LexicalIndex, edit_distance};
use crate::types::{Reaction, ReactionResult};

/// Weight of the whole-document embedding in the semantic similarity. The
/// remainder goes to the best-matching single field (description or one
/// usage scenario), which rewards a precise scenario match without letting a
/// single short phrase dominate.
const DOC_WEIGHT: f32 = 0.5;

/// Weight of the normalized BM25 score added to the semantic similarity.
const LEXICAL_WEIGHT: f32 = 0.10;

/// Bonus when a query term exactly matches one of the reaction's tags.
const TAG_BOOST: f32 = 0.05;

/// Maximum number of results a search may return.
pub const MAX_LIMIT: usize = 20;

/// Errors from the search engine.
#[derive(Error, Debug)]
pub enum EngineError {
    /// The embedding backend failed.
    #[error("embedding failed: {0}")]
    Encoding(String),
}

/// Immutable, validated set of reactions plus lookup and lexical indexes.
///
/// Building a catalog needs no model, so id lookups, listings, tag browsing,
/// and lexical search work even when the embedding model is unavailable.
#[derive(Debug)]
pub struct Catalog {
    reactions: Vec<Reaction>,
    id_to_index: HashMap<String, usize>,
    /// Lowercased tag -> number of reactions carrying it.
    tag_counts: BTreeMap<String, usize>,
    lexical: LexicalIndex,
}

impl Catalog {
    /// Build a catalog. Reactions are expected to be validated and unique by
    /// id (see [`crate::config::sanitize_reactions`]); if not, the last
    /// duplicate wins lookups.
    pub fn new(reactions: Vec<Reaction>) -> Self {
        let id_to_index = reactions
            .iter()
            .enumerate()
            .map(|(i, r)| (r.id.clone(), i))
            .collect();
        let mut tag_counts = BTreeMap::new();
        for r in &reactions {
            for tag in &r.tags {
                *tag_counts.entry(tag.to_lowercase()).or_insert(0) += 1;
            }
        }
        let lexical = LexicalIndex::build(&reactions);
        Self {
            reactions,
            id_to_index,
            tag_counts,
            lexical,
        }
    }

    /// All reactions in config order.
    pub fn reactions(&self) -> &[Reaction] {
        &self.reactions
    }

    /// Number of reactions.
    pub fn len(&self) -> usize {
        self.reactions.len()
    }

    /// Lowercased tag -> count, sorted by tag.
    pub fn tag_counts(&self) -> &BTreeMap<String, usize> {
        &self.tag_counts
    }

    /// Look up a reaction by id: exact match first, then case-insensitive.
    pub fn get(&self, id: &str) -> Option<&Reaction> {
        let id = id.trim();
        if let Some(&i) = self.id_to_index.get(id) {
            return Some(&self.reactions[i]);
        }
        self.reactions
            .iter()
            .find(|r| r.id.eq_ignore_ascii_case(id))
    }

    /// Up to `n` ids that look like `id` (substring match or small edit
    /// distance), best first.
    pub fn suggest(&self, id: &str, n: usize) -> Vec<String> {
        let needle = id.trim().to_lowercase();
        if needle.is_empty() {
            return Vec::new();
        }
        let max_dist = (needle.chars().count() / 3).max(2);
        let mut scored: Vec<(usize, &str)> = self
            .reactions
            .iter()
            .filter_map(|r| {
                let cand = r.id.to_lowercase();
                if cand.contains(&needle) || needle.contains(&cand) {
                    Some((0, r.id.as_str()))
                } else {
                    let d = edit_distance(&needle, &cand);
                    (d <= max_dist).then_some((d, r.id.as_str()))
                }
            })
            .collect();
        scored.sort();
        scored
            .into_iter()
            .take(n)
            .map(|(_, id)| id.to_string())
            .collect()
    }
}

/// Precomputed, L2-normalized embeddings for a [`Catalog`].
#[derive(Debug)]
pub struct SemanticIndex {
    /// One row per reaction: embedding of [`Reaction::searchable_text`].
    docs: Array2<f32>,
    /// One row per field text (description and each usage scenario).
    fields: Array2<f32>,
    /// Reaction index owning each row of `fields`.
    field_owner: Vec<usize>,
}

impl SemanticIndex {
    /// Embed every reaction (whole text and individual fields).
    ///
    /// CPU-bound: call from a blocking thread.
    pub fn build(catalog: &Catalog, embedder: &dyn Embedder) -> Result<Self, EngineError> {
        let doc_texts: Vec<String> = catalog
            .reactions()
            .iter()
            .map(Reaction::searchable_text)
            .collect();

        let mut field_texts = Vec::new();
        let mut field_owner = Vec::new();
        for (i, r) in catalog.reactions().iter().enumerate() {
            let fields = std::iter::once(&r.description).chain(&r.usage_scenarios);
            for text in fields.filter(|t| !t.trim().is_empty()) {
                field_texts.push(text.clone());
                field_owner.push(i);
            }
        }

        // One batched call for throughput; split the result afterwards.
        let n_docs = doc_texts.len();
        let mut all = doc_texts;
        all.extend(field_texts);
        let vectors = embedder.embed(&all).map_err(EngineError::Encoding)?;
        if vectors.len() != all.len() {
            return Err(EngineError::Encoding(format!(
                "embedder returned {} vectors for {} texts",
                vectors.len(),
                all.len()
            )));
        }
        let mut vectors = vectors.into_iter();
        let docs = to_normalized_matrix(vectors.by_ref().take(n_docs).collect())?;
        let fields = to_normalized_matrix(vectors.collect())?;
        Ok(Self {
            docs,
            fields,
            field_owner,
        })
    }

    /// Embedding dimension (0 if the catalog was empty).
    pub fn dim(&self) -> usize {
        self.docs.ncols()
    }

    /// `[reactions, dim]` shape of the document matrix.
    pub fn shape(&self) -> [usize; 2] {
        [self.docs.nrows(), self.docs.ncols()]
    }

    /// Number of embedded field texts.
    pub fn field_count(&self) -> usize {
        self.field_owner.len()
    }

    /// Semantic similarity of `query` (a raw embedding) to every reaction:
    /// `DOC_WEIGHT * cos(query, doc) + (1 - DOC_WEIGHT) * max cos(query, field)`.
    pub fn similarities(&self, query: Vec<f32>) -> Result<Vec<f32>, EngineError> {
        if query.len() != self.dim() {
            return Err(EngineError::Encoding(format!(
                "query embedding has dimension {}, index has {}",
                query.len(),
                self.dim()
            )));
        }
        let q = normalize(Array1::from_vec(query));
        let doc_sims = self.docs.dot(&q);
        let field_sims = self.fields.dot(&q);

        let mut best_field = vec![f32::NEG_INFINITY; self.docs.nrows()];
        for (&owner, &sim) in self.field_owner.iter().zip(field_sims.iter()) {
            best_field[owner] = best_field[owner].max(sim);
        }
        Ok(doc_sims
            .iter()
            .zip(best_field)
            .map(|(&doc, field)| {
                let field = if field.is_finite() { field } else { doc };
                DOC_WEIGHT * doc + (1.0 - DOC_WEIGHT) * field
            })
            .collect())
    }
}

fn normalize(v: Array1<f32>) -> Array1<f32> {
    let norm = v.dot(&v).sqrt();
    if norm > f32::EPSILON { v / norm } else { v }
}

fn normalize_row(row: ArrayView1<f32>) -> Array1<f32> {
    normalize(row.to_owned())
}

fn to_normalized_matrix(rows: Vec<Vec<f32>>) -> Result<Array2<f32>, EngineError> {
    let n = rows.len();
    let dim = rows.first().map_or(0, Vec::len);
    if rows.iter().any(|r| r.len() != dim) {
        return Err(EngineError::Encoding(
            "inconsistent embedding dimensions".into(),
        ));
    }
    let flat: Vec<f32> = rows.into_iter().flatten().collect();
    let mut m =
        Array2::from_shape_vec((n, dim), flat).map_err(|e| EngineError::Encoding(e.to_string()))?;
    for mut row in m.rows_mut() {
        let normalized = normalize_row(row.view());
        row.assign(&normalized);
    }
    Ok(m)
}

/// How a search was ranked.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SearchMode {
    /// Embedding similarity plus keyword/tag boosts.
    Semantic,
    /// Keyword (BM25) and tag matching only; used when no model is available.
    Lexical,
}

/// Validated search parameters.
#[derive(Debug, Clone)]
pub struct SearchOptions {
    /// Maximum results, `1..=MAX_LIMIT`.
    pub limit: usize,
    /// Keep only reactions with at least one of these tags (lowercase).
    pub tags: Vec<String>,
    /// Drop these reaction ids (lowercase).
    pub exclude: Vec<String>,
    /// Drop results whose similarity is below this value.
    pub min_similarity: f32,
}

impl Default for SearchOptions {
    fn default() -> Self {
        Self {
            limit: 5,
            tags: Vec::new(),
            exclude: Vec::new(),
            min_similarity: 0.0,
        }
    }
}

/// Rank the catalog against `query`.
///
/// `semantic` holds per-reaction similarities from
/// [`SemanticIndex::similarities`]; when `None` the ranking is purely lexical
/// and reactions with no keyword or tag match are omitted (there is no
/// meaningful order among them).
pub fn rank(
    catalog: &Catalog,
    semantic: Option<&[f32]>,
    query: &str,
    opts: &SearchOptions,
) -> Vec<ReactionResult> {
    let lexical = catalog.lexical.normalized_scores(query);
    let tag_hits = catalog.lexical.tag_hits(query);

    let mut scored: Vec<(usize, f32, f32)> = catalog
        .reactions()
        .iter()
        .enumerate()
        .filter(|(_, r)| opts.tags.is_empty() || opts.tags.iter().any(|t| r.has_tag(t)))
        .filter(|(_, r)| !opts.exclude.iter().any(|x| r.id.eq_ignore_ascii_case(x)))
        .filter_map(|(i, _)| {
            let boost = if tag_hits[i] { TAG_BOOST } else { 0.0 };
            let (similarity, score) = match semantic {
                Some(sims) => {
                    let sim = sims.get(i).copied().unwrap_or(0.0).clamp(0.0, 1.0);
                    (sim, sim + LEXICAL_WEIGHT * lexical[i] + boost)
                },
                None => {
                    if lexical[i] <= 0.0 && !tag_hits[i] {
                        return None;
                    }
                    (lexical[i], lexical[i] + boost)
                },
            };
            (similarity >= opts.min_similarity).then_some((i, similarity, score))
        })
        .collect();

    scored.sort_by(|a, b| {
        b.2.total_cmp(&a.2).then_with(|| {
            catalog.reactions()[a.0]
                .id
                .cmp(&catalog.reactions()[b.0].id)
        })
    });
    scored
        .into_iter()
        .take(opts.limit)
        .map(|(i, sim, score)| ReactionResult::from_reaction(&catalog.reactions()[i], sim, score))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::embed::HashEmbedder;
    use crate::types::reaction;

    fn catalog() -> Catalog {
        Catalog::new(vec![
            reaction(
                "felix",
                "Happy cheerful excited expression",
                &["happy", "excited"],
                &["Celebrating good news", "Positive reaction"],
            ),
            reaction(
                "confused",
                "Confused questioning expression",
                &["confused", "puzzled"],
                &["When you do not understand the error"],
            ),
            reaction(
                "kagami_annoyed",
                "Annoyed irritated glare",
                &["annoyed", "irritated"],
                &["When tests keep failing"],
            ),
            reaction(
                "thinking_foxgirl",
                "Deep in thought",
                &["thinking"],
                &["Pondering a hard debugging problem"],
            ),
        ])
    }

    fn semantic_search(c: &Catalog, query: &str, opts: &SearchOptions) -> Vec<ReactionResult> {
        let idx = SemanticIndex::build(c, &HashEmbedder).unwrap();
        let q = HashEmbedder.embed(&[query.to_string()]).unwrap().remove(0);
        let sims = idx.similarities(q).unwrap();
        rank(c, Some(&sims), query, opts)
    }

    #[test]
    fn catalog_lookup_and_tags() {
        let c = catalog();
        assert_eq!(c.len(), 4);
        assert_eq!(c.get("felix").unwrap().id, "felix");
        assert_eq!(c.get(" FELIX ").unwrap().id, "felix");
        assert!(c.get("nope").is_none());
        assert_eq!(c.tag_counts().get("happy"), Some(&1));
    }

    #[test]
    fn suggestions_find_near_misses() {
        let c = catalog();
        assert_eq!(c.suggest("felx", 3), vec!["felix"]);
        assert_eq!(c.suggest("kagami", 3), vec!["kagami_annoyed"]);
        assert!(c.suggest("zzzzzzzz", 3).is_empty());
        assert!(c.suggest("", 3).is_empty());
    }

    #[test]
    fn semantic_index_shapes() {
        let c = catalog();
        let idx = SemanticIndex::build(&c, &HashEmbedder).unwrap();
        assert_eq!(idx.shape()[0], 4);
        // 4 descriptions + 5 scenarios
        assert_eq!(idx.field_count(), 9);
        assert!(idx.similarities(vec![1.0; 3]).is_err());
    }

    #[test]
    fn semantic_ranking_prefers_matching_reaction() {
        let c = catalog();
        let opts = SearchOptions::default();
        assert_eq!(
            semantic_search(&c, "confused about the error", &opts)[0].id,
            "confused"
        );
        assert_eq!(
            semantic_search(&c, "tests keep failing, annoyed", &opts)[0].id,
            "kagami_annoyed"
        );
        let results = semantic_search(&c, "celebrating good news", &opts);
        assert_eq!(results[0].id, "felix");
        // Sorted by score, similarity within [0, 1].
        for w in results.windows(2) {
            assert!(w[0].score >= w[1].score);
        }
        assert!(results.iter().all(|r| (0.0..=1.0).contains(&r.similarity)));
    }

    #[test]
    fn filters_limit_exclude_and_threshold() {
        let c = catalog();
        let mut opts = SearchOptions {
            limit: 2,
            ..Default::default()
        };
        assert_eq!(semantic_search(&c, "happy", &opts).len(), 2);

        opts.limit = 20;
        opts.tags = vec!["thinking".into()];
        let r = semantic_search(&c, "happy", &opts);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].id, "thinking_foxgirl");

        opts.tags = vec![];
        opts.exclude = vec!["FELIX".into()];
        assert!(
            semantic_search(&c, "happy", &opts)
                .iter()
                .all(|r| r.id != "felix")
        );

        opts.exclude = vec![];
        opts.min_similarity = 1.1;
        assert!(semantic_search(&c, "happy", &opts).is_empty());
    }

    #[test]
    fn lexical_mode_only_returns_matches() {
        let c = catalog();
        let r = rank(&c, None, "so confused", &SearchOptions::default());
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].id, "confused");
        assert_eq!(r[0].similarity, 1.0);
        assert!(rank(&c, None, "xyzzy", &SearchOptions::default()).is_empty());
    }

    #[test]
    fn ties_break_by_id_for_determinism() {
        let c = catalog();
        let sims = vec![0.5; c.len()];
        let r = rank(
            &c,
            Some(&sims),
            "xyzzy",
            &SearchOptions {
                limit: 20,
                ..Default::default()
            },
        );
        let ids: Vec<&str> = r.iter().map(|r| r.id.as_str()).collect();
        assert_eq!(
            ids,
            vec!["confused", "felix", "kagami_annoyed", "thinking_foxgirl"]
        );
    }

    #[test]
    fn empty_catalog_is_harmless() {
        let c = Catalog::new(vec![]);
        let idx = SemanticIndex::build(&c, &HashEmbedder).unwrap();
        assert_eq!(idx.shape(), [0, 0]);
        assert!(rank(&c, None, "anything", &SearchOptions::default()).is_empty());
    }
}

/// Real-model check. Downloads all-MiniLM-L6-v2 (~90 MB) on first run, so it
/// is ignored by default: `cargo test -- --ignored real_model`.
#[cfg(test)]
mod real_model_tests {
    use super::*;
    use crate::embed::FastEmbedder;
    use crate::types::reaction;

    #[test]
    #[ignore = "downloads the embedding model"]
    fn real_model_ranks_expected_reactions() {
        let c = Catalog::new(vec![
            reaction(
                "felix",
                "Happy, cheerful, or excited expression",
                &["happy", "cheerful", "excited"],
                &[
                    "Celebrating something pleasant",
                    "Positive reaction to good news",
                ],
            ),
            reaction(
                "confused",
                "Confused or questioning expression",
                &["confused", "puzzled"],
                &["When you don't understand something"],
            ),
            reaction(
                "kagami_annoyed",
                "Annoyed, irritated glare",
                &["annoyed", "irritated"],
                &["When something is frustrating"],
            ),
            reaction(
                "thinking_foxgirl",
                "Deep in thought",
                &["thinking", "pondering"],
                &["Working through a hard problem"],
            ),
            reaction(
                "kyouko_sleepy",
                "Tired and sleepy",
                &["sleepy", "tired"],
                &["Late night work sessions"],
            ),
        ]);
        let dir = std::env::temp_dir().join("mcp_reaction_search_test_models");
        let e = FastEmbedder::load(dir).unwrap();
        let idx = SemanticIndex::build(&c, &e).unwrap();
        assert_eq!(idx.dim(), 384);
        for (query, expected) in [
            ("celebrating after fixing a bug", "felix"),
            ("confused about the error message", "confused"),
            ("irritated at the failing tests", "kagami_annoyed"),
            ("pondering while debugging", "thinking_foxgirl"),
            ("exhausted after a late night coding", "kyouko_sleepy"),
        ] {
            let q = e.embed(&[query.to_string()]).unwrap().remove(0);
            let sims = idx.similarities(q).unwrap();
            let results = rank(&c, Some(&sims), query, &SearchOptions::default());
            assert_eq!(results[0].id, expected, "query: {query}");
        }
    }
}
