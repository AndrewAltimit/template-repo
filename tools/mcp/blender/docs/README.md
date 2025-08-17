# Blender MCP Server Documentation

## Overview

The Blender MCP Server provides comprehensive 3D content creation, rendering, and simulation capabilities through the Model Context Protocol. It enables programmatic control of Blender for creating scenes, rendering images/animations, physics simulations, and procedural generation.

## Architecture

### Hybrid Approach: FastAPI + Headless Blender

The server uses a **hybrid architecture**:
- **FastAPI server** handles HTTP requests and job management
- **Headless Blender instances** execute actual 3D operations as subprocesses
- **Asynchronous job system** for long-running operations like rendering

This design ensures:
- **Stability**: Server remains operational even if Blender crashes
- **Scalability**: Multiple Blender instances can run in parallel
- **Performance**: GPU acceleration for rendering
- **Portability**: Fully containerized with Docker

## Features

### 🎨 Scene Generation
- Create projects from templates (basic, studio lighting, animation-ready)
- Add primitive objects (cubes, spheres, cylinders, etc.)
- Configure professional lighting setups
- Apply PBR materials and textures

### 🎬 Rendering
- Single frame rendering (Cycles/Eevee/Workbench)
- Animation sequence rendering
- GPU-accelerated rendering with NVIDIA CUDA
- Multiple output formats (PNG, JPEG, EXR, MP4)
- Blender 4.5.1 with latest features

### ⚛️ Physics Simulation
- Rigid body dynamics
- Soft body simulation
- Cloth simulation
- Fluid dynamics
- Particle systems

### 🎭 Animation
- Keyframe animation
- Armature rigging
- Animation constraints
- Motion paths
- Shape keys for deformation
- NLA (Non-Linear Animation) editing

### 🔷 Geometry Nodes
- Procedural geometry generation
- Scatter/distribution systems
- Array and grid layouts
- Curve-based geometry
- Volume/voxel operations

### 📦 Asset Management
- Project organization
- Model import/export (FBX, OBJ, GLTF, STL, USD)
- Texture management
- Template library

## Installation

### Docker Setup (Recommended)

1. **Build the container:**
```bash
docker-compose build mcp-blender
```

2. **Start the server:**
```bash
docker-compose up -d mcp-blender
```

3. **Verify installation:**
```bash
curl http://localhost:8017/health
```

### Local Setup

1. **Install Blender:**
```bash
# Download Blender 4.0 LTS
wget https://download.blender.org/release/Blender4.0/blender-4.0.2-linux-x64.tar.xz
tar -xf blender-4.0.2-linux-x64.tar.xz
sudo mv blender-4.0.2-linux-x64 /opt/blender
sudo ln -s /opt/blender/blender /usr/local/bin/blender
```

2. **Install Python dependencies:**
```bash
pip install -r tools/mcp/blender/requirements.txt
```

3. **Run the server:**
```bash
python -m tools.mcp.blender.server
```

## GPU Support

### NVIDIA GPU Setup

1. **Install NVIDIA Container Toolkit:**
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

2. **Run with GPU support:**
```bash
docker-compose --profile gpu up mcp-blender
```

## API Reference

### Project Management

#### Create Blender Project
```python
POST /tools/create_blender_project
{
    "name": "my_scene",
    "template": "studio_lighting",
    "settings": {
        "resolution": [1920, 1080],
        "fps": 24,
        "engine": "CYCLES"
    }
}
```

Templates available:
- `empty` - Blank project
- `basic_scene` - Scene with ground, light, camera
- `studio_lighting` - Three-point lighting setup
- `procedural` - Ready for geometry nodes
- `animation` - Configured for animation
- `physics` - Physics simulation ready
- `architectural` - Architectural visualization
- `product` - Product rendering
- `vfx` - VFX compositing
- `game_asset` - Game asset creation
- `sculpting` - Digital sculpting

### Scene Building

#### Add Primitive Objects
```python
POST /tools/add_primitive_objects
{
    "project": "/app/projects/my_scene.blend",
    "objects": [
        {
            "type": "cube",
            "name": "MyCube",
            "location": [0, 0, 1],
            "rotation": [0, 0, 0.785],
            "scale": [2, 2, 2]
        },
        {
            "type": "sphere",
            "name": "MySphere",
            "location": [3, 0, 1]
        }
    ]
}
```

#### Setup Lighting
```python
POST /tools/setup_lighting
{
    "project": "/app/projects/my_scene.blend",
    "type": "three_point",
    "settings": {
        "strength": 1.5,
        "color": [1, 0.95, 0.8]
    }
}
```

Lighting types:
- `three_point` - Key, fill, and back lights
- `studio` - Multiple soft box lights
- `hdri` - HDRI environment lighting
- `sun` - Directional sun light
- `area` - Single area light

#### Apply Materials
```python
POST /tools/apply_material
{
    "project": "/app/projects/my_scene.blend",
    "object_name": "MyCube",
    "material": {
        "type": "metal",
        "base_color": [0.7, 0.7, 0.7, 1.0],
        "roughness": 0.2
    }
}
```

Material types:
- `principled` - PBR material
- `emission` - Emissive material
- `glass` - Transparent glass
- `metal` - Metallic surface
- `plastic` - Plastic material
- `wood` - Procedural wood texture

### Rendering

#### Render Single Frame
```python
POST /tools/render_image
{
    "project": "/app/projects/my_scene.blend",
    "frame": 1,
    "settings": {
        "resolution": [1920, 1080],
        "samples": 128,
        "engine": "CYCLES",
        "format": "PNG"
    }
}
```

Returns job ID for async processing:
```json
{
    "success": true,
    "job_id": "uuid-1234",
    "status": "QUEUED",
    "check_status": "/jobs/uuid-1234/status"
}
```

#### Render Animation
```python
POST /tools/render_animation
{
    "project": "/app/projects/my_scene.blend",
    "start_frame": 1,
    "end_frame": 250,
    "settings": {
        "resolution": [1920, 1080],
        "samples": 64,
        "engine": "EEVEE",
        "format": "MP4"
    }
}
```

### Physics Simulation

#### Setup Physics
```python
POST /tools/setup_physics
{
    "project": "/app/projects/my_scene.blend",
    "object_name": "MyCube",
    "physics_type": "rigid_body",
    "settings": {
        "mass": 2.0,
        "friction": 0.5,
        "bounce": 0.3,
        "collision_shape": "convex_hull"
    }
}
```

Physics types:
- `rigid_body` - Solid object physics
- `soft_body` - Deformable objects
- `cloth` - Fabric simulation
- `fluid` - Liquid simulation

#### Bake Simulation
```python
POST /tools/bake_simulation
{
    "project": "/app/projects/my_scene.blend",
    "start_frame": 1,
    "end_frame": 250
}
```

### Animation

#### Create Keyframe Animation
```python
POST /tools/create_animation
{
    "project": "/app/projects/my_scene.blend",
    "object_name": "MyCube",
    "keyframes": [
        {
            "frame": 1,
            "location": [0, 0, 0],
            "rotation": [0, 0, 0]
        },
        {
            "frame": 50,
            "location": [5, 0, 0],
            "rotation": [0, 0, 3.14]
        },
        {
            "frame": 100,
            "location": [0, 0, 0],
            "rotation": [0, 0, 6.28]
        }
    ],
    "interpolation": "BEZIER"
}
```

### Geometry Nodes

#### Create Procedural Geometry
```python
POST /tools/create_geometry_nodes
{
    "project": "/app/projects/my_scene.blend",
    "object_name": "Ground",
    "node_setup": "scatter",
    "parameters": {
        "count": 1000,
        "seed": 42,
        "scale_variance": 0.2
    }
}
```

Node setups:
- `scatter` - Distribute objects on surface
- `array` - Linear/grid arrays
- `curve` - Curve-based geometry
- `volume` - Volumetric operations
- `custom` - Custom node setup

### Job Management

#### Check Job Status
```python
GET /tools/get_job_status
{
    "job_id": "uuid-1234"
}
```

Response:
```json
{
    "job_id": "uuid-1234",
    "status": "RUNNING",
    "progress": 45,
    "message": "Rendering frame 45/100",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:01:00"
}
```

Status values:
- `QUEUED` - Job waiting to start
- `RUNNING` - Job in progress
- `COMPLETED` - Job finished successfully
- `FAILED` - Job encountered error
- `CANCELLED` - Job was cancelled

#### Get Job Result
```python
GET /tools/get_job_result
{
    "job_id": "uuid-1234"
}
```

#### Cancel Job
```python
POST /tools/cancel_job
{
    "job_id": "uuid-1234"
}
```

### Asset Management

#### List Projects
```python
GET /tools/list_projects
```

#### Import Model
```python
POST /tools/import_model
{
    "project": "/app/projects/my_scene.blend",
    "model_path": "/app/assets/models/character.fbx",
    "format": "FBX",
    "location": [0, 0, 0]
}
```

Supported formats:
- FBX, OBJ, GLTF/GLB, STL, PLY, COLLADA, USD

#### Export Scene
```python
POST /tools/export_scene
{
    "project": "/app/projects/my_scene.blend",
    "format": "GLTF",
    "selected_only": false
}
```

## Examples

### Example 1: Create and Render a Simple Scene

```python
# 1. Create project
create_response = client.call_tool("create_blender_project", {
    "name": "simple_scene",
    "template": "basic_scene"
})

project_path = create_response["project_path"]

# 2. Add objects
client.call_tool("add_primitive_objects", {
    "project": project_path,
    "objects": [
        {"type": "monkey", "name": "Suzanne", "location": [0, 0, 2]}
    ]
})

# 3. Setup lighting
client.call_tool("setup_lighting", {
    "project": project_path,
    "type": "three_point"
})

# 4. Apply material
client.call_tool("apply_material", {
    "project": project_path,
    "object_name": "Suzanne",
    "material": {"type": "metal", "roughness": 0.3}
})

# 5. Render
render_response = client.call_tool("render_image", {
    "project": project_path,
    "settings": {"samples": 256}
})

# 6. Check status
job_id = render_response["job_id"]
status = client.call_tool("get_job_status", {"job_id": job_id})
print(f"Render status: {status['status']} ({status['progress']}%)")
```

### Example 2: Physics Simulation

```python
# 1. Create physics scene
project = client.call_tool("create_blender_project", {
    "name": "physics_demo",
    "template": "physics"
})["project_path"]

# 2. Add falling objects
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "cube", "name": "Box1", "location": [0, 0, 5]},
        {"type": "sphere", "name": "Ball1", "location": [1, 0, 7]},
        {"type": "cube", "name": "Box2", "location": [-1, 0, 9]}
    ]
})

# 3. Setup physics for each object
for obj in ["Box1", "Ball1", "Box2"]:
    client.call_tool("setup_physics", {
        "project": project,
        "object_name": obj,
        "physics_type": "rigid_body",
        "settings": {"mass": 1.0, "bounce": 0.5}
    })

# 4. Bake simulation
client.call_tool("bake_simulation", {
    "project": project,
    "end_frame": 250
})

# 5. Render animation
render_job = client.call_tool("render_animation", {
    "project": project,
    "end_frame": 250,
    "settings": {"format": "MP4"}
})
```

### Example 3: Procedural Generation with Geometry Nodes

```python
# 1. Create project
project = client.call_tool("create_blender_project", {
    "name": "procedural_forest",
    "template": "procedural"
})["project_path"]

# 2. Create ground plane
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [
        {"type": "plane", "name": "Terrain", "scale": [50, 50, 1]}
    ]
})

# 3. Add procedural trees with geometry nodes
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

# 4. Setup HDRI lighting
client.call_tool("setup_lighting", {
    "project": project,
    "type": "hdri",
    "settings": {
        "hdri_path": "/app/assets/hdri/forest_clearing_4k.hdr",
        "strength": 1.0
    }
})

# 5. Render
client.call_tool("render_image", {
    "project": project,
    "settings": {
        "resolution": [3840, 2160],
        "samples": 512,
        "engine": "CYCLES"
    }
})
```

## Performance Optimization

### Rendering Performance

1. **Use Eevee for previews**: Faster real-time rendering
2. **Optimize samples**: Balance quality vs speed
3. **Enable GPU rendering**: Massive speedup with NVIDIA GPUs
4. **Use render regions**: Render only parts of the frame
5. **Enable denoising**: Reduce samples needed

### Memory Management

1. **Limit texture sizes**: Use appropriate resolutions
2. **Instance objects**: Use instancing for repeated geometry
3. **Optimize modifiers**: Apply modifiers when possible
4. **Clear unused data**: Remove orphaned data blocks

### Container Resources

```yaml
# docker-compose.yml resource limits
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## Troubleshooting

### Common Issues

#### 1. Blender not found
```bash
# Check Blender installation
docker exec mcp-blender blender --version

# Reinstall if needed
docker-compose build --no-cache mcp-blender
```

#### 2. GPU not detected
```bash
# Check NVIDIA driver
nvidia-smi

# Check container GPU access
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

#### 3. Rendering fails
- Check project file exists
- Verify sufficient memory
- Check render settings
- Review Blender logs

#### 4. Jobs stuck in QUEUED
- Check server logs: `docker logs mcp-blender`
- Verify Blender subprocess running
- Check system resources

### Debug Mode

Enable debug logging:
```python
# In server.py
logging.basicConfig(level=logging.DEBUG)
```

View container logs:
```bash
docker-compose logs -f mcp-blender
```

## Best Practices

### Project Organization
1. Use descriptive project names
2. Organize assets by type
3. Create templates for common setups
4. Regular backups of projects

### Rendering Workflow
1. Test with low samples first
2. Use viewport rendering for previews
3. Batch render overnight
4. Monitor job progress

### Performance Tips
1. Optimize geometry before rendering
2. Use appropriate texture resolutions
3. Enable GPU rendering when available
4. Use render farms for large projects

## Integration with Other MCP Servers

### ComfyUI Integration
Generate textures with ComfyUI and apply in Blender:
```python
# Generate texture with ComfyUI
texture = comfyui_client.generate_texture(...)

# Apply in Blender
blender_client.apply_material({
    "texture_path": texture["path"],
    ...
})
```

### Gaea2 Integration
Import terrain from Gaea2:
```python
# Generate terrain in Gaea2
terrain = gaea2_client.create_terrain(...)

# Import into Blender
blender_client.import_model({
    "model_path": terrain["mesh_path"],
    "format": "OBJ"
})
```

## Security Considerations

1. **File path validation**: All paths are sanitized
2. **Resource limits**: CPU/memory limits enforced
3. **User permissions**: Runs as non-root user
4. **Network isolation**: Isolated Docker network
5. **Input validation**: All parameters validated

## Support

For issues or questions:
1. Check the [troubleshooting section](#troubleshooting)
2. Review server logs
3. Open an issue on GitHub
4. Contact the maintainer

## License

This MCP server is part of the template-repo project and follows the same license terms.
