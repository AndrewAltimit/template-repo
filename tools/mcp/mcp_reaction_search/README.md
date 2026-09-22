# Reaction Search MCP Server (Rust)

> Semantic search over the anime reaction image catalog published in
> [AndrewAltimit/Media](https://github.com/AndrewAltimit/Media/tree/main/reaction),
> using ONNX sentence embeddings (all-MiniLM-L6-v2 via fastembed) with a
> keyword/tag boost and a fully offline keyword fallback.

## Overview

- Natural-language search ("annoyed at the failing tests") ranked by hybrid
  semantic + keyword scoring
- Id lookup with "did you mean" suggestions, catalog listing, tag browsing
- Config fetched from GitHub, cached on disk (1-week TTL), with stale-cache
  fallback when offline
- Embedding model cached on disk and preloaded in the background at startup
- Degrades instead of failing: if the model cannot load (offline, download in
  progress), searches use keyword ranking and say so

## Quick Start

```bash
cd tools/mcp/mcp_reaction_search
cargo build --release

# STDIO mode (Claude Code / MCP clients)
./target/release/mcp-reaction-search --mode stdio

# HTTP mode
./target/release/mcp-reaction-search --mode standalone --port 8024
curl http://localhost:8024/health
curl -X POST http://localhost:8024/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "search_reactions", "arguments": {"query": "happy coding", "limit": 3}}'
```

## Tools

| Tool | Parameters | Needs model |
|------|------------|-------------|
| `search_reactions` | `query` (required), `limit`, `tags`, `exclude`, `min_similarity` | No (semantic when available, keyword otherwise) |
| `get_reaction` | `reaction_id` (required) | No |
| `list_reactions` | `tags`, `limit` | No |
| `list_reaction_tags` | none | No |
| `refresh_reactions` | none | No |
| `reaction_search_status` | none | No |

### `search_reactions`

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `query` | string | required | Emotion or situation; 1-1000 chars |
| `limit` | integer | 5 | Clamped to 1-20 |
| `tags` | string or string[] | none | Keep reactions with at least one of these tags (case-insensitive) |
| `exclude` | string or string[] | none | Reaction ids to leave out, e.g. ones used in recent comments |
| `min_similarity` | number | 0.0 | 0-1; drops results below this similarity |

Response:

```json
{
  "success": true,
  "query": "confused about the error message",
  "search_mode": "semantic",
  "count": 3,
  "results": [
    {
      "id": "confused",
      "url": "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/confused.gif",
      "markdown": "![Reaction](https://raw.githubusercontent.com/.../confused.gif)",
      "description": "Confused or questioning expression",
      "similarity": 0.2213,
      "score": 0.3713,
      "tags": ["confused", "questioning", "uncertain", "puzzled"],
      "usage_scenarios": ["..."],
      "character_appearance": "..."
    }
  ]
}
```

- `similarity`: semantic mode = embedding similarity (0-1); lexical mode =
  keyword score scaled so the best match is 1.0.
- `score`: final ranking value (similarity + keyword/tag boosts). Results are
  sorted by it.
- `search_mode`: `semantic` or `lexical`. When `lexical`, `note` explains why
  (model still loading, model failed to load, ...). Lexical mode only returns
  reactions that match at least one query keyword or tag.

### `get_reaction`

Case-insensitive id lookup. Unknown ids return `isError: true` with
`{"success": false, "error": "...", "suggestions": ["felix", ...]}`.

### `list_reactions`

Compact catalog listing (`id`, `description`, `tags`, `markdown`), optionally
filtered by `tags` (any-of) and truncated to `limit`. Returns `total` (matches)
and `count` (returned).

### `list_reaction_tags`

Lowercased tag counts as `tags` (alphabetical), `by_count` (most-used first),
and `categorized` (`emotions`, `actions`, `other`).

### `refresh_reactions`

Re-fetches the config ignoring the TTL. On failure the previously loaded
reactions and the on-disk cache are kept, and the error says so. On success it
reports `reaction_count`, `previous_count`, `added`, `removed`, `source`, and
`semantic_ready`. It also retries a failed model load immediately.

### `reaction_search_status`

Never blocks on loading. Reports `initialized`, `search_mode`
(`not_loaded`/`semantic`/`lexical`), `model` (`state`:
`not_loaded`/`loading`/`ready`/`failed`, `error`, `retry_in_secs`,
`load_secs`, `cache_dir`), `catalog` (count, `source`, `loaded_at`, config
validation `warnings`), `engine` (legacy summary incl. `embeddings_shape`),
and `cache` (on-disk config cache status).

## How search works

1. **Semantic similarity.** Each reaction is embedded once as a whole
   (description + usage scenarios + tags) and per field (description and each
   usage scenario separately). A query's similarity is
   `0.5 * cos(query, whole) + 0.5 * max cos(query, field)`, which rewards a
   precise scenario match without letting one short phrase dominate. Character
   appearance (hair colour, clothing) is left out of the embeddings because it
   dilutes the emotional signal.
2. **Keyword boost.** A BM25 index over tags (weight 3), id and description
   (2), usage scenarios (1), and appearance (0.5), with light stemming, adds
   `0.10 * normalized_bm25`. An exact query-term/tag match adds `0.05`.
3. **Lexical fallback.** Without the model, ranking is BM25 + tag boost only.

Ties are broken by id, so results are deterministic.

## Configuration

Every option is a CLI flag and an environment variable.

| Flag | Env var | Default | Purpose |
|------|---------|---------|---------|
| `--mode` | | `standalone` | `standalone` (HTTP MCP), `stdio`, `server` (REST only), `client` |
| `--port` | | `8000` | HTTP port (docker-compose uses 8024) |
| `--log-level` | | `info` | Log level (logs go to stderr) |
| `--config-url` | `REACTION_SEARCH_CONFIG_URL` | Media repo `config.yaml` | `http(s)://` URL, `file://` URL, or local path. Local files are read directly and never cached |
| `--cache-dir` | `REACTION_SEARCH_CACHE_DIR` | `<cache dir>/mcp_reaction_search` | Config cache; model goes in `models/` below it |
| `--cache-ttl-secs` | `REACTION_SEARCH_CACHE_TTL_SECS` | `604800` (1 week) | Config cache freshness |
| `--fetch-timeout-secs` | `REACTION_SEARCH_FETCH_TIMEOUT_SECS` | `15` | Total config fetch timeout (connect timeout is 10s) |
| `--model-wait-secs` | `REACTION_SEARCH_MODEL_WAIT_SECS` | `30` | How long a search waits for a loading model before answering lexically |
| `--model-retry-secs` | `REACTION_SEARCH_MODEL_RETRY_SECS` | `300` | Backoff before retrying a failed model load |
| `--preload <bool>` | `REACTION_SEARCH_PRELOAD` | `true` | Load config + model in the background at startup |

`<cache dir>` is `$XDG_CACHE_HOME` or `~/.cache` on Linux,
`~/Library/Caches` on macOS, `%LOCALAPPDATA%` on Windows. fastembed also
honours `HF_HOME` (overrides the model directory) and `HF_ENDPOINT` (mirror).

### Cache files

```
<cache-dir>/
  reaction_config.json   # validated reactions (JSON), written atomically
  cache_meta.json        # cached_at, source_url, reaction_count
  models/                # all-MiniLM-L6-v2 ONNX model (~90 MB)
```

A cache counts as fresh only if it is younger than the TTL **and** was written
for the same `config_url`.

### Config loading and offline behaviour

1. Local file source: read directly.
2. Fresh cache: used without touching the network.
3. Otherwise fetch (max 8 MiB, timeout above) and rewrite the cache.
4. If the fetch fails, fall back to the expired cache (`source: stale_cache`).
5. With no cache and no network, tools return `isError` with the fetch error.

Config entries are validated: ids must be `[A-Za-z0-9_.-]` (unsafe or empty ids
are skipped), duplicate ids keep the later entry, and tags are trimmed and
de-duplicated. A document with no valid entries is rejected, so a bad upstream
push cannot overwrite a good cache. Validation warnings appear in
`reaction_search_status`.

## Docker

```bash
docker compose --profile services up -d mcp-reaction-search   # HTTP on 8024
docker compose logs -f mcp-reaction-search
```

`.mcp.json` launches it in STDIO mode with
`docker compose --profile services run --rm -T mcp-reaction-search --mode stdio`.
The `reaction-search-cache` volume is mounted at `/home/mcp/.cache`, so the
config cache and the model persist across these one-shot containers (the model
downloads only once).

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test                                   # offline; uses a fake embedder
cargo test -- --ignored real_model           # downloads the real model
```

Unit tests cover config validation, cache freshness/stale fallback, refresh
safety, tokenizer/BM25, ranking and filters, model-failure and slow-model
fallback, and every tool's argument validation and error paths.

## Project Structure

```
src/
  main.rs     CLI/env settings, server bootstrap, preload
  server.rs   MCP tool definitions and typed argument parsing
  service.rs  Shared state: catalog snapshots, model lifecycle, refresh, status
  engine.rs   Catalog, semantic index, hybrid ranking
  text.rs     Tokenizer, stemmer, BM25 index, edit distance
  embed.rs    Embedder trait and fastembed backend
  config.rs   Config fetch, validation, disk cache, offline fallback
  types.rs    Data types
```

## Performance (release build, 81 reactions)

| Operation | Typical time |
|-----------|--------------|
| Server startup | immediate (loading happens in the background) |
| First model download | depends on network (~90 MB, once per cache dir) |
| Model load from disk | ~1s |
| Index build (81 reactions + ~350 field texts) | ~2s |
| Search after warm-up | a few ms (one query embedding + dot products) |

## Limitations

- English-only model; very short or unusual queries may rank loosely. Use
  `tags` to constrain or `list_reaction_tags` to browse.
- The emotion/action grouping in `list_reaction_tags` is a fixed list; unknown
  tags go to `other`.
- A running model download cannot be cancelled; searches stop waiting after
  `--model-wait-secs` and use keyword ranking until it finishes.
- `client` mode is provided by mcp-core and simply proxies to a backend.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `search_mode: "lexical"` with "still loading" | First model download in progress | Wait; check `reaction_search_status` |
| `search_mode: "lexical"` with "unavailable" | Model download failed (offline / HF blocked) | Restore network, then `refresh_reactions` (retries immediately) |
| `source: "stale_cache"` | GitHub unreachable | Works from cache; `refresh_reactions` when back online |
| "no reaction config available" | No network and no cache | Provide network once, or set `REACTION_SEARCH_CONFIG_URL` to a local file |
| New reactions missing | Cache still fresh | `refresh_reactions` |
