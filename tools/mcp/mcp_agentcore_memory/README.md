# AgentCore Memory MCP Server (Rust)

> A Model Context Protocol server that gives AI agents persistent memory backed
> by a self-hosted ChromaDB vector database: short-term session events,
> long-term facts organized in namespaces, and semantic search over those facts.

Despite the historical name, this server does **not** talk to AWS Bedrock
AgentCore. ChromaDB is the only backend.

## Features

- **Session events** (`store_event`, `list_session_events`): goals, decisions
  and outcomes for an `(actor_id, session_id)` pair, listed newest first.
- **Long-term facts** (`store_facts`): stored per namespace, deduplicated by
  content (storing the same fact twice is a no-op that reports a duplicate).
- **Semantic search** (`search_memories`): embeddings are computed locally with
  all-MiniLM-L6-v2 (the model ChromaDB's Python client uses by default), so
  results are ranked by meaning, not keywords.
- **Memory hygiene** (`list_memories`, `delete_memories`, `reindex_namespace`):
  browse a namespace, delete wrong or stale facts, and re-embed old data.
- **Secret sanitization**: content and string metadata are scrubbed of API keys,
  tokens, private keys, passwords and high-entropy blobs before storage.
- **Search cache**: in-process LRU/TTL cache, invalidated on writes and deletes.
- **ChromaDB 0.4.x through 1.x**: speaks both the v1 and v2 REST APIs and picks
  the right one automatically.

## Quick Start

```bash
# Start ChromaDB (profile "memory-chromadb" in the repo's docker-compose.yml)
docker compose --profile memory-chromadb up -d chromadb

# Build and run locally
cd tools/mcp/mcp_agentcore_memory
cargo build --release
./target/release/mcp-agentcore-memory --mode stdio                    # for MCP clients
./target/release/mcp-agentcore-memory --mode standalone --port 8023   # HTTP

# HTTP mode checks
curl http://localhost:8023/health
curl http://localhost:8023/mcp/tools
curl -X POST http://localhost:8023/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "memory_status", "arguments": {}}'
```

The first call that needs an embedding downloads the model (~90 MB) into
`MEMORY_MODEL_CACHE_DIR`. Run `mcp-agentcore-memory --prefetch-model` once to
do this ahead of time; the Docker image already contains the model.

## Tools

All tools return JSON text. Invalid arguments produce an MCP
`InvalidParameters` error with a specific message. Runtime failures (ChromaDB
unreachable, embedding failure, ...) produce a tool result with `isError: true`
whose text is `{"success": false, "error": "...", "error_kind": "..."}` where
`error_kind` is one of `store_unavailable`, `store_error`, `embedding_error`,
`incompatible_collection`.

| Tool | Purpose | Parameters |
|------|---------|------------|
| `store_event` | Store a short-term session event | `content` (req), `actor_id` (req), `session_id` (req), `metadata` (object) |
| `list_session_events` | List a session's events, newest first | `actor_id` (req), `session_id` (req), `limit` (1-1000, default 50) |
| `store_facts` | Store long-term facts in a namespace | `facts` (req, 1-100 strings), `namespace` (req), `source` |
| `search_memories` | Semantic search within one namespace | `query` (req), `namespace` (req), `top_k` (1-50, default 5), `min_relevance` (-1..1) |
| `list_memories` | Browse a namespace without a query | `namespace` (req), `limit` (1-1000, default 20), `offset` (default 0) |
| `delete_memories` | Delete facts by id | `namespace` (req), `ids` (req, 1-100) |
| `reindex_namespace` | Re-embed every fact in a namespace | `namespace` (req) |
| `list_namespaces` | Predefined namespaces (plus stored ones) | `include_stored` (bool, default false) |
| `memory_status` | Connectivity, ChromaDB version, embedder, cache stats | none |

Limits: content/facts/queries up to 32 KiB each; identifiers (`actor_id`,
`session_id`, `source`, ids) up to 256 bytes without control characters;
`store_event` metadata up to 32 keys (nested values are stored as JSON strings,
`null` values are dropped, `actor_id`/`session_id`/`timestamp`/`timestamp_ms`
are reserved and reported back in `ignored_metadata_keys`).

### Examples

```jsonc
// store_facts
{"facts": ["All Rust MCP servers use the mcp-core crate"], "namespace": "codebase/patterns", "source": "PR #42"}
// -> {"success": true, "created": 1, "duplicates": 0, "failed": 0,
//     "namespace": "codebase/patterns", "ids": ["fact-ce0e..."], "redacted": 0}

// search_memories
{"query": "what do the MCP servers build on", "namespace": "codebase/patterns", "top_k": 3}
// -> {"query": "...", "namespace": "codebase/patterns", "count": 1, "cached": false,
//     "memories": [{"id": "fact-ce0e...", "content": "...", "relevance": 0.61,
//                   "created_at": "...", "source": "PR #42", "metadata": {}, "namespace": "..."}]}

// store_event
{"content": "Goal: migrate CI to Rust", "actor_id": "claude-code", "session_id": "2026-09-22",
 "metadata": {"pr": 335}}

// delete_memories
{"namespace": "codebase/patterns", "ids": ["fact-ce0e..."]}
// -> {"success": true, "namespace": "...", "deleted": ["fact-ce0e..."], "not_found": []}
```

`relevance` is `1 - cosine distance` (1.0 = identical meaning). Ranking matters
more than absolute values: with MiniLM a paraphrased match often scores only
0.3-0.6 while unrelated text tends to score below about 0.1. Use
`min_relevance` to drop weak matches.

## Namespaces

Facts live in hierarchical, `/`-separated namespaces. Any namespace made of
segments of ASCII letters, digits, `_`, `-` and `.` (max 128 bytes, no empty or
`..` segments) is accepted; the predefined ones help agents converge:

| Category | Namespaces |
|----------|------------|
| Codebase | `codebase/architecture`, `codebase/patterns`, `codebase/conventions`, `codebase/dependencies` |
| Reviews | `reviews/pr`, `reviews/issues` |
| Preferences | `preferences/user`, `preferences/project` |
| Agents | `agents/claude`, `agents/gemini`, `agents/opencode`, `agents/crush`, `agents/codex` |
| Personality | `personality/voice_preferences`, `personality/expression_patterns`, `personality/reaction_history`, `personality/avatar_settings` |
| Context | `context/conversation_tone`, `context/user_preferences`, `context/interaction_history` |
| Cross-cutting | `security/patterns`, `testing/patterns`, `performance/patterns` |

Each namespace is its own ChromaDB collection, so a search covers exactly one
namespace; `codebase` does not include `codebase/patterns`.
`list_namespaces` with `include_stored: true` shows which namespaces hold data
and how many facts each has.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMADB_URL` | unset | Full ChromaDB base URL (e.g. `http://chromadb:8000`); overrides host/port |
| `CHROMADB_HOST` | `localhost` | ChromaDB host |
| `CHROMADB_PORT` | `8000` | ChromaDB port |
| `CHROMADB_TENANT` | `default_tenant` | Tenant (v2 API only) |
| `CHROMADB_DATABASE` | `default_database` | Database (v2 API only) |
| `CHROMADB_COLLECTION` | `agent_memory` | Collection name prefix (1-40 chars of `[A-Za-z0-9_-]`) |
| `CHROMADB_TIMEOUT_SECS` | `30` | Per-request timeout (1-600) |
| `MEMORY_EMBEDDER` | `fastembed` | `fastembed` (semantic, all-MiniLM-L6-v2) or `hash` (lexical, offline) |
| `MEMORY_MODEL_CACHE_DIR` | `$XDG_CACHE_HOME` or `~/.cache` + `/mcp-agentcore-memory/models` | Model file location (`FASTEMBED_CACHE_DIR` is also honored) |
| `MEMORY_CACHE_TTL_SECS` | `300` | Search cache TTL; `0` disables the cache |
| `MEMORY_CACHE_MAX_ENTRIES` | `1000` | Search cache capacity; `0` disables the cache |
| `RUST_LOG` | from `--log-level` | Log filter (logs go to stderr) |

Invalid values are logged and replaced by the default.

### CLI

```
--mode <MODE>         standalone | stdio | server | client   [default: standalone]
--port <PORT>         HTTP port (use 8023 for this server)   [default: 8000]
--backend-url <URL>   Backend for client mode
--log-level <LEVEL>   [default: info]
--prefetch-model      Download/load the embedding model, then exit
```

### MCP client configuration

The repository's `.mcp.json` runs the server through Docker Compose
(`docker compose --profile memory run --rm -T mcp-agentcore-memory mcp-agentcore-memory --mode stdio`).
For a locally built binary:

```json
{
  "mcpServers": {
    "agentcore-memory": {
      "command": "mcp-agentcore-memory",
      "args": ["--mode", "stdio"],
      "env": {"CHROMADB_URL": "http://localhost:8000"}
    }
  }
}
```

## Storage Layout

| Data | Collection | Record metadata |
|------|------------|-----------------|
| Session events | `{prefix}_events` | `actor_id`, `session_id`, `timestamp` (RFC 3339), `timestamp_ms`, user metadata |
| Facts | `{prefix}_rec_{sha256(namespace)[0..16 hex]}` | `namespace`, `created_at`, `source` |

Fact ids are `fact-` + a SHA-256 prefix of namespace and sanitized text, which
makes `store_facts` idempotent. Collections created by this release carry
`hnsw:space=cosine`, `embedder`, `embedding_dim`, `kind` and `namespace` in
their metadata. The server refuses to write to or search a collection built
with a different embedder (`incompatible_collection`) instead of returning
meaningless similarities; switch embedders by also changing
`CHROMADB_COLLECTION`.

## Security

Every piece of content and every string metadata value passes through two
layers before being embedded or stored:

1. **Known formats** replaced by `[REDACTED]`: PEM private-key blocks,
   connection strings with inline passwords, Anthropic/OpenRouter/OpenAI/Stripe
   keys, AWS access keys and labelled secret keys, GitHub tokens (classic and
   fine-grained), Slack tokens, Google OAuth tokens and API keys, Hugging Face
   tokens, JWTs, Bearer/Basic credentials, and labelled assignments such as
   `password=...`, `api_key: ...`, `token = ...`.
2. **High-entropy tokens** replaced by `[HIGH_ENTROPY_REDACTED]`: base64 /
   url-safe tokens of 20+ chars with both letters and digits and Shannon
   entropy above 4.5 bits/char. Paths, UUIDs and git SHAs are left intact.

Responses report `redacted` (and for events the detector names) so callers
know something was scrubbed. This is a safety net; do not send credentials to
memory tools deliberately.

## Limitations

- The search cache is per process. Facts written by another process sharing the
  same ChromaDB become visible to cached queries only after the TTL expires.
- `list_session_events` sorts client-side (ChromaDB `get` has no ordering) and
  scans at most 50,000 events per session; `truncated_scan: true` is set if
  the cap is hit.
- `reindex_namespace` processes at most 100,000 facts per call and cannot
  change a collection's embedding dimension.
- Facts stored by releases before 1.1.0 were written without embeddings (the
  old client relied on ChromaDB embedding server-side, which its HTTP API never
  does), so they are invisible to `search_memories` until you run
  `reindex_namespace` on their namespace. On ChromaDB 1.x such vector-less
  writes break the collection (every later request fails with a compaction
  error), so never point pre-1.1.0 binaries at ChromaDB 1.x.
- Search covers one namespace per call.

## Development

```bash
cd tools/mcp/mcp_agentcore_memory
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test                                   # offline: in-memory store + hash embedder
cargo test --no-default-features             # build without ONNX Runtime

# Live integration test against a real ChromaDB (any version 0.4.x - 1.x)
docker run -d --rm -p 8000:8000 chromadb/chroma:0.5.23
CHROMADB_TEST_URL=http://localhost:8000 cargo test -- --ignored live_chromadb
```

The `fastembed` cargo feature (default) pulls in ONNX Runtime; build with
`--no-default-features` for a lean binary that only offers the `hash` embedder.

### Project structure

```
src/
  main.rs          CLI entry point, wiring, --prefetch-model
  config.rs        Environment configuration
  server.rs        MCP tool definitions (typed argument parsing, schemas)
  service.rs       Tool logic: validation, sanitization, dedup, caching
  embedding.rs     Embedder trait, FastEmbedder (ONNX) and HashEmbedder
  store/mod.rs     VectorStore trait and shared types
  store/chroma.rs  ChromaDB v1/v2 HTTP implementation
  store/memory.rs  In-memory store for tests
  cache.rs         Search-result LRU/TTL cache
  sanitize.rs      Secret redaction
  namespaces.rs    Predefined namespaces and validation
  tests.rs         End-to-end tool tests
docs/
  README.md        Architecture notes
  RUNBOOK.md       Operations: health, backup/restore, troubleshooting
```

## License

Part of the template-repo project. See repository LICENSE file.
