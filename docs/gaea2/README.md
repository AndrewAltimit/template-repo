# Gaea2 MCP (Model Context Protocol) System

A comprehensive, intelligent terrain generation toolkit for Gaea2, providing programmatic control over terrain creation with advanced validation, error recovery, and pattern-based intelligence.

## 🚀 Overview

The Gaea2 MCP system enables programmatic creation and manipulation of Gaea2 terrain projects through the Model Context Protocol. It includes intelligent validation, automatic error recovery, pattern-based suggestions, and comprehensive node support for all 185 documented Gaea2 nodes.

### Key Features

- **Complete Node Coverage**: Support for all 185 Gaea2 nodes across 9 categories
- **Intelligent Validation**: Multi-level validation with automatic error correction
- **Pattern Intelligence**: Learning from 31 real projects (374 nodes, 440 connections)
- **Auto-Fix Capabilities**: Automatic detection and correction of common issues
- **Performance Optimization**: 19x speedup through intelligent caching
- **Professional Templates**: Ready-to-use workflow templates
- **Advanced Features**: Groups, modifiers, automation variables, draw nodes

## 📁 System Architecture

```
tools/mcp/
├── Core Components
│   ├── gaea2_schema.py              # Core schema definitions
│   ├── gaea2_complete_schema.json   # Complete node definitions (185 nodes)
│   ├── gaea2_validation.py          # Basic validation
│   └── gaea2_accurate_validation.py # Enhanced validation
│
├── Validation & Error Handling
│   ├── gaea2_structure_validator.py   # Project structure validation
│   ├── gaea2_property_validator.py    # Property validation with patterns
│   ├── gaea2_connection_validator.py  # Connection compatibility
│   ├── gaea2_error_handler.py        # Error classification
│   └── gaea2_error_recovery.py       # Automated error recovery
│
├── Intelligence & Analysis
│   ├── gaea2_knowledge_graph.py      # Node relationships & suggestions
│   ├── gaea2_pattern_knowledge.py    # Real project patterns
│   ├── gaea2_workflow_analyzer.py    # Workflow analysis
│   └── gaea2_workflow_tools.py       # Advanced workflow management
│
└── Infrastructure
    ├── gaea2_cache.py                # Performance caching
    ├── gaea2_logging.py              # Structured logging
    └── gaea2_project_repair.py       # Project repair tools
```

## 🛠️ Available MCP Tools

### 1. **create_gaea2_project**
Create custom Gaea2 terrain projects with full control over nodes and connections.

```python
# Example usage
result = await create_gaea2_project(
    project_name="Alpine Valley",
    nodes=[
        {"type": "Mountain", "properties": {"Scale": 1.5}},
        {"type": "Erosion2", "properties": {"Duration": 0.07}}
    ],
    connections=[{"from_node": 0, "to_node": 1}]
)
```

### 2. **validate_and_fix_workflow**
Comprehensive validation and automatic repair of Gaea2 workflows.

```python
# Validates and fixes common issues
result = await validate_and_fix_workflow(
    nodes=workflow_nodes,
    connections=workflow_connections,
    auto_fix=True,
    aggressive=False  # Conservative mode
)
```

### 3. **analyze_workflow_patterns**
Analyze workflows to get intelligent suggestions based on real project patterns.

```python
# Get next node suggestions
result = await analyze_workflow_patterns(
    current_workflow=[
        {"type": "Mountain"},
        {"type": "Erosion2"}
    ]
)
# Returns suggestions like: Rivers (65% probability), TextureBase (45%)
```

### 4. **repair_gaea2_project**
Repair damaged or invalid Gaea2 project files.

```python
# Analyze and repair project
result = await repair_gaea2_project(
    project_data=loaded_project,
    auto_fix=True
)
# Returns health score, errors found, and fixes applied
```

### 5. **create_gaea2_from_template**
Create projects using professional workflow templates.

```python
# Available templates: basic_terrain, detailed_mountain, volcanic_terrain, desert_canyon
result = await create_gaea2_from_template(
    template_name="detailed_mountain",
    project_name="My Mountain"
)
```

### 6. **optimize_gaea2_properties**
Optimize node properties for performance or quality.

```python
# Optimize for performance
result = await optimize_gaea2_properties(
    node_type="Erosion2",
    properties={"Duration": 0.15},
    mode="performance"  # or "quality"
)
```

### 7. **suggest_gaea2_nodes**
Get intelligent node suggestions based on terrain type and context.

```python
# Get suggestions for specific terrain
result = await suggest_gaea2_nodes(
    terrain_type="mountain",
    existing_nodes=["Mountain", "Erosion2"]
)
```

## 🎯 Node Categories & Support

### Supported Node Categories (185 total)

1. **🟢 Primitive (24 nodes)** - Noise generators and basic patterns
2. **🟢 Terrain (14 nodes)** - Primary terrain generators
3. **🔵 Modify (41 nodes)** - Terrain modification tools
4. **🟡 Surface (21 nodes)** - Surface detail and texture
5. **🟠 Simulate (25 nodes)** - Natural process simulation
6. **⚪ Derive (13 nodes)** - Analysis and mask generation
7. **🟣 Colorize (13 nodes)** - Color and texture operations
8. **🔴 Output (13 nodes)** - Export and integration nodes
9. **⚫ Utility (20 nodes)** - Helper and utility nodes

## 🧠 Intelligence Features

### Pattern-Based Knowledge

The system has analyzed 31 real Gaea2 projects to extract common patterns:

- **Most Common Workflow**: Slump → FractalTerraces → Combine → Shear (9 occurrences)
- **Most Used Nodes**: SatMap (47), Combine (38), Erosion2 (29)
- **Average Complexity**: 12.1 nodes, 14.2 connections per project

### Validation Levels

1. **Structure Validation** - Ensures valid Gaea2 project format
2. **Node Validation** - Validates node types and configurations
3. **Property Validation** - Type checking and range validation
4. **Connection Validation** - Ensures compatible connections
5. **Pattern Validation** - Checks against known good patterns

### Error Recovery

Automatic fixes for common issues:
- Remove duplicate connections
- Fix out-of-range property values
- Add missing required nodes (e.g., Export)
- Connect orphaned nodes intelligently
- Optimize workflow order

## 📊 Performance

- **Caching System**: 19x speedup for repeated operations
- **In-Memory Cache**: Fast access with TTL support
- **Disk Persistence**: Optional cache persistence
- **Optimized Validation**: Efficient pattern matching

## 🚦 Getting Started

### Basic Project Creation

```python
from tools.mcp.mcp_server import MCPTools

# Create a simple terrain
result = await MCPTools.create_gaea2_project(
    project_name="Simple Mountain",
    nodes=[
        {"type": "Mountain", "name": "Base"},
        {"type": "Erosion2", "name": "Eroded"},
        {"type": "SatMap", "name": "Colored"}
    ],
    connections=[
        {"from_node": 0, "to_node": 1},
        {"from_node": 1, "to_node": 2}
    ]
)
```

### Validation & Repair

```python
# Load and validate a project
with open("terrain.json") as f:
    project = json.load(f)

# Validate and fix
result = await MCPTools.validate_and_fix_workflow(
    nodes=project["nodes"],
    connections=project["connections"],
    auto_fix=True
)

print(f"Quality Score: {result['quality_scores']['fixed']}/100")
print(f"Fixes Applied: {len(result['fixes']['applied'])}")
```

## 📚 Documentation

- [Comprehensive Guide](../GAEA2_MCP_COMPREHENSIVE_GUIDE.md) - Complete user guide
- [Knowledge Base](GAEA2_KNOWLEDGE_BASE.md) - Patterns from real projects
- [API Reference](GAEA2_API_REFERENCE.md) - Detailed API documentation
- [Examples](GAEA2_EXAMPLES.md) - Code examples and patterns

## 🔧 Advanced Features

### Groups and Modifiers

```python
# Create with groups
result = await MCPTools.create_gaea2_project(
    project_name="Grouped Terrain",
    nodes=[...],
    groups=[
        {
            "name": "Erosion Group",
            "node_ids": [100, 101, 102],
            "color": "#FF5733"
        }
    ]
)
```

### Automation Variables

```python
# Add automation
result = await MCPTools.create_gaea2_project(
    project_name="Automated Terrain",
    nodes=[...],
    automation_variables=[
        {
            "name": "GlobalScale",
            "value": 1.0,
            "min": 0.1,
            "max": 10.0
        }
    ]
)
```

### Draw Nodes

```python
# Add hand-drawn features
nodes = [{
    "type": "Draw",
    "properties": {
        "stroke_data": [...],  # Stroke information
        "brush_size": 50
    }
}]
```

## 🎨 Professional Templates

### Available Templates

1. **basic_terrain** - Simple terrain with erosion and coloring
2. **detailed_mountain** - Advanced mountain with rivers, snow, and strata
3. **volcanic_terrain** - Volcanic landscape with lava and ash
4. **desert_canyon** - Desert canyon with stratification

### Template Usage

```python
# Create from template
result = await MCPTools.create_gaea2_from_template(
    template_name="volcanic_terrain",
    project_name="Mount Doom",
    output_path="mount_doom.terrain"
)
```

## 🔍 Workflow Analysis

### Performance Analysis

```python
# Analyze workflow performance
analysis = await MCPTools.analyze_workflow_patterns(
    current_workflow=nodes
)

# Get bottlenecks and optimization suggestions
print(f"Performance Score: {analysis['performance_score']}")
print(f"Bottlenecks: {analysis['bottlenecks']}")
```

### Pattern Matching

```python
# Find similar workflows
similar = await MCPTools.find_similar_workflows(
    workflow=current_nodes,
    similarity_threshold=0.8
)
```

## 🛡️ Error Handling

The system provides comprehensive error handling with:

- **Severity Levels**: Critical, Error, Warning, Info
- **Categories**: Validation, Connection, Property, Structure, Compatibility, Performance
- **Auto-Fix Support**: Identifies which errors can be automatically fixed
- **Detailed Suggestions**: Provides actionable fix suggestions

## 🏆 Best Practices

1. **Always Validate**: Run validation before saving projects
2. **Use Templates**: Start with templates for common terrain types
3. **Follow Patterns**: Use analyzed patterns for better results
4. **Optimize Properties**: Use optimization tools for better performance
5. **Handle Errors**: Check error reports and apply suggested fixes

## 🤝 Contributing

The Gaea2 MCP system is actively maintained. For issues or contributions:

1. Check the [Knowledge Base](GAEA2_KNOWLEDGE_BASE.md) for patterns
2. Review [API Reference](GAEA2_API_REFERENCE.md) for implementation details
3. See [Examples](GAEA2_EXAMPLES.md) for usage patterns

## 📈 Performance Metrics

Based on analysis of 31 real projects:

- **Average Project Size**: 12.1 nodes, 14.2 connections
- **Most Complex Project**: 31 nodes, 33 connections
- **Cache Performance**: 19x speedup on repeated operations
- **Validation Speed**: <100ms for average projects
- **Auto-Fix Success Rate**: 85% of common issues

## 🔗 Related Documentation

- [Gaea2 Official Documentation](https://docs.quadspinner.com/gaea/)
- [MCP Protocol Specification](https://docs.anthropic.com/mcp)
- [Template Repository](https://github.com/AndrewAltimit/template-repo)

---

*Built with intelligence from analyzing 31 real Gaea2 projects containing 374 nodes and 440 connections.*
