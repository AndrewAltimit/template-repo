# Gaea2 MCP Server Changelog

All notable changes to the Gaea2 MCP Server are documented here.

## [Latest] - 2025-07-20

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
- ✅ Missing connections: 490 → 174 (node ordering issue)
- ✅ Missing connections to Combine nodes (indentation issue)
- ✅ Type mismatch when looking up nodes (string/int consistency)
- ✅ All 8 previously missing connections in Level1 terrain now work

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
