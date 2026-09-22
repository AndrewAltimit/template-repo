# Gaea2 MCP Server (Rust)

> Model Context Protocol server for [Gaea2](https://quadspinner.com/) terrain generation:
> create, validate, analyze, repair and (on a Windows host with Gaea2 installed) build
> `.terrain` projects.

## Overview

- **Project generation** - turns a node/connection workflow into a Gaea2 2.2.6.0 `.terrain`
  file (Json.NET reference-preserving format: unique `$id`s, `$values` arrays, connection
  `Record`s embedded in input ports, `SaveDefinition`s for Export nodes, modifiers).
- **Validation with auto-fix** - node types, ports, connections, cycles, duplicate ids,
  multiple inputs into one port, property types/ranges/enums. `create_*` tools validate first
  and **refuse to write a file that would be invalid**.
- **11 templates** usable as-is, with property overrides, or as starting points.
- **Analysis and optimization** - reference-project patterns, relative build cost, quality
  issues, and tuning of the properties that dominate build time.
- **Repair** of existing `.terrain` files in place (dangling/self connections, key/Id
  mismatches, misspelled types, duplicate `$id`s, broken parent refs), with dry-run and backups.
- **Build automation** through `Gaea.Swarm.exe` with hard timeouts (the process is killed on
  timeout), concurrency limiting and recursive output discovery.

### Deployment model

Gaea2 only runs on Windows, so the production server runs on a dedicated Windows machine at
**`192.168.0.152:8007`** and clients connect over HTTP (`.mcp.json`:
`{"type": "http", "url": "http://192.168.0.152:8007/messages"}`). The Docker image and any
Linux/macOS build provide every tool except `run_gaea2_project`, `validate_gaea2_runtime`
and `runtime_check`, which need `Gaea.Swarm.exe`.

## Quick start

```bash
cd tools/mcp/mcp_gaea2
cargo build --release

# HTTP (as on the Windows host)
./target/release/mcp-gaea2 --mode standalone --port 8007 \
    --gaea-path "C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe" \
    --output-dir "C:\gaea2_output"

# STDIO (local MCP client)
./target/release/mcp-gaea2 --mode stdio --output-dir ./output

curl http://localhost:8007/health
```

On Windows, `automation/launchers/windows/start-gaea2-mcp.bat` auto-detects Gaea2, builds the
binary if needed, and starts the server on port 8007.

## Configuration

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--mode` | | `standalone` | `standalone` (HTTP MCP), `stdio`, `server` (REST only), `client` (proxy) |
| `--port` | | `8000` | HTTP port (use `8007` for Gaea2) |
| `--log-level` | `RUST_LOG` | `info` | Log level (logs go to stderr) |
| `--gaea-path` | `GAEA2_PATH` | unset | Path to `Gaea.Swarm.exe`; enables build tools |
| `--output-dir` | `GAEA2_OUTPUT_DIR` | `/app/output/gaea2` | Where projects are written; created if missing |
| `--allowed-dirs` | `GAEA2_ALLOWED_DIRS` | unset | Extra directories clients may access (OS path list: `;` on Windows, `:` elsewhere) |
| `--max-concurrent-builds` | `GAEA2_MAX_CONCURRENT_BUILDS` | `1` | Concurrent `Gaea.Swarm` builds; extra builds queue |

### Path sandbox

The server is network-reachable, so every client-supplied path (`project_path`,
`build_path`, `directory`) is confined to the output directory plus `GAEA2_ALLOWED_DIRS`.
Relative paths resolve against the output directory, `..` is rejected, and symlinks are
resolved before the check. Project names are sanitized into file names
(`<name>_<timestamp>_<random>.terrain`), so they can never escape the output directory or
overwrite each other.

## Tools

All tools take typed arguments: a missing required parameter, a wrong type, an unknown
parameter name or an invalid enum value is rejected with an `Invalid params` error rather than
silently defaulted.

| Tool | Purpose | Required | Optional |
|------|---------|----------|----------|
| `create_gaea2_project` | Validate (auto-fix) and write a project | `project_name`, `nodes` | `connections`, `build_config`, `description`, `validate`=true, `auto_fix`=true, `strict`=false |
| `create_gaea2_from_template` | Write a project from a template | `template_name`, `project_name` | `modifications`, `build_config`, `description` |
| `validate_and_fix_workflow` | Validate and return the fixed workflow | `nodes` | `connections`, `strict_mode`, `auto_fix`=true, `runtime_check`, `runtime_timeout`=60 |
| `suggest_gaea2_nodes` | Next-node suggestions with reasons | `current_nodes` | `context` |
| `optimize_gaea2_properties` | Tune build-cost properties | `nodes` | `mode` = `performance` / `quality` / `balanced` |
| `analyze_workflow_patterns` | Patterns, cost, quality issues | `nodes` | `connections`, `analysis_type` = `patterns` / `performance` / `quality` / `all`, `workflow_type` |
| `list_gaea2_templates` | List templates | | `include_workflow` |
| `list_gaea2_nodes` | Node types by category, or ports/properties of one type | | `category`, `node_type` |
| `list_gaea2_projects` | List `.terrain` files, newest first | | `directory` |
| `download_gaea2_project` | Return a file (max 25 MB) | `project_path` | `encoding` = `base64` / `raw` |
| `repair_gaea2_project` | Repair a `.terrain` file in place | `project_path` | `create_backup`=true, `dry_run`=false |
| `run_gaea2_project` | Build with Gaea.Swarm (Windows) | `project_path` | `resolution` (512-8192, string or int), `build_path`, `profile`, `seed`, `region`, `target_node`, `variables`, `ignore_cache`, `verbose`, `timeout`=300 |
| `validate_gaea2_runtime` | 512px test build in a temp dir (Windows) | `project_path` | `timeout`=30 |
| `analyze_execution_history` | Build history summary (last 200, in memory) | | `limit`=10, `failures_only` |
| `get_gaea2_status` | CLI availability, directories, counts | | |

### Workflow format

```json
{
  "nodes": [
    {"id": 1, "type": "Mountain", "properties": {"Scale": 1.2, "Style": "Alpine"}},
    {"id": 2, "type": "Erosion2", "properties": {"Duration": 0.15}},
    {"id": 3, "type": "Combine", "properties": {"Mode": "Max"}},
    {"id": 4, "type": "Perlin"},
    {"id": 5, "type": "Export", "save_definition": {"filename": "height", "format": "PNG16"}}
  ],
  "connections": [
    {"from_node": 1, "to_node": 2},
    {"from_node": 2, "to_node": 3},
    {"from_node": 4, "to_node": 3, "to_port": "Input2"},
    [3, 5]
  ]
}
```

- `id` is an integer or numeric string; omitted ids are assigned without colliding.
- `type` is required. `name` defaults to the type. Omit `position` for automatic
  left-to-right layout by graph depth.
- `properties` use Gaea2's PascalCase names. `{x, y}` objects become Gaea2 range/point
  objects; other objects and arrays are wrapped in `$id`/`$values` form automatically.
  Reserved keys (`$id`, `Id`, `Name`, `Position`, `Ports`, ...) are rejected/removed.
- `ports` overrides the default ports: `[{"name": "In", "type": "PrimaryIn"}, ...]`
  (types `PrimaryIn`, `In`, `PrimaryOut`, `Out`). Use it for ports the built-in table lacks.
- Connections accept `from`/`source`, `to`/`target`, `source_port`/`target_port` aliases and
  `[from, to]` or `[from, to, from_port, to_port]` tuples. Ports default to `Out` -> `In`.
- Generator nodes without a `Seed` get a random one at generation time.

### Validation semantics

`validate_and_fix_workflow` returns `valid`, `fixed`, `errors`, `warnings`, `fixes_applied`
and the fixed `workflow`.

- **errors** block file generation: unknown node types without a confident match,
  duplicate/negative ids, connections to ports that do not exist (the old implementation
  silently dropped these), more than one connection into an input, cycles, wrong property
  types, malformed explicit ports or save definitions.
- **fixes** (when `auto_fix`): type typos (`erosion_2` -> `Erosion2`), property names to
  PascalCase (`erosion scale` -> `ErosionScale`), out-of-range numbers clamped, numeric
  strings/booleans coerced, enum case, port-name case, removal of connections to missing
  nodes, self-connections and duplicates, removal of reserved properties.
  With `auto_fix=false` these are reported as errors and the workflow is returned unchanged.
- **warnings**: unknown property names (Gaea2 ignores them), unknown enum values, color
  outputs feeding heightfield inputs, unconnected nodes, empty primary inputs, no Export.
  `strict_mode` turns the completeness warnings into errors.

A fix never makes a workflow "valid" while other errors remain.

### Examples

```bash
# Template with overrides
curl -s -X POST http://192.168.0.152:8007/mcp/execute -H 'Content-Type: application/json' -d '{
  "tool": "create_gaea2_from_template",
  "arguments": {"template_name": "detailed_mountain", "project_name": "alps",
                "modifications": {"InitialErosion": {"Duration": 0.25}},
                "build_config": {"resolution": 4096}}}'

# Inspect a node type before using it
curl -s -X POST http://192.168.0.152:8007/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "list_gaea2_nodes", "arguments": {"node_type": "Rivers"}}'

# Check an existing file without modifying it
curl -s -X POST http://192.168.0.152:8007/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "repair_gaea2_project", "arguments": {"project_path": "alps_20260101_120000_ab12cd.terrain", "dry_run": true}}'

# Build (Windows host only)
curl -s -X POST http://192.168.0.152:8007/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "run_gaea2_project", "arguments": {"project_path": "alps_20260101_120000_ab12cd.terrain", "resolution": 2048, "timeout": 900}}'
```

## Templates

| Template | Pipeline |
|----------|----------|
| `basic_terrain` | Mountain -> Erosion2 -> Export; Erosion2 -> TextureBase -> SatMap |
| `detailed_mountain` | 2x Mountain -> Combine -> Erosion2 -> Rivers -> Export / Snow -> SatMap |
| `volcanic_terrain` | Volcano + Island -> Combine -> Erosion2 -> Thermal -> Export / SatMap |
| `desert_canyon` | Canyon -> Stratify -> FractalTerraces -> Erosion2 -> Sand -> Export / SatMap |
| `mountain_range` | Mountain + Ridge -> Combine -> Erosion2 -> Export / Snow -> SatMap |
| `volcanic_island` | Island + Volcano -> Combine -> Thermal -> Erosion2 -> Export / SatMap |
| `canyon_system` | Voronoi -> Stratify -> Erosion2 -> Thermal -> Sediment -> Export / SatMap |
| `coastal_cliffs` | Mountain -> Coast -> Terraces -> Erosion2 -> Sea -> Export / SatMap |
| `river_valley` | Mountain -> Erosion2 -> Rivers -> Sediment -> Export / SatMap |
| `arctic_terrain` | Mountain -> Erosion2 -> Snow -> Glacier -> Export / SatMap |
| `modular_portal_terrain` | Mountain -> PortalTransmit ... PortalReceive -> Erosion2 -> ... -> Export / SatMap |

Templates live in `src/templates.json` in the same format `create_gaea2_project` accepts;
`list_gaea2_templates` with `include_workflow=true` returns them for editing. Unit tests
ensure every template validates cleanly and generates.

## Transport and endpoints

`--mode standalone` serves `/health`, `/mcp/tools`, `/mcp/execute` (simple REST),
`/messages` (MCP JSON-RPC) and `/.well-known/mcp`. `--mode stdio` speaks JSON-RPC over
stdin/stdout (logs on stderr). See [mcp_core_rust](../mcp_core_rust/README.md).

## Docker

```bash
docker compose --profile services up -d mcp-gaea2   # port 8007, outputs in ./outputs/mcp-gaea2
```

The image (`docker/mcp-gaea2.Dockerfile`) has no Gaea2, so build tools report
"Gaea2 CLI not configured". Use it for generation, validation, analysis and repair.

## Development

```bash
cd tools/mcp/mcp_gaea2
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # offline; Gaea.Swarm is replaced by a fake script in CLI tests
cargo build --release
```

| Module | Responsibility |
|--------|----------------|
| `main.rs` | CLI flags, server bootstrap |
| `server.rs` | Tool definitions and typed argument structs |
| `input.rs` | Parsing of user node/connection JSON |
| `schema.rs` | Node types, categories, ports, property specs, suggestions |
| `validation.rs` | Validation/auto-fix, topological order, cycle detection |
| `generation.rs` | `.terrain` document generation and atomic writes |
| `repair.rs` | In-place repair of existing `.terrain` files |
| `analysis.rs` | Pattern/performance/quality analysis, property optimization |
| `templates.rs` / `templates.json` | Templates and modifications |
| `cli.rs` | Gaea.Swarm argument building, execution, timeouts, output discovery |
| `config.rs` | Configuration and path sandbox |

## Limitations

- Gaea2 has no published machine-readable schema. Port tables and property specs cover the
  most common nodes and come from analysis of reference files; unknown properties are
  warnings, not errors, and ports missing from the table can be declared via `ports`.
- Only one graph tab is generated; groups, notes and automation variables are not authored
  (repair preserves them in existing files).
- The `Gaea.Swarm.exe` argument set (`--Filename`, `--resolution`, `--buildpath`,
  `--silent`, `--profile`, `--region`, `--seed`, `--node`, `-v name:value`, `--ignorecache`,
  `--verbose`) targets Gaea 2.2.6.0.
- Execution history is in memory and lost on restart.

Background material from the original project analysis (node reference, knowledge base,
patterns) is in [docs/](docs/INDEX.md).
