# AgentCore Memory Integration Guide

**Status**: Implemented (Rust + ChromaDB)
**Location**: `tools/mcp/mcp_agentcore_memory/`
**Author**: Claude Code
**Date**: 2025-12-04
**Last Revised**: 2026-02-16 (Updated to reflect Rust/ChromaDB implementation)

---

> [!NOTE]
> ## Implementation History
>
> This MCP server was originally designed for AWS Bedrock AgentCore (Python + aiobotocore).
> After three rounds of external review uncovering rate limit constraints, API shape issues,
> and architectural problems with the AWS approach, the implementation was rewritten in Rust
> with ChromaDB as a self-hosted vector store. The historical review sections below are
> preserved for context.

---

## Critical Corrections (from External Reviews)

> **This section documents critical issues identified during external review that led to the current architecture.**

### First Review - Hard Blockers

| Issue | Impact | Resolution |
|-------|--------|------------|
| **Rate limits wrong** | CreateEvent is 0.25 req/sec per actor+session (not 100 TPS) | Migrated to ChromaDB (no rate limits) |
| **Control vs Data plane** | Separate clients needed for setup vs runtime | ChromaDB uses a single unified REST API |
| **API shapes wrong** | Response paths, payload formats don't match actual AWS APIs | ChromaDB has straightforward JSON API |
| **async + boto3 = blocking** | boto3 is synchronous; will stall MCP server under load | Resolved: Rust async with reqwest HTTP client |

### Second Review - Implementation Fixes

| Issue | Impact | Resolution |
|-------|--------|------------|
| **Tests mock boto3** | Implementation uses aiobotocore; tests give false confidence | Resolved: Rust unit tests with direct assertions |
| **Sanitize patterns incomplete** | Missing AWS access keys, GitHub tokens | Fixed: 18 regex patterns + high-entropy detection |

### Third Review - Real AWS Integration Testing (2025-12-07)

| Issue | Impact | Resolution |
|-------|--------|------------|
| **BatchCreateMemoryRecords param name** | API expects `records`, not `memoryRecords` | Resolved: Migrated to ChromaDB |
| **eventExpiryDuration units** | Value is in DAYS (max 365), not ISO 8601 duration | N/A: ChromaDB has no expiry mechanism |
| **Memory name constraints** | Must match `[a-zA-Z][a-zA-Z0-9_]{0,47}` | Resolved: SHA-256 namespace hashing in Rust |

### Design Changes Required

| Original Design | Final Design |
|-----------------|--------------|
| `store_event` for every conversation turn | Store only: session goals, key decisions, outcomes |
| AWS Bedrock AgentCore (cloud) | ChromaDB (self-hosted Docker container) |
| Python + aiobotocore | Rust + reqwest |
| 0.25 req/sec rate limit per actor+session | No rate limits |
| Per-record/day cloud pricing | Zero cost (self-hosted) |
| PrivateLink for data plane | Local HTTP (no network boundary) |

---

## Executive Summary

This document describes the AgentCore Memory MCP server, a Rust-based service that provides persistent short-term and long-term memory for AI agents (Claude Code, Gemini, OpenCode, Crush, Codex) using ChromaDB as a self-hosted vector store.

**Key design principle**: This is NOT a logging system. Store sparse, high-value events (goals, decisions, outcomes) and explicit facts (codebase patterns, user preferences).

### Goals

1. **Cross-session memory**: Agents remember context across sessions
2. **Shared knowledge**: Multiple agents share learned patterns about the codebase
3. **Semantic search**: Find relevant past context via natural language queries
4. **Self-hosted**: Zero cloud cost, container-first philosophy

### Non-Goals

- Replacing GitHub Board for work coordination
- Depending on cloud services
- Automatic context injection (explicit memory calls only)
- **Logging every conversation turn**

---

## Architecture Overview

### Current Architecture

```
+-----------------------------------------------------------------+
|              SELF-HOSTED INFRASTRUCTURE                          |
|                                                                  |
|  +----------+  +----------+  +----------+  +---------+          |
|  |  Claude   |  |  Gemini  |  | OpenCode |  |  Codex  |          |
|  +-----+-----+  +-----+----+  +-----+----+  +----+----+          |
|        |              |              |             |               |
|        +--------------+--------------+-------------+              |
|                        |                                          |
|                        v                                          |
|  +------------------------------------------------------------+  |
|  |          mcp-agentcore-memory (Rust MCP Server)             |  |
|  |  +------------------+  +----------+  +------------------+  |  |
|  |  | ChromaDBClient   |  |  Cache   |  |   Sanitizer      |  |  |
|  |  | (reqwest HTTP)   |  |  (LRU)   |  |   (2-layer)      |  |  |
|  |  +--------+---------+  +----------+  +------------------+  |  |
|  +-----------|------------------------------------------------+  |
|              | HTTP (localhost:8000)                              |
|              v                                                    |
|  +------------------------------------------------------------+  |
|  |              ChromaDB (Docker Container)                    |  |
|  |  +------------------+  +------------------+                 |  |
|  |  | Short-Term       |  | Long-Term        |                 |  |
|  |  | Events Collection|  | Records (per-ns) |                 |  |
|  |  | (no rate limit)  |  | (no rate limit)  |                 |  |
|  |  +------------------+  +------------------+                 |  |
|  +------------------------------------------------------------+  |
+-----------------------------------------------------------------+
```

### Memory Lifecycle Flow

```
Agent Input --> Sanitize Secrets (Layer 1: regex, Layer 2: entropy)
                    |
                    +--> store_event (short-term, per-session)
                    |       |
                    |       v
                    |   ChromaDB events collection
                    |
                    +--> store_facts (long-term, per-namespace)
                    |       |
                    |       v
                    |   ChromaDB records collection (SHA-256 hashed name)
                    |   + Cache invalidation for namespace
                    |
                    +--> search_memories (semantic search)
                            |
                            +--> Check LRU cache
                            |       |
                            |       +--> Hit: return cached results
                            |       +--> Miss: query ChromaDB, cache results
                            v
                        Return ranked results (cosine similarity)
```

---

## Component Design

### MCP Server: `mcp-agentcore-memory`

**Location**: `tools/mcp/mcp_agentcore_memory/`

**Purpose**: Persistent memory for AI agents via ChromaDB vector store

#### Directory Structure

```
tools/mcp/mcp_agentcore_memory/
+-- Cargo.toml
+-- src/
|   +-- main.rs          # CLI entry point, server initialization
|   +-- server.rs        # 6 MCP tool definitions and handlers
|   +-- client.rs        # ChromaDB HTTP client (reqwest)
|   +-- types.rs         # Data structures, ChromaDB API types, namespaces
|   +-- cache.rs         # LRU cache with TTL and namespace invalidation
|   +-- sanitize.rs      # Multi-layer secret sanitization
+-- docs/
    +-- README.md        # Quick start guide
    +-- RUNBOOK.md       # Operational procedures
```

#### Dependencies

```toml
[dependencies]
mcp-core = { path = "../mcp_core_rust/crates/mcp-core" }
tokio = { version = "1.40", features = ["full"] }
async-trait = "0.1"
reqwest = { version = "0.12", features = ["json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
clap = { version = "4.5", features = ["derive"] }
tracing = "0.1"
uuid = { version = "1.11", features = ["v4"] }
chrono = { version = "0.4", features = ["serde"] }
regex = "1.11"
sha2 = "0.10"
md5 = "0.7"
anyhow = "1.0"
```

#### MCP Tools (6 total)

| Tool | Purpose | Cache Behavior |
|------|---------|----------------|
| `store_event` | Short-term session events | No cache interaction |
| `store_facts` | Long-term knowledge storage | Invalidates namespace cache |
| `search_memories` | Semantic similarity search | Read-through cache |
| `list_session_events` | Retrieve session history | No cache interaction |
| `list_namespaces` | Discover available namespaces | Static data |
| `memory_status` | Health check and metrics | Reports cache stats |

### Predefined Namespaces

```rust
pub mod namespaces {
    // Codebase Knowledge
    pub const ARCHITECTURE: &str = "codebase/architecture";
    pub const PATTERNS: &str = "codebase/patterns";
    pub const CONVENTIONS: &str = "codebase/conventions";
    pub const DEPENDENCIES: &str = "codebase/dependencies";

    // Review Context
    pub const PR_REVIEWS: &str = "reviews/pr";
    pub const ISSUE_CONTEXT: &str = "reviews/issues";

    // User Preferences
    pub const USER_PREFS: &str = "preferences/user";
    pub const PROJECT_PREFS: &str = "preferences/project";

    // Agent-Specific Learnings
    pub const CLAUDE_LEARNINGS: &str = "agents/claude";
    pub const GEMINI_LEARNINGS: &str = "agents/gemini";
    pub const OPENCODE_LEARNINGS: &str = "agents/opencode";
    pub const CRUSH_LEARNINGS: &str = "agents/crush";
    pub const CODEX_LEARNINGS: &str = "agents/codex";

    // Security & Testing
    pub const SECURITY_PATTERNS: &str = "security/patterns";
    pub const TESTING_PATTERNS: &str = "testing/patterns";
}
```

---

## Server Implementation

### Entry Point

```rust
// main.rs
use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use server::MemoryServer;

#[derive(Parser)]
#[command(name = "mcp-agentcore-memory")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let memory_server = MemoryServer::new();
    let mut builder = MCPServer::builder("agentcore-memory", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in memory_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();
    server.run().await?;
    Ok(())
}
```

### Server Structure

```rust
// server.rs
pub struct MemoryServer {
    client: Arc<ChromaDBClient>,
    cache: Arc<RwLock<MemoryCache>>,
}

impl MemoryServer {
    pub fn new() -> Self {
        let config = ChromaDBConfig::from_env();
        let client = ChromaDBClient::new(config);
        Self {
            client: Arc::new(client),
            cache: Arc::new(RwLock::new(MemoryCache::default())),
        }
    }

    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(StoreEventTool { client: self.client.clone() }),
            Arc::new(StoreFactsTool {
                client: self.client.clone(),
                cache: self.cache.clone(),
            }),
            Arc::new(SearchMemoriesTool {
                client: self.client.clone(),
                cache: self.cache.clone(),
            }),
            Arc::new(ListSessionEventsTool { client: self.client.clone() }),
            Arc::new(ListNamespacesTool),
            Arc::new(MemoryStatusTool {
                client: self.client.clone(),
                cache: self.cache.clone(),
            }),
        ]
    }
}
```

### Core Types

```rust
// types.rs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEvent {
    pub id: String,
    pub actor_id: String,
    pub session_id: String,
    pub content: String,
    pub timestamp: DateTime<Utc>,
    pub metadata: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryRecord {
    pub id: String,
    pub content: String,
    pub namespace: String,
    pub relevance: Option<f64>,           // Cosine similarity score
    pub created_at: Option<DateTime<Utc>>,
    pub metadata: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchResult {
    pub created: usize,
    pub failed: usize,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct ChromaDBConfig {
    pub host: String,              // default: "localhost"
    pub port: u16,                 // default: 8000
    pub collection_prefix: String, // default: "agent_memory"
}
```

---

## ChromaDB Client

### Client Structure

```rust
// client.rs
pub struct ChromaDBClient {
    client: Client,                                         // reqwest HTTP client
    config: ChromaDBConfig,
    collection_cache: Arc<RwLock<HashMap<String, String>>>, // name -> ID cache
}
```

### Collection Naming Strategy

Collections use SHA-256 hashing for stable, cross-platform naming:

```rust
// Events collection: "{prefix}_events"
fn events_collection_name(&self) -> String {
    format!("{}_events", self.config.collection_prefix)
}

// Records collection: "{prefix}_rec_{sha256_hash}"
fn records_collection_name(&self, namespace: &str) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(namespace.as_bytes());
    let hash = hasher.finalize();
    let hash_str: String = hash.iter().take(8).map(|b| format!("{:02x}", b)).collect();
    format!("{}_rec_{}", self.config.collection_prefix, hash_str)
}
```

**Why SHA-256?** Ensures stable hashing across compiler versions so existing memories remain accessible after rebuilds. Also prevents collision between similar namespaces (`a/b`, `a-b`, `a_b`).

### Store Event (Short-Term Memory)

```rust
pub async fn store_event(
    &self,
    actor_id: &str,
    session_id: &str,
    content: &str,
    metadata: Option<HashMap<String, Value>>,
) -> Result<MemoryEvent, String> {
    let collection_name = self.events_collection_name();
    let collection_id = self.get_or_create_collection(&collection_name).await?;

    let event_id = uuid::Uuid::new_v4().to_string();
    let timestamp = Utc::now();
    let sanitized_content = sanitize_content(content);

    // Reserved system keys prevent user metadata collisions
    const RESERVED_KEYS: &[&str] = &["actor_id", "session_id", "timestamp"];

    let mut meta: HashMap<String, Value> = HashMap::new();
    if let Some(extra) = metadata.clone() {
        for (k, v) in extra {
            if !RESERVED_KEYS.contains(&k.as_str()) {
                meta.insert(k, flatten_metadata_value(v));
            }
        }
    }
    meta.insert("actor_id".to_string(), json!(actor_id));
    meta.insert("session_id".to_string(), json!(session_id));
    meta.insert("timestamp".to_string(), json!(timestamp.to_rfc3339()));

    // POST to ChromaDB
    let url = format!("{}/api/v1/collections/{}/add", self.base_url(), collection_id);
    let request = AddDocumentsRequest {
        ids: vec![event_id.clone()],
        documents: vec![sanitized_content.clone()],
        metadatas: Some(vec![meta]),
    };

    self.client.post(&url).json(&request).send().await?;

    Ok(MemoryEvent { id: event_id, actor_id: actor_id.to_string(), /* ... */ })
}
```

### Search Records (Semantic Search)

```rust
pub async fn search_records(
    &self,
    query: &str,
    namespace: &str,
    top_k: u32,
) -> Result<Vec<MemoryRecord>, String> {
    let collection_name = self.records_collection_name(namespace);
    let collection_id = self.get_or_create_collection(&collection_name).await?;

    let url = format!("{}/api/v1/collections/{}/query", self.base_url(), collection_id);
    let request = QueryRequest {
        query_texts: vec![query.to_string()],
        n_results: top_k,
        include: vec!["documents", "metadatas", "distances"],
    };

    let response = self.client.post(&url).json(&request).send().await?;
    let query_result: QueryResponse = response.json().await?;

    // Convert cosine distances to relevance scores
    // relevance = 1.0 - distance
    // Returns ordered by relevance (highest first)
}
```

### Metadata Flattening

ChromaDB only supports primitive types (string, int, float, bool). Arrays and objects are serialized to JSON strings:

```rust
fn flatten_metadata_value(value: Value) -> Value {
    match value {
        Value::Null | Value::Bool(_) | Value::Number(_) | Value::String(_) => value,
        Value::Array(_) | Value::Object(_) => {
            Value::String(serde_json::to_string(&value).unwrap_or_default())
        },
    }
}
```

---

## Local Memory Cache

### Implementation

```rust
// cache.rs
struct CacheEntry {
    results: Vec<Value>,
    timestamp: Instant,
    namespace: String,
}

pub struct MemoryCache {
    max_size: usize,    // default: 1000
    ttl: Duration,      // default: 300 seconds (5 minutes)
    cache: HashMap<String, CacheEntry>,
}
```

### Cache Key Generation

```rust
fn make_key(query: &str, namespace: &str) -> String {
    let data = format!("{}:{}", query, namespace);
    format!("{:x}", md5::compute(data.as_bytes()))
}
```

### Get (with LRU Timestamp Update)

```rust
pub fn get(&mut self, query: &str, namespace: &str) -> Option<Vec<Value>> {
    let key = Self::make_key(query, namespace);
    if let Some(entry) = self.cache.get_mut(&key) {
        if entry.timestamp.elapsed() < self.ttl {
            entry.timestamp = Instant::now(); // LRU update
            return Some(entry.results.clone());
        }
    }
    None
}
```

### Namespace-Aware Invalidation

```rust
pub fn invalidate(&mut self, namespace: Option<&str>) -> usize {
    match namespace {
        None => {
            let count = self.cache.len();
            self.cache.clear();
            count
        },
        Some(ns) => {
            // Invalidate entries for namespace AND sub-namespaces
            let keys_to_remove: Vec<String> = self.cache.iter()
                .filter(|(_, entry)| {
                    entry.namespace == ns || entry.namespace.starts_with(&format!("{}/", ns))
                })
                .map(|(k, _)| k.clone())
                .collect();

            let count = keys_to_remove.len();
            for key in keys_to_remove {
                self.cache.remove(&key);
            }
            count
        },
    }
}
```

---

## Security: Content Sanitization

### Two-Layer Defense

**Layer 1: Known Secret Patterns** (18 regex patterns)

```rust
// sanitize.rs
static BLOCKED_PATTERNS: LazyLock<Vec<(&'static str, Regex)>> = LazyLock::new(|| {
    vec![
        // Generic secrets
        ("generic_secret", Regex::new(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+").unwrap()),
        // Private keys
        ("private_key", Regex::new(r"-----BEGIN.*PRIVATE KEY-----").unwrap()),
        // OpenAI / Stripe
        ("openai_stripe", Regex::new(r"(sk-|pk_|rk_)[a-zA-Z0-9]{20,}").unwrap()),
        // AWS
        ("aws_access_key", Regex::new(r"AKIA[0-9A-Z]{16}").unwrap()),
        // GitHub PATs
        ("github_pat_new", Regex::new(r"gh[pousr]_[A-Za-z0-9_]{36,}").unwrap()),
        ("github_pat_fine", Regex::new(r"github_pat_[A-Za-z0-9_]{22,}").unwrap()),
        // Anthropic & OpenRouter
        ("anthropic_key", Regex::new(r"sk-ant-[a-zA-Z0-9-]+").unwrap()),
        ("openrouter_key", Regex::new(r"sk-or-[a-zA-Z0-9-]+").unwrap()),
        // Auth tokens
        ("bearer_token", Regex::new(r"Bearer\s+[A-Za-z0-9_-]{20,}").unwrap()),
        // Connection strings
        ("connection_string", Regex::new(r"(?i)(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@").unwrap()),
        // ... and more
    ]
});
```

**Layer 2: High-Entropy Detection**

```rust
fn calculate_entropy(s: &str) -> f64 {
    if s.is_empty() { return 0.0; }
    let mut counts: HashMap<char, usize> = HashMap::new();
    for c in s.chars() {
        *counts.entry(c).or_insert(0) += 1;
    }
    let length = s.len() as f64;
    counts.values()
        .map(|&count| {
            let p = count as f64 / length;
            -p * p.log2()
        })
        .sum()
}

fn is_high_entropy_blob(s: &str, threshold: f64, min_length: usize) -> bool {
    if s.len() < min_length { return false; }
    // Only check base64-like strings
    static BASE64_LIKE: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"^[A-Za-z0-9+/=_-]+$").unwrap());
    if !BASE64_LIKE.is_match(s) { return false; }
    calculate_entropy(s) > threshold  // Default: 4.5 bits/char
}
```

### Data Classification

| Data Type | Sensitivity | Storage Policy |
|-----------|-------------|----------------|
| Codebase patterns | Low | Store freely in `codebase/*` namespaces |
| User preferences | Medium | Sanitize before storing in `preferences/*` |
| API keys / tokens | **Critical** | **NEVER store** - auto-redacted by sanitizer |
| PR review context | Low-Medium | Store summaries, not full diffs |

---

## Infrastructure Setup

### Prerequisites

- Docker and Docker Compose installed
- Rust toolchain (for building from source) or pre-built binary
- Available port 8000 for ChromaDB

### Docker Compose Configuration

```yaml
# docker-compose.yml
services:
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chromadb_data:/chroma/chroma
    environment:
      - IS_PERSISTENT=TRUE
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3

  mcp-agentcore-memory:
    build: ./tools/mcp/mcp_agentcore_memory
    environment:
      - CHROMADB_HOST=chromadb
      - CHROMADB_PORT=8000
      - RUST_LOG=info
    depends_on:
      chromadb:
        condition: service_healthy

volumes:
  chromadb_data:
```

### MCP Configuration (Claude Code)

```json
{
  "mcpServers": {
    "agentcore-memory": {
      "command": "./tools/mcp/mcp_agentcore_memory/target/release/mcp-agentcore-memory",
      "args": ["--mode", "stdio"],
      "env": {
        "CHROMADB_HOST": "localhost",
        "CHROMADB_PORT": "8000",
        "RUST_LOG": "info"
      }
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMADB_HOST` | `localhost` | ChromaDB server hostname |
| `CHROMADB_PORT` | `8000` | ChromaDB server port |
| `CHROMADB_COLLECTION` | `agent_memory` | Collection name prefix |
| `RUST_LOG` | `info` | Log level (debug, info, warn, error) |

---

## Integration Points

### 1. Claude Code Integration

```json
// Store a codebase pattern after discovering it
{
  "tool": "store_facts",
  "params": {
    "facts": [
      "MCP servers follow the pattern: MCPServer::builder() + tool_boxed() + server.run().await",
      "All workspace crates use kebab-case names prefixed by package name"
    ],
    "namespace": "codebase/patterns",
    "source": "claude-code"
  }
}

// Search for relevant context before starting work
{
  "tool": "search_memories",
  "params": {
    "query": "how are MCP servers structured in this repo",
    "namespace": "codebase/patterns",
    "top_k": 5
  }
}

// Store session goal at start
{
  "tool": "store_event",
  "params": {
    "content": "Goal: Implement new mcp-weather server following existing patterns",
    "actor_id": "claude-code",
    "session_id": "session-2026-02-16-abc123"
  }
}
```

### 2. GitHub Agents Integration

```json
// Store PR review context
{
  "tool": "store_facts",
  "params": {
    "facts": [
      "PR #289 refactored composite actions for PR review reuse",
      "PR reviews should check for Unicode emoji violations per CLAUDE.md"
    ],
    "namespace": "reviews/pr",
    "source": "gemini"
  }
}
```

### 3. Gemini Code Review Integration

```json
// Search for relevant patterns before reviewing
{
  "tool": "search_memories",
  "params": {
    "query": "common review issues in Rust MCP servers",
    "namespace": "reviews/pr",
    "top_k": 3
  }
}
```

---

## Testing Strategy

### Unit Tests (Rust)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_aws_key() {
        let content = "key = AKIAIOSFODNN7EXAMPLE";
        let sanitized = sanitize_content(content);
        assert!(sanitized.contains("[REDACTED]"));
        assert!(!sanitized.contains("AKIAIOSFODNN7EXAMPLE"));
    }

    #[test]
    fn test_sanitize_github_pat() {
        let content = "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl";
        let sanitized = sanitize_content(content);
        assert!(sanitized.contains("[REDACTED]"));
    }

    #[test]
    fn test_high_entropy_detection() {
        // Random base64-like string with high entropy
        let high_entropy = "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1v";
        assert!(is_high_entropy_blob(high_entropy, 4.5, 20));

        // Normal text has low entropy
        let normal = "hello world this is normal text";
        assert!(!is_high_entropy_blob(normal, 4.5, 20));
    }

    #[test]
    fn test_server_creation() {
        // Verify server initializes with all 6 tools
        let server = MemoryServer::new();
        assert_eq!(server.tools().len(), 6);
    }

    #[test]
    fn test_collection_name_stability() {
        // SHA-256 hashing must produce stable names across rebuilds
        let client = ChromaDBClient::new(ChromaDBConfig::default());
        let name1 = client.records_collection_name("codebase/patterns");
        let name2 = client.records_collection_name("codebase/patterns");
        assert_eq!(name1, name2);
    }
}
```

### Running Tests

```bash
# Via CI
automation-cli ci run mcp-test

# Direct (requires ChromaDB running)
docker compose run --rm -w /app/tools/mcp/mcp_agentcore_memory rust-ci cargo test

# With logging
RUST_LOG=debug cargo test -- --nocapture
```

---

## Monitoring

### Health Check

```json
// Use the memory_status MCP tool
{
  "tool": "memory_status",
  "params": {}
}

// Response:
{
  "status": "connected",
  "provider": {
    "type": "chromadb",
    "host": "localhost",
    "port": 8000,
    "semantic_search": true,
    "collection_prefix": "agent_memory"
  },
  "cache": {
    "size": 42,
    "max_size": 1000,
    "ttl_seconds": 300,
    "expired_entries": 3,
    "active_entries": 39
  }
}
```

### ChromaDB Direct Health Check

```bash
# Check ChromaDB heartbeat
curl http://localhost:8000/api/v1/heartbeat

# List collections
curl http://localhost:8000/api/v1/collections

# View logs
docker compose logs -f mcp-agentcore-memory
```

### Key Metrics

- **Latency**: `store_event` (5-20ms), `search_memories` (10-50ms), `list_session_events` (5-30ms)
- **Error rates**: Success/failure counts by operation type
- **ChromaDB health**: Heartbeat endpoint and collection count
- **Cache effectiveness**: Hit rate from `memory_status` tool

---

## Latency and Performance

| Operation | Expected Latency | Notes |
|-----------|------------------|-------|
| `store_event` | 5-20ms | Local ChromaDB write |
| `search_memories` | 10-50ms | LRU cache with 5-min TTL |
| `list_session_events` | 5-30ms | Session-scoped query |
| `store_facts` | 10-30ms | Batch write + cache invalidation |
| `list_namespaces` | <1ms | Static data, no DB call |
| `memory_status` | 5-10ms | Heartbeat check |

---

## Backup and Recovery

### Volume Backup

```bash
# Stop server for consistency
docker compose stop chromadb

# Create compressed backup
docker run --rm \
    -v chromadb_data:/data \
    -v $(pwd)/backups:/backup \
    alpine tar czf /backup/chromadb-$(date +%Y%m%d).tar.gz -C /data .

# Restart
docker compose up -d chromadb
```

### Volume Restore

```bash
# Stop services
docker compose stop chromadb mcp-agentcore-memory

# Restore from backup
docker run --rm \
    -v chromadb_data:/data \
    -v $(pwd)/backups:/backup \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/chromadb-20260101.tar.gz -C /data"

# Restart
docker compose up -d chromadb mcp-agentcore-memory
```

### Backup Schedule

- **Weekly full backup**: `0 0 * * 0 ./scripts/backup-chromadb.sh`
- **Store locally**: Keep backups on a separate drive or NAS
- **Test restores**: Quarterly restore to test environment
- **Retention**: Keep 4 weekly backups, 3 monthly backups

---

## Cost Estimation

| Component | Est. Volume | Monthly Cost |
|-----------|-------------|--------------|
| ChromaDB container | Persistent | $0.00 |
| Storage volume | <1 GB | $0.00 |
| Semantic searches | Unlimited | $0.00 |
| **Total** | | **$0.00** |

ChromaDB is open-source and runs locally. The only costs are disk storage and compute overhead (minimal).

---

## Rollout Plan

### Phase 1: Foundation
- [x] Create `mcp_agentcore_memory` Rust crate structure
- [x] Implement `ChromaDBClient` with reqwest HTTP client
- [x] Implement MCP server with 6 core tools
- [x] Write unit tests (sanitization, cache, server creation)
- [x] Set up ChromaDB Docker service

### Phase 2: Claude Code Integration
- [x] Add MCP config for Claude Code
- [x] Store codebase patterns during sessions
- [x] Search for context at session start
- [x] Validate end-to-end flow

### Phase 3: GitHub Agents Integration
- [ ] Integrate with issue/PR monitors
- [ ] Store review context and patterns
- [ ] Cross-agent knowledge sharing

### Phase 4: Production Hardening
- [ ] Add comprehensive monitoring
- [ ] Set up automated backups
- [ ] Document operational runbook
- [ ] Performance tuning

---

## References

- [ChromaDB - Open-Source Vector Database](https://github.com/chroma-core/chroma)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [reqwest - Rust HTTP Client](https://docs.rs/reqwest/latest/reqwest/)
- MCP Server Source: `tools/mcp/mcp_agentcore_memory/`
- MCP Server Docs: `tools/mcp/mcp_agentcore_memory/docs/README.md`
- MCP Server Runbook: `tools/mcp/mcp_agentcore_memory/docs/RUNBOOK.md`
