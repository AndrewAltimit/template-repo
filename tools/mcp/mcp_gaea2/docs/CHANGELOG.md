# Gaea2 MCP Server Changelog

> **Version history and notable changes**

## [1.1.0] - 2026-09 (Rust overhaul)

### Fixed
- Connections to ports that do not exist were silently dropped from generated files; they
  are now validation errors. Multiple connections into one input port are rejected.
- `SaveDefinition`, modifier properties and user `ports` were ignored by generation; they are
  now emitted. `{x, y}` properties become proper `$id`-tagged Gaea2 objects; user `X`/`Y`
  properties are no longer overwritten.
- Validation reported `valid: true` whenever any fix was applied, even with remaining
  errors. `valid` now means "no blocking errors remain".
- `repair_gaea2_project` only re-serialized the file and reported fake repairs; it now
  performs real structural repair (see README) with `dry_run` support.
- Path traversal: project names could escape the output directory and
  `download`/`repair`/`run`/`list` accepted any path on the host. All client paths are now
  confined to the output directory plus `GAEA2_ALLOWED_DIRS`.
- Builds that timed out kept running; the Gaea process is now killed. Output files in
  per-node sub-folders were not found. `variables` were passed JSON-quoted.
- Integer `resolution` values silently fell back to 1024; invalid `mode`/`analysis_type`
  silently fell back to defaults. All tool arguments are now typed and validated.
- `analysis_type` was ignored; `suggest_gaea2_nodes` suggested non-existent node types.
- Release builds used `panic = "abort"`, defeating mcp-core's tool panic boundary.

### Added
- `list_gaea2_nodes`, `get_gaea2_status` tools; template `modifications`; `build_config`
  and `description` on template creation; `auto_fix`/`strict` on project creation;
  `include_workflow` on template listing; `failures_only` on history.
- Property schema checks (types, ranges, enums) with auto-fix; automatic graph layout;
  concurrency-limited builds; unit tests for every module (78 tests, offline).

## Python implementation history (retired)

The entries below describe the former Python server and reference scripts that no longer
exist in this repository.

## [Python] - 2025-07-20

### Fixed

#### Critical Connection Handling Fixes
1. **Node ID Mapping Order** - Fixed critical bug where connections failed when target nodes appeared before source nodes in the node list
   - The server now builds a complete node_id_map in a first pass before processing any nodes
   - This ensures all node IDs are available when processing connections
   - Affects: Multi-node projects with complex connection patterns

2. **Type Consistency** - Fixed type mismatch issues in connection handling
   - All node IDs are now consistently handled as strings internally
   - Prevents failures when looking up nodes in node_id_map
   - Affects: All projects with connections

3. **Indentation Error** - Fixed indentation bug in Combine node connection handling
   - The from_node lookup code was not properly indented within the conditional block
   - This caused connections to Combine nodes to be skipped
   - Affects: Projects using Combine nodes

4. **Connection Storage Format** - Clarified and documented how connections are stored
   - Connections are embedded as `Record` objects within port definitions
   - Not stored as a separate connections array
   - Each receiving port contains its connection information

### Added

#### Debug Tools
- `scripts/test-progressive-connections.py` - Test connections with increasing complexity
- `scripts/debug-node-id-mapping.py` - Debug node ID mapping issues
- `scripts/analyze-connections-detail.py` - Compare connections between files
- `scripts/test-combine-to-combine.py` - Test specific Combine node connections
- `scripts/generate-fresh-level1.py` - Generate complete Level1 terrain for testing

#### Documentation
- Added comprehensive Connection System Details section to CLAUDE.md
- Added Connection Troubleshooting section to README.md
- Updated API Reference with accurate connection format documentation
- Added Multi-Port Connections example to GAEA2_EXAMPLES.md
- Documented common port names by node type

### Known Issues Resolved

| Issue | Resolution |
|-------|------------|
| Missing connections: 490 → 174 | Fixed node ordering issue |
| Missing connections to Combine nodes | Fixed indentation issue |
| Type mismatch when looking up nodes | Fixed string/int consistency |
| All 8 previously missing connections in Level1 terrain | Now working |

## [Previous] - 2025-07-19

### Added
- Initial Gaea2 MCP server implementation
- Automatic validation and fixing
- Pattern-based intelligence from 31 real projects
- Professional templates
- Performance optimization features

### Fixed
- Property name formatting (camelCase → spaces)
- Missing node properties (PortCount, NodeSize, IsMaskable)
- Range property format with proper $id references
- Non-sequential ID generation for better Gaea2 compatibility
