//! MCP server implementation for AgentCore Memory operations

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, error};

use crate::cache::MemoryCache;
use crate::client::ChromaDBClient;
use crate::types::{ChromaDBConfig, namespaces};

/// AgentCore Memory MCP server
pub struct MemoryServer {
    client: Arc<ChromaDBClient>,
    cache: Arc<RwLock<MemoryCache>>,
}

impl MemoryServer {
    /// Create a new memory server
    pub fn new() -> Self {
        let config = ChromaDBConfig::from_env();
        let client = ChromaDBClient::new(config);

        Self {
            client: Arc::new(client),
            cache: Arc::new(RwLock::new(MemoryCache::default())),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(StoreEventTool {
                client: self.client.clone(),
            }),
            Arc::new(StoreFactsTool {
                client: self.client.clone(),
                cache: self.cache.clone(),
            }),
            Arc::new(SearchMemoriesTool {
                client: self.client.clone(),
                cache: self.cache.clone(),
            }),
            Arc::new(ListSessionEventsTool {
                client: self.client.clone(),
            }),
            Arc::new(ListNamespacesTool),
            Arc::new(MemoryStatusTool {
                client: self.client.clone(),
                cache: self.cache.clone(),
            }),
        ]
    }
}

impl Default for MemoryServer {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tool: store_event
// ============================================================================

struct StoreEventTool {
    client: Arc<ChromaDBClient>,
}

#[async_trait]
impl Tool for StoreEventTool {
    fn name(&self) -> &str {
        "store_event"
    }

    fn description(&self) -> &str {
        r#"Store a short-term memory event.

Use for sparse, high-value events:
- Session start goals
- Key decisions made
- Final outcomes

ChromaDB has no rate limits (unlike AWS AgentCore)."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Content to remember"
                },
                "actor_id": {
                    "type": "string",
                    "description": "Actor identifier (e.g., 'claude-code', 'issue-monitor')"
                },
                "session_id": {
                    "type": "string",
                    "description": "Session identifier"
                }
            },
            "required": ["content", "actor_id", "session_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let content = args
            .get("content")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("content is required".to_string()))?;
        let actor_id = args
            .get("actor_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("actor_id is required".to_string()))?;
        let session_id = args
            .get("session_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("session_id is required".to_string()))?;

        match self
            .client
            .store_event(actor_id, session_id, content, None)
            .await
        {
            Ok(event) => {
                let response = json!({
                    "success": true,
                    "event_id": event.id,
                    "provider": "chromadb",
                    "timestamp": event.timestamp.to_rfc3339()
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                error!("Failed to store event: {}", e);
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: store_facts
// ============================================================================

struct StoreFactsTool {
    client: Arc<ChromaDBClient>,
    cache: Arc<RwLock<MemoryCache>>,
}

#[async_trait]
impl Tool for StoreFactsTool {
    fn name(&self) -> &str {
        "store_facts"
    }

    fn description(&self) -> &str {
        r#"Store facts/patterns for long-term retention.

Use for:
- Discovered patterns
- Architectural decisions
- Learned conventions"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of facts to store"
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace for organization (e.g., 'codebase/patterns')"
                },
                "source": {
                    "type": "string",
                    "description": "Source attribution (e.g., 'PR #42', 'claude-code')"
                }
            },
            "required": ["facts", "namespace"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let facts: Vec<String> = args
            .get("facts")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .ok_or_else(|| MCPError::InvalidParameters("facts array is required".to_string()))?;

        let namespace = args
            .get("namespace")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("namespace is required".to_string()))?;

        let source = args.get("source").and_then(|v| v.as_str());

        // Build records with metadata
        let records: Vec<(String, Option<HashMap<String, Value>>)> = facts
            .into_iter()
            .map(|fact| {
                let mut meta = HashMap::new();
                if let Some(src) = source {
                    meta.insert("source".to_string(), json!(src));
                }
                (fact, if meta.is_empty() { None } else { Some(meta) })
            })
            .collect();

        match self.client.store_records(records, namespace).await {
            Ok(result) => {
                // Invalidate cache for this namespace
                {
                    let mut cache = self.cache.write().await;
                    cache.invalidate(Some(namespace));
                }

                let response = json!({
                    "success": result.failed == 0,
                    "created": result.created,
                    "failed": result.failed,
                    "namespace": namespace,
                    "errors": if result.failed > 0 { Some(&result.errors) } else { None }
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                error!("Failed to store facts: {}", e);
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: search_memories
// ============================================================================

struct SearchMemoriesTool {
    client: Arc<ChromaDBClient>,
    cache: Arc<RwLock<MemoryCache>>,
}

#[async_trait]
impl Tool for SearchMemoriesTool {
    fn name(&self) -> &str {
        "search_memories"
    }

    fn description(&self) -> &str {
        r#"Search memories using semantic query.

Returns relevant memories ranked by similarity."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace to search (e.g., 'codebase/patterns')"
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum results to return"
                }
            },
            "required": ["query", "namespace"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let query = args
            .get("query")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("query is required".to_string()))?;

        let namespace = args
            .get("namespace")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("namespace is required".to_string()))?;

        let top_k = args.get("top_k").and_then(|v| v.as_u64()).unwrap_or(5) as u32;

        // Check cache first
        {
            let cache = self.cache.read().await;
            if let Some(cached) = cache.get(query, namespace) {
                debug!("Returning cached search results");
                let response = json!({
                    "query": query,
                    "namespace": namespace,
                    "count": cached.len(),
                    "cached": true,
                    "memories": cached
                });
                return ToolResult::json(&response);
            }
        }

        match self.client.search_records(query, namespace, top_k).await {
            Ok(records) => {
                let memories: Vec<Value> = records
                    .iter()
                    .map(|r| {
                        json!({
                            "content": r.content,
                            "relevance": r.relevance,
                            "created_at": r.created_at.map(|dt| dt.to_rfc3339())
                        })
                    })
                    .collect();

                // Cache the results
                {
                    let mut cache = self.cache.write().await;
                    cache.set(query, namespace, memories.clone());
                }

                let response = json!({
                    "query": query,
                    "namespace": namespace,
                    "count": memories.len(),
                    "cached": false,
                    "memories": memories
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                error!("Failed to search memories: {}", e);
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: list_session_events
// ============================================================================

struct ListSessionEventsTool {
    client: Arc<ChromaDBClient>,
}

#[async_trait]
impl Tool for ListSessionEventsTool {
    fn name(&self) -> &str {
        "list_session_events"
    }

    fn description(&self) -> &str {
        "List events from a specific session."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "actor_id": {
                    "type": "string",
                    "description": "Actor identifier"
                },
                "session_id": {
                    "type": "string",
                    "description": "Session identifier"
                },
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum events to return"
                }
            },
            "required": ["actor_id", "session_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let actor_id = args
            .get("actor_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("actor_id is required".to_string()))?;

        let session_id = args
            .get("session_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("session_id is required".to_string()))?;

        let limit = args.get("limit").and_then(|v| v.as_u64()).unwrap_or(50) as u32;

        match self.client.list_events(actor_id, session_id, limit).await {
            Ok(events) => {
                let event_list: Vec<Value> = events
                    .iter()
                    .map(|e| {
                        json!({
                            "id": e.id,
                            "content": e.content,
                            "timestamp": e.timestamp.to_rfc3339()
                        })
                    })
                    .collect();

                let response = json!({
                    "actor_id": actor_id,
                    "session_id": session_id,
                    "count": event_list.len(),
                    "events": event_list
                });
                ToolResult::json(&response)
            }
            Err(e) => {
                error!("Failed to list events: {}", e);
                let response = json!({
                    "success": false,
                    "error": e
                });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: list_namespaces
// ============================================================================

struct ListNamespacesTool;

#[async_trait]
impl Tool for ListNamespacesTool {
    fn name(&self) -> &str {
        "list_namespaces"
    }

    fn description(&self) -> &str {
        "List available predefined namespaces."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let response = json!({
            "namespaces": {
                "codebase": {
                    "architecture": namespaces::ARCHITECTURE,
                    "patterns": namespaces::PATTERNS,
                    "conventions": namespaces::CONVENTIONS,
                    "dependencies": namespaces::DEPENDENCIES
                },
                "reviews": {
                    "pr": namespaces::PR_REVIEWS,
                    "issues": namespaces::ISSUE_CONTEXT
                },
                "preferences": {
                    "user": namespaces::USER_PREFS,
                    "project": namespaces::PROJECT_PREFS
                },
                "agents": {
                    "claude": namespaces::CLAUDE_LEARNINGS,
                    "gemini": namespaces::GEMINI_LEARNINGS,
                    "opencode": namespaces::OPENCODE_LEARNINGS,
                    "crush": namespaces::CRUSH_LEARNINGS,
                    "codex": namespaces::CODEX_LEARNINGS
                }
            },
            "note": "Use hierarchical namespaces with '/' separator for organization"
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: memory_status
// ============================================================================

struct MemoryStatusTool {
    client: Arc<ChromaDBClient>,
    cache: Arc<RwLock<MemoryCache>>,
}

#[async_trait]
impl Tool for MemoryStatusTool {
    fn name(&self) -> &str {
        "memory_status"
    }

    fn description(&self) -> &str {
        "Get memory provider status and info."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let healthy = self.client.health_check().await;
        let info = self.client.get_info();
        let cache_stats = {
            let cache = self.cache.read().await;
            cache.get_stats()
        };

        let response = json!({
            "status": if healthy { "connected" } else { "disconnected" },
            "provider": info,
            "cache": cache_stats
        });
        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        // Just verify it compiles and can be created
        // (actual client won't connect without ChromaDB running)
        let _ = MemoryServer::new();
    }

    #[test]
    fn test_tool_names() {
        let server = MemoryServer::new();
        let tools = server.tools();

        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        assert!(names.contains(&"store_event"));
        assert!(names.contains(&"store_facts"));
        assert!(names.contains(&"search_memories"));
        assert!(names.contains(&"list_session_events"));
        assert!(names.contains(&"list_namespaces"));
        assert!(names.contains(&"memory_status"));
    }
}
