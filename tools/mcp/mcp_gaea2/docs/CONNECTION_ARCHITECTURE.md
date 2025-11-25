# Gaea2 Connection Architecture

This document explains how connections work in the Gaea2 MCP server based on extensive debugging and analysis.

## Overview

The Gaea2 terrain file format stores connections differently than most node-based systems. Understanding this architecture is crucial for successfully generating terrain files.

## Key Concepts

### 1. Connection Storage

Unlike typical node graph systems where connections are stored separately, Gaea2 embeds connections within the receiving node's port definitions:

```json
{
  "Ports": {
    "$values": [
      {
        "Name": "In",
        "Type": "PrimaryIn",
        "Record": {
          "$id": "123",
          "From": 490,
          "To": 174,
          "FromPort": "Out",
          "ToPort": "In",
          "IsValid": true
        }
      }
    ]
  }
}
```

### 2. API vs File Format

The MCP API accepts a simplified format:
```python
{
    "from_node": 490,
    "to_node": 174,
    "from_port": "Out",
    "to_port": "In"
}
```

But internally converts it to the Gaea2 format with Record objects embedded in ports.

### 3. Node ID Mapping Process

The server uses a two-pass approach:

**First Pass**: Build complete node_id_map
```python
for node in nodes:
    original_id = node.get("id")
    node_id_map[str(original_id)] = node_id
```

**Second Pass**: Process nodes with connections
```python
for node in nodes:
    # Now all node IDs are available for connection lookups
    process_node_with_connections(node)
```

### 4. Port Configurations by Node Type

Different nodes have different port configurations:

| Node Type | Input Ports | Output Ports |
|-----------|------------|--------------|
| Standard | In | Out |
| Combine | In, Input2, Mask | Out |
| Rivers | In, Headwaters, Mask | Out, Rivers, Depth, Surface, Direction |
| Sea | In | Out, Water, Depth, Shore, Surface |
| TextureBase | In | Out |
| SatMap | In (Required) | Out |

### 5. Connection Processing Flow

1. **Parse connections** into node_connections dict keyed by target node ID and port
2. **Build node_id_map** with all nodes before processing
3. **Process each node**:
   - Create port definitions
   - Check if port should have a connection
   - If yes, embed Record object with connection data
   - Use string keys throughout to prevent type mismatches

## Common Issues and Solutions

### Issue 1: Missing Connections
**Cause**: Target node processed before source node exists in node_id_map
**Solution**: Build complete node_id_map before processing any nodes

### Issue 2: Type Mismatches
**Cause**: Node IDs stored as integers but looked up as strings
**Solution**: Convert all IDs to strings consistently

### Issue 3: Wrong Port Names
**Cause**: Case sensitivity or incorrect port names
**Solution**: Use exact port names as documented

### Issue 4: Combine Node Connections
**Cause**: Indentation error in connection handling code
**Solution**: Ensure connection lookup code is properly indented

## Best Practices

1. **Always define all nodes before connections**
2. **Use string IDs consistently** in your API calls
3. **Specify both from_port and to_port** explicitly
4. **Test with progressive complexity** when debugging
5. **Use the debug scripts** to analyze generated files

## Debug Scripts

- `test-progressive-connections.py` - Test with increasing complexity
- `debug-node-id-mapping.py` - Check node ID mapping
- `analyze-connections-detail.py` - Compare with reference files
- `test-combine-to-combine.py` - Test specific node types

## Connection Validation

The server validates connections by:
1. Checking node existence in node_id_map
2. Verifying port names are valid for node type
3. Ensuring no duplicate connections
4. Confirming connection compatibility

## Future Improvements

1. Add connection validation before processing
2. Provide better error messages for missing nodes
3. Support for connection reordering
4. Visual debugging output for connection graphs
