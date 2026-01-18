//! Reaction image URL handling.
//!
//! Fetches and validates reaction image URLs from the configured repository.

use regex::Regex;
use serde::Deserialize;
use std::collections::HashMap;
use std::time::Duration;

use crate::error::{Error, Result};

/// Default reaction config URL
const DEFAULT_REACTION_CONFIG_URL: &str =
    "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml";

/// Raw reaction configuration from the remote config (actual YAML format)
#[derive(Debug, Deserialize)]
struct RawReactionConfig {
    /// List of reaction images
    reaction_images: Vec<RawReactionInfo>,
}

/// Raw information about a single reaction (actual YAML format)
#[derive(Debug, Deserialize)]
struct RawReactionInfo {
    /// Unique identifier for the reaction
    id: String,
    /// Full source URL for the reaction image
    source_url: String,
    /// Description of the reaction
    #[serde(default)]
    description: String,
    /// Tags for categorization
    #[serde(default)]
    tags: Vec<String>,
}

/// Processed reaction configuration (internal representation)
#[derive(Debug)]
pub struct ReactionConfig {
    /// Map of reaction IDs to their info
    pub reactions: HashMap<String, ReactionInfo>,
}

/// Information about a single reaction (internal representation)
#[derive(Debug)]
pub struct ReactionInfo {
    /// Full URL for the reaction image
    pub source_url: String,
    /// Description of the reaction
    pub description: String,
    /// Tags for categorization
    pub tags: Vec<String>,
}

/// Fetch reaction config from the remote URL
pub async fn fetch_reaction_config(config_url: Option<&str>) -> Result<ReactionConfig> {
    let url = config_url.unwrap_or(DEFAULT_REACTION_CONFIG_URL);

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .map_err(|e| Error::Http(e))?;

    let response = client.get(url).send().await.map_err(|e| Error::Http(e))?;

    if !response.status().is_success() {
        return Err(Error::Config(format!(
            "Failed to fetch reaction config: HTTP {}",
            response.status()
        )));
    }

    let text = response.text().await.map_err(|e| Error::Http(e))?;
    let raw_config: RawReactionConfig =
        serde_yaml::from_str(&text).map_err(|e| Error::Config(format!("Invalid YAML: {}", e)))?;

    // Convert raw config to internal representation
    let mut reactions = HashMap::new();
    for raw in raw_config.reaction_images {
        reactions.insert(
            raw.id,
            ReactionInfo {
                source_url: raw.source_url,
                description: raw.description,
                tags: raw.tags,
            },
        );
    }

    tracing::debug!("Loaded {} reactions from config", reactions.len());

    Ok(ReactionConfig { reactions })
}

/// Fix reaction image URLs in a review
///
/// Converts shorthand reaction references to full URLs
pub fn fix_reaction_urls(review: &str, config: &ReactionConfig) -> String {
    let mut result = review.to_string();

    // Pattern to match markdown images: ![alt](url)
    let img_re = Regex::new(r"!\[([^\]]*)\]\(([^)]+)\)").unwrap();

    // Pattern to match reaction shorthand: :reaction_name:
    let shorthand_re = Regex::new(r":([a-zA-Z0-9_]+):").unwrap();

    // First, check if any existing image URLs need fixing
    for captures in img_re.captures_iter(review) {
        let full_match = captures.get(0).map(|m| m.as_str()).unwrap_or("");
        let alt = captures.get(1).map(|m| m.as_str()).unwrap_or("");
        let url = captures.get(2).map(|m| m.as_str()).unwrap_or("");

        // Skip if URL is already a full URL
        if url.starts_with("http://") || url.starts_with("https://") {
            continue;
        }

        // Try to match the alt or URL to a known reaction
        let reaction_name = if !alt.is_empty() {
            alt.to_lowercase().replace(' ', "_")
        } else {
            url.to_lowercase().replace(' ', "_")
        };

        if let Some(info) = config.reactions.get(&reaction_name) {
            let replacement = format!("![{}]({})", alt, info.source_url);
            result = result.replace(full_match, &replacement);
        }
    }

    // Then, convert shorthand reactions to full markdown
    for captures in shorthand_re.captures_iter(review) {
        let full_match = captures.get(0).map(|m| m.as_str()).unwrap_or("");
        let name = captures.get(1).map(|m| m.as_str()).unwrap_or("");

        if let Some(info) = config.reactions.get(name) {
            let replacement = format!("![{}]({})", name, info.source_url);
            result = result.replace(full_match, &replacement);
        }
    }

    result
}

/// Validate that a review has exactly one reaction image at the end
pub fn validate_reaction_placement(review: &str) -> bool {
    let img_re = Regex::new(r"!\[([^\]]*)\]\(([^)]+)\)").unwrap();

    let matches: Vec<_> = img_re.find_iter(review).collect();

    if matches.len() != 1 {
        return false;
    }

    // Check that the reaction is near the end (within last 200 chars)
    if let Some(m) = matches.first() {
        let end_pos = review.len();
        let img_end = m.end();
        let remaining = &review[img_end..];

        // Allow only whitespace after the image
        remaining.trim().is_empty() || end_pos - img_end < 200
    } else {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> ReactionConfig {
        let mut reactions = HashMap::new();
        reactions.insert(
            "happy".to_string(),
            ReactionInfo {
                source_url: "https://example.com/reactions/happy.gif".to_string(),
                description: "Happy reaction".to_string(),
                tags: vec!["positive".to_string()],
            },
        );
        reactions.insert(
            "confused".to_string(),
            ReactionInfo {
                source_url: "https://example.com/reactions/confused.png".to_string(),
                description: "Confused reaction".to_string(),
                tags: vec!["neutral".to_string()],
            },
        );

        ReactionConfig { reactions }
    }

    #[test]
    fn test_fix_shorthand_reactions() {
        let config = test_config();
        let review = "Great work! :happy:";
        let fixed = fix_reaction_urls(review, &config);

        assert!(fixed.contains("![happy](https://example.com/reactions/happy.gif)"));
    }

    #[test]
    fn test_validate_reaction_placement() {
        let valid = "Review content here\n\n![reaction](https://example.com/img.gif)";
        assert!(validate_reaction_placement(valid));

        let no_reaction = "Review content without reaction";
        assert!(!validate_reaction_placement(no_reaction));

        let multiple = "![one](url1) content ![two](url2)";
        assert!(!validate_reaction_placement(multiple));
    }
}
