# AgentCore Memory Operations Runbook

Operational procedures for the ChromaDB-backed memory server. Commands assume
the repository root and the services defined in `docker-compose.yml`
(`chromadb` with the `chromadb_data` volume, `mcp-agentcore-memory`).

## Health Check

```bash
# ChromaDB itself (v2 API; 0.4.x servers only answer /api/v1/heartbeat)
curl -s http://localhost:8000/api/v2/heartbeat

# The MCP server in HTTP mode
curl -s http://localhost:8023/health
curl -s -X POST http://localhost:8023/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "memory_status", "arguments": {}}'
```

In Claude Code, call the `memory_status` tool. A healthy response has
`"status": "connected"`, a `provider.server_version`, and
`embedder.id` = `fastembed-all-minilm-l6-v2`. `embedder.loaded` becomes true
after the first embedding.

## Inventory

`list_namespaces` with `{"include_stored": true}` lists every namespace that
holds facts, with counts and the embedder that built it. `list_memories` pages
through a namespace.

## Backup

ChromaDB keeps everything in the `chromadb_data` volume. Stop writers first for
a consistent copy.

```bash
docker compose --profile memory-chromadb stop chromadb
docker run --rm -v template-repo_chromadb_data:/data:ro -v "$PWD":/backup busybox \
  tar czf /backup/chromadb-$(date +%Y%m%d).tar.gz -C /data .
docker compose --profile memory-chromadb up -d chromadb
```

(The volume name is `<compose project>_chromadb_data`; check with
`docker volume ls | grep chromadb`.)

## Restore

```bash
docker compose --profile memory-chromadb stop chromadb
docker run --rm -v template-repo_chromadb_data:/data -v "$PWD":/backup busybox \
  sh -c 'rm -rf /data/* && tar xzf /backup/chromadb-YYYYMMDD.tar.gz -C /data'
docker compose --profile memory-chromadb up -d chromadb
```

Restore into the same ChromaDB major version that produced the backup;
upgrading ChromaDB (for example 0.5 to 1.x) migrates data on first start and is
not reversible.

## Cleanup

- Remove individual wrong or stale facts with `delete_memories` (ids come from
  `store_facts`, `search_memories` or `list_memories`).
- Session events are never expired automatically. To drop everything and start
  over, stop ChromaDB and remove the `chromadb_data` volume, or point the server
  at a new `CHROMADB_COLLECTION` prefix.

## Upgrading From Releases Before 1.1.0

Older releases stored facts without embeddings, so those facts never showed up
in searches. After upgrading:

1. `list_namespaces` with `include_stored: true` to find namespaces with data.
2. `reindex_namespace` for each of them.
3. Verify with a `search_memories` call.

Do not run pre-1.1.0 binaries against ChromaDB 1.x: their vector-less writes
break the collection.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `error_kind: store_unavailable` | ChromaDB not running or wrong address | `docker compose --profile memory-chromadb up -d chromadb`; check `CHROMADB_URL` / `CHROMADB_HOST` / `CHROMADB_PORT` (inside compose the host is `chromadb`) |
| `error_kind: embedding_error` on first use | Model download failed (no network, unwritable cache dir) | Run `mcp-agentcore-memory --prefetch-model` with network access, or set `MEMORY_MODEL_CACHE_DIR` to a writable directory; the Docker image ships the model |
| `error_kind: incompatible_collection` | Collection built with a different `MEMORY_EMBEDDER` | Restore the original `MEMORY_EMBEDDER`, or use a new `CHROMADB_COLLECTION` prefix |
| `store_error` mentioning "dimension" | Collection holds vectors of another size (e.g. written by other tooling) | Same as above |
| Search returns nothing but `list_memories` shows facts | Facts written before 1.1.0 have no vectors | `reindex_namespace` |
| Search results stale after another agent stored facts | Per-process search cache | Wait for `MEMORY_CACHE_TTL_SECS` (default 300) or set it to `0` |
| `truncated_scan: true` in `list_session_events` | Session has more than 50,000 events | Use shorter-lived session ids |
| stdio client sees garbage on stdout | Should not happen: logs go to stderr and model download progress is disabled | Report with `RUST_LOG=debug` output |

Verbose logs: run with `--log-level debug` or `RUST_LOG=mcp_agentcore_memory=debug`.
