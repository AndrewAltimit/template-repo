# Gaea2 Terrain File Format Analysis

## Key Differences Between Generated and Working Files

### 1. Connection Record Placement
- **Working (Level1.terrain)**: Record objects are placed inside the receiving port (usually "In" port)
- **Generated**: Records are correctly placed in receiving ports

### 2. Property Naming Conventions
- **Working**: Uses spaces in property names: "Rock Softness", "Snow Line", "Settle Duration"
- **Generated**: Sometimes uses camelCase or different formatting

### 3. Missing Node Properties
Working files include additional properties our generator misses:
- `PortCount` on Combine nodes (always 2)
- `NodeSize` ("Small", "Standard") on various nodes
- `IsMaskable: true` on most nodes
- `RenderIntentOverride: "Color"` on color-handling Combine nodes

### 4. Range Property Format
- **Working**: Range has its own $id: `{"$id":"103","X":0.87732744,"Y":1.0}`
- **Generated**: Simple object: `{"X":0.5,"Y":0.5}`

### 5. ID Allocation Pattern
- **Working**: Non-sequential IDs (183, 668, 427, 281, 294...)
- **Generated**: Sequential IDs (100, 110, 120, 130...)

### 6. SaveDefinition Structure
Working files may have SaveDefinition at node level with specific format requirements.

### 7. Critical Missing Elements
- Variables object should be `{"$id":"72"}` not `{}`
- BoundProperties needs proper $id references
- Camera object needs proper structure

## Required Fixes for Gaea2 MCP Server

1. **Property Name Mapping**: Ensure all property names match Gaea2's exact format
2. **Add Missing Node Properties**: Include PortCount, NodeSize, IsMaskable
3. **Fix Range Properties**: Add $id to all Range objects
4. **Non-Sequential ID Generation**: Use more scattered ID pattern
5. **Proper Empty Object Formatting**: Use `{"$id":"XX"}` for empty objects

## API Call Format Discovery

The correct MCP execute format requires:
```json
{
  "tool": "create_gaea2_project",
  "parameters": {
    "project_name": "name",
    "workflow": [/* nodes with connections inline */],
    "auto_validate": true
  }
}
```

NOT the documented format with separate nodes/connections arrays.
