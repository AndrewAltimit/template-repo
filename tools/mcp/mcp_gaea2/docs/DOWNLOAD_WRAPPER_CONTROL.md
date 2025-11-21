# Gaea2 Download Wrapper Control

## Overview

The Gaea2 MCP server generates terrain files with metadata wrapper for CI/CD purposes. This wrapper includes:
- `success`: Boolean indicating if creation was successful
- `project`: The actual Gaea2 terrain data
- `node_count`: Number of nodes in the terrain
- `connection_count`: Number of connections
- `output_path`: Path where the file was saved

## The Problem

While this metadata is useful for CI/CD pipelines and validation, Gaea2 itself expects only the `project` field contents when opening `.terrain` files.

## The Solution

The download endpoint now supports an optional `extract_project` query parameter:

### Default Behavior (with wrapper)
```bash
# Downloads the file as-is with the metadata wrapper
curl -X GET "http://192.168.0.152:8007/download/my_terrain.terrain" -o my_terrain.terrain
```

### Extract Project Only (Gaea2-ready)
```bash
# Downloads only the project field, ready for Gaea2
curl -X GET "http://192.168.0.152:8007/download/my_terrain.terrain?extract_project=true" -o my_terrain.terrain
```

## Usage Examples

### For End Users (Opening in Gaea2)
```bash
# Download terrain file ready to open in Gaea2
curl -X GET "http://192.168.0.152:8007/download/mountain_terrain_20250722_120000.terrain?extract_project=true" \
  -o mountain_terrain.terrain
```

### For CI/CD Pipelines (Need metadata)
```bash
# Download with full metadata for validation
response=$(curl -X GET "http://192.168.0.152:8007/download/mountain_terrain_20250722_120000.terrain")

# Extract metadata
success=$(echo "$response" | jq -r '.success')
node_count=$(echo "$response" | jq -r '.node_count')
connection_count=$(echo "$response" | jq -r '.connection_count')

# Validate
if [ "$success" = "true" ] && [ "$node_count" -gt 0 ]; then
  echo "Terrain validated: $node_count nodes, $connection_count connections"
fi
```

### Python Example
```python
import requests
import json

# For Gaea2 use
response = requests.get("http://192.168.0.152:8007/download/terrain.terrain?extract_project=true")
with open("terrain.terrain", "w") as f:
    f.write(response.text)

# For CI/CD validation
response = requests.get("http://192.168.0.152:8007/download/terrain.terrain")
data = response.json()
if data["success"] and data["node_count"] > 0:
    print(f"Valid terrain: {data['node_count']} nodes")
    # Save just the project for Gaea2
    with open("terrain.terrain", "w") as f:
        json.dump(data["project"], f, indent=2)
```

## Testing

Use the provided test script to verify the functionality:

```bash
# Test with automatic file selection
python tools/mcp/gaea2/scripts/test_extract_project.py

# Test with specific file
python tools/mcp/gaea2/scripts/test_extract_project.py my_terrain.terrain
```

## Benefits

1. **Backward Compatibility**: Existing CI/CD pipelines continue to work without changes
2. **User-Friendly**: End users can download Gaea2-ready files with a simple parameter
3. **Flexibility**: Choose whether to include metadata based on use case
4. **No Breaking Changes**: Default behavior remains unchanged

## Implementation Notes

- The extraction only happens for `.terrain` files
- If the file doesn't have the wrapper structure, it's returned as-is
- If JSON parsing fails, the file is returned unchanged
- The `extract_project` parameter is case-insensitive (`true`, `True`, `TRUE` all work)
