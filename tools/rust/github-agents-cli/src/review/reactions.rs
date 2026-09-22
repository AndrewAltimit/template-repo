//! Reaction image URL handling.
//!
//! Fetches the reaction catalog and rewrites shorthand/relative reaction
//! references in reviews into full image URLs.

use regex::Regex;
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::LazyLock;
use std::time::Duration;

use crate::error::{Error, Result};

/// Default reaction config URL
const DEFAULT_REACTION_CONFIG_URL: &str =
    "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml";

/// Markdown image: `![alt](url)`
static IMG_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"!\[([^\]]*)\]\(([^)]+)\)").expect("valid image regex"));

/// Reaction shorthand: `:reaction_name:`
static SHORTHAND_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r":([a-zA-Z0-9_]+):").expect("valid shorthand regex"));

/// Raw reaction configuration from the remote config (actual YAML format)
#[derive(Debug, Deserialize)]
struct RawReactionConfig {
    reaction_images: Vec<RawReactionInfo>,
}

/// Raw information about a single reaction
#[derive(Debug, Deserialize)]
struct RawReactionInfo {
    id: String,
    source_url: String,
}

/// Reaction catalog: reaction id -> full image URL
#[derive(Debug, Default)]
pub struct ReactionConfig {
    pub reactions: HashMap<String, String>,
}

/// Fetch reaction config from the remote URL
pub async fn fetch_reaction_config(config_url: Option<&str>) -> Result<ReactionConfig> {
    let url = config_url.unwrap_or(DEFAULT_REACTION_CONFIG_URL);

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(30))
        .build()?;

    let response = client.get(url).send().await?;
    if !response.status().is_success() {
        return Err(Error::Config(format!(
            "Failed to fetch reaction config: HTTP {}",
            response.status()
        )));
    }

    let text = response.text().await?;
    parse_reaction_config(&text)
}

fn parse_reaction_config(yaml: &str) -> Result<ReactionConfig> {
    let raw: RawReactionConfig =
        serde_yaml::from_str(yaml).map_err(|e| Error::Config(format!("Invalid YAML: {}", e)))?;
    let reactions: HashMap<String, String> = raw
        .reaction_images
        .into_iter()
        .map(|r| (r.id, r.source_url))
        .collect();
    tracing::debug!("Loaded {} reactions from config", reactions.len());
    Ok(ReactionConfig { reactions })
}

/// Fix reaction image URLs in a review
///
/// Converts relative/shorthand reaction references to full URLs.
pub fn fix_reaction_urls(review: &str, config: &ReactionConfig) -> String {
    let mut result = review.to_string();

    for captures in IMG_RE.captures_iter(review) {
        let full_match = &captures[0];
        let alt = &captures[1];
        let url = &captures[2];

        if url.starts_with("http://") || url.starts_with("https://") {
            continue;
        }

        let key = if alt.is_empty() { url } else { alt };
        let reaction_name = key.to_lowercase().replace(' ', "_");
        if let Some(source) = config.reactions.get(&reaction_name) {
            result = result.replace(full_match, &format!("![{}]({})", alt, source));
        }
    }

    for captures in SHORTHAND_RE.captures_iter(review) {
        let full_match = &captures[0];
        let name = &captures[1];
        if let Some(source) = config.reactions.get(name) {
            result = result.replace(full_match, &format!("![{}]({})", name, source));
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> ReactionConfig {
        let mut reactions = HashMap::new();
        reactions.insert(
            "happy".to_string(),
            "https://example.com/reactions/happy.gif".to_string(),
        );
        reactions.insert(
            "confused".to_string(),
            "https://example.com/reactions/confused.png".to_string(),
        );
        ReactionConfig { reactions }
    }

    #[test]
    fn test_fix_shorthand_reactions() {
        let fixed = fix_reaction_urls("Great work! :happy:", &test_config());
        assert!(fixed.contains("![happy](https://example.com/reactions/happy.gif)"));
    }

    #[test]
    fn test_fix_relative_image() {
        let fixed = fix_reaction_urls("![Confused](confused.png)", &test_config());
        assert_eq!(
            fixed,
            "![Confused](https://example.com/reactions/confused.png)"
        );
        // Full URLs are left alone
        let s = "![happy](https://other/x.gif)";
        assert_eq!(fix_reaction_urls(s, &test_config()), s);
    }

    #[test]
    fn test_parse_reaction_config() {
        let yaml = r#"
reaction_images:
  - id: miku_typing
    source_url: https://example.com/miku.webp
    description: typing
    tags: [work]
"#;
        let config = parse_reaction_config(yaml).unwrap();
        assert_eq!(
            config.reactions.get("miku_typing").map(String::as_str),
            Some("https://example.com/miku.webp")
        );
        assert!(parse_reaction_config("nope: 1").is_err());
    }
}
