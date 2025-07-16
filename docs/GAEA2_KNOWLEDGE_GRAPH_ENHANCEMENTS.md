# Gaea2 Knowledge Graph Enhancements

## Overview

The Gaea MCP tool has been enhanced with a knowledge graph system that significantly improves reliability and usability by:

1. **Understanding node relationships** - Captures how nodes work together
2. **Validating workflows** - Detects conflicts and missing dependencies
3. **Providing intelligent suggestions** - Recommends next nodes based on patterns
4. **Optimizing properties** - Automatically adjusts properties based on constraints

## Key Features

### 1. Node Relationships

The knowledge graph tracks various relationship types between nodes:

- **REQUIRES** - Node A requires Node B to function
- **ENHANCES** - Node A improves the output of Node B
- **CONFLICTS** - Node A conflicts with Node B
- **FOLLOWS/PRECEDES** - Common workflow ordering
- **COMBINES_WITH** - Nodes that work well together
- **ALTERNATIVE_TO** - Different approaches to same goal
- **PROVIDES_DATA_FOR** - Data flow relationships
- **CONSUMES_DATA_FROM** - Input requirements

Example relationships:
- Mountain → Erosion (PRECEDES with 0.9 strength)
- Erosion → Erosion2 (CONFLICTS - over-processing)
- Erosion produces Wear/Flow/Deposits data maps
- CLUTer consumes Flow/Wear/Deposits for coloring

### 2. Workflow Patterns

The system recognizes common workflow patterns:

- **Basic Terrain** - Mountain → Erosion → TextureBase → SatMap
- **Realistic Mountain** - Includes rivers, snow, multiple erosion
- **Desert Terrain** - DuneSea → Erosion → Sand → SatMap
- **Data-Driven Texturing** - Uses erosion outputs for coloring
- **Combined Erosion** - Chains multiple erosion types
- **Complete Water System** - Rivers + Lakes with proper flow
- **Selective Processing** - Masked erosion using slope data

### 3. Property Constraints

Automatic property optimization based on relationships:

- Erosion FeatureScale proportional to terrain Scale (×2000)
- Snow Altitude relative to Mountain Height (×0.8)
- River Depth correlates with Erosion Strength

### 4. New MCP Tools

Three new tools leverage the knowledge graph:

#### `analyze_gaea2_workflow`
Analyzes a workflow for issues and improvements:
```python
{
    "nodes": [...],
    "connections": [...]
}
```
Returns validation results, similar patterns, and suggestions.

#### `suggest_gaea2_nodes`
Gets intelligent node suggestions:
```python
{
    "current_nodes": ["Mountain", "Erosion"]
}
```
Returns ranked suggestions with confidence scores.

#### `optimize_gaea2_properties`
Optimizes node properties:
```python
{
    "nodes": [
        {"name": "Mountain", "type": "Mountain", "properties": {...}},
        {"name": "Erosion", "type": "Erosion", "properties": {...}}
    ]
}
```
Returns optimized properties with explanations.

## Benefits

1. **Improved Reliability**
   - Detects conflicting node combinations
   - Validates portal connections
   - Ensures proper data flow

2. **Better User Experience**
   - Intelligent suggestions guide workflow creation
   - Automatic property optimization saves time
   - Pattern recognition helps users learn

3. **Reduced Errors**
   - Warns about missing dependencies
   - Suggests proper node ordering
   - Optimizes critical parameters

4. **Educational Value**
   - Shows why certain nodes work together
   - Explains property relationships
   - Teaches best practices through patterns

## Implementation Details

The knowledge graph is implemented in `gaea2_knowledge_graph.py` with:

- **NodeRelationship** - Stores relationships between nodes
- **NodePattern** - Defines common workflow patterns
- **PropertyConstraint** - Captures property dependencies
- **Gaea2KnowledgeGraph** - Main class managing all data

The graph is initialized with relationships extracted from:
- Official Gaea2 documentation
- Common workflow patterns
- Best practices from examples

## Future Enhancements

1. **Machine Learning Integration**
   - Learn patterns from user workflows
   - Improve suggestions over time
   - Detect anomalies

2. **Extended Constraints**
   - More property relationships
   - Resolution-dependent adjustments
   - Performance optimization hints

3. **Visual Graph Explorer**
   - Interactive relationship viewer
   - Pattern visualization
   - Workflow debugging tools

4. **Custom Pattern Support**
   - User-defined patterns
   - Project-specific workflows
   - Team knowledge sharing

## Usage Example

```python
# Analyze a workflow
nodes = [
    {"name": "Mountain", "type": "Mountain", "properties": {"Scale": 1.0}},
    {"name": "Erosion", "type": "Erosion", "properties": {"Duration": 0.04}}
]
connections = [
    {"from_node": "Mountain", "to_node": "Erosion"}
]

result = await analyze_gaea2_workflow(nodes, connections)
# Returns validation, suggestions, and similar patterns

# Get next node suggestions
suggestions = await suggest_gaea2_nodes(["Mountain", "Erosion"])
# Returns: Thermal, Rivers, Snow, SatMap, etc.

# Optimize properties
optimized = await optimize_gaea2_properties(nodes)
# Adjusts Erosion.FeatureScale to 2000 based on Mountain.Scale
```

The knowledge graph makes the Gaea MCP tool more intelligent, helping users create better terrain with less trial and error.
