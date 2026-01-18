//! Trust-level bucketing for GitHub comments.
//!
//! This module provides utilities for categorizing comments by author trust level
//! based on the security configuration in .agents.yaml.
//!
//! Trust levels (in order of authority):
//! - ADMIN: agent_admins - users authorized to direct agent implementation
//! - TRUSTED: trusted_sources - vetted automation and bots (excludes admins)
//! - COMMUNITY: all other commenters - consider but verify

use lazy_static::lazy_static;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use crate::error::{BoardError, Result};

/// Trust levels for comment authors.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TrustLevel {
    /// agent_admins - highest authority
    Admin,
    /// trusted_sources - vetted automation
    Trusted,
    /// everyone else
    Community,
}

impl std::fmt::Display for TrustLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TrustLevel::Admin => write!(f, "admin"),
            TrustLevel::Trusted => write!(f, "trusted"),
            TrustLevel::Community => write!(f, "community"),
        }
    }
}

/// Configuration for trust-level determination.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct TrustConfig {
    pub agent_admins: Vec<String>,
    pub trusted_sources: Vec<String>,
}

/// Structure for .agents.yaml file
#[derive(Debug, Clone, Default, Deserialize)]
struct AgentsYamlFile {
    #[serde(default)]
    security: SecuritySection,
}

#[derive(Debug, Clone, Default, Deserialize)]
struct SecuritySection {
    #[serde(default)]
    agent_admins: Vec<String>,
    #[serde(default)]
    trusted_sources: Vec<String>,
}

impl TrustConfig {
    /// Load trust configuration from .agents.yaml.
    pub fn from_yaml(config_path: Option<&Path>) -> Result<Self> {
        let path = if let Some(p) = config_path {
            if p.exists() {
                Some(p.to_path_buf())
            } else {
                None
            }
        } else {
            Self::find_config_file()
        };

        match path {
            Some(p) => Self::load_from_path(&p),
            None => Ok(Self::default()),
        }
    }

    /// Find .agents.yaml from current directory up.
    fn find_config_file() -> Option<PathBuf> {
        let mut current_dir = std::env::current_dir().ok()?;

        loop {
            let potential_config = current_dir.join(".agents.yaml");
            if potential_config.exists() {
                return Some(potential_config);
            }

            if !current_dir.pop() {
                break;
            }
        }

        None
    }

    /// Load configuration from a specific path.
    fn load_from_path(path: &Path) -> Result<Self> {
        let content = fs::read_to_string(path)
            .map_err(|e| BoardError::Config(format!("Failed to read .agents.yaml: {}", e)))?;

        let config: AgentsYamlFile = serde_yaml::from_str(&content)
            .map_err(|e| BoardError::Config(format!("Failed to parse .agents.yaml: {}", e)))?;

        Ok(Self {
            agent_admins: config.security.agent_admins,
            trusted_sources: config.security.trusted_sources,
        })
    }
}

lazy_static! {
    /// Patterns for automated noise that should be filtered out.
    static ref NOISE_PATTERNS: Vec<Regex> = vec![
        // Agent claim comments
        Regex::new(r"^🤖 \*\*\[Agent Claim\]\*\*").unwrap(),
        // Simple approval triggers (just "[Approved][Agent]" with no other content)
        Regex::new(r"^\[Approved\]\[[^\]]+\]$").unwrap(),
    ];
}

/// A comment with author information.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Comment {
    pub id: Option<String>,
    pub body: String,
    pub author: String,
    #[serde(rename = "createdAt")]
    pub created_at: Option<String>,
}

impl Comment {
    /// Create a comment from a JSON value.
    pub fn from_json(value: &serde_json::Value) -> Option<Self> {
        let body = value.get("body")?.as_str()?.to_string();
        let author = match value.get("author") {
            Some(serde_json::Value::String(s)) => s.clone(),
            Some(serde_json::Value::Object(obj)) => obj.get("login")?.as_str()?.to_string(),
            _ => "unknown".to_string(),
        };
        let id = value
            .get("id")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let created_at = value
            .get("createdAt")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        Some(Self {
            id,
            body,
            author,
            created_at,
        })
    }
}

/// Buckets comments by author trust level.
#[derive(Debug, Clone)]
pub struct TrustBucketer {
    config: TrustConfig,
    admins: HashSet<String>,
    trusted: HashSet<String>,
}

impl TrustBucketer {
    /// Create a new trust bucketer.
    pub fn new(config: TrustConfig) -> Self {
        let admins: HashSet<String> = config.agent_admins.iter().cloned().collect();
        let trusted: HashSet<String> = config
            .trusted_sources
            .iter()
            .filter(|s| !admins.contains(*s))
            .cloned()
            .collect();

        Self {
            config,
            admins,
            trusted,
        }
    }

    /// Create a new trust bucketer from .agents.yaml.
    pub fn from_yaml(config_path: Option<&Path>) -> Result<Self> {
        let config = TrustConfig::from_yaml(config_path)?;
        Ok(Self::new(config))
    }

    /// Determine the trust level for a username.
    pub fn get_trust_level(&self, username: &str) -> TrustLevel {
        if self.admins.contains(username) {
            TrustLevel::Admin
        } else if self.trusted.contains(username) {
            TrustLevel::Trusted
        } else {
            TrustLevel::Community
        }
    }

    /// Check if a comment body is automated noise.
    pub fn is_noise(&self, body: &str) -> bool {
        if body.is_empty() {
            return true;
        }

        let trimmed = body.trim();
        NOISE_PATTERNS
            .iter()
            .any(|pattern| pattern.is_match(trimmed))
    }

    /// Bucket comments by author trust level.
    pub fn bucket_comments<'a>(
        &self,
        comments: &'a [Comment],
        filter_noise: bool,
    ) -> HashMap<TrustLevel, Vec<&'a Comment>> {
        let mut buckets: HashMap<TrustLevel, Vec<&'a Comment>> = HashMap::new();
        buckets.insert(TrustLevel::Admin, Vec::new());
        buckets.insert(TrustLevel::Trusted, Vec::new());
        buckets.insert(TrustLevel::Community, Vec::new());

        for comment in comments {
            // Skip noise if filtering enabled
            if filter_noise && self.is_noise(&comment.body) {
                continue;
            }

            let trust_level = self.get_trust_level(&comment.author);
            buckets.get_mut(&trust_level).unwrap().push(comment);
        }

        buckets
    }

    /// Bucket comments and format as markdown.
    pub fn format_bucketed_comments(
        &self,
        comments: &[Comment],
        filter_noise: bool,
        include_empty_buckets: bool,
    ) -> String {
        let buckets = self.bucket_comments(comments, filter_noise);
        let mut output = String::new();

        // Admin guidance (highest trust)
        let admin_comments = &buckets[&TrustLevel::Admin];
        if !admin_comments.is_empty() {
            output.push_str("## Admin Guidance (Highest Trust)\n");
            output.push_str(
                "Comments from repository administrators with authority to direct implementation:\n\n",
            );
            for comment in admin_comments {
                output.push_str(&self.format_comment(comment));
            }
        } else if include_empty_buckets {
            output.push_str("## Admin Guidance (Highest Trust)\n\n_No admin comments._\n\n");
        }

        // Trusted context (medium trust)
        let trusted_comments = &buckets[&TrustLevel::Trusted];
        if !trusted_comments.is_empty() {
            output.push_str("## Trusted Context (Medium Trust)\n");
            output.push_str("Comments from trusted automation and vetted sources:\n\n");
            for comment in trusted_comments {
                output.push_str(&self.format_comment(comment));
            }
        } else if include_empty_buckets {
            output.push_str("## Trusted Context (Medium Trust)\n\n_No trusted comments._\n\n");
        }

        // Community input (review carefully)
        let community_comments = &buckets[&TrustLevel::Community];
        if !community_comments.is_empty() {
            output.push_str("## Community Input (Review Carefully)\n");
            output.push_str("Comments from other sources - consider but verify:\n\n");
            for comment in community_comments {
                output.push_str(&self.format_comment(comment));
            }
        } else if include_empty_buckets {
            output
                .push_str("## Community Input (Review Carefully)\n\n_No community comments._\n\n");
        }

        output.trim_end_matches(&['\n', '-'][..]).to_string()
    }

    /// Format a single comment as markdown.
    fn format_comment(&self, comment: &Comment) -> String {
        let date = comment
            .created_at
            .as_ref()
            .map(|s| &s[..10.min(s.len())])
            .unwrap_or("unknown date");

        format!(
            "### {} ({})\n\n{}\n\n---\n\n",
            comment.author, date, comment.body
        )
    }

    /// Get the underlying config.
    pub fn config(&self) -> &TrustConfig {
        &self.config
    }
}

/// Convenience function to bucket and format comments for agent context.
pub fn bucket_comments_for_context(
    comments: &[Comment],
    config_path: Option<&Path>,
) -> Result<String> {
    let bucketer = TrustBucketer::from_yaml(config_path)?;
    Ok(bucketer.format_bucketed_comments(comments, true, false))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_comment(author: &str, body: &str) -> Comment {
        Comment {
            id: None,
            body: body.to_string(),
            author: author.to_string(),
            created_at: Some("2024-01-15T10:00:00Z".to_string()),
        }
    }

    #[test]
    fn test_trust_level_determination() {
        let config = TrustConfig {
            agent_admins: vec!["admin_user".to_string()],
            trusted_sources: vec!["bot_user".to_string(), "admin_user".to_string()],
        };
        let bucketer = TrustBucketer::new(config);

        assert_eq!(bucketer.get_trust_level("admin_user"), TrustLevel::Admin);
        assert_eq!(bucketer.get_trust_level("bot_user"), TrustLevel::Trusted);
        assert_eq!(
            bucketer.get_trust_level("random_user"),
            TrustLevel::Community
        );
    }

    #[test]
    fn test_noise_detection() {
        let bucketer = TrustBucketer::new(TrustConfig::default());

        assert!(bucketer.is_noise(""));
        assert!(bucketer.is_noise("🤖 **[Agent Claim]** something"));
        assert!(bucketer.is_noise("[Approved][Claude]"));
        assert!(!bucketer.is_noise("This is a real comment"));
    }

    #[test]
    fn test_bucket_comments() {
        let config = TrustConfig {
            agent_admins: vec!["admin".to_string()],
            trusted_sources: vec!["bot".to_string()],
        };
        let bucketer = TrustBucketer::new(config);

        let comments = vec![
            make_comment("admin", "Admin feedback"),
            make_comment("bot", "Bot message"),
            make_comment("user", "Community input"),
            make_comment("user2", "[Approved][Claude]"), // noise
        ];

        let buckets = bucketer.bucket_comments(&comments, true);

        assert_eq!(buckets[&TrustLevel::Admin].len(), 1);
        assert_eq!(buckets[&TrustLevel::Trusted].len(), 1);
        assert_eq!(buckets[&TrustLevel::Community].len(), 1); // noise filtered
    }

    #[test]
    fn test_format_bucketed_comments() {
        let config = TrustConfig {
            agent_admins: vec!["admin".to_string()],
            trusted_sources: vec![],
        };
        let bucketer = TrustBucketer::new(config);

        let comments = vec![
            make_comment("admin", "Please fix this issue"),
            make_comment("user", "I think there's a bug"),
        ];

        let formatted = bucketer.format_bucketed_comments(&comments, true, false);

        assert!(formatted.contains("## Admin Guidance"));
        assert!(formatted.contains("Please fix this issue"));
        assert!(formatted.contains("## Community Input"));
        assert!(formatted.contains("I think there's a bug"));
    }
}
