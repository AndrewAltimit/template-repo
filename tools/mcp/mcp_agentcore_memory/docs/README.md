# AgentCore Memory MCP Server - Design Notes

The user-facing reference (tools, parameters, configuration, limitations) is
the crate [README](../README.md). This page explains how the server works
internally. Operational procedures are in the [RUNBOOK](RUNBOOK.md).

## Request Flow

```
MCP client (stdio / HTTP)
  |
  v
server.rs        typed argument structs -> InvalidParameters on bad input
  |
  v
service.rs       validate -> sanitize -> dedupe -> embed -> store / query
  |          \
  |           +-- cache.rs      search cache keyed by (namespace, top_k, query)
  |           +-- embedding.rs  FastEmbedder (ONNX, 384 dims) | HashEmbedder (256 dims)
  v
store/chroma.rs  ChromaDB REST client (auto-detects v2 or v1 API)
  |
  v
ChromaDB server (docker compose service `chromadb`)
```

## Why Embeddings Are Computed Here

ChromaDB's REST API stores and searches vectors; it never turns text into
vectors. The official Python/JS clients run an embedding function before each
request. Releases of this server before 1.1.0 sent `documents` without
`embeddings` and `query_texts` without `query_embeddings`, which meant:

- every `search_memories` call failed with HTTP 422 (`query_embeddings` missing);
- facts were stored as text only, with no vector, so they could never match;
- on ChromaDB 1.x, the vector-less writes broke the collection entirely.

The server now embeds locally with all-MiniLM-L6-v2 via ONNX Runtime
(`fastembed` crate), matching the default embedding function of ChromaDB's
Python client. Model inference runs on Tokio's blocking pool so it never stalls
the async runtime; the model is loaded lazily and shared.

Old facts can be made searchable with `reindex_namespace`.

## Embedder Safety

Each collection created by this server records `embedder` and `embedding_dim`
in its metadata. Before writing to or searching a collection the service checks
that the recorded embedder matches the running one (once per collection per
process) and fails with `incompatible_collection` otherwise. The two built-in
embedders also use different dimensions (384 vs 256), so even an unchecked
mix would be rejected by ChromaDB instead of producing meaningless scores.

## Collection Naming

Names are unchanged from earlier releases so existing data stays reachable:

- events: `{prefix}_events`
- facts: `{prefix}_rec_{first 16 hex chars of SHA-256(namespace)}`

Hashing keeps names within ChromaDB's 3-63 character limit and prevents
collisions such as `a/b` vs `a-b`. Because names are hashes, the namespace is
also stored in the collection metadata (and in every record) so
`list_namespaces(include_stored=true)` can map collections back to namespaces.

## Deduplication

A fact's id is `fact-` + the first 32 hex chars of
SHA-256(`namespace` + newline + sanitized text). `store_facts` looks the ids up
first and only embeds and writes the new ones, so repeated stores are cheap and
keep the original `created_at`.

## Robustness

- All ChromaDB requests share a client with a connect timeout (10 s) and a
  total timeout (`CHROMADB_TIMEOUT_SECS`, default 30 s).
- Reads on a collection that does not exist return empty results and do not
  create it.
- Cached collection ids that go stale (collection deleted or recreated) are
  dropped and the operation is retried once.
- Upstream error bodies are truncated to 500 characters.
- The release profile keeps unwinding, so mcp-core's panic boundary can turn an
  unexpected panic into a tool error rather than killing the server.

## Testing Strategy

`store/memory.rs` implements the `VectorStore` trait in memory with ChromaDB's
semantics (create on write, empty reads for missing collections, fixed
dimension, cosine distance). Combined with the deterministic `HashEmbedder`,
`src/tests.rs` exercises every tool end to end without network access.
`live_chromadb_roundtrip` (ignored by default) runs the same flows against a
real ChromaDB and has been verified against 0.4.24 (v1 API), 0.5.23 and 1.0.x
(v2 API).
