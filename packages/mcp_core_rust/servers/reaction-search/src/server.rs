//! MCP server implementation for reaction search.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::config::ConfigLoader;
use crate::engine::ReactionSearchEngine;

/// Reaction search MCP server
pub struct ReactionSearchServer {
    config_loader: Arc<RwLock<ConfigLoader>>,
    search_engine: Arc<RwLock<ReactionSearchEngine>>,
    initialized: Arc<RwLock<bool>>,
}

impl ReactionSearchServer {
    /// Create a new reaction search server
    pub fn new() -> Self {
        Self {
            config_loader: Arc::new(RwLock::new(ConfigLoader::new())),
            search_engine: Arc::new(RwLock::new(ReactionSearchEngine::new())),
            initialized: Arc::new(RwLock::new(false)),
        }
    }

    /// Ensure the engine is initialized (lazy initialization)
    async fn ensure_initialized(&self) -> Result<()> {
        let mut initialized = self.initialized.write().await;
        if *initialized {
            return Ok(());
        }

        info!("Initializing reaction search engine...");

        // Load reactions from config
        let mut config = self.config_loader.write().await;
        let reactions = config.get_reactions().await.map_err(|e| {
            MCPError::Internal(format!("Failed to load config: {}", e))
        })?;

        // Initialize search engine
        let mut engine = self.search_engine.write().await;
        engine.initialize(reactions).map_err(|e| {
            MCPError::Internal(format!("Failed to initialize engine: {}", e))
        })?;

        *initialized = true;
        info!("Reaction search engine initialized");

        Ok(())
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(SearchReactionsTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetReactionTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListReactionTagsTool {
                server: self.clone_refs(),
            }),
            Arc::new(RefreshReactionsTool {
                server: self.clone_refs(),
            }),
            Arc::new(ReactionSearchStatusTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone the Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            config_loader: self.config_loader.clone(),
            search_engine: self.search_engine.clone(),
            initialized: self.initialized.clone(),
        }
    }
}

impl Default for ReactionSearchServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    config_loader: Arc<RwLock<ConfigLoader>>,
    search_engine: Arc<RwLock<ReactionSearchEngine>>,
    initialized: Arc<RwLock<bool>>,
}

impl ServerRefs {
    async fn ensure_initialized(&self) -> Result<()> {
        let mut initialized = self.initialized.write().await;
        if *initialized {
            return Ok(());
        }

        info!("Initializing reaction search engine...");

        let mut config = self.config_loader.write().await;
        let reactions = config.get_reactions().await.map_err(|e| {
            MCPError::Internal(format!("Failed to load config: {}", e))
        })?;

        let mut engine = self.search_engine.write().await;
        engine.initialize(reactions).map_err(|e| {
            MCPError::Internal(format!("Failed to initialize engine: {}", e))
        })?;

        *initialized = true;
        info!("Reaction search engine initialized");

        Ok(())
    }
}

// ============================================================================
// Tool: search_reactions
// ============================================================================

struct SearchReactionsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SearchReactionsTool {
    fn name(&self) -> &str {
        "search_reactions"
    }

    fn description(&self) -> &str {
        r#"Search for reaction images using natural language.

Returns contextually appropriate anime reaction images based on semantic similarity.
Useful for finding reactions that match an emotional state or situation.

Examples:
- "celebrating after fixing a bug" -> felix, aqua_happy
- "confused about the error message" -> confused, miku_confused
- "annoyed at the failing tests" -> kagami_annoyed, nao_annoyed
- "deep in thought while debugging" -> thinking_foxgirl, hifumi_studious"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query describing the desired reaction"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 5, max: 20)",
                    "default": 5
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tag filter - reactions must have at least one of these tags"
                },
                "min_similarity": {
                    "type": "number",
                    "description": "Minimum similarity threshold 0-1 (default: 0.0)",
                    "default": 0.0
                }
            },
            "required": ["query"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        // Ensure initialized
        self.server.ensure_initialized().await?;

        // Parse arguments
        let query = args
            .get("query")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'query' parameter".to_string()))?;

        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .map(|v| v.min(20) as usize)
            .unwrap_or(5);

        let tags: Option<Vec<String>> = args.get("tags").and_then(|v| {
            v.as_array().map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
        });

        let min_similarity = args
            .get("min_similarity")
            .and_then(|v| v.as_f64())
            .map(|v| v as f32)
            .unwrap_or(0.0);

        // Search
        let engine = self.server.search_engine.read().await;
        let results = engine
            .search(query, limit, tags.as_deref(), min_similarity)
            .map_err(|e| MCPError::Internal(format!("Search failed: {}", e)))?;

        let response = json!({
            "success": true,
            "query": query,
            "count": results.len(),
            "results": results
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_reaction
// ============================================================================

struct GetReactionTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetReactionTool {
    fn name(&self) -> &str {
        "get_reaction"
    }

    fn description(&self) -> &str {
        r#"Get a specific reaction image by ID.

Returns the full details for a reaction including URL and markdown for embedding."#
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
        self.server.ensure_initialized().await?;

        let reaction_id = args
            .get("reaction_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'reaction_id' parameter".to_string())
            })?;

        let engine = self.server.search_engine.read().await;
        match engine.get_by_id(reaction_id) {
            Some(result) => {
                let response = json!({
                    "success": true,
                    "reaction": result
                });
                ToolResult::json(&response)
            }
            None => {
                let response = json!({
                    "success": false,
                    "error": format!("Reaction not found: {}", reaction_id)
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: list_reaction_tags
// ============================================================================

struct ListReactionTagsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListReactionTagsTool {
    fn name(&self) -> &str {
        "list_reaction_tags"
    }

    fn description(&self) -> &str {
        r#"List all available reaction tags with counts.

Useful for browsing available categories and filtering searches."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        self.server.ensure_initialized().await?;

        let engine = self.server.search_engine.read().await;
        let tags = engine.list_tags();

        // Categorize tags
        let emotions = [
            "happy", "sad", "angry", "confused", "excited", "annoyed", "smug", "shocked",
            "nervous", "bored", "content",
        ];
        let actions = [
            "typing", "thinking", "working", "gaming", "drinking", "waving", "cheering",
            "crying", "laughing", "studying",
        ];

        let mut emotions_map = serde_json::Map::new();
        let mut actions_map = serde_json::Map::new();
        let mut other_map = serde_json::Map::new();

        for (tag, count) in tags {
            let value = json!(count);
            if emotions.contains(&tag.as_str()) {
                emotions_map.insert(tag.clone(), value);
            } else if actions.contains(&tag.as_str()) {
                actions_map.insert(tag.clone(), value);
            } else {
                other_map.insert(tag.clone(), value);
            }
        }

        let response = json!({
            "success": true,
            "total_tags": tags.len(),
            "tags": tags,
            "categorized": {
                "emotions": emotions_map,
                "actions": actions_map,
                "other": other_map
            }
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: refresh_reactions
// ============================================================================

struct RefreshReactionsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RefreshReactionsTool {
    fn name(&self) -> &str {
        "refresh_reactions"
    }

    fn description(&self) -> &str {
        r#"Refresh the reaction cache from GitHub.

Forces a fetch of the latest config, bypassing the 1-week cache TTL."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        // Clear cache and force refresh
        {
            let mut config = self.server.config_loader.write().await;
            config.clear_cache();
        }

        // Reset initialization flag
        {
            let mut initialized = self.server.initialized.write().await;
            *initialized = false;
        }

        // Re-initialize
        self.server.ensure_initialized().await?;

        let engine = self.server.search_engine.read().await;
        let response = json!({
            "success": true,
            "message": "Reactions refreshed from GitHub",
            "reaction_count": engine.reaction_count()
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: reaction_search_status
// ============================================================================

struct ReactionSearchStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ReactionSearchStatusTool {
    fn name(&self) -> &str {
        "reaction_search_status"
    }

    fn description(&self) -> &str {
        r#"Get reaction search server status.

Returns information about initialization state, cache status, and model."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let initialized = *self.server.initialized.read().await;

        let mut response = json!({
            "server": "reaction-search",
            "version": "1.0.0",
            "initialized": initialized
        });

        if initialized {
            let engine = self.server.search_engine.read().await;
            let config = self.server.config_loader.read().await;

            response["engine"] = json!(engine.get_status());
            response["cache"] = json!(config.get_cache_info());
        } else {
            response["note"] = json!("Engine will initialize on first search");
        }

        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = ReactionSearchServer::new();
        let tools = server.tools();
        assert_eq!(tools.len(), 5);
    }

    #[test]
    fn test_tool_names() {
        let server = ReactionSearchServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"search_reactions"));
        assert!(names.contains(&"get_reaction"));
        assert!(names.contains(&"list_reaction_tags"));
        assert!(names.contains(&"refresh_reactions"));
        assert!(names.contains(&"reaction_search_status"));
    }
}
