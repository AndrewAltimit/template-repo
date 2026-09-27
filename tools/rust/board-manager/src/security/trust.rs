//! Trust-level bucketing for GitHub comments.
//!
//! Categorizes comments by author trust level based on the security
//! configuration in `.agents.yaml`.
//!
//! Trust levels (in order of authority):
//! - ADMIN: `agent_admins` - users authorized to direct agent implementation
//! - TRUSTED: `trusted_sources` - vetted automation and bots (excludes admins)
//! - COMMUNITY: all other commenters - consider but verify

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;
use std::sync::LazyLock;

use trust_common::{Fallback, TrustError, TrustPolicy};
pub use trust_common::{TrustConfig, TrustLevel};

use crate::error::{BoardError, Result};

/// Markdown section heading, intro line and empty-bucket text for a level.
fn section(level: TrustLevel) -> (&'static str, &'static str, &'static str) {
    match level {
        TrustLevel::Admin => (
            "## Admin Guidance (Highest Trust)",
            "Comments from repository administrators with authority to direct implementation:",
            "_No admin comments._",
        ),
        TrustLevel::Trusted => (
            "## Trusted Context (Medium Trust)",
            "Comments from trusted automation and vetted sources:",
            "_No trusted comments._",
        ),
        TrustLevel::Community => (
            "## Community Input (Review Carefully)",
            "Comments from other sources - consider but verify:",
            "_No community comments._",
        ),
    }
}

/// Load trust configuration from `.agents.yaml` (shared `trust-common`
/// implementation).
///
/// `config_path` defaults to the first `.agents.yaml` in the current
/// directory or a parent. Fails closed ([`Fallback::Error`]): a missing or
/// unparseable file is an error. In a PR-triggered run where the PR modifies
/// the file, the base-branch version is used.
pub fn load_trust_config(config_path: Option<&Path>) -> Result<TrustConfig> {
    let path = match config_path {
        Some(p) => p.to_path_buf(),
        None => std::env::current_dir()
            .ok()
            .and_then(|cwd| trust_common::find_config_file(&cwd))
            .ok_or_else(|| {
                BoardError::Config(
                    "No .agents.yaml found. Trust bucketing requires a security config file."
                        .to_string(),
                )
            })?,
    };
    TrustConfig::load(&path, Fallback::Error, &mut |m: &str| {
        tracing::warn!("{}", m)
    })
    .map_err(|e| match e {
        TrustError::NotFound(p) => {
            BoardError::Config(format!("Security config file not found: {}", p.display()))
        },
        other => BoardError::Config(other.to_string()),
    })
}

/// Patterns for automated noise that should be filtered out.
static NOISE_PATTERNS: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    [
        // Board claim/renewal/release comments, with or without a leading
        // robot emoji (U+1F916) used by older versions.
        r"^(?:\x{1F916}\s*)?\*\*\[(?:Agent Claim|Claim Renewal|Agent Release)\]\*\*",
        // Bare approval triggers (just "[Approved][Agent]" with no other content)
        r"^\[Approved\]\[[^\]]+\]$",
    ]
    .iter()
    .map(|p| Regex::new(p).expect("noise regex is valid"))
    .collect()
});

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
    /// Create a comment from JSON in either GraphQL / `gh --json` shape
    /// (`author.login`, `createdAt`) or REST shape (`user.login`,
    /// `created_at`). Returns `None` only when there is no string `body`.
    pub fn from_json(value: &serde_json::Value) -> Option<Self> {
        let body = value.get("body")?.as_str()?.to_string();
        let login = |v: &serde_json::Value| match v {
            serde_json::Value::String(s) => Some(s.clone()),
            serde_json::Value::Object(obj) => obj.get("login")?.as_str().map(String::from),
            _ => None,
        };
        let author = value
            .get("author")
            .and_then(login)
            .or_else(|| value.get("user").and_then(login))
            .filter(|a| !a.is_empty())
            .unwrap_or_else(|| "unknown".to_string());
        let id = value.get("id").and_then(|v| match v {
            serde_json::Value::String(s) => Some(s.clone()),
            serde_json::Value::Number(n) => Some(n.to_string()),
            _ => None,
        });
        let created_at = value
            .get("createdAt")
            .or_else(|| value.get("created_at"))
            .and_then(|v| v.as_str())
            .map(String::from);

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
    policy: TrustPolicy,
}

impl TrustBucketer {
    /// Create a new trust bucketer.
    ///
    /// Matching is case-insensitive since GitHub usernames are
    /// case-insensitive; admins outrank trusted sources.
    pub fn new(config: TrustConfig) -> Self {
        Self {
            policy: config.policy(),
        }
    }

    /// Create a new trust bucketer from `.agents.yaml`.
    pub fn from_yaml(config_path: Option<&Path>) -> Result<Self> {
        Ok(Self::new(load_trust_config(config_path)?))
    }

    /// Determine the trust level for a username (case-insensitive).
    pub fn get_trust_level(&self, username: &str) -> TrustLevel {
        self.policy.level(username)
    }

    /// Check if a comment body is automated noise.
    pub fn is_noise(&self, body: &str) -> bool {
        let trimmed = body.trim();
        trimmed.is_empty() || NOISE_PATTERNS.iter().any(|p| p.is_match(trimmed))
    }

    /// Bucket comments by author trust level. Every level is present in the
    /// returned map, possibly with an empty list.
    pub fn bucket_comments<'a>(
        &self,
        comments: &'a [Comment],
        filter_noise: bool,
    ) -> HashMap<TrustLevel, Vec<&'a Comment>> {
        let mut buckets: HashMap<TrustLevel, Vec<&'a Comment>> =
            TrustLevel::ALL.iter().map(|l| (*l, Vec::new())).collect();

        for comment in comments {
            if filter_noise && self.is_noise(&comment.body) {
                continue;
            }
            buckets
                .entry(self.get_trust_level(&comment.author))
                .or_default()
                .push(comment);
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

        for level in TrustLevel::ALL {
            let (heading, intro, empty) = section(level);
            let bucket = buckets.get(&level).map(Vec::as_slice).unwrap_or_default();
            if !bucket.is_empty() {
                output.push_str(heading);
                output.push('\n');
                output.push_str(intro);
                output.push_str("\n\n");
                for comment in bucket {
                    output.push_str(&Self::format_comment(comment));
                }
            } else if include_empty_buckets {
                output.push_str(&format!("{}\n\n{}\n\n", heading, empty));
            }
        }

        // Drop the trailing separator after the last comment.
        let trimmed = output.trim_end();
        trimmed
            .strip_suffix("---")
            .unwrap_or(trimmed)
            .trim_end()
            .to_string()
    }

    /// Format a single comment as markdown.
    fn format_comment(comment: &Comment) -> String {
        let date = comment
            .created_at
            .as_deref()
            .map(|s| s.get(..10).unwrap_or(s))
            .unwrap_or("unknown date");

        format!(
            "### {} ({})\n\n{}\n\n---\n\n",
            comment.author, date, comment.body
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn make_comment(author: &str, body: &str) -> Comment {
        Comment {
            id: None,
            body: body.to_string(),
            author: author.to_string(),
            created_at: Some("2024-01-15T10:00:00Z".to_string()),
        }
    }

    #[test]
    fn trust_level_determination() {
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
    fn noise_detection() {
        let bucketer = TrustBucketer::new(TrustConfig::default());

        assert!(bucketer.is_noise(""));
        assert!(bucketer.is_noise("   "));
        assert!(bucketer.is_noise("\u{1F916} **[Agent Claim]** something"));
        assert!(bucketer.is_noise("**[Agent Claim]**\n\nAgent: `claude`"));
        assert!(bucketer.is_noise("**[Claim Renewal]**\n\nAgent: `claude`"));
        assert!(bucketer.is_noise("**[Agent Release]**\n\nAgent: `claude`"));
        assert!(bucketer.is_noise("[Approved][Claude]"));
        assert!(!bucketer.is_noise("[Approved][Claude] but also fix the tests"));
        assert!(!bucketer.is_noise("This is a real comment"));
    }

    #[test]
    fn bucket_comments_by_level() {
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
        assert_eq!(buckets[&TrustLevel::Community].len(), 1);

        let unfiltered = bucketer.bucket_comments(&comments, false);
        assert_eq!(unfiltered[&TrustLevel::Community].len(), 2);
    }

    #[test]
    fn format_bucketed_comments_sections() {
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
        assert!(formatted.contains("### admin (2024-01-15)"));
        assert!(formatted.contains("Please fix this issue"));
        assert!(formatted.contains("## Community Input"));
        assert!(!formatted.contains("## Trusted Context"));
        assert!(!formatted.ends_with("---"));

        let with_empty = bucketer.format_bucketed_comments(&comments, true, true);
        assert!(with_empty.contains("_No trusted comments._"));
    }

    #[test]
    fn case_insensitive_trust_levels() {
        let config = TrustConfig {
            agent_admins: vec!["AdminUser".to_string()],
            trusted_sources: vec!["BotUser".to_string()],
        };
        let bucketer = TrustBucketer::new(config);

        for name in ["AdminUser", "adminuser", "ADMINUSER"] {
            assert_eq!(bucketer.get_trust_level(name), TrustLevel::Admin);
        }
        for name in ["BotUser", "botuser", "BOTUSER"] {
            assert_eq!(bucketer.get_trust_level(name), TrustLevel::Trusted);
        }
    }

    #[test]
    fn comment_from_graphql_and_rest_json() {
        let gql = json!({
            "id": "IC_1", "body": "hi", "author": { "login": "alice" },
            "createdAt": "2024-01-01T00:00:00Z"
        });
        let c = Comment::from_json(&gql).unwrap();
        assert_eq!(c.author, "alice");
        assert_eq!(c.id.as_deref(), Some("IC_1"));
        assert_eq!(c.created_at.as_deref(), Some("2024-01-01T00:00:00Z"));

        // REST API shape (used by `gh api .../comments`)
        let rest = json!({
            "id": 123, "body": "hi", "user": { "login": "bob" },
            "created_at": "2024-02-01T00:00:00Z"
        });
        let c = Comment::from_json(&rest).unwrap();
        assert_eq!(c.author, "bob");
        assert_eq!(c.id.as_deref(), Some("123"));
        assert_eq!(c.created_at.as_deref(), Some("2024-02-01T00:00:00Z"));

        // Deleted user (author null) and string author
        let ghost = json!({ "body": "x", "author": null });
        assert_eq!(Comment::from_json(&ghost).unwrap().author, "unknown");
        let s = json!({ "body": "x", "author": "carol" });
        assert_eq!(Comment::from_json(&s).unwrap().author, "carol");

        assert!(Comment::from_json(&json!({ "author": "x" })).is_none());
    }

    #[test]
    fn short_or_non_ascii_dates_do_not_panic() {
        let bucketer = TrustBucketer::new(TrustConfig::default());
        let mut c = make_comment("u", "body");
        c.created_at = Some("2024\u{00e9}\u{00e9}\u{00e9}\u{00e9}".to_string());
        let out = bucketer.format_bucketed_comments(&[c], false, false);
        assert!(out.contains("### u ("));
        let mut c = make_comment("u", "body");
        c.created_at = Some("2024".to_string());
        assert!(
            bucketer
                .format_bucketed_comments(&[c], false, false)
                .contains("### u (2024)")
        );
    }

    #[test]
    fn parses_agents_yaml() {
        let yaml = "security:\n  agent_admins: [Alice]\n  trusted_sources: [bot]\nother: 1\n";
        let c = TrustConfig::from_yaml_str(yaml).unwrap();
        assert_eq!(c.agent_admins, vec!["Alice"]);
        assert_eq!(c.trusted_sources, vec!["bot"]);
        let err = load_trust_config(Some(Path::new("/nope/.agents.yaml"))).unwrap_err();
        assert!(err.to_string().contains("not found"), "{err}");
    }

    #[test]
    fn load_trust_config_fails_closed_on_invalid_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(".agents.yaml");
        std::fs::write(&path, "security:\n  agent_admins: solo\n").unwrap();
        assert!(load_trust_config(Some(&path)).is_err());
        assert!(TrustBucketer::from_yaml(Some(&path)).is_err());

        // A valid file without admins is accepted: nobody is elevated.
        std::fs::write(&path, "security:\n  trusted_sources: [bot]\n").unwrap();
        let b = TrustBucketer::from_yaml(Some(&path)).unwrap();
        assert_eq!(b.get_trust_level("bot"), TrustLevel::Trusted);
        assert_eq!(b.get_trust_level("andrewaltimit"), TrustLevel::Community);
    }
}
