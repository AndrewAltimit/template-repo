//! MCP tool definitions.
//!
//! Each tool deserializes its arguments into a typed struct (so a missing or
//! mistyped argument is a clean `InvalidParameters` error, never a panic) and
//! delegates to [`MemoryService`]. Hand-written JSON schemas are kept because
//! they carry `items`, `default`, `minimum`/`maximum` and richer descriptions
//! than the generic `#[mcp_tool]` macro can derive.
//!
//! Error mapping:
//! * argument/validation problems -> `MCPError::InvalidParameters`;
//! * runtime failures (database down, embedding failure, ...) -> a tool result
//!   with `isError: true` whose text is `{"success": false, "error": ...,
//!   "error_kind": ...}` (the same JSON shape earlier releases returned).

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use std::sync::Arc;
use tracing::error;

use crate::service::{
    MAX_FACTS_PER_CALL, MAX_IDS_PER_CALL, MAX_LIST_LIMIT, MAX_TOP_K, MemoryService, ServiceError,
};

/// Deserialize tool arguments (absent arguments are treated as `{}`).
fn parse<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

/// Convert a service result into a tool result.
fn respond<T: Serialize>(
    tool: &str,
    result: std::result::Result<T, ServiceError>,
) -> Result<ToolResult> {
    match result {
        Ok(v) => ToolResult::json(&v),
        Err(ServiceError::Invalid(msg)) => Err(MCPError::InvalidParameters(msg)),
        Err(e) => {
            error!("{tool} failed: {e}");
            let body = json!({
                "success": false,
                "error": e.to_string(),
                "error_kind": e.kind(),
            });
            Ok(ToolResult::error(body.to_string()))
        },
    }
}

/// Declare a tool struct wrapping the shared service.
macro_rules! memory_tool {
    ($ty:ident, $name:literal, $desc:expr, $schema:expr, |$svc:ident, $args:ident| $body:expr) => {
        struct $ty(Arc<MemoryService>);

        #[async_trait]
        impl Tool for $ty {
            fn name(&self) -> &str {
                $name
            }

            fn description(&self) -> &str {
                $desc
            }

            fn schema(&self) -> Value {
                $schema
            }

            async fn execute(&self, $args: Value) -> Result<ToolResult> {
                let $svc: &MemoryService = &self.0;
                $body
            }
        }
    };
}

/// All tools, sharing one service.
pub fn tools(service: Arc<MemoryService>) -> Vec<BoxedTool> {
    vec![
        Arc::new(StoreEventTool(service.clone())),
        Arc::new(StoreFactsTool(service.clone())),
        Arc::new(SearchMemoriesTool(service.clone())),
        Arc::new(ListSessionEventsTool(service.clone())),
        Arc::new(ListNamespacesTool(service.clone())),
        Arc::new(MemoryStatusTool(service.clone())),
        Arc::new(ListMemoriesTool(service.clone())),
        Arc::new(DeleteMemoriesTool(service.clone())),
        Arc::new(ReindexNamespaceTool(service)),
    ]
}

// ---------------------------------------------------------------------------
// store_event
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct StoreEventArgs {
    content: String,
    actor_id: String,
    session_id: String,
    #[serde(default)]
    metadata: Option<Map<String, Value>>,
}

memory_tool!(
    StoreEventTool,
    "store_event",
    "Store a short-term memory event for a session.\n\n\
     Use for sparse, high-value events: session goals, key decisions, final \
     outcomes. Retrieve them with list_session_events. Secrets in content and \
     metadata are redacted before storage.",
    json!({
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Content to remember (max 32 KiB)"},
            "actor_id": {"type": "string", "description": "Actor identifier (e.g. 'claude-code', 'issue-monitor')"},
            "session_id": {"type": "string", "description": "Session identifier"},
            "metadata": {
                "type": "object",
                "description": "Optional extra key/value metadata (max 32 keys). Nested values are stored as JSON strings; reserved keys (actor_id, session_id, timestamp, timestamp_ms) are ignored.",
                "additionalProperties": true
            }
        },
        "required": ["content", "actor_id", "session_id"]
    }),
    |svc, args| {
        let a: StoreEventArgs = parse(args)?;
        respond(
            "store_event",
            svc.store_event(&a.actor_id, &a.session_id, &a.content, a.metadata)
                .await,
        )
    }
);

// ---------------------------------------------------------------------------
// store_facts
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct StoreFactsArgs {
    facts: Vec<String>,
    namespace: String,
    #[serde(default)]
    source: Option<String>,
}

memory_tool!(
    StoreFactsTool,
    "store_facts",
    "Store facts/patterns for long-term retention in a namespace.\n\n\
     Use for discovered patterns, architectural decisions and learned \
     conventions. Storing is idempotent: a fact whose (sanitized) text already \
     exists in the namespace is reported as a duplicate, not stored twice. \
     Returns the record id of every fact (usable with delete_memories).",
    json!({
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": MAX_FACTS_PER_CALL,
                "description": "Facts to store (each non-empty, max 32 KiB)"
            },
            "namespace": {"type": "string", "description": "Namespace, e.g. 'codebase/patterns' (see list_namespaces)"},
            "source": {"type": "string", "description": "Source attribution (e.g. 'PR #42', 'claude-code')"}
        },
        "required": ["facts", "namespace"]
    }),
    |svc, args| {
        let a: StoreFactsArgs = parse(args)?;
        respond(
            "store_facts",
            svc.store_facts(a.facts, &a.namespace, a.source.as_deref())
                .await,
        )
    }
);

// ---------------------------------------------------------------------------
// search_memories
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct SearchArgs {
    query: String,
    namespace: String,
    #[serde(default = "default_top_k")]
    top_k: u32,
    #[serde(default)]
    min_relevance: Option<f64>,
}

fn default_top_k() -> u32 {
    5
}

memory_tool!(
    SearchMemoriesTool,
    "search_memories",
    "Search the facts in one namespace by semantic similarity.\n\n\
     Returns memories ranked by relevance (1 - cosine distance; 1.0 = \
     identical). Only the exact namespace is searched, not its children.",
    json!({
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "namespace": {"type": "string", "description": "Namespace to search (e.g. 'codebase/patterns')"},
            "top_k": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": MAX_TOP_K,
                "description": "Maximum results to return (values above the maximum are clamped)"
            },
            "min_relevance": {
                "type": "number",
                "minimum": -1.0,
                "maximum": 1.0,
                "description": "Drop results whose relevance is below this value (e.g. 0.3)"
            }
        },
        "required": ["query", "namespace"]
    }),
    |svc, args| {
        let a: SearchArgs = parse(args)?;
        respond(
            "search_memories",
            svc.search(&a.query, &a.namespace, a.top_k, a.min_relevance)
                .await,
        )
    }
);

// ---------------------------------------------------------------------------
// list_session_events
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct ListEventsArgs {
    actor_id: String,
    session_id: String,
    #[serde(default = "default_event_limit")]
    limit: u32,
}

fn default_event_limit() -> u32 {
    50
}

memory_tool!(
    ListSessionEventsTool,
    "list_session_events",
    "List events from a specific session, newest first.",
    json!({
        "type": "object",
        "properties": {
            "actor_id": {"type": "string", "description": "Actor identifier"},
            "session_id": {"type": "string", "description": "Session identifier"},
            "limit": {
                "type": "integer",
                "default": 50,
                "minimum": 1,
                "maximum": MAX_LIST_LIMIT,
                "description": "Maximum events to return"
            }
        },
        "required": ["actor_id", "session_id"]
    }),
    |svc, args| {
        let a: ListEventsArgs = parse(args)?;
        respond(
            "list_session_events",
            svc.list_events(&a.actor_id, &a.session_id, a.limit).await,
        )
    }
);

// ---------------------------------------------------------------------------
// list_namespaces
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct ListNamespacesArgs {
    #[serde(default)]
    include_stored: bool,
}

memory_tool!(
    ListNamespacesTool,
    "list_namespaces",
    "List the predefined namespaces. With include_stored=true, also list the \
     namespaces that currently hold facts, with record counts.",
    json!({
        "type": "object",
        "properties": {
            "include_stored": {
                "type": "boolean",
                "default": false,
                "description": "Also query the database for namespaces that contain facts"
            }
        }
    }),
    |svc, args| {
        let a: ListNamespacesArgs = parse(args)?;
        ToolResult::json(&svc.list_namespaces(a.include_stored).await)
    }
);

// ---------------------------------------------------------------------------
// memory_status
// ---------------------------------------------------------------------------

memory_tool!(
    MemoryStatusTool,
    "memory_status",
    "Get memory provider status: database connectivity and version, embedder, \
     and search-cache statistics.",
    json!({"type": "object", "properties": {}}),
    |svc, _args| ToolResult::json(&svc.status().await)
);

// ---------------------------------------------------------------------------
// list_memories
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct ListMemoriesArgs {
    namespace: String,
    #[serde(default = "default_list_limit")]
    limit: u32,
    #[serde(default)]
    offset: u32,
}

fn default_list_limit() -> u32 {
    20
}

memory_tool!(
    ListMemoriesTool,
    "list_memories",
    "Browse the facts stored in a namespace without a search query (for \
     auditing or finding ids to delete). Order is storage order.",
    json!({
        "type": "object",
        "properties": {
            "namespace": {"type": "string", "description": "Namespace to browse"},
            "limit": {
                "type": "integer",
                "default": 20,
                "minimum": 1,
                "maximum": MAX_LIST_LIMIT,
                "description": "Page size"
            },
            "offset": {"type": "integer", "default": 0, "minimum": 0, "description": "Records to skip"}
        },
        "required": ["namespace"]
    }),
    |svc, args| {
        let a: ListMemoriesArgs = parse(args)?;
        respond(
            "list_memories",
            svc.list_memories(&a.namespace, a.limit, a.offset).await,
        )
    }
);

// ---------------------------------------------------------------------------
// delete_memories
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct DeleteMemoriesArgs {
    namespace: String,
    ids: Vec<String>,
}

memory_tool!(
    DeleteMemoriesTool,
    "delete_memories",
    "Delete facts from a namespace by record id (ids come from store_facts, \
     search_memories or list_memories). Reports which ids were deleted and \
     which were not found.",
    json!({
        "type": "object",
        "properties": {
            "namespace": {"type": "string", "description": "Namespace containing the facts"},
            "ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": MAX_IDS_PER_CALL,
                "description": "Record ids to delete"
            }
        },
        "required": ["namespace", "ids"]
    }),
    |svc, args| {
        let a: DeleteMemoriesArgs = parse(args)?;
        respond(
            "delete_memories",
            svc.delete_memories(&a.namespace, a.ids).await,
        )
    }
);

// ---------------------------------------------------------------------------
// reindex_namespace
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct ReindexArgs {
    namespace: String,
}

memory_tool!(
    ReindexNamespaceTool,
    "reindex_namespace",
    "Recompute the embeddings of every fact in a namespace with the current \
     embedder. Needed once for facts written by releases before 1.1.0, which \
     stored text without vectors and are therefore invisible to \
     search_memories.",
    json!({
        "type": "object",
        "properties": {
            "namespace": {"type": "string", "description": "Namespace to re-embed"}
        },
        "required": ["namespace"]
    }),
    |svc, args| {
        let a: ReindexArgs = parse(args)?;
        respond(
            "reindex_namespace",
            svc.reindex_namespace(&a.namespace).await,
        )
    }
);
