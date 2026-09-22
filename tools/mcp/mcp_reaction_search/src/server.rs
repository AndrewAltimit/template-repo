//! MCP tool definitions for reaction search.
//!
//! Arguments are deserialized into typed structs (never indexed out of raw
//! JSON), so malformed input becomes an `InvalidParameters` error instead of
//! a panic or a silently ignored value. The hand-written JSON schemas are kept
//! because they carry `items`, bounds, and `oneOf` details that the
//! `#[mcp_tool]` macro's derived schemas cannot express.

use std::collections::BTreeMap;
use std::sync::Arc;

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};

use crate::engine::{MAX_LIMIT, SearchOptions};
use crate::service::ReactionService;
use crate::types::{ReactionResult, ReactionSummary};

/// Longest accepted search query, in characters. The embedding model only
/// reads the first ~256 tokens anyway.
const MAX_QUERY_CHARS: usize = 1000;

/// Emotion tags surfaced as a category by `list_reaction_tags`.
const EMOTION_TAGS: &[&str] = &[
    "happy",
    "sad",
    "angry",
    "confused",
    "excited",
    "annoyed",
    "smug",
    "shocked",
    "surprised",
    "nervous",
    "bored",
    "content",
    "cheerful",
    "irritated",
    "disappointed",
    "embarrassed",
    "worried",
    "concerned",
    "unamused",
    "determined",
    "focused",
    "thoughtful",
    "frustrated",
    "amused",
    "playful",
];

/// Action tags surfaced as a category by `list_reaction_tags`.
const ACTION_TAGS: &[&str] = &[
    "typing",
    "thinking",
    "working",
    "gaming",
    "drinking",
    "eating",
    "waving",
    "cheering",
    "crying",
    "laughing",
    "giggling",
    "studying",
    "celebrating",
    "shrugging",
    "sipping",
    "glaring",
    "staring",
    "pouting",
    "facepalm",
    "sleeping",
    "writing",
];

/// Parse tool arguments into `T`, treating a missing/null argument object as
/// empty.
fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

/// A string or a list of strings (LLM clients often send a bare string where
/// a list is expected).
#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum OneOrMany {
    One(String),
    Many(Vec<String>),
}

impl OneOrMany {
    /// Trimmed, lowercased, non-empty values.
    fn normalized(self) -> Vec<String> {
        let v = match self {
            Self::One(s) => vec![s],
            Self::Many(v) => v,
        };
        v.into_iter()
            .map(|s| s.trim().to_lowercase())
            .filter(|s| !s.is_empty())
            .collect()
    }
}

fn normalized(v: Option<OneOrMany>) -> Vec<String> {
    v.map(OneOrMany::normalized).unwrap_or_default()
}

/// Validate a `limit` argument (accepts integers or integral floats) and
/// clamp it to `1..=max`.
fn parse_limit(limit: Option<f64>, default: usize, max: usize) -> Result<usize> {
    match limit {
        None => Ok(default),
        Some(l) if !l.is_finite() => Err(MCPError::InvalidParameters(
            "limit must be a finite number".into(),
        )),
        Some(l) => Ok((l.round().max(1.0) as usize).min(max)),
    }
}

/// Error result that still carries structured JSON (keeps the historical
/// `{"success": false, ...}` shape while flagging `isError` for clients).
fn json_error(value: &Value) -> Result<ToolResult> {
    let mut result = ToolResult::json(value)?;
    result.is_error = true;
    Ok(result)
}

/// Build all tools over a shared service.
pub fn tools(service: &Arc<ReactionService>) -> Vec<BoxedTool> {
    vec![
        Arc::new(SearchReactionsTool {
            service: Arc::clone(service),
        }),
        Arc::new(GetReactionTool {
            service: Arc::clone(service),
        }),
        Arc::new(ListReactionsTool {
            service: Arc::clone(service),
        }),
        Arc::new(ListReactionTagsTool {
            service: Arc::clone(service),
        }),
        Arc::new(RefreshReactionsTool {
            service: Arc::clone(service),
        }),
        Arc::new(ReactionSearchStatusTool {
            service: Arc::clone(service),
        }),
    ]
}

// ============================================================================
// Tool: search_reactions
// ============================================================================

struct SearchReactionsTool {
    service: Arc<ReactionService>,
}

#[derive(Debug, Deserialize)]
struct SearchArgs {
    query: String,
    #[serde(default)]
    limit: Option<f64>,
    #[serde(default)]
    tags: Option<OneOrMany>,
    #[serde(default)]
    exclude: Option<OneOrMany>,
    #[serde(default)]
    min_similarity: Option<f64>,
}

impl SearchArgs {
    fn validate(self) -> Result<(String, SearchOptions)> {
        let query = self.query.trim().to_string();
        if query.is_empty() {
            return Err(MCPError::InvalidParameters(
                "query must not be empty; describe the emotion or situation".into(),
            ));
        }
        if query.chars().count() > MAX_QUERY_CHARS {
            return Err(MCPError::InvalidParameters(format!(
                "query is too long (max {MAX_QUERY_CHARS} characters)"
            )));
        }
        let min_similarity = match self.min_similarity {
            None => 0.0,
            Some(m) if m.is_finite() && (0.0..=1.0).contains(&m) => m as f32,
            Some(m) => {
                return Err(MCPError::InvalidParameters(format!(
                    "min_similarity must be between 0 and 1 (got {m})"
                )));
            },
        };
        Ok((
            query,
            SearchOptions {
                limit: parse_limit(self.limit, 5, MAX_LIMIT)?,
                tags: normalized(self.tags),
                exclude: normalized(self.exclude),
                min_similarity,
            },
        ))
    }
}

#[async_trait]
impl Tool for SearchReactionsTool {
    fn name(&self) -> &str {
        "search_reactions"
    }

    fn description(&self) -> &str {
        r#"Search for reaction images using natural language.

Returns contextually appropriate anime reaction images ranked by semantic
similarity (sentence embeddings) with a small keyword/tag boost. If the
embedding model is unavailable (offline or still downloading), falls back to
keyword matching and says so in `search_mode` / `note`.

Examples:
- "celebrating after fixing a bug"
- "confused about the error message"
- "annoyed at the failing tests"
- "deep in thought while debugging"

Each result includes `markdown` ready to paste into a comment. Use `exclude`
with previously used ids to vary reactions across comments."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language description of the desired reaction (emotion or situation)"
                },
                "limit": {
                    "type": "integer",
                    "description": format!("Maximum number of results (default: 5, max: {MAX_LIMIT})"),
                    "default": 5,
                    "minimum": 1,
                    "maximum": MAX_LIMIT
                },
                "tags": {
                    "oneOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "string"}
                    ],
                    "description": "Optional tag filter (case-insensitive) - reactions must have at least one of these tags"
                },
                "exclude": {
                    "oneOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "string"}
                    ],
                    "description": "Optional reaction ids to leave out (e.g. ones already used recently)"
                },
                "min_similarity": {
                    "type": "number",
                    "description": "Minimum similarity threshold 0-1 (default: 0.0)",
                    "default": 0.0,
                    "minimum": 0.0,
                    "maximum": 1.0
                }
            },
            "required": ["query"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let (query, opts) = parse_args::<SearchArgs>(args)?.validate()?;
        let outcome = match self.service.search(&query, &opts).await {
            Ok(o) => o,
            Err(e) => {
                return json_error(&json!({
                    "success": false,
                    "error": format!("Search unavailable: {e}"),
                }));
            },
        };
        let mut response = json!({
            "success": true,
            "query": query,
            "search_mode": outcome.mode,
            "count": outcome.results.len(),
            "results": outcome.results,
        });
        if let Some(note) = outcome.note {
            response["note"] = json!(note);
        }
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_reaction
// ============================================================================

struct GetReactionTool {
    service: Arc<ReactionService>,
}

#[derive(Debug, Deserialize)]
struct GetArgs {
    reaction_id: String,
}

#[async_trait]
impl Tool for GetReactionTool {
    fn name(&self) -> &str {
        "get_reaction"
    }

    fn description(&self) -> &str {
        r#"Get a specific reaction image by ID.

Returns the full details for a reaction including URL and markdown for
embedding. Lookup is case-insensitive; unknown ids return close matches in
`suggestions`. Does not need the embedding model."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "reaction_id": {
                    "type": "string",
                    "description": "Reaction identifier (e.g., 'felix', 'miku_typing')"
                }
            },
            "required": ["reaction_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let GetArgs { reaction_id } = parse_args(args)?;
        if reaction_id.trim().is_empty() {
            return Err(MCPError::InvalidParameters(
                "reaction_id must not be empty".into(),
            ));
        }
        let catalog = match self.service.catalog().await {
            Ok(c) => c,
            Err(e) => {
                return json_error(&json!({
                    "success": false,
                    "error": format!("Reactions unavailable: {e}"),
                }));
            },
        };
        match catalog.get(&reaction_id) {
            Some(r) => ToolResult::json(&json!({
                "success": true,
                "reaction": ReactionResult::from_reaction(r, 1.0, 1.0),
            })),
            None => json_error(&json!({
                "success": false,
                "error": format!("Reaction not found: {}", reaction_id.trim()),
                "suggestions": catalog.suggest(&reaction_id, 5),
            })),
        }
    }
}

// ============================================================================
// Tool: list_reactions
// ============================================================================

struct ListReactionsTool {
    service: Arc<ReactionService>,
}

#[derive(Debug, Deserialize)]
struct ListArgs {
    #[serde(default)]
    tags: Option<OneOrMany>,
    #[serde(default)]
    limit: Option<f64>,
}

#[async_trait]
impl Tool for ListReactionsTool {
    fn name(&self) -> &str {
        "list_reactions"
    }

    fn description(&self) -> &str {
        r#"List available reaction images (id, description, tags, markdown).

Optionally filter to reactions having at least one of `tags`. Useful for
browsing the catalog or picking by id; works without the embedding model."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "tags": {
                    "oneOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "string"}
                    ],
                    "description": "Optional tag filter (case-insensitive, any-of)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum entries to return (default: all)",
                    "minimum": 1
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: ListArgs = parse_args(args)?;
        let tags = normalized(args.tags);
        let catalog = match self.service.catalog().await {
            Ok(c) => c,
            Err(e) => {
                return json_error(&json!({
                    "success": false,
                    "error": format!("Reactions unavailable: {e}"),
                }));
            },
        };
        let limit = parse_limit(args.limit, catalog.len().max(1), catalog.len().max(1))?;
        let matching: Vec<ReactionSummary> = catalog
            .reactions()
            .iter()
            .filter(|r| tags.is_empty() || tags.iter().any(|t| r.has_tag(t)))
            .map(ReactionSummary::from)
            .collect();
        let total = matching.len();
        let reactions: Vec<ReactionSummary> = matching.into_iter().take(limit).collect();
        ToolResult::json(&json!({
            "success": true,
            "total": total,
            "count": reactions.len(),
            "reactions": reactions,
        }))
    }
}

// ============================================================================
// Tool: list_reaction_tags
// ============================================================================

struct ListReactionTagsTool {
    service: Arc<ReactionService>,
}

/// Split tag counts into emotion / action / other categories.
fn categorize_tags(tags: &BTreeMap<String, usize>) -> Value {
    let mut emotions = serde_json::Map::new();
    let mut actions = serde_json::Map::new();
    let mut other = serde_json::Map::new();
    for (tag, &count) in tags {
        let bucket = if EMOTION_TAGS.contains(&tag.as_str()) {
            &mut emotions
        } else if ACTION_TAGS.contains(&tag.as_str()) {
            &mut actions
        } else {
            &mut other
        };
        bucket.insert(tag.clone(), json!(count));
    }
    json!({ "emotions": emotions, "actions": actions, "other": other })
}

#[async_trait]
impl Tool for ListReactionTagsTool {
    fn name(&self) -> &str {
        "list_reaction_tags"
    }

    fn description(&self) -> &str {
        r#"List all available reaction tags with counts.

Tags are lowercased. `tags` is alphabetical, `by_count` is most-used first,
and `categorized` groups common emotion and action tags. Useful for browsing
categories and for the `tags` filter of search_reactions / list_reactions."#
    }

    fn schema(&self) -> Value {
        json!({ "type": "object", "properties": {} })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let catalog = match self.service.catalog().await {
            Ok(c) => c,
            Err(e) => {
                return json_error(&json!({
                    "success": false,
                    "error": format!("Reactions unavailable: {e}"),
                }));
            },
        };
        let tags = catalog.tag_counts();
        let mut by_count: Vec<(&String, &usize)> = tags.iter().collect();
        by_count.sort_by(|a, b| b.1.cmp(a.1).then_with(|| a.0.cmp(b.0)));
        let by_count: Vec<Value> = by_count
            .into_iter()
            .map(|(tag, count)| json!({ "tag": tag, "count": count }))
            .collect();

        ToolResult::json(&json!({
            "success": true,
            "total_tags": tags.len(),
            "tags": tags,
            "by_count": by_count,
            "categorized": categorize_tags(tags),
        }))
    }
}

// ============================================================================
// Tool: refresh_reactions
// ============================================================================

struct RefreshReactionsTool {
    service: Arc<ReactionService>,
}

#[async_trait]
impl Tool for RefreshReactionsTool {
    fn name(&self) -> &str {
        "refresh_reactions"
    }

    fn description(&self) -> &str {
        r#"Refresh the reaction catalog from its source (GitHub by default).

Bypasses the 1-week cache TTL. If the fetch fails, the previously loaded
reactions and on-disk cache are kept. Also retries a failed model load.
Reports added/removed reaction ids."#
    }

    fn schema(&self) -> Value {
        json!({ "type": "object", "properties": {} })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        match self.service.refresh().await {
            Ok(outcome) => {
                let mut response = json!({
                    "success": true,
                    "message": format!(
                        "Reactions refreshed ({} loaded, {} added, {} removed)",
                        outcome.reaction_count,
                        outcome.added.len(),
                        outcome.removed.len()
                    ),
                });
                if let (Value::Object(target), Ok(Value::Object(extra))) =
                    (&mut response, serde_json::to_value(&outcome))
                {
                    target.extend(extra);
                }
                ToolResult::json(&response)
            },
            Err(e) => json_error(&json!({
                "success": false,
                "error": format!("Refresh failed: {e}"),
            })),
        }
    }
}

// ============================================================================
// Tool: reaction_search_status
// ============================================================================

struct ReactionSearchStatusTool {
    service: Arc<ReactionService>,
}

#[async_trait]
impl Tool for ReactionSearchStatusTool {
    fn name(&self) -> &str {
        "reaction_search_status"
    }

    fn description(&self) -> &str {
        r#"Get reaction search server status.

Reports catalog state (count, source: network/cache/stale_cache/local_file),
embedding model state (not_loaded/loading/ready/failed and any error), the
active search mode (semantic or lexical), and on-disk cache details. Never
blocks on loading."#
    }

    fn schema(&self) -> Value {
        json!({ "type": "object", "properties": {} })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        ToolResult::json(&self.service.status().await)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::service::tests::{SAMPLE, failing_factory, hash_factory, test_service};
    use std::sync::atomic::AtomicUsize;

    fn tool(service: &Arc<ReactionService>, name: &str) -> BoxedTool {
        tools(service)
            .into_iter()
            .find(|t| t.name() == name)
            .unwrap_or_else(|| panic!("tool {name} missing"))
    }

    fn body(result: &ToolResult) -> Value {
        match &result.content[0] {
            Content::Text { text } => serde_json::from_str(text).unwrap(),
            other => panic!("unexpected content {other:?}"),
        }
    }

    #[test]
    fn tool_names_are_stable() {
        let (svc, _) = test_service("names", SAMPLE, hash_factory());
        let names: Vec<String> = tools(&svc).iter().map(|t| t.name().to_string()).collect();
        for expected in [
            "search_reactions",
            "get_reaction",
            "list_reactions",
            "list_reaction_tags",
            "refresh_reactions",
            "reaction_search_status",
        ] {
            assert!(names.iter().any(|n| n == expected), "{expected} missing");
        }
        for t in tools(&svc) {
            assert_eq!(t.schema()["type"], "object", "{}", t.name());
        }
    }

    #[test]
    fn limit_parsing() {
        assert_eq!(parse_limit(None, 5, 20).unwrap(), 5);
        assert_eq!(parse_limit(Some(3.0), 5, 20).unwrap(), 3);
        assert_eq!(parse_limit(Some(100.0), 5, 20).unwrap(), 20);
        assert_eq!(parse_limit(Some(0.0), 5, 20).unwrap(), 1);
        assert_eq!(parse_limit(Some(-4.0), 5, 20).unwrap(), 1);
        assert!(parse_limit(Some(f64::NAN), 5, 20).is_err());
    }

    #[tokio::test]
    async fn search_validates_arguments() {
        let (svc, _) = test_service("search_args", SAMPLE, hash_factory());
        let t = tool(&svc, "search_reactions");
        for bad in [
            json!({}),
            json!(null),
            json!({"query": 42}),
            json!({"query": "   "}),
            json!({"query": "x".repeat(MAX_QUERY_CHARS + 1)}),
            json!({"query": "happy", "min_similarity": 1.5}),
            json!({"query": "happy", "limit": "five"}),
            json!({"query": "happy", "tags": 7}),
        ] {
            let err = t.execute(bad.clone()).await.unwrap_err();
            assert!(
                matches!(err, MCPError::InvalidParameters(_)),
                "{bad}: {err}"
            );
        }
    }

    #[tokio::test]
    async fn search_returns_ranked_results() {
        let (svc, _) = test_service("search_ok", SAMPLE, hash_factory());
        let t = tool(&svc, "search_reactions");
        let result = t
            .execute(json!({"query": "confused about the error", "limit": 2.0}))
            .await
            .unwrap();
        assert!(!result.is_error);
        let v = body(&result);
        assert_eq!(v["success"], true);
        assert_eq!(v["search_mode"], "semantic");
        assert_eq!(v["count"], 2);
        assert_eq!(v["results"][0]["id"], "confused");
        assert!(
            v["results"][0]["markdown"]
                .as_str()
                .unwrap()
                .starts_with("![Reaction](")
        );

        // Single-string tag filter and exclude.
        let v = body(
            &t.execute(json!({"query": "anything", "tags": "HAPPY", "exclude": ["confused"]}))
                .await
                .unwrap(),
        );
        assert_eq!(v["count"], 1);
        assert_eq!(v["results"][0]["id"], "felix");
    }

    #[tokio::test]
    async fn search_reports_lexical_fallback() {
        let (svc, _) = test_service(
            "search_lex",
            SAMPLE,
            failing_factory(Arc::new(AtomicUsize::new(0))),
        );
        let v = body(
            &tool(&svc, "search_reactions")
                .execute(json!({"query": "annoyed"}))
                .await
                .unwrap(),
        );
        assert_eq!(v["search_mode"], "lexical");
        assert!(v["note"].as_str().unwrap().contains("keyword"));
        assert_eq!(v["results"][0]["id"], "kagami_annoyed");
    }

    #[tokio::test]
    async fn get_reaction_found_and_not_found() {
        let (svc, _) = test_service("get", SAMPLE, hash_factory());
        let t = tool(&svc, "get_reaction");
        let v = body(&t.execute(json!({"reaction_id": "Felix"})).await.unwrap());
        assert_eq!(v["reaction"]["id"], "felix");

        let result = t.execute(json!({"reaction_id": "felx"})).await.unwrap();
        assert!(result.is_error);
        let v = body(&result);
        assert_eq!(v["success"], false);
        assert_eq!(v["suggestions"][0], "felix");

        assert!(t.execute(json!({})).await.is_err());
        assert!(t.execute(json!({"reaction_id": ""})).await.is_err());
    }

    #[tokio::test]
    async fn list_tools_work_without_model() {
        let (svc, _) = test_service(
            "lists",
            SAMPLE,
            failing_factory(Arc::new(AtomicUsize::new(0))),
        );
        let v = body(
            &tool(&svc, "list_reactions")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(v["total"], 3);
        let v = body(
            &tool(&svc, "list_reactions")
                .execute(json!({"tags": ["annoyed"], "limit": 5}))
                .await
                .unwrap(),
        );
        assert_eq!(v["count"], 1);
        assert_eq!(v["reactions"][0]["id"], "kagami_annoyed");

        let v = body(
            &tool(&svc, "list_reaction_tags")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(v["total_tags"], 4);
        assert_eq!(v["categorized"]["emotions"]["happy"], 1);
        assert_eq!(v["by_count"].as_array().unwrap().len(), 4);
    }

    #[tokio::test]
    async fn refresh_and_status() {
        let (svc, _) = test_service("refresh_tool", SAMPLE, hash_factory());
        let status = body(
            &tool(&svc, "reaction_search_status")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(status["initialized"], false);

        let v = body(
            &tool(&svc, "refresh_reactions")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(v["success"], true);
        assert_eq!(v["reaction_count"], 3);
        assert_eq!(v["source"], "local_file");

        let status = body(
            &tool(&svc, "reaction_search_status")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(status["initialized"], true);
        assert_eq!(status["catalog"]["reaction_count"], 3);
    }

    #[tokio::test]
    async fn unavailable_config_is_reported_not_panicked() {
        let (svc, path) = test_service("unavail", SAMPLE, hash_factory());
        std::fs::remove_file(&path).unwrap();
        for (name, args) in [
            ("search_reactions", json!({"query": "happy"})),
            ("get_reaction", json!({"reaction_id": "felix"})),
            ("list_reactions", json!({})),
            ("list_reaction_tags", json!({})),
            ("refresh_reactions", json!({})),
        ] {
            let result = tool(&svc, name).execute(args).await.unwrap();
            assert!(result.is_error, "{name}");
            assert_eq!(body(&result)["success"], false, "{name}");
        }
    }
}
