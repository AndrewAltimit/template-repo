//! Data types for reaction search.

use serde::{Deserialize, Serialize};

/// Base URL used to build an image URL for reactions that omit `source_url`.
pub const MEDIA_BASE_URL: &str =
    "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction";

/// A reaction image entry from the upstream config.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Reaction {
    /// Unique identifier (also the image file stem when `source_url` is absent)
    pub id: String,
    /// Source URL (optional, constructed from the id if missing)
    #[serde(default)]
    pub source_url: Option<String>,
    /// Human-readable description
    #[serde(default)]
    pub description: String,
    /// Tags for categorization (emotions, actions, characters)
    #[serde(default)]
    pub tags: Vec<String>,
    /// Example usage scenarios
    #[serde(default)]
    pub usage_scenarios: Vec<String>,
    /// Visual appearance description
    #[serde(default)]
    pub character_appearance: String,
}

impl Reaction {
    /// Full URL to the reaction image.
    ///
    /// Uses `source_url` when present and non-empty, otherwise falls back to
    /// `<MEDIA_BASE_URL>/<id>.webp`.
    pub fn url(&self) -> String {
        match self.source_url.as_deref().map(str::trim) {
            Some(url) if !url.is_empty() => url.to_string(),
            _ => format!("{MEDIA_BASE_URL}/{}.webp", self.id),
        }
    }

    /// Markdown snippet for embedding the image in a comment.
    pub fn markdown(&self) -> String {
        format!("![Reaction]({})", self.url())
    }

    /// Whether this reaction carries `tag` (case-insensitive).
    pub fn has_tag(&self, tag: &str) -> bool {
        self.tags.iter().any(|t| t.eq_ignore_ascii_case(tag))
    }

    /// Searchable text built from the semantic fields.
    ///
    /// The character appearance is intentionally excluded: it describes hair
    /// colour and clothing, which dilutes the emotional/situational meaning a
    /// query is matched against. (Appearance still participates in the lexical
    /// index, so searching for a character name keeps working.)
    pub fn searchable_text(&self) -> String {
        let mut parts: Vec<&str> = Vec::new();
        if !self.description.is_empty() {
            parts.push(&self.description);
        }
        let scenarios = self.usage_scenarios.join(". ");
        if !scenarios.is_empty() {
            parts.push(&scenarios);
        }
        let tags = self.tags.join(", ");
        if !tags.is_empty() {
            parts.push(&tags);
        }
        parts.join(". ")
    }
}

/// A search (or lookup) result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReactionResult {
    /// Unique identifier
    pub id: String,
    /// Full URL to the image
    pub url: String,
    /// Markdown for embedding
    pub markdown: String,
    /// Human-readable description
    pub description: String,
    /// Relevance of this reaction to the query in `[0, 1]`, rounded to 4
    /// decimals. In semantic mode this is the embedding cosine similarity; in
    /// lexical mode it is the keyword score normalized to the best match.
    pub similarity: f64,
    /// Final ranking score (similarity plus keyword/tag boosts). Results are
    /// sorted by this value.
    pub score: f64,
    /// Tags for categorization
    pub tags: Vec<String>,
    /// Example usage scenarios
    pub usage_scenarios: Vec<String>,
    /// Visual appearance description
    pub character_appearance: String,
}

/// Round to 4 decimal places as `f64`, so JSON shows `0.2781` rather than the
/// f32 widening artefact `0.27810001373291016`.
fn round4(x: f32) -> f64 {
    (f64::from(x) * 10000.0).round() / 10000.0
}

impl ReactionResult {
    /// Create a result from a reaction with a similarity and ranking score.
    pub fn from_reaction(reaction: &Reaction, similarity: f32, score: f32) -> Self {
        Self {
            id: reaction.id.clone(),
            url: reaction.url(),
            markdown: reaction.markdown(),
            description: reaction.description.clone(),
            similarity: round4(similarity),
            score: round4(score),
            tags: reaction.tags.clone(),
            usage_scenarios: reaction.usage_scenarios.clone(),
            character_appearance: reaction.character_appearance.clone(),
        }
    }
}

/// Compact listing entry used by `list_reactions`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReactionSummary {
    /// Unique identifier
    pub id: String,
    /// Human-readable description
    pub description: String,
    /// Tags for categorization
    pub tags: Vec<String>,
    /// Markdown for embedding
    pub markdown: String,
}

impl From<&Reaction> for ReactionSummary {
    fn from(r: &Reaction) -> Self {
        Self {
            id: r.id.clone(),
            description: r.description.clone(),
            tags: r.tags.clone(),
            markdown: r.markdown(),
        }
    }
}

/// Upstream config file structure.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ReactionConfig {
    /// List of reaction images
    #[serde(default)]
    pub reaction_images: Vec<Reaction>,
}

/// On-disk cache metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheMeta {
    /// Unix timestamp when cached
    pub cached_at: f64,
    /// Source URL
    pub source_url: String,
    /// Number of reactions
    pub reaction_count: usize,
}

/// Cache status information (reported by `reaction_search_status`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheStatus {
    /// Cache directory path
    pub cache_dir: String,
    /// Whether cache file exists
    pub cache_file_exists: bool,
    /// Whether cache is valid (within TTL and from the configured source)
    pub cache_valid: bool,
    /// Cache TTL in seconds
    pub cache_ttl_seconds: u64,
    /// Config source URL
    pub config_url: String,
    /// Unix timestamp when cached
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cached_at: Option<f64>,
    /// Number of cached reactions
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reaction_count: Option<usize>,
    /// Cache age in hours
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cache_age_hours: Option<f64>,
    /// Hours until cache expires (negative once expired)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cache_expires_in_hours: Option<f64>,
}

#[cfg(test)]
pub(crate) fn reaction(id: &str, description: &str, tags: &[&str], scenarios: &[&str]) -> Reaction {
    Reaction {
        id: id.to_string(),
        source_url: None,
        description: description.to_string(),
        tags: tags.iter().map(|s| s.to_string()).collect(),
        usage_scenarios: scenarios.iter().map(|s| s.to_string()).collect(),
        character_appearance: String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn url_falls_back_to_webp_when_missing_or_blank() {
        let mut r = reaction("test", "Test", &[], &[]);
        assert_eq!(r.url(), format!("{MEDIA_BASE_URL}/test.webp"));
        r.source_url = Some("   ".into());
        assert_eq!(r.url(), format!("{MEDIA_BASE_URL}/test.webp"));
        r.source_url = Some("https://example.com/a.gif".into());
        assert_eq!(r.url(), "https://example.com/a.gif");
        assert_eq!(r.markdown(), "![Reaction](https://example.com/a.gif)");
    }

    #[test]
    fn searchable_text_includes_semantic_fields_only() {
        let mut r = reaction(
            "happy",
            "Happy anime girl",
            &["happy", "excited"],
            &["Celebrating"],
        );
        r.character_appearance = "Pink hair".into();
        let text = r.searchable_text();
        assert!(text.contains("Happy anime girl"));
        assert!(text.contains("happy, excited"));
        assert!(text.contains("Celebrating"));
        assert!(!text.contains("Pink hair"));
    }

    #[test]
    fn has_tag_is_case_insensitive() {
        let r = reaction("x", "", &["Happy"], &[]);
        assert!(r.has_tag("happy"));
        assert!(r.has_tag("HAPPY"));
        assert!(!r.has_tag("sad"));
    }

    #[test]
    fn result_rounds_scores() {
        let r = reaction("test", "Test", &[], &[]);
        let result = ReactionResult::from_reaction(&r, 0.876_543_2, 0.912_345_6);
        assert_eq!(result.similarity, 0.8765);
        assert_eq!(result.score, 0.9123);
    }
}
