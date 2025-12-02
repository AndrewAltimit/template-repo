# Gaea2 MCP Quick Reference

## 🔥 Important: Automatic Validation is Built-in!

**All projects created with `create_gaea2_project` automatically include:**
- ✅ Property validation and fixing
- ✅ Missing Export/SatMap nodes added
- ✅ Connection validation and repair
- ✅ Performance optimization
- ✅ Guaranteed Gaea2 compatibility

**Set `auto_validate=False` only if you need to bypass validation.**

## Essential Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `create_gaea2_project` | Create terrain projects | `nodes`, `connections`, `output_path`, `auto_validate=True` |
| `validate_and_fix_workflow` | Manual validation & repair | `nodes`, `auto_fix=True`, `aggressive=False` |
| `create_gaea2_from_template` | Use templates | `template_name`, `project_name` |
| `analyze_workflow_patterns` | Get suggestions | `current_workflow` |
| `repair_gaea2_project` | Fix existing projects | `project_path` or `project_data` |

## Available Templates

- `basic_terrain` - Simple terrain with erosion
- `detailed_mountain` - Mountain with rivers & snow
- `volcanic_terrain` - Volcanic landscape
- `desert_canyon` - Desert with stratification

## Common Node Sequences

1. **Basic**: Mountain → Erosion2 → SatMap → Export
2. **Detailed**: Mountain → Erosion2 → Rivers → TextureBase → SatMap → Export
3. **Pattern**: Slump → FractalTerraces → Combine → Shear (most common)

## Node Categories

- 🟢 **Primitive** (24) - Noise generators
- 🟢 **Terrain** (14) - Terrain generators
- 🔵 **Modify** (41) - Modifiers
- 🟡 **Surface** (21) - Detail/texture
- 🟠 **Simulate** (25) - Natural processes
- ⚪ **Derive** (13) - Analysis maps
- 🟣 **Colorize** (13) - Color ops
- 🔴 **Output** (13) - Export
- ⚫ **Utility** (20) - Helpers

## Quick Examples

### Create Simple Terrain (Automatic Validation)
```python
# Minimal example - Export and SatMap are added automatically!
result = await MCPTools.create_gaea2_project(
    project_name="Simple Mountain",
    nodes=[
        {"type": "Mountain", "id": 100},
        {"type": "Erosion2", "id": 101}
        # No need for Export or SatMap!
    ],
    connections=[
        {"from_node": 100, "to_node": 101}
    ]
)
# Result will have 4 nodes: Mountain, Erosion2, SatMap (auto), Export (auto)
```

### Use Template
```python
result = await MCPTools.create_gaea2_from_template(
    template_name="detailed_mountain",
    project_name="My Mountain"
)
```

### Validate & Fix
```python
result = await MCPTools.validate_and_fix_workflow(
    nodes=workflow_nodes,
    connections=workflow_connections,
    auto_fix=True
)
```

### Get Suggestions
```python
analysis = await MCPTools.analyze_workflow_patterns(
    current_workflow=[
        {"type": "Mountain"},
        {"type": "Erosion2"}
    ]
)
# Returns: Rivers (65%), TextureBase (45%), etc.
```

## Common Properties

### Mountain
- `Scale`: 0.1-10.0 (default: 1.0)
- `Height`: 0.0-2.0 (default: 1.0)
- `Seed`: Any integer

### Erosion2
- `Duration`: 0.01-0.1 (auto-capped for performance)
- `Scale`: 1-100000 (default: 10000)

### Rivers
- `Headwaters`: 10-200 (auto-capped for performance)

### SatMap
- `Preset`: "Rocky", "Desert", "Alpine", "Volcanic", "Custom"

## Auto-Fix Capabilities

✅ **Automatically Fixed:**
- Duplicate connections
- Out-of-range properties
- Missing Export node
- Invalid property types
- Orphaned nodes (with suggestions)

❌ **Manual Fix Required:**
- Invalid node types
- Circular dependencies
- Complex workflow issues

## Optimization Modes

- **Performance**: Lower quality, faster processing
- **Quality**: Higher quality, slower processing
- **Balanced**: Good compromise (default)

```python
result = await MCPTools.optimize_gaea2_properties(
    node_type="Erosion2",
    properties={"Duration": 0.15},
    mode="performance"  # or "quality", "balanced"
)
```

## Build Configurations

### Game Development
```python
build_config = {
    "resolution": 2048,
    "format": "PNG",
    "bit_depth": 16
}
```

### Film/VFX
```python
build_config = {
    "resolution": 8192,
    "format": "EXR",
    "bit_depth": 32,
    "method": "Tiled"
}
```

## Error Handling

```python
try:
    result = await MCPTools.create_gaea2_project(...)
    if result['success']:
        print(f"Created: {result['output_path']}")
    else:
        print(f"Error: {result['error']}")
except Exception as e:
    print(f"Exception: {str(e)}")
```

## Performance Tips

1. **Use Caching**: Operations are cached for 1 hour
2. **Batch Operations**: Validate multiple nodes at once
3. **Templates**: Start with templates instead of building from scratch
4. **Conservative Fixes**: Use `aggressive=False` for safer repairs

## Pattern Statistics

From 31 real projects:
- **Average nodes**: 12.1
- **Average connections**: 14.2
- **Most complex**: 31 nodes, 33 connections
- **Cache speedup**: 19x
- **Auto-fix success**: 85%

## Documentation

- **Main Guide**: [README.md](README.md)
- **API Reference**: [GAEA2_API_REFERENCE.md](GAEA2_API_REFERENCE.md)
- **Examples**: [GAEA2_EXAMPLES.md](GAEA2_EXAMPLES.md)
- **Knowledge Base**: [GAEA2_KNOWLEDGE_BASE.md](GAEA2_KNOWLEDGE_BASE.md)
