# Gaea2 Project File Analysis - Summary of Findings

## Executive Summary

After extensive analysis comparing working and failing Gaea2 project files, we've discovered that the issue is NOT what we initially thought. The real problem appears to be more subtle than missing properties or connections.

## Key Findings

### 1. Properties ARE Valid ✓
- ALL reference files have node properties (Scale, Height, Style, etc.)
- The failing file's properties match reference file patterns
- X,Y properties on Mountain/Volcano nodes are valid (0-1 range parameters)

### 2. Connections ARE Present ✓
- The failing file has all connections properly embedded as Record objects
- Connection format matches reference files exactly
- Workflow flow is complete: Mountain → Erosion2 → TextureBase → SatMap → Export

### 3. Export Nodes ARE Used ✓
- 21 out of 37 reference files contain Export nodes
- Export nodes are valid parts of Gaea2 projects

### 4. What Works vs What Fails

**Working File Characteristics:**
- Single Mountain node
- NO properties (empty)
- Simple node ID: "1"
- NO Export node
- File size: ~2.2KB

**Failing File Characteristics:**
- Multiple nodes (Mountain, Erosion2, TextureBase, SatMap, Export)
- Properties on all nodes
- Node IDs: "100", "101", "102", "103", "104"
- Has Export node with conflicting formats (PNG vs EXR)
- Larger file size

## Potential Issues Identified

### 1. Export Node Format Conflict
The failing file has:
```json
"Format": "PNG",  // At node level
"SaveDefinition": {
    "Format": "EXR",  // Different format!
    ...
}
```
This conflict might be causing Gaea2 to reject the file.

### 2. Property Completeness
Some nodes might be missing required properties or have incorrect default values:
- Erosion2 has many properties set to 0.0 (might need non-zero defaults)
- Duration: 0.04 (very low - typical values are 0.15+)

### 3. Node ID Pattern
- Working files often use simple IDs: "1", "2", "3"
- Failing file uses: "100", "101", "102", "103", "104"
- While both patterns exist in reference files, simple IDs are more common

## Recommendations for Fixes

### 1. Immediate Fix - Remove Export Node
Since the working file has no Export node and our analysis shows they're optional:
```python
# Don't auto-add Export nodes
# Let users explicitly add them if needed
```

### 2. Fix Export Node Format Conflict
If Export nodes are needed:
```python
# Remove the 'Format' property at node level
# Keep only SaveDefinition.Format
```

### 3. Use Conservative Property Defaults
Instead of setting properties to 0.0, use typical values from reference files:
```python
'Duration': 0.15,      # Not 0.04
'Downcutting': 0.3,    # Good
'Shape': 0.5,          # Good
```

### 4. Simplify Node IDs
Use simple sequential IDs starting from 1:
```python
node_id = 1  # Not 100
```

### 5. Property Strategy
The server should:
- Accept properties when provided by users
- NOT add default properties automatically
- Use empty properties {} for simple use cases
- Add properties only when explicitly requested

## Test Files Created

1. `test_minimal_mountain.json` - Works! (no properties, no Export)
2. `test_no_export.json` - Properties but no Export node
3. `test_no_export_exact.json` - Failing file minus Export node
4. `test_simple_ids.json` - Simple IDs (1,2,3) instead of (100,101,102)

## Next Steps

1. Test the created files to identify which change fixes the issue
2. Update the server based on test results
3. Document the findings in the Gaea2 documentation
4. Consider adding a "strict mode" that generates minimal files
