//! Data types for reaction search.

use serde::{Deserialize, Serialize};

/// A reaction image from the config
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Reaction {
    /// Unique identifier
    pub id: String,
    /// Source URL (optional, constructed if missing)
    #[serde(default)]
    pub source_url: Option<String>,
    /// Human-readable description
    #[serde(default)]
    pub description: String,
    /// Tags for categorization (emotions, actions)
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
    /// Get the full URL to the reaction image
    pub fn url(&self) -> String {
        self.source_url.clone().unwrap_or_else(|| {
            format!(
                "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/{}.webp",
                self.id
            )
        })
    }

    /// Get markdown for embedding the image
    pub fn markdown(&self) -> String {
        format!("![Reaction]({})", self.url())
    }

    /// Build searchable text from all fields
    pub fn searchable_text(&self) -> String {
        let mut parts = Vec::new();

        if !self.description.is_empty() {
            parts.push(self.description.clone());
        }

        if !self.usage_scenarios.is_empty() {
            parts.push(self.usage_scenarios.join(" "));
        }

        if !self.tags.is_empty() {
            parts.push(self.tags.join(" "));
        }

        if !self.character_appearance.is_empty() {
            parts.push(self.character_appearance.clone());
        }

        parts.join(" ")
    }
}

/// A search result with similarity score
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
    /// Similarity score (0-1)
    pub similarity: f32,
    /// Tags for categorization
    pub tags: Vec<String>,
    /// Example usage scenarios
    pub usage_scenarios: Vec<String>,
    /// Visual appearance description
    pub character_appearance: String,
}

impl ReactionResult {
    /// Create a result from a reaction with similarity score
    pub fn from_reaction(reaction: &Reaction, similarity: f32) -> Self {
        Self {
            id: reaction.id.clone(),
            url: reaction.url(),
            markdown: reaction.markdown(),
            description: reaction.description.clone(),
            similarity: (similarity * 10000.0).round() / 10000.0, // Round to 4 decimals
            tags: reaction.tags.clone(),
            usage_scenarios: reaction.usage_scenarios.clone(),
            character_appearance: reaction.character_appearance.clone(),
        }
    }
}

/// Config file structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReactionConfig {
    /// List of reaction images
    #[serde(default)]
    pub reaction_images: Vec<Reaction>,
}

/// Cache metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheMeta {
    /// Unix timestamp when cached
    pub cached_at: f64,
    /// Source URL
    pub source_url: String,
    /// Number of reactions
    pub reaction_count: usize,
}

/// Engine status information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineStatus {
    /// Whether the engine is initialized
    pub initialized: bool,
    /// Model name
    pub model_name: String,
    /// Number of reactions
    pub reaction_count: usize,
    /// Number of unique tags
    pub unique_tags: usize,
    /// Embeddings shape [rows, cols]
    pub embeddings_shape: [usize; 2],
}

/// Cache status information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheStatus {
    /// Cache directory path
    pub cache_dir: String,
    /// Whether cache file exists
    pub cache_file_exists: bool,
    /// Whether cache is valid (within TTL)
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
    /// Hours until cache expires
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cache_expires_in_hours: Option<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reaction_url() {
        let reaction = Reaction {
            id: "test".to_string(),
            source_url: None,
            description: "Test".to_string(),
            tags: vec![],
            usage_scenarios: vec![],
            character_appearance: String::new(),
        };

        assert!(reaction.url().contains("test.webp"));
        assert!(reaction.markdown().contains("![Reaction]"));
    }

    #[test]
    fn test_searchable_text() {
        let reaction = Reaction {
            id: "happy".to_string(),
            source_url: None,
            description: "Happy anime girl".to_string(),
            tags: vec!["happy".to_string(), "excited".to_string()],
            usage_scenarios: vec!["Celebrating".to_string()],
            character_appearance: "Pink hair".to_string(),
        };

        let text = reaction.searchable_text();
        assert!(text.contains("Happy anime girl"));
        assert!(text.contains("happy excited"));
        assert!(text.contains("Celebrating"));
        assert!(text.contains("Pink hair"));
    }

    #[test]
    fn test_reaction_result_similarity_rounding() {
        let reaction = Reaction {
            id: "test".to_string(),
            source_url: None,
            description: "Test".to_string(),
            tags: vec![],
            usage_scenarios: vec![],
            character_appearance: String::new(),
        };

        let result = ReactionResult::from_reaction(&reaction, 0.876_543_2);
        assert_eq!(result.similarity, 0.8765);
    }
}
