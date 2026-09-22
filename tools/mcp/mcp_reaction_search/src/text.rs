//! Lightweight lexical matching: tokenizer, suffix stemmer, and a BM25 index.
//!
//! Used two ways:
//! - as a small keyword/tag boost on top of semantic similarity (hybrid
//!   ranking), which rescues exact-intent queries like "smug" or a character
//!   name that the embedding model ranks loosely;
//! - as the complete ranking when the embedding model is unavailable
//!   (offline, first-download still in progress, or load failure).

use std::collections::{HashMap, HashSet};

use crate::types::Reaction;

/// Words that carry no search signal in reaction queries.
#[rustfmt::skip]
const STOPWORDS: &[&str] = &[
    "a", "about", "after", "again", "all", "an", "and", "any", "are", "as", "at",
    "be", "been", "before", "being", "but", "by", "can", "could", "do", "does", "doing", "for",
    "from", "get", "getting", "got", "had", "has", "have", "having", "he", "her", "him", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "just", "me", "more", "my", "of", "on",
    "or", "our", "out", "over", "she", "so", "some", "someone", "something", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "to", "too", "up", "us",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "why", "will",
    "with", "would", "you", "your",
];

/// Reduce a lowercase word to a crude stem so that inflections match
/// ("celebrating"/"celebrate" -> "celebrat", "annoyed"/"annoying" -> "annoy").
pub fn stem(word: &str) -> String {
    let mut w = word;
    for suffix in ["ing", "ed", "es", "s"] {
        if let Some(stripped) = w.strip_suffix(suffix)
            && stripped.len() >= 3
            && !(suffix == "s" && stripped.ends_with('s'))
        {
            w = stripped;
            break;
        }
    }
    let w = w.strip_suffix('e').filter(|s| s.len() >= 4).unwrap_or(w);
    let w = w.strip_suffix('y').filter(|s| s.len() >= 4).unwrap_or(w);
    w.to_string()
}

/// Lowercase, split on non-alphanumerics, drop stopwords and 1-char tokens,
/// then stem.
pub fn tokenize(text: &str) -> Vec<String> {
    text.to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|t| t.len() >= 2 && !STOPWORDS.contains(t))
        .map(stem)
        .collect()
}

/// Per-field weights for the lexical index. Tags and ids are curated
/// keywords, so they count most; appearance mostly carries character names.
const W_TAGS: f32 = 3.0;
const W_ID: f32 = 2.0;
const W_DESCRIPTION: f32 = 2.0;
const W_SCENARIOS: f32 = 1.0;
const W_APPEARANCE: f32 = 0.5;

const BM25_K1: f32 = 1.2;
const BM25_B: f32 = 0.75;

/// BM25 index over weighted reaction fields.
#[derive(Debug, Clone, Default)]
pub struct LexicalIndex {
    /// Weighted term frequency per document.
    docs: Vec<HashMap<String, f32>>,
    /// Weighted document length.
    doc_len: Vec<f32>,
    avg_len: f32,
    /// Number of documents containing each term.
    df: HashMap<String, usize>,
    /// Stemmed tag tokens per document, for exact tag hits.
    tag_terms: Vec<HashSet<String>>,
}

impl LexicalIndex {
    /// Build the index from reactions (document order is preserved).
    pub fn build(reactions: &[Reaction]) -> Self {
        let mut idx = Self::default();
        for r in reactions {
            let mut tf: HashMap<String, f32> = HashMap::new();
            let mut add = |text: &str, weight: f32| {
                for tok in tokenize(text) {
                    *tf.entry(tok).or_insert(0.0) += weight;
                }
            };
            add(&r.tags.join(" "), W_TAGS);
            add(&r.id, W_ID);
            add(&r.description, W_DESCRIPTION);
            add(&r.usage_scenarios.join(" "), W_SCENARIOS);
            add(&r.character_appearance, W_APPEARANCE);

            for term in tf.keys() {
                *idx.df.entry(term.clone()).or_insert(0) += 1;
            }
            idx.doc_len.push(tf.values().sum());
            idx.docs.push(tf);
            idx.tag_terms
                .push(r.tags.iter().flat_map(|t| tokenize(t)).collect());
        }
        let n = idx.docs.len().max(1) as f32;
        idx.avg_len = (idx.doc_len.iter().sum::<f32>() / n).max(1.0);
        idx
    }

    /// Raw BM25 score of `query` against every document.
    pub fn scores(&self, query: &str) -> Vec<f32> {
        let n = self.docs.len() as f32;
        let mut terms = tokenize(query);
        terms.sort();
        terms.dedup();

        self.docs
            .iter()
            .zip(&self.doc_len)
            .map(|(tf, &len)| {
                terms
                    .iter()
                    .filter_map(|t| {
                        let f = *tf.get(t)?;
                        let df = *self.df.get(t)? as f32;
                        let idf = ((n - df + 0.5) / (df + 0.5) + 1.0).ln();
                        let norm = BM25_K1 * (1.0 - BM25_B + BM25_B * len / self.avg_len);
                        Some(idf * f * (BM25_K1 + 1.0) / (f + norm))
                    })
                    .sum()
            })
            .collect()
    }

    /// BM25 scores scaled so the best document scores 1.0 (all zeros if
    /// nothing matched).
    pub fn normalized_scores(&self, query: &str) -> Vec<f32> {
        let mut scores = self.scores(query);
        let max = scores.iter().copied().fold(0.0f32, f32::max);
        if max > 0.0 {
            for s in &mut scores {
                *s /= max;
            }
        }
        scores
    }

    /// For each document, whether any query term exactly matches one of its
    /// (stemmed) tags.
    pub fn tag_hits(&self, query: &str) -> Vec<bool> {
        let terms: HashSet<String> = tokenize(query).into_iter().collect();
        self.tag_terms
            .iter()
            .map(|tags| tags.iter().any(|t| terms.contains(t)))
            .collect()
    }
}

/// Levenshtein edit distance (for "did you mean" id suggestions).
pub fn edit_distance(a: &str, b: &str) -> usize {
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut cur = vec![0; b.len() + 1];
    for (i, ca) in a.chars().enumerate() {
        cur[0] = i + 1;
        for (j, &cb) in b.iter().enumerate() {
            let cost = usize::from(ca != cb);
            cur[j + 1] = (prev[j + 1] + 1).min(cur[j] + 1).min(prev[j] + cost);
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[b.len()]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::reaction;

    #[test]
    fn stemming_unifies_inflections() {
        assert_eq!(stem("celebrating"), stem("celebrate"));
        assert_eq!(stem("annoyed"), stem("annoying"));
        assert_eq!(stem("confused"), stem("confusing"));
        assert_eq!(stem("tests"), stem("test"));
        assert_eq!(stem("happy"), stem("happy"));
        // Short words are left alone.
        assert_eq!(stem("sad"), "sad");
        assert_eq!(stem("glass"), "glass");
    }

    #[test]
    fn tokenize_drops_stopwords_and_punctuation() {
        assert_eq!(
            tokenize("Celebrating after fixing a bug!"),
            vec![stem("celebrating"), stem("fixing"), "bug".to_string()]
        );
        assert!(tokenize("the a of I").is_empty());
        assert_eq!(
            tokenize("gathering-thoughts"),
            vec![stem("gathering"), stem("thoughts")]
        );
    }

    fn corpus() -> Vec<Reaction> {
        vec![
            reaction(
                "felix",
                "Happy cheerful expression",
                &["happy", "excited"],
                &["Celebrating good news"],
            ),
            reaction(
                "confused",
                "Confused questioning look",
                &["confused", "puzzled"],
                &["When you don't understand"],
            ),
            reaction(
                "kagami_annoyed",
                "Irritated glare",
                &["annoyed", "irritated"],
                &["When something is frustrating"],
            ),
        ]
    }

    #[test]
    fn bm25_ranks_matching_document_first() {
        let idx = LexicalIndex::build(&corpus());
        let scores = idx.normalized_scores("so confused by this error");
        assert_eq!(scores[1], 1.0);
        assert_eq!(scores[0], 0.0);
        let scores = idx.normalized_scores("annoying failures");
        assert!(scores[2] > scores[0] && scores[2] > scores[1]);
    }

    #[test]
    fn id_tokens_are_searchable() {
        let idx = LexicalIndex::build(&corpus());
        let scores = idx.normalized_scores("kagami");
        assert_eq!(scores[2], 1.0);
    }

    #[test]
    fn no_match_yields_zeros() {
        let idx = LexicalIndex::build(&corpus());
        assert!(idx.normalized_scores("xyzzy").iter().all(|&s| s == 0.0));
        assert!(idx.normalized_scores("").iter().all(|&s| s == 0.0));
    }

    #[test]
    fn tag_hits_match_stemmed_tags() {
        let idx = LexicalIndex::build(&corpus());
        assert_eq!(idx.tag_hits("feeling annoyed"), vec![false, false, true]);
        assert_eq!(idx.tag_hits("excitement"), vec![false, false, false]);
    }

    #[test]
    fn edit_distance_basics() {
        assert_eq!(edit_distance("felix", "felix"), 0);
        assert_eq!(edit_distance("felx", "felix"), 1);
        assert_eq!(edit_distance("", "abc"), 3);
        assert_eq!(edit_distance("kitten", "sitting"), 3);
    }
}
