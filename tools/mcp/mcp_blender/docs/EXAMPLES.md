# Blender MCP Server - Examples and Tutorials

This document provides comprehensive examples and tutorials for using the Blender MCP Server to create 3D content, animations, and renders programmatically.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Scene Creation](#basic-scene-creation)
3. [Advanced Lighting](#advanced-lighting)
4. [Materials and Textures](#materials-and-textures)
5. [Animation Workflows](#animation-workflows)
6. [Physics Simulations](#physics-simulations)
7. [Procedural Generation](#procedural-generation)
8. [Camera Techniques](#camera-techniques)
9. [Modifiers](#modifiers)
10. [Particle Systems](#particle-systems)
11. [Rendering Strategies](#rendering-strategies)
12. [Complete Projects](#complete-projects)

---

## Getting Started

### Basic Setup

First, ensure the Blender MCP server is running:

```bash
# Using Docker (recommended)
docker-compose up -d mcp-blender

# Or locally
python -m tools.mcp.blender.server
```

### Python Client Example

```python
import requests
import json

class BlenderMCPClient:
    def __init__(self, base_url="http://localhost:8017"):
        self.base_url = base_url

    def call_tool(self, tool_name, arguments):
        """Call a Blender MCP tool."""
        payload = {
            "tool": tool_name,
            "arguments": arguments
        }
        response = requests.post(f"{self.base_url}/mcp/execute", json=payload)
        return response.json()

# Initialize client
client = BlenderMCPClient()
```

---

## Basic Scene Creation

### Example 1: Simple Scene with Primitives

```python
# Create a new project
result = client.call_tool("create_blender_project", {
    "name": "simple_scene",
    "template": "basic_scene",
    "settings": {
        "resolution": [1920, 1080],
        "fps": 24,
        "engine": "CYCLES"
    }
})

project = result["result"]["project_path"]

# Add some objects
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {
            "type": "monkey",
            "name": "Suzanne",
            "location": [0, 0, 2],
            "rotation": [0, 0, 0],
            "scale": [1, 1, 1]
        },
        {
            "type": "cube",
            "name": "Platform",
            "location": [0, 0, 0],
            "scale": [5, 5, 0.2]
        },
        {
            "type": "sphere",
            "name": "Ball",
            "location": [2, 0, 2],
            "scale": [0.5, 0.5, 0.5]
        }
    ]
})

# Setup lighting
client.call_tool("setup_lighting", {
    "project": project,
    "type": "three_point",
    "settings": {
        "strength": 2.0,
        "color": [1, 0.95, 0.8]
    }
})

# Apply materials
client.call_tool("apply_material", {
    "project": project,
    "object_name": "Suzanne",
    "material": {
        "type": "metal",
        "base_color": [0.8, 0.6, 0.2, 1],
        "roughness": 0.3,
        "metallic": 0.9
    }
})

# Render the scene
render_job = client.call_tool("render_image", {
    "project": project,
    "frame": 1,
    "settings": {
        "resolution": [1920, 1080],
        "samples": 128,
        "engine": "CYCLES",
        "format": "PNG"
    }
})
```

### Example 2: Building a Room Interior

```python
# Create interior scene
result = client.call_tool("create_blender_project", {
    "name": "room_interior",
    "template": "basic_scene"
})

project = result["result"]["project_path"]

# Create room structure
room_parts = []

# Floor
room_parts.append({
    "type": "cube",
    "name": "Floor",
    "location": [0, 0, -0.1],
    "scale": [5, 5, 0.1]
})

# Walls
wall_positions = [
    ([0, -5, 2.5], [5, 0.1, 2.5], "WallBack"),
    ([0, 5, 2.5], [5, 0.1, 2.5], "WallFront"),
    ([-5, 0, 2.5], [0.1, 5, 2.5], "WallLeft"),
    ([5, 0, 2.5], [0.1, 5, 2.5], "WallRight")
]

for pos, scale, name in wall_positions:
    room_parts.append({
        "type": "cube",
        "name": name,
        "location": pos,
        "scale": scale
    })

# Ceiling
room_parts.append({
    "type": "cube",
    "name": "Ceiling",
    "location": [0, 0, 5.1],
    "scale": [5, 5, 0.1]
})

# Add all room parts
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": room_parts
})

# Add furniture
furniture = [
    {"type": "cube", "name": "Table", "location": [0, 0, 0.75], "scale": [1.5, 0.8, 0.05]},
    {"type": "cylinder", "name": "TableLeg1", "location": [-0.6, -0.3, 0.35], "scale": [0.05, 0.05, 0.35]},
    {"type": "cylinder", "name": "TableLeg2", "location": [0.6, -0.3, 0.35], "scale": [0.05, 0.05, 0.35]},
    {"type": "cylinder", "name": "TableLeg3", "location": [-0.6, 0.3, 0.35], "scale": [0.05, 0.05, 0.35]},
    {"type": "cylinder", "name": "TableLeg4", "location": [0.6, 0.3, 0.35], "scale": [0.05, 0.05, 0.35]},
    {"type": "cube", "name": "Chair", "location": [0, -1.5, 0.4], "scale": [0.4, 0.4, 0.05]},
    {"type": "cube", "name": "ChairBack", "location": [0, -1.7, 0.7], "scale": [0.4, 0.05, 0.4]}
]

client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": furniture
})
```

---

## Advanced Lighting

### Example 3: HDRI Environment Lighting

```python
# Create scene with HDRI lighting
result = client.call_tool("create_blender_project", {
    "name": "hdri_scene",
    "template": "basic_scene"
})

project = result["result"]["project_path"]

# Setup HDRI lighting (requires HDRI file)
client.call_tool("setup_lighting", {
    "project": project,
    "type": "hdri",
    "settings": {
        "hdri_path": "/app/assets/hdri/studio_small_09_4k.hdr",
        "strength": 1.0,
        "rotation": 0.785  # 45 degrees
    }
})
```

### Example 4: Studio Lighting Setup

```python
# Professional studio lighting
client.call_tool("setup_lighting", {
    "project": project,
    "type": "studio",
    "settings": {
        "strength": 3.0,
        "color": [1, 1, 1]
    }
})

# Add rim lighting for dramatic effect
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "plane", "name": "RimLight", "location": [5, 5, 3], "rotation": [-0.785, 0, -0.785]}
    ]
})

client.call_tool("apply_material", {
    "project": project,
    "object_name": "RimLight",
    "material": {
        "type": "emission",
        "base_color": [1, 0.9, 0.8, 1],
        "emission_strength": 5.0
    }
})
```

---

## Materials and Textures

### Example 5: PBR Materials

```python
# Create various PBR materials
materials = [
    {
        "object": "GoldSphere",
        "material": {
            "type": "metal",
            "base_color": [1.0, 0.766, 0.336, 1.0],
            "metallic": 1.0,
            "roughness": 0.2
        }
    },
    {
        "object": "RubberCube",
        "material": {
            "type": "principled",
            "base_color": [0.1, 0.1, 0.1, 1.0],
            "metallic": 0.0,
            "roughness": 0.9
        }
    },
    {
        "object": "GlassSphere",
        "material": {
            "type": "glass",
            "base_color": [0.8, 0.9, 1.0, 0.1],
            "roughness": 0.0
        }
    },
    {
        "object": "EmissivePlane",
        "material": {
            "type": "emission",
            "base_color": [0.5, 0.8, 1.0, 1.0],
            "emission_strength": 3.0
        }
    }
]

for mat_config in materials:
    client.call_tool("apply_material", {
        "project": project,
        "object_name": mat_config["object"],
        "material": mat_config["material"]
    })
```

---

## Animation Workflows

### Example 6: Simple Object Animation

```python
# Create bouncing ball animation
result = client.call_tool("create_blender_project", {
    "name": "bouncing_ball",
    "template": "animation",
    "settings": {"fps": 30}
})

project = result["result"]["project_path"]

# Add ball
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "sphere", "name": "Ball", "location": [0, 0, 5]}
    ]
})

# Create bounce animation
keyframes = []
for bounce in range(3):
    base_frame = bounce * 30
    # Peak
    keyframes.append({
        "frame": base_frame + 1,
        "location": [bounce * 2, 0, 5],
        "scale": [1, 1, 1]
    })
    # Squash at impact
    keyframes.append({
        "frame": base_frame + 15,
        "location": [bounce * 2 + 1, 0, 0.5],
        "scale": [1.2, 1.2, 0.8]
    })
    # Stretch on way up
    keyframes.append({
        "frame": base_frame + 20,
        "location": [bounce * 2 + 1.3, 0, 2],
        "scale": [0.9, 0.9, 1.1]
    })

client.call_tool("create_animation", {
    "project": project,
    "object_name": "Ball",
    "keyframes": keyframes,
    "interpolation": "BEZIER"
})

# Render animation
render_job = client.call_tool("render_animation", {
    "project": project,
    "start_frame": 1,
    "end_frame": 90,
    "settings": {
        "resolution": [1920, 1080],
        "samples": 64,
        "engine": "BLENDER_EEVEE",
        "format": "MP4"
    }
})
```

### Example 7: Camera Animation

```python
# Create camera fly-through
camera_path = [
    {"location": [10, -10, 5], "rotation": [1.1, 0, 0.785]},
    {"location": [5, -5, 3], "rotation": [1.2, 0, 0.5]},
    {"location": [0, 0, 8], "rotation": [1.0, 0, 0]},
    {"location": [-5, 5, 3], "rotation": [1.2, 0, -0.5]},
    {"location": [-10, 10, 5], "rotation": [1.1, 0, -0.785]}
]

# Create camera animation using keyframes
camera_keyframes = []
for i, point in enumerate(camera_path):
    camera_keyframes.append({
        "frame": i * 30 + 1,
        "location": point["location"],
        "rotation": point["rotation"]
    })

client.call_tool("create_animation", {
    "project": project,
    "object_name": "Camera",
    "keyframes": camera_keyframes,
    "interpolation": "BEZIER"
})
```

---

## Physics Simulations

### Example 8: Domino Effect

```python
# Create domino physics simulation
result = client.call_tool("create_blender_project", {
    "name": "domino_effect",
    "template": "basic_scene"
})

project = result["result"]["project_path"]

# Create ground
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "cube", "name": "Ground", "location": [0, 0, -0.5], "scale": [20, 20, 0.5]}
    ]
})

# Setup ground as passive rigid body
client.call_tool("setup_physics", {
    "project": project,
    "object_name": "Ground",
    "physics_type": "rigid_body",
    "settings": {
        "mass": 0,  # 0 mass = passive/static
        "friction": 0.5
    }
})

# Create dominoes
dominoes = []
for i in range(20):
    dominoes.append({
        "type": "cube",
        "name": f"Domino_{i}",
        "location": [i * 0.5 - 5, 0, 1],
        "scale": [0.1, 0.5, 1]
    })

client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": dominoes
})

# Setup physics for each domino
for i in range(20):
    client.call_tool("setup_physics", {
        "project": project,
        "object_name": f"Domino_{i}",
        "physics_type": "rigid_body",
        "settings": {
            "mass": 0.5,
            "friction": 0.5,
            "bounce": 0.1
        }
    })

# Add pusher ball
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "sphere", "name": "Pusher", "location": [-6, 0, 1], "scale": [0.5, 0.5, 0.5]}
    ]
})

# Animate pusher to knock first domino
client.call_tool("create_animation", {
    "project": project,
    "object_name": "Pusher",
    "keyframes": [
        {"frame": 1, "location": [-6, 0, 1]},
        {"frame": 20, "location": [-4.5, 0, 1]}
    ],
    "interpolation": "LINEAR"
})

# Setup pusher physics
client.call_tool("setup_physics", {
    "project": project,
    "object_name": "Pusher",
    "physics_type": "rigid_body",
    "settings": {
        "mass": 2.0,
        "friction": 0.5
    }
})

# Bake the simulation
client.call_tool("bake_simulation", {
    "project": project,
    "start_frame": 1,
    "end_frame": 250
})
```

### Example 9: Fluid Simulation

```python
# Create fluid simulation scene
result = client.call_tool("create_blender_project", {
    "name": "fluid_sim",
    "template": "basic_scene"
})

project = result["result"]["project_path"]

# Create container
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "cube", "name": "Container", "location": [0, 0, 2], "scale": [2, 2, 2]}
    ]
})

# Create fluid emitter
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "sphere", "name": "FluidEmitter", "location": [0, 0, 3.5], "scale": [0.5, 0.5, 0.5]}
    ]
})

# Setup fluid physics (conceptual - would need fluid-specific implementation)
client.call_tool("setup_physics", {
    "project": project,
    "object_name": "FluidEmitter",
    "physics_type": "fluid",
    "settings": {
        "fluid_type": "INFLOW",
        "flow_rate": 1.0
    }
})
```

---

## Procedural Generation

### Example 10: Procedural Forest

```python
# Create procedural forest
result = client.call_tool("create_blender_project", {
    "name": "procedural_forest",
    "template": "procedural"
})

project = result["result"]["project_path"]

# Create terrain
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "plane", "name": "Terrain", "location": [0, 0, 0], "scale": [50, 50, 1]}
    ]
})

# Add procedural scattering for trees
client.call_tool("create_geometry_nodes", {
    "project": project,
    "object_name": "Terrain",
    "node_setup": "scatter",
    "parameters": {
        "count": 500,
        "seed": 12345,
        "scale_variance": 0.3
    }
})

# Apply terrain material
client.call_tool("apply_material", {
    "project": project,
    "object_name": "Terrain",
    "material": {
        "type": "principled",
        "base_color": [0.2, 0.4, 0.1, 1],
        "roughness": 0.9
    }
})
```

### Example 11: Abstract Procedural Art

```python
# Create abstract procedural art
result = client.call_tool("create_blender_project", {
    "name": "procedural_art",
    "template": "procedural"
})

project = result["result"]["project_path"]

# Create base mesh
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "torus", "name": "BaseTorus", "location": [0, 0, 0], "scale": [2, 2, 2]}
    ]
})

# Apply array geometry nodes
client.call_tool("create_geometry_nodes", {
    "project": project,
    "object_name": "BaseTorus",
    "node_setup": "array",
    "parameters": {
        "count": 10,
        "offset": [0, 0, 0.5]
    }
})

# Apply emissive material
client.call_tool("apply_material", {
    "project": project,
    "object_name": "BaseTorus",
    "material": {
        "type": "emission",
        "base_color": [0.5, 0.8, 1.0, 1],
        "emission_strength": 2.0
    }
})

# Animate rotation
client.call_tool("create_animation", {
    "project": project,
    "object_name": "BaseTorus",
    "keyframes": [
        {"frame": 1, "rotation": [0, 0, 0]},
        {"frame": 120, "rotation": [6.28, 6.28, 6.28]}
    ],
    "interpolation": "LINEAR"
})
```

---

## Camera Techniques

### Example 12: Depth of Field

```python
# Setup camera with depth of field
client.call_tool("setup_camera", {
    "project": project,
    "camera_name": "MainCamera",
    "location": [7, -7, 5],
    "rotation": [1.1, 0, 0.785],
    "focal_length": 50,
    "depth_of_field": {
        "enabled": True,
        "focus_distance": 10,
        "f_stop": 1.4
    }
})
```

### Example 13: Camera Tracking

```python
# Make camera track an object
client.call_tool("add_camera_track", {
    "project": project,
    "camera_name": "MainCamera",
    "target_object": "Suzanne",
    "track_type": "DAMPED_TRACK"
})
```

---

## Modifiers

### Example 14: Using Modifiers

```python
# Add subdivision surface modifier
client.call_tool("add_modifier", {
    "project": project,
    "object_name": "Suzanne",
    "modifier_type": "SUBSURF",
    "settings": {
        "levels": 2,
        "render_levels": 3
    }
})

# Add array modifier
client.call_tool("add_modifier", {
    "project": project,
    "object_name": "Cube",
    "modifier_type": "ARRAY",
    "settings": {
        "count": 5,
        "relative_offset": [1.1, 0, 0]
    }
})

# Add mirror modifier
client.call_tool("add_modifier", {
    "project": project,
    "object_name": "HalfModel",
    "modifier_type": "MIRROR",
    "settings": {
        "use_axis": [True, False, False],
        "use_bisect": [True, False, False]
    }
})
```

---

## Particle Systems

### Example 15: Particle Effects

```python
# Add particle system
client.call_tool("add_particle_system", {
    "project": project,
    "object_name": "Emitter",
    "particle_type": "EMITTER",
    "settings": {
        "count": 10000,
        "frame_start": 1,
        "frame_end": 250,
        "lifetime": 100,
        "emit_from": "FACE",
        "physics_type": "NEWTONIAN",
        "velocity": 5.0,
        "gravity": 1.0,
        "size": 0.05,
        "size_random": 0.5
    }
})

# Add hair system
client.call_tool("add_hair_system", {
    "project": project,
    "object_name": "Head",
    "settings": {
        "count": 1000,
        "length": 0.3,
        "segments": 5,
        "use_dynamics": True,
        "use_children": True,
        "children_count": 10
    }
})
```

---

## Rendering Strategies

### Example 16: Batch Rendering

```python
# Render multiple views
views = [
    {"frame": 1, "camera_location": [5, -5, 3], "camera_rotation": [1.2, 0, 0.785]},
    {"frame": 1, "camera_location": [-5, -5, 3], "camera_rotation": [1.2, 0, -0.785]},
    {"frame": 1, "camera_location": [0, -8, 5], "camera_rotation": [1.0, 0, 0]},
    {"frame": 1, "camera_location": [0, 0, 10], "camera_rotation": [0, 0, 0]}
]

for i, view in enumerate(views):
    # Move camera
    client.call_tool("setup_camera", {
        "project": project,
        "camera_name": "Camera",
        "location": view["camera_location"],
        "rotation": view["camera_rotation"]
    })

    # Render
    render_job = client.call_tool("render_image", {
        "project": project,
        "frame": view["frame"],
        "settings": {
            "resolution": [1920, 1080],
            "samples": 128,
            "engine": "CYCLES",
            "format": "PNG"
        }
    })
    print(f"Rendering view {i+1}: Job ID {render_job['result']['job_id']}")
```

### Example 17: Quality vs Speed Settings

```python
# Preview quality (fast)
preview_settings = {
    "resolution": [960, 540],
    "samples": 32,
    "engine": "BLENDER_EEVEE",
    "format": "JPEG"
}

# Final quality (slow)
final_settings = {
    "resolution": [3840, 2160],
    "samples": 512,
    "engine": "CYCLES",
    "format": "EXR"
}

# Production quality with denoising
production_settings = {
    "resolution": [1920, 1080],
    "samples": 256,
    "engine": "CYCLES",
    "format": "PNG",
    "denoise": True
}
```

---

## Complete Projects

### Example 18: Product Visualization

```python
def create_product_visualization(product_name="smartphone"):
    """Complete product visualization workflow."""

    # Create project
    result = client.call_tool("create_blender_project", {
        "name": f"{product_name}_viz",
        "template": "studio_lighting",
        "settings": {
            "resolution": [2560, 1440],
            "engine": "CYCLES"
        }
    })

    project = result["result"]["project_path"]

    # Create turntable
    client.call_tool("add_primitive_objects", {
        "project": project,
        "objects": [
            {"type": "cylinder", "name": "Turntable", "location": [0, 0, -0.1], "scale": [3, 3, 0.1]}
        ]
    })

    # Import product model (placeholder with cube)
    client.call_tool("add_primitive_objects", {
        "project": project,
        "objects": [
            {"type": "cube", "name": "Product", "location": [0, 0, 0.5], "scale": [0.5, 1, 0.1]}
        ]
    })

    # Apply materials
    client.call_tool("apply_material", {
        "project": project,
        "object_name": "Turntable",
        "material": {
            "type": "principled",
            "base_color": [0.9, 0.9, 0.9, 1],
            "roughness": 0.2,
            "metallic": 0.8
        }
    })

    client.call_tool("apply_material", {
        "project": project,
        "object_name": "Product",
        "material": {
            "type": "glass",
            "base_color": [0.1, 0.1, 0.1, 1],
            "roughness": 0.1
        }
    })

    # Animate turntable rotation
    client.call_tool("create_animation", {
        "project": project,
        "object_name": "Turntable",
        "keyframes": [
            {"frame": 1, "rotation": [0, 0, 0]},
            {"frame": 120, "rotation": [0, 0, 6.28]}
        ],
        "interpolation": "LINEAR"
    })

    # Setup camera
    client.call_tool("setup_camera", {
        "project": project,
        "camera_name": "ProductCamera",
        "location": [3, -3, 2],
        "rotation": [1.2, 0, 0.785],
        "focal_length": 85,
        "depth_of_field": {
            "enabled": True,
            "focus_distance": 4.24,
            "f_stop": 4.0
        }
    })

    # Render animation
    render_job = client.call_tool("render_animation", {
        "project": project,
        "start_frame": 1,
        "end_frame": 120,
        "settings": {
            "resolution": [1920, 1080],
            "samples": 128,
            "engine": "CYCLES",
            "format": "MP4"
        }
    })

    return project, render_job

# Execute the product visualization
project, render_job = create_product_visualization("smartphone")
print(f"Project: {project}")
print(f"Render Job: {render_job['result']['job_id']}")
```

### Example 19: Architectural Walkthrough

```python
def create_architectural_walkthrough():
    """Create an architectural visualization with camera walkthrough."""

    # Create project
    result = client.call_tool("create_blender_project", {
        "name": "arch_walkthrough",
        "template": "basic_scene"
    })

    project = result["result"]["project_path"]

    # Build simple house structure
    house_parts = [
        # Foundation
        {"type": "cube", "name": "Foundation", "location": [0, 0, -0.1], "scale": [6, 8, 0.1]},
        # Walls
        {"type": "cube", "name": "WallFront", "location": [0, 4, 1.5], "scale": [6, 0.1, 1.5]},
        {"type": "cube", "name": "WallBack", "location": [0, -4, 1.5], "scale": [6, 0.1, 1.5]},
        {"type": "cube", "name": "WallLeft", "location": [-3, 0, 1.5], "scale": [0.1, 8, 1.5]},
        {"type": "cube", "name": "WallRight", "location": [3, 0, 1.5], "scale": [0.1, 8, 1.5]},
        # Roof
        {"type": "cube", "name": "Roof", "location": [0, 0, 3.1], "scale": [6.5, 8.5, 0.1]}
    ]

    client.call_tool("add_primitive_objects", {
        "project": project,
        "objects": house_parts
    })

    # Create camera path for walkthrough
    camera_path = [
        {"frame": 1, "location": [10, 10, 2], "rotation": [1.4, 0, -0.785]},
        {"frame": 30, "location": [5, 5, 2], "rotation": [1.4, 0, -0.785]},
        {"frame": 60, "location": [0, 6, 1.5], "rotation": [1.57, 0, 0]},
        {"frame": 90, "location": [0, 0, 1.5], "rotation": [1.57, 0, 0]},
        {"frame": 120, "location": [0, -6, 1.5], "rotation": [1.57, 0, 3.14]},
        {"frame": 150, "location": [-5, -5, 2], "rotation": [1.4, 0, 2.35]},
        {"frame": 180, "location": [-10, -10, 5], "rotation": [1.2, 0, 2.35]}
    ]

    client.call_tool("create_animation", {
        "project": project,
        "object_name": "Camera",
        "keyframes": camera_path,
        "interpolation": "BEZIER"
    })

    # Apply materials
    materials = [
        ("Foundation", {"type": "principled", "base_color": [0.5, 0.5, 0.5, 1], "roughness": 0.9}),
        ("WallFront", {"type": "principled", "base_color": [0.9, 0.85, 0.7, 1], "roughness": 0.7}),
        ("WallBack", {"type": "principled", "base_color": [0.9, 0.85, 0.7, 1], "roughness": 0.7}),
        ("WallLeft", {"type": "principled", "base_color": [0.9, 0.85, 0.7, 1], "roughness": 0.7}),
        ("WallRight", {"type": "principled", "base_color": [0.9, 0.85, 0.7, 1], "roughness": 0.7}),
        ("Roof", {"type": "principled", "base_color": [0.6, 0.3, 0.2, 1], "roughness": 0.8})
    ]

    for obj_name, material in materials:
        client.call_tool("apply_material", {
            "project": project,
            "object_name": obj_name,
            "material": material
        })

    # Setup sun lighting
    client.call_tool("setup_lighting", {
        "project": project,
        "type": "sun",
        "settings": {
            "strength": 3.0,
            "color": [1, 0.95, 0.8]
        }
    })

    # Render the walkthrough
    render_job = client.call_tool("render_animation", {
        "project": project,
        "start_frame": 1,
        "end_frame": 180,
        "settings": {
            "resolution": [1920, 1080],
            "samples": 128,
            "engine": "CYCLES",
            "format": "MP4"
        }
    })

    return project, render_job
```

---

## Tips and Best Practices

### Performance Optimization

1. **Use Eevee for previews**: Much faster than Cycles for test renders
2. **Optimize sample counts**: Start with low samples (32-64) for testing
3. **Use instances**: For repeated objects, use array modifiers or geometry nodes
4. **Simplify geometry**: Use subdivision surface modifiers instead of high-poly meshes
5. **Bake simulations**: Always bake physics simulations before rendering

### Workflow Tips

1. **Save incrementally**: Create new project versions for major changes
2. **Use templates**: Start with appropriate templates to save setup time
3. **Test at low resolution**: Render at 50% resolution for testing
4. **Monitor job status**: Check render job progress regularly
5. **Batch operations**: Group similar operations for efficiency

### Common Patterns

```python
# Pattern: Setup -> Create -> Modify -> Animate -> Render
def standard_workflow(project_name):
    # 1. Setup
    project = create_project(project_name)

    # 2. Create
    add_objects(project)

    # 3. Modify
    apply_materials(project)
    apply_modifiers(project)

    # 4. Animate
    create_animations(project)

    # 5. Render
    render_output(project)

    return project
```

---

## Troubleshooting

### Common Issues and Solutions

1. **Render not starting**: Check job status and server logs
2. **Objects not visible**: Verify object location and scale
3. **Materials look wrong**: Ensure correct engine (Cycles vs Eevee)
4. **Animation jumpy**: Check interpolation mode (use BEZIER)
5. **Physics not working**: Remember to bake simulation

### Debug Helpers

```python
# List all projects
result = client.call_tool("list_projects", {})
print("Available projects:", result["result"]["projects"])

# Check job status
job_status = client.call_tool("get_job_status", {
    "job_id": "your-job-id-here"
})
print("Job status:", job_status["result"])

# Analyze scene
analysis = client.call_tool("analyze_scene", {
    "project": project,
    "include_details": ["OBJECTS", "MATERIALS", "ANIMATIONS"]
})
print("Scene analysis:", analysis["result"])
```

---

## Advanced Topics

### Custom Geometry Nodes

```python
# Create custom procedural setup
client.call_tool("create_geometry_nodes", {
    "project": project,
    "object_name": "CustomGeo",
    "node_setup": "custom",
    "parameters": {
        "custom_script": "path/to/custom_nodes.py"
    }
})
```

### Compositor Post-Processing

```python
# Add post-processing effects
client.call_tool("setup_compositor", {
    "project": project,
    "effects": ["GLARE", "COLOR_CORRECTION", "VIGNETTE"],
    "settings": {
        "glare_type": "FOG_GLOW",
        "glare_threshold": 1.0,
        "vignette_amount": 0.3,
        "color_balance": [1.1, 1.0, 0.9]
    }
})
```

### Multi-Layer Rendering

```python
# Setup render layers for compositing
client.call_tool("setup_render_layers", {
    "project": project,
    "layers": [
        {"name": "Foreground", "objects": ["Product"]},
        {"name": "Background", "objects": ["Environment"]},
        {"name": "Effects", "objects": ["Particles"]}
    ]
})
```

---

## Conclusion

The Blender MCP Server provides a powerful API for programmatic 3D content creation. These examples demonstrate various workflows from simple scene creation to complex animations and simulations. Combine these techniques to create sophisticated 3D content entirely through code.

For more information, refer to the main documentation and API reference.
