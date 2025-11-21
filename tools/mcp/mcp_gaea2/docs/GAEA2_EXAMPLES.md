# Gaea2 MCP Examples

Comprehensive examples demonstrating the Gaea2 MCP system capabilities.

## Table of Contents

1. [Basic Examples](#basic-examples)
2. [Validation and Repair](#validation-and-repair)
3. [Pattern-Based Workflows](#pattern-based-workflows)
4. [Advanced Features](#advanced-features)
5. [Real-World Scenarios](#real-world-scenarios)
6. [Performance Optimization](#performance-optimization)
7. [Error Handling](#error-handling)

---

## Basic Examples

### 1. Simple Mountain Terrain (With Automatic Validation)

Create a basic mountain terrain - validation and fixing is automatic!

```python
from tools.mcp.mcp_server import MCPTools
import asyncio

async def create_simple_mountain():
    # Define only the essential nodes - Export and SatMap are added automatically!
    nodes = [
        {
            "id": 100,
            "type": "Mountain",
            "name": "Base Mountain",
            "properties": {
                "Scale": 1.5,
                "Seed": 42,
                "Height": 1.0
            }
        },
        {
            "id": 101,
            "type": "Erosion2",
            "name": "Natural Erosion",
            "properties": {
                "Duration": 0.15,  # Will be auto-corrected to 0.1 max
                "Scale": 10000,
                "Detail": 0.8
            }
        }
        # No need to add Export or SatMap - they're added automatically!
    ]

    # Define connections
    connections = [
        {"from_node": 100, "to_node": 101}
    ]

    # Create project with automatic validation (default behavior)
    result = await MCPTools.create_gaea2_project(
        project_name="Simple Mountain",
        nodes=nodes,
        connections=connections,
        output_path="simple_mountain.terrain"
        # auto_validate=True is the default!
    )

    print(f"Created project: {result['output_path']}")
    print(f"Nodes after validation: {result['node_count']}")  # Will show 4 (added Export + SatMap)
    print(f"Quality score: {result['validation']['quality_score']}/100")
    print(f"Fixes applied: {result['validation']['fixes_applied']}")

# Run the example
asyncio.run(create_simple_mountain())
```

**What happens automatically:**
- ✅ Export node is added (required for Gaea2)
- ✅ SatMap node is added for coloring
- ✅ Erosion Duration reduced from 0.15 to 0.1 (performance optimization)
- ✅ All connections are validated and created
- ✅ File format is guaranteed to work in Gaea2

### 2. Multi-Port Connections (Combine Nodes)

Example showing how to properly connect nodes with multiple input ports.

```python
async def create_multi_port_terrain():
    # Define nodes including Combine nodes with multiple inputs
    nodes = [
        {"id": 100, "type": "Mountain", "name": "Primary"},
        {"id": 101, "type": "Mountain", "name": "Secondary"},
        {"id": 102, "type": "Combine", "name": "Mix Mountains"},
        {"id": 103, "type": "Erosion2", "name": "Erode"},
        {"id": 104, "type": "Rivers", "name": "Add Rivers"},
        {"id": 105, "type": "Sea", "name": "Add Sea"},
        {"id": 106, "type": "Combine", "name": "Final Mix"},
        {"id": 107, "type": "Height", "name": "Height Mask"},
        {"id": 108, "type": "SatMap", "name": "Color"}
    ]

    # Define connections with specific ports
    connections = [
        # Connect two mountains to Combine
        {"from_node": 100, "to_node": 102, "from_port": "Out", "to_port": "In"},
        {"from_node": 101, "to_node": 102, "from_port": "Out", "to_port": "Input2"},

        # Continue processing
        {"from_node": 102, "to_node": 103, "from_port": "Out", "to_port": "In"},
        {"from_node": 103, "to_node": 104, "from_port": "Out", "to_port": "In"},
        {"from_node": 104, "to_node": 105, "from_port": "Out", "to_port": "In"},

        # Complex multi-port connection to final Combine
        {"from_node": 105, "to_node": 106, "from_port": "Out", "to_port": "In"},
        {"from_node": 108, "to_node": 106, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 107, "to_node": 106, "from_port": "Out", "to_port": "Mask"},

        # Use special output ports
        {"from_node": 105, "to_node": 107, "from_port": "Out", "to_port": "In"},
        {"from_node": 104, "to_node": 108, "from_port": "Rivers", "to_port": "In"}
    ]

    # Create project
    result = await MCPTools.create_gaea2_project(
        project_name="Multi-Port Example",
        nodes=nodes,
        connections=connections
    )

    print(f"Created {result['connection_count']} connections successfully!")

asyncio.run(create_multi_port_terrain())
```

**Important Connection Notes:**
- **Combine nodes** have ports: "In", "Input2", "Mask", "Out"
- **Rivers nodes** have special outputs: "Rivers", "Depth", "Surface", "Direction"
- **Sea nodes** have outputs: "Water", "Shore", "Depth", "Surface"
- Always specify both `from_port` and `to_port` for clarity
- Node IDs must exist before they can be referenced in connections

### 3. Using Templates

Create terrain using predefined templates.

```python
async def use_templates():
    # List available templates
    templates = await MCPTools.list_gaea2_templates()
    print("Available templates:")
    for name, info in templates['templates'].items():
        print(f"  - {name}: {info['description']}")

    # Create from template
    result = await MCPTools.create_gaea2_from_template(
        template_name="detailed_mountain",
        project_name="My Detailed Mountain",
        output_path="detailed_mountain.terrain"
    )

    print(f"\nCreated {result['node_count']} nodes with {result['connection_count']} connections")

asyncio.run(use_templates())
```

### 3. Node Suggestions

Get intelligent node suggestions based on terrain type.

```python
async def get_node_suggestions():
    # Get suggestions for a volcanic terrain
    result = await MCPTools.suggest_gaea2_nodes(
        terrain_type="volcanic",
        existing_nodes=["Mountain"],
        purpose="game"
    )

    print("Suggested nodes for volcanic terrain:")
    for suggestion in result['suggestions']:
        print(f"\n{suggestion['node']} ({suggestion['category']})")
        print(f"  Priority: {suggestion['priority']}")
        print(f"  Reason: {suggestion['reason']}")
        if suggestion['properties']:
            print(f"  Recommended properties: {suggestion['properties']}")

asyncio.run(get_node_suggestions())
```

---

## Validation and Repair

### 4. Project Validation

Validate an existing project and identify issues.

```python
async def validate_project():
    # Load a project
    import json
    with open("terrain_project.terrain") as f:
        project_data = json.load(f)

    # Extract nodes and connections
    nodes = []
    connections = []

    # Parse project structure (simplified)
    for asset in project_data.get("Assets", {}).get("$values", []):
        terrain = asset.get("Terrain", {})
        for node_id, node_data in terrain.get("Nodes", {}).items():
            nodes.append({
                "id": int(node_id),
                "type": node_data.get("$type", "").split(".")[-2],
                "properties": {k: v for k, v in node_data.items()
                             if not k.startswith("$")}
            })

    # Validate without fixing
    result = await MCPTools.validate_and_fix_workflow(
        nodes=nodes,
        connections=connections,
        auto_fix=False
    )

    print("Validation Results:")
    print(f"  Quality Score: {result['quality_scores']['original']}/100")
    print(f"  Property Issues: {len(result['validation']['property_issues'])}")
    print(f"  Connection Errors: {len(result['validation']['connection_errors'])}")
    print(f"  Connection Warnings: {len(result['validation']['connection_warnings'])}")

    # Show specific issues
    for issue in result['validation']['property_issues'][:3]:
        print(f"\nProperty Issue: {issue}")

asyncio.run(validate_project())
```

### 5. Automatic Project Repair

Repair a project with automatic fixes.

```python
async def repair_project():
    # Create a project with intentional issues
    problematic_nodes = [
        {
            "id": 100,
            "type": "Mountain",
            "name": "Mountain1",
            "properties": {
                "Scale": "wrong_type",  # Should be float
                "InvalidProp": 123      # Invalid property
            }
        },
        {
            "id": 101,
            "type": "Rivers",
            "name": "Rivers1",
            "properties": {
                "Headwaters": 500  # Too high, will be clamped
            }
        },
        {
            "id": 102,
            "type": "Erosion2",
            "name": "Erosion1"
            # Missing required properties
        },
        {
            "id": 103,
            "type": "SatMap",
            "name": "Orphaned"
            # Not connected to anything
        }
    ]

    problematic_connections = [
        {"from_node": 100, "to_node": 101},  # Rivers before erosion
        {"from_node": 100, "to_node": 101},  # Duplicate
        {"from_node": 999, "to_node": 102}   # Invalid reference
    ]

    # Repair with aggressive mode
    result = await MCPTools.validate_and_fix_workflow(
        nodes=problematic_nodes,
        connections=problematic_connections,
        auto_fix=True,
        aggressive=True
    )

    print("Repair Results:")
    print(f"  Original Quality: {result['quality_scores']['original']}/100")
    print(f"  Fixed Quality: {result['quality_scores']['fixed']}/100")
    print(f"  Improvement: +{result['quality_scores']['improvement']}")

    print(f"\nFixes Applied ({len(result['fixes']['applied'])}):")
    for fix in result['fixes']['applied']:
        print(f"  - {fix}")

    # Show the fixed workflow
    print(f"\nFixed workflow has {len(result['fixed_workflow']['nodes'])} nodes")
    print(f"and {len(result['fixed_workflow']['connections'])} connections")

asyncio.run(repair_project())
```

---

## Pattern-Based Workflows

### 6. Building with Patterns

Create workflows using learned patterns.

```python
async def build_with_patterns():
    # Start with a terrain generator
    workflow = [
        {"type": "Ridge", "id": 100, "name": "Base Ridge"}
    ]

    # Build workflow step by step using patterns
    for i in range(4):
        # Get pattern-based suggestions
        analysis = await MCPTools.analyze_workflow_patterns(
            current_workflow=workflow
        )

        # Get the most likely next node
        if analysis['recommendations']['next_nodes']:
            next_node = analysis['recommendations']['next_nodes'][0]

            print(f"\nStep {i+1}: Adding {next_node['node']}")
            print(f"  Reason: Used {next_node['frequency']} times after {workflow[-1]['type']}")
            print(f"  Probability: {next_node['probability']:.0%}")

            # Get optimized properties for the node
            props_result = await MCPTools.optimize_gaea2_properties(
                node_type=next_node['node'],
                properties={},
                mode="balanced"
            )

            # Add to workflow
            new_node = {
                "type": next_node['node'],
                "id": 100 + len(workflow),
                "name": f"{next_node['node']}_{i+1}",
                "properties": props_result['optimized_properties']
            }
            workflow.append(new_node)

    # Create connections
    connections = []
    for i in range(len(workflow) - 1):
        connections.append({
            "from_node": workflow[i]['id'],
            "to_node": workflow[i + 1]['id']
        })

    # Create the project
    result = await MCPTools.create_gaea2_project(
        project_name="Pattern-Based Ridge",
        nodes=workflow,
        connections=connections
    )

    print(f"\nCreated workflow: {' → '.join(n['type'] for n in workflow)}")
    print(f"Quality Score: {result['validation']['warnings']}")

asyncio.run(build_with_patterns())
```

### 7. Workflow Analysis

Analyze existing workflows for patterns and improvements.

```python
async def analyze_workflow():
    # Define a complex workflow
    workflow = [
        {"type": "Mountain", "id": 100},
        {"type": "Erosion2", "id": 101},
        {"type": "Rivers", "id": 102},
        {"type": "Snow", "id": 103},
        {"type": "TextureBase", "id": 104},
        {"type": "SatMap", "id": 105}
    ]

    # Analyze the workflow
    analysis = await MCPTools.analyze_workflow_patterns(
        current_workflow=workflow
    )

    print("Workflow Analysis:")
    print(f"  Quality Score: {analysis['recommendations']['workflow_quality']}/100")

    # Check for missing common nodes
    if analysis['recommendations']['missing_common_nodes']:
        print("\nMissing commonly used nodes:")
        for node in analysis['recommendations']['missing_common_nodes']:
            print(f"  - {node}")

    # Find similar workflows
    if analysis['recommendations']['similar_workflows']:
        print("\nSimilar workflows found:")
        for similar in analysis['recommendations']['similar_workflows'][:3]:
            print(f"  - {similar['description']}")
            print(f"    Similarity: {similar['similarity']:.0%}")

    # Next node suggestions
    print("\nSuggested next nodes:")
    for suggestion in analysis['recommendations']['next_nodes'][:3]:
        print(f"  - {suggestion['node']}: {suggestion['reason']}")

asyncio.run(analyze_workflow())
```

---

## Advanced Features

### 8. Groups and Organization

Create organized projects with node groups.

```python
async def create_grouped_project():
    # Create nodes for different terrain features
    nodes = [
        # Mountain group
        {"id": 100, "type": "Mountain", "name": "Main Peak"},
        {"id": 101, "type": "Mountain", "name": "Secondary Peak"},
        {"id": 102, "type": "Combine", "name": "Merge Peaks"},

        # Erosion group
        {"id": 200, "type": "Erosion2", "name": "Primary Erosion"},
        {"id": 201, "type": "Rivers", "name": "River Carving"},
        {"id": 202, "type": "Combine", "name": "Erosion Mix"},

        # Details group
        {"id": 300, "type": "TextureBase", "name": "Rock Texture"},
        {"id": 301, "type": "Snow", "name": "Snow Cap"},
        {"id": 302, "type": "SatMap", "name": "Final Colors"},

        # Output
        {"id": 400, "type": "Export", "name": "Final Export"}
    ]

    # Define connections
    connections = [
        # Mountain connections
        {"from_node": 100, "to_node": 102, "to_port": "A"},
        {"from_node": 101, "to_node": 102, "to_port": "B"},

        # Erosion connections
        {"from_node": 102, "to_node": 200},
        {"from_node": 200, "to_node": 201},
        {"from_node": 200, "to_node": 202, "to_port": "A"},
        {"from_node": 201, "to_node": 202, "to_port": "B"},

        # Detail connections
        {"from_node": 202, "to_node": 300},
        {"from_node": 202, "to_node": 301},
        {"from_node": 300, "to_node": 302, "to_port": "A"},
        {"from_node": 301, "to_node": 302, "to_port": "B"},

        # Output
        {"from_node": 302, "to_node": 400}
    ]

    # Define groups
    groups = [
        {
            "name": "Mountain Generation",
            "node_ids": [100, 101, 102],
            "color": "#FF6B6B"
        },
        {
            "name": "Erosion System",
            "node_ids": [200, 201, 202],
            "color": "#4ECDC4"
        },
        {
            "name": "Surface Details",
            "node_ids": [300, 301, 302],
            "color": "#45B7D1"
        }
    ]

    # Create project with groups
    result = await MCPTools.create_gaea2_project(
        project_name="Organized Mountain",
        nodes=nodes,
        connections=connections,
        groups=groups
    )

    print(f"Created organized project with {len(groups)} groups")
    print(f"Total nodes: {result['node_count']}")
    print(f"Total connections: {result['connection_count']}")

asyncio.run(create_grouped_project())
```

### 9. Automation Variables

Create projects with automation for parameter control.

```python
async def create_automated_project():
    # Define automation variables
    automation_variables = [
        {
            "name": "GlobalScale",
            "value": 1.0,
            "min": 0.1,
            "max": 10.0,
            "exposed": True
        },
        {
            "name": "ErosionStrength",
            "value": 0.07,
            "min": 0.01,
            "max": 0.2,
            "step": 0.01,
            "exposed": True
        },
        {
            "name": "SnowLevel",
            "value": 0.7,
            "min": 0.0,
            "max": 1.0,
            "exposed": True
        }
    ]

    # Create nodes with automation
    nodes = [
        {
            "id": 100,
            "type": "Mountain",
            "name": "Base Terrain",
            "properties": {
                "Scale": 1.5,
                "Height": 1.0
            },
            "automation": {
                "Scale": {
                    "variable": "GlobalScale",
                    "expression": "GlobalScale * 1.5"
                }
            }
        },
        {
            "id": 101,
            "type": "Erosion2",
            "name": "Erosion",
            "properties": {
                "Duration": 0.07,
                "Scale": 10000
            },
            "automation": {
                "Duration": {
                    "variable": "ErosionStrength",
                    "expression": "ErosionStrength"
                }
            }
        },
        {
            "id": 102,
            "type": "Snow",
            "name": "Snow Coverage",
            "properties": {
                "Level": 0.7,
                "Blend": 0.8
            },
            "automation": {
                "Level": {
                    "variable": "SnowLevel",
                    "expression": "SnowLevel"
                }
            }
        },
        {
            "id": 103,
            "type": "Export",
            "name": "Output"
        }
    ]

    connections = [
        {"from_node": 100, "to_node": 101},
        {"from_node": 101, "to_node": 102},
        {"from_node": 102, "to_node": 103}
    ]

    # Create automated project
    result = await MCPTools.create_gaea2_project(
        project_name="Automated Terrain",
        nodes=nodes,
        connections=connections,
        automation_variables=automation_variables
    )

    print("Created automated project with variables:")
    for var in automation_variables:
        print(f"  - {var['name']}: {var['value']} (range: {var['min']}-{var['max']})")

asyncio.run(create_automated_project())
```

### 10. Custom Build Configuration

Create projects with specific build settings.

```python
async def create_with_build_config():
    # Use a template
    template_result = await MCPTools.create_gaea2_from_template(
        template_name="detailed_mountain",
        project_name="High Resolution Mountain"
    )

    # Load and modify with build config
    nodes = template_result.get('nodes', [])
    connections = template_result.get('connections', [])

    # Define high-quality build configuration
    build_config = {
        "resolution": 4096,           # 4K resolution
        "format": "EXR",             # OpenEXR format
        "bit_depth": 32,             # 32-bit float
        "range": [-1000.0, 2000.0],  # Height range in meters
        "method": "Tiled",           # Tiled build for large terrains
        "tile_size": 1024,           # 1K tiles
        "build_options": {
            "enable_caching": True,
            "multi_threaded": True,
            "memory_limit": 16384     # 16GB memory limit
        }
    }

    # Define viewport configuration
    viewport_config = {
        "default_resolution": 512,
        "preview_quality": "high",
        "show_grid": True,
        "grid_size": 100,
        "background_color": "#1a1a1a"
    }

    # Create project with configurations
    result = await MCPTools.create_gaea2_project(
        project_name="High Quality Mountain",
        nodes=nodes,
        connections=connections,
        build_config=build_config,
        viewport_config=viewport_config
    )

    print("Created project with custom build configuration:")
    print(f"  Resolution: {build_config['resolution']}x{build_config['resolution']}")
    print(f"  Format: {build_config['format']} ({build_config['bit_depth']}-bit)")
    print(f"  Build Method: {build_config['method']}")

asyncio.run(create_with_build_config())
```

---

## Real-World Scenarios

### 11. Game-Ready Terrain

Create optimized terrain for game development.

```python
async def create_game_terrain():
    # Get suggestions for game terrain
    suggestions = await MCPTools.suggest_gaea2_nodes(
        terrain_type="mountain",
        purpose="game"
    )

    # Build optimized workflow
    nodes = []
    node_id = 100

    # Add suggested nodes with performance optimization
    for suggestion in suggestions['suggestions']:
        if suggestion['priority'] in ['essential', 'recommended']:
            # Get performance-optimized properties
            opt_result = await MCPTools.optimize_gaea2_properties(
                node_type=suggestion['node'],
                properties=suggestion.get('properties', {}),
                mode="performance"
            )

            nodes.append({
                "id": node_id,
                "type": suggestion['node'],
                "name": f"{suggestion['node']}_{node_id}",
                "properties": opt_result['optimized_properties']
            })
            node_id += 1

    # Add game-specific nodes
    game_nodes = [
        {
            "id": node_id,
            "type": "Slope",
            "name": "Slope Mask",
            "properties": {"Angle": 45}
        },
        {
            "id": node_id + 1,
            "type": "Height",
            "name": "Height Zones",
            "properties": {"Levels": 4}
        },
        {
            "id": node_id + 2,
            "type": "Export",
            "name": "Game Export"
        }
    ]
    nodes.extend(game_nodes)

    # Create connections
    connections = []
    for i in range(len(nodes) - 1):
        connections.append({
            "from_node": nodes[i]['id'],
            "to_node": nodes[i + 1]['id']
        })

    # Game-optimized build config
    build_config = {
        "resolution": 2048,      # Standard game resolution
        "format": "PNG",         # Game-friendly format
        "bit_depth": 16,         # Good precision/size balance
        "method": "Normal",      # Fast single build
        "game_export": {
            "generate_lods": True,
            "lod_levels": [1024, 512, 256],
            "export_masks": True,
            "export_normals": True
        }
    }

    # Create game-ready terrain
    result = await MCPTools.create_gaea2_project(
        project_name="Game Terrain",
        nodes=nodes,
        connections=connections,
        build_config=build_config
    )

    print("Created game-ready terrain:")
    print(f"  Nodes: {result['node_count']}")
    print(f"  Optimized for performance")
    print(f"  Includes gameplay masks (slope, height zones)")

asyncio.run(create_game_terrain())
```

### 12. Film Production Terrain

Create high-quality terrain for film/VFX.

```python
async def create_film_terrain():
    # Start with detailed mountain template
    template = await MCPTools.create_gaea2_from_template(
        template_name="detailed_mountain",
        project_name="Film Mountain Base"
    )

    # Load the created nodes
    nodes = template.get('nodes', [])
    connections = template.get('connections', [])

    # Find highest ID
    max_id = max(n['id'] for n in nodes)

    # Add film-quality enhancement nodes
    film_nodes = [
        {
            "id": max_id + 1,
            "type": "Displace",
            "name": "Micro Detail",
            "properties": {
                "Amount": 0.1,
                "Scale": 0.001  # Very fine detail
            }
        },
        {
            "id": max_id + 2,
            "type": "Data",
            "name": "32bit Height",
            "properties": {
                "Format": "EXR32"
            }
        },
        {
            "id": max_id + 3,
            "type": "Normal",
            "name": "Normal Map",
            "properties": {
                "Strength": 1.0,
                "HighQuality": True
            }
        },
        {
            "id": max_id + 4,
            "type": "Ambient",
            "name": "Ambient Occlusion",
            "properties": {
                "Samples": 64,
                "Radius": 50
            }
        }
    ]

    # Get quality-optimized properties
    for node in nodes:
        opt_result = await MCPTools.optimize_gaea2_properties(
            node_type=node['type'],
            properties=node.get('properties', {}),
            mode="quality"
        )
        node['properties'] = opt_result['optimized_properties']

    # Add film nodes
    nodes.extend(film_nodes)

    # Connect film enhancement nodes
    last_node = nodes[-5]  # Last node before film nodes
    for i, film_node in enumerate(film_nodes[:-1]):
        connections.append({
            "from_node": last_node['id'] if i == 0 else film_nodes[i-1]['id'],
            "to_node": film_node['id']
        })

    # Film production build config
    build_config = {
        "resolution": 8192,       # 8K for film
        "format": "EXR",         # Film standard
        "bit_depth": 32,         # Full float precision
        "range": [-2000.0, 4000.0],
        "method": "Tiled",       # For huge terrains
        "tile_size": 2048,
        "film_export": {
            "export_layers": True,
            "layer_format": "EXR",
            "include_passes": [
                "height", "normal", "ao",
                "slope", "flow", "deposit"
            ]
        }
    }

    # Create film-quality terrain
    result = await MCPTools.create_gaea2_project(
        project_name="Film Quality Mountain",
        nodes=nodes,
        connections=connections,
        build_config=build_config
    )

    print("Created film production terrain:")
    print(f"  Resolution: 8K ({build_config['resolution']}x{build_config['resolution']})")
    print(f"  Format: 32-bit OpenEXR")
    print(f"  Includes: Height, Normals, AO, and additional passes")
    print(f"  Quality-optimized properties")

asyncio.run(create_film_terrain())
```

---

## Performance Optimization

### 13. Benchmark and Optimize

Test performance and optimize workflows.

```python
async def benchmark_and_optimize():
    import time

    # Create a complex workflow
    complex_workflow = [
        {"id": 100, "type": "Mountain"},
        {"id": 101, "type": "Erosion2"},
        {"id": 102, "type": "Rivers"},
        {"id": 103, "type": "Thermal2"},
        {"id": 104, "type": "Snow"},
        {"id": 105, "type": "Displace"},
        {"id": 106, "type": "TextureBase"},
        {"id": 107, "type": "SatMap"}
    ]

    connections = [{"from_node": i, "to_node": i+1}
                  for i in range(100, 107)]

    # Benchmark validation without cache
    start = time.time()
    result1 = await MCPTools.validate_and_fix_workflow(
        nodes=complex_workflow,
        connections=connections,
        auto_fix=False
    )
    time1 = time.time() - start

    # Benchmark with cache (second run)
    start = time.time()
    result2 = await MCPTools.validate_and_fix_workflow(
        nodes=complex_workflow,
        connections=connections,
        auto_fix=False
    )
    time2 = time.time() - start

    print(f"Performance Benchmark:")
    print(f"  First run: {time1:.4f}s")
    print(f"  Cached run: {time2:.4f}s")
    print(f"  Speedup: {time1/time2:.1f}x")

    # Optimize for performance
    print("\nOptimizing workflow for performance...")
    optimized_nodes = []

    for node in complex_workflow:
        opt_result = await MCPTools.optimize_gaea2_properties(
            node_type=node['type'],
            properties=node.get('properties', {}),
            mode="performance"
        )

        optimized_node = node.copy()
        optimized_node['properties'] = opt_result['optimized_properties']
        optimized_nodes.append(optimized_node)

        if opt_result['changes']:
            print(f"\n{node['type']} optimizations:")
            for change in opt_result['changes']:
                print(f"  - {change['property']}: {change['original']} → {change['optimized']}")
                print(f"    Reason: {change['reason']}")

    # Create optimized project
    result = await MCPTools.create_gaea2_project(
        project_name="Optimized Complex Terrain",
        nodes=optimized_nodes,
        connections=connections
    )

    print(f"\nCreated optimized project with {len(optimized_nodes)} nodes")

asyncio.run(benchmark_and_optimize())
```

### 14. Cache Management

Manage caching for optimal performance.

```python
async def manage_cache():
    from tools.mcp.gaea2_cache import get_cache

    # Get cache instance
    cache = get_cache()

    # Perform multiple operations to populate cache
    test_nodes = [
        {"type": "Mountain", "properties": {"Scale": 1.0}},
        {"type": "Erosion2", "properties": {"Duration": 0.07}},
        {"type": "Rivers", "properties": {"Headwaters": 100}}
    ]

    print("Populating cache...")
    for node in test_nodes:
        # First call - cache miss
        start = time.time()
        result = await MCPTools.optimize_gaea2_properties(
            node_type=node['type'],
            properties=node['properties'],
            mode="balanced"
        )
        miss_time = time.time() - start

        # Second call - cache hit
        start = time.time()
        result = await MCPTools.optimize_gaea2_properties(
            node_type=node['type'],
            properties=node['properties'],
            mode="balanced"
        )
        hit_time = time.time() - start

        print(f"\n{node['type']}:")
        print(f"  Cache miss: {miss_time:.4f}s")
        print(f"  Cache hit: {hit_time:.4f}s")
        print(f"  Speedup: {miss_time/hit_time:.1f}x")

    # Clear specific operations
    print("\nClearing optimization cache...")
    cache.clear("optimize_properties")

    # Test after clear
    start = time.time()
    result = await MCPTools.optimize_gaea2_properties(
        node_type="Mountain",
        properties={"Scale": 1.0},
        mode="balanced"
    )
    clear_time = time.time() - start
    print(f"After cache clear: {clear_time:.4f}s")

asyncio.run(manage_cache())
```

---

## Error Handling

### 15. Comprehensive Error Handling

Handle various error scenarios gracefully.

```python
async def handle_errors():
    # Test various error scenarios
    error_scenarios = [
        {
            "name": "Invalid node type",
            "nodes": [{"id": 100, "type": "InvalidNode"}],
            "connections": []
        },
        {
            "name": "Missing node ID",
            "nodes": [{"type": "Mountain"}],
            "connections": []
        },
        {
            "name": "Invalid connection",
            "nodes": [{"id": 100, "type": "Mountain"}],
            "connections": [{"from_node": 100, "to_node": 999}]
        },
        {
            "name": "Circular connection",
            "nodes": [
                {"id": 100, "type": "Mountain"},
                {"id": 101, "type": "Erosion2"}
            ],
            "connections": [
                {"from_node": 100, "to_node": 101},
                {"from_node": 101, "to_node": 100}
            ]
        },
        {
            "name": "Invalid property type",
            "nodes": [{
                "id": 100,
                "type": "Mountain",
                "properties": {"Scale": "not_a_number"}
            }],
            "connections": []
        }
    ]

    for scenario in error_scenarios:
        print(f"\nTesting: {scenario['name']}")

        try:
            result = await MCPTools.validate_and_fix_workflow(
                nodes=scenario['nodes'],
                connections=scenario['connections'],
                auto_fix=True,
                aggressive=True
            )

            if result['success']:
                print(f"  ✓ Handled successfully")
                print(f"  Original quality: {result['quality_scores']['original']}")
                print(f"  Fixed quality: {result['quality_scores']['fixed']}")

                if result['fixes']['applied']:
                    print(f"  Fixes applied:")
                    for fix in result['fixes']['applied'][:3]:
                        print(f"    - {fix}")
            else:
                print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"  ✗ Exception: {str(e)}")

    # Test project repair
    print("\nTesting project repair...")

    # Create corrupted project data
    corrupted_project = {
        "$id": "1",
        "Assets": {
            "$values": [{
                "Terrain": {
                    "Nodes": {
                        "100": {
                            "$type": "Invalid.Type",
                            "Id": "not_a_number"
                        }
                    }
                }
            }]
        }
    }

    try:
        result = await MCPTools.repair_gaea2_project(
            project_data=corrupted_project,
            auto_fix=True
        )

        print(f"Repair result:")
        print(f"  Health score: {result['analysis']['health_score']}/100")
        print(f"  Errors found: {result['analysis']['errors']['total_errors']}")
        print(f"  Auto-fixable: {result['analysis']['errors']['auto_fixable']}")

    except Exception as e:
        print(f"Repair failed: {str(e)}")

asyncio.run(handle_errors())
```

### 16. Custom Error Recovery

Implement custom error recovery strategies.

```python
async def custom_error_recovery():
    from tools.mcp.gaea2_error_handler import ErrorSeverity

    # Create a workflow with multiple issues
    problematic_workflow = {
        "nodes": [
            {
                "id": 100,
                "type": "Mountain",
                "properties": {"Scale": -5}  # Negative scale
            },
            {
                "id": 101,
                "type": "Rivers",
                "properties": {"Headwaters": 1000}  # Too many
            },
            {
                "id": 102,
                "type": "Erosion2"
                # Missing properties
            },
            {
                "id": 103,
                "type": "UnknownNode"  # Invalid type
            }
        ],
        "connections": [
            {"from_node": 100, "to_node": 101},  # Wrong order
            {"from_node": 102, "to_node": 103},  # Invalid target
            {"from_node": 101, "to_node": 101}   # Self-connection
        ]
    }

    # First, analyze without fixing
    analysis = await MCPTools.validate_and_fix_workflow(
        nodes=problematic_workflow['nodes'],
        connections=problematic_workflow['connections'],
        auto_fix=False
    )

    print("Issues found:")
    print(f"  Property issues: {len(analysis['validation']['property_issues'])}")
    print(f"  Connection errors: {len(analysis['validation']['connection_errors'])}")
    print(f"  Structure issues: {len(analysis['validation']['structure_issues'])}")

    # Apply conservative fixes
    print("\nApplying conservative fixes...")
    conservative = await MCPTools.validate_and_fix_workflow(
        nodes=problematic_workflow['nodes'],
        connections=problematic_workflow['connections'],
        auto_fix=True,
        aggressive=False
    )

    print(f"Conservative fixes: {len(conservative['fixes']['applied'])}")
    for fix in conservative['fixes']['applied']:
        print(f"  - {fix}")

    # Apply aggressive fixes
    print("\nApplying aggressive fixes...")
    aggressive = await MCPTools.validate_and_fix_workflow(
        nodes=problematic_workflow['nodes'],
        connections=problematic_workflow['connections'],
        auto_fix=True,
        aggressive=True
    )

    print(f"Aggressive fixes: {len(aggressive['fixes']['applied'])}")
    for fix in aggressive['fixes']['applied']:
        print(f"  - {fix}")

    # Compare results
    print(f"\nQuality comparison:")
    print(f"  Original: {analysis['quality_scores']['original']}/100")
    print(f"  Conservative: {conservative['quality_scores']['fixed']}/100")
    print(f"  Aggressive: {aggressive['quality_scores']['fixed']}/100")

    # Create final project with best result
    best_result = aggressive if aggressive['quality_scores']['fixed'] > conservative['quality_scores']['fixed'] else conservative

    result = await MCPTools.create_gaea2_project(
        project_name="Recovered Workflow",
        nodes=best_result['fixed_workflow']['nodes'],
        connections=best_result['fixed_workflow']['connections']
    )

    print(f"\nCreated recovered project with quality score: {best_result['quality_scores']['fixed']}/100")

asyncio.run(custom_error_recovery())
```

---

## Summary

These examples demonstrate the full capabilities of the Gaea2 MCP system:

1. **Basic Operations** - Creating simple terrains and using templates
2. **Validation & Repair** - Detecting and fixing project issues
3. **Pattern Intelligence** - Building workflows based on learned patterns
4. **Advanced Features** - Groups, automation, custom configurations
5. **Real-World Use Cases** - Game and film production workflows
6. **Performance** - Optimization and caching strategies
7. **Error Handling** - Comprehensive error detection and recovery

Each example is self-contained and can be run independently. For production use, combine these techniques to create robust, intelligent terrain generation workflows.

For API details, see [GAEA2_API_REFERENCE.md](GAEA2_API_REFERENCE.md).
For the complete guide, see [README.md](README.md).
