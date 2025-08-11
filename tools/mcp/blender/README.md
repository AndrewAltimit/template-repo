# 🎬 Blender MCP Server

A comprehensive Model Context Protocol (MCP) server for **Blender 3D** operations, enabling programmatic control of 3D content creation, rendering, physics simulations, and procedural generation.

## 🚀 Quick Start

```bash
# Start the server
./tools/mcp/blender/quickstart.sh start

# Run a demo
./tools/mcp/blender/quickstart.sh demo

# Check status
./tools/mcp/blender/quickstart.sh status
```

## ✨ Features

### Core Capabilities
- **🎨 Scene Generation** - Create 3D scenes from templates
- **🎬 Rendering** - GPU-accelerated image and animation rendering
- **⚛️ Physics** - Rigid body, soft body, cloth, and fluid simulations
- **🎭 Animation** - Keyframe animation, rigging, and constraints
- **🔷 Geometry Nodes** - Procedural content generation
- **📦 Asset Management** - Import/export models and textures

### Render Engines
- **Cycles** - Photorealistic path-traced rendering
- **Eevee** - Real-time viewport rendering
- **Workbench** - Fast solid/wireframe rendering

### Supported Formats
- **Models**: FBX, OBJ, GLTF/GLB, STL, PLY, USD, Collada
- **Images**: PNG, JPEG, EXR, TIFF, HDR
- **Video**: MP4, AVI, MOV

## 🏗️ Architecture

```
┌─────────────┐     HTTP/JSON    ┌──────────────┐
│   Claude    │ ◄──────────────► │  FastAPI     │
│    Code     │                   │   Server     │
└─────────────┘                   └──────┬───────┘
                                         │
                                    Subprocess
                                         │
                                   ┌─────▼───────┐
                                   │  Headless   │
                                   │   Blender   │
                                   │  Instance   │
                                   └─────────────┘
```

- **FastAPI Server**: Handles HTTP requests and job management (Port 8017)
- **Headless Blender**: Executes 3D operations as subprocesses
- **Async Job System**: Manages long-running operations like rendering
- **GPU Acceleration**: NVIDIA CUDA support for fast rendering

## 📡 API Examples

### Create a Scene
```python
# Create project with studio lighting
await create_blender_project(
    name="my_scene",
    template="studio_lighting",
    settings={
        "resolution": [1920, 1080],
        "engine": "CYCLES"
    }
)

# Add objects
await add_primitive_objects(
    project="/app/projects/my_scene.blend",
    objects=[
        {"type": "monkey", "name": "Suzanne", "location": [0, 0, 2]},
        {"type": "cube", "name": "Box", "location": [3, 0, 1]}
    ]
)
```

### Render an Image
```python
# Start render job
render_job = await render_image(
    project="/app/projects/my_scene.blend",
    settings={
        "resolution": [1920, 1080],
        "samples": 128,
        "engine": "CYCLES"
    }
)

# Check status
status = await get_job_status(job_id=render_job["job_id"])
# Returns: {"status": "RUNNING", "progress": 45, ...}
```

### Physics Simulation
```python
# Setup physics
await setup_physics(
    project="/app/projects/my_scene.blend",
    object_name="Box",
    physics_type="rigid_body",
    settings={"mass": 2.0, "bounce": 0.5}
)

# Bake simulation
await bake_simulation(
    project="/app/projects/my_scene.blend",
    end_frame=250
)
```

## 🐳 Docker Setup

### Build and Run
```bash
# Build container
docker-compose build mcp-blender

# Start server
docker-compose up -d mcp-blender

# View logs
docker-compose logs -f mcp-blender
```

### GPU Support (NVIDIA)
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Run with GPU
docker-compose --profile gpu up mcp-blender
```

## 🧪 Testing

### Run Tests
```bash
# Unit tests
pytest tools/mcp/blender/tests/

# Integration test
python tools/mcp/blender/scripts/test_server.py

# Interactive mode
python tools/mcp/blender/scripts/test_server.py --interactive
```

### Available Demos
- **Render Demo** - Create and render a simple scene
- **Physics Demo** - Falling objects simulation
- **Animation Demo** - Keyframe animation example
- **Geometry Nodes** - Procedural generation

## 📚 Templates

| Template | Description | Use Case |
|----------|-------------|----------|
| `empty` | Blank scene | Starting from scratch |
| `basic_scene` | Ground, light, camera | General purpose |
| `studio_lighting` | Three-point lighting | Product shots |
| `procedural` | Geometry nodes ready | Procedural generation |
| `animation` | Timeline configured | Character animation |
| `physics` | Simulation ready | Dynamics/simulations |
| `architectural` | High-quality setup | Architecture viz |
| `product` | Clean background | Product rendering |
| `vfx` | Compositing nodes | Visual effects |
| `game_asset` | Export optimized | Game development |
| `sculpting` | Matcap shading | Digital sculpting |

## 🔧 Configuration

### Environment Variables
```bash
# Port configuration
PORT=8017

# GPU settings
CUDA_VISIBLE_DEVICES=0

# Resource limits
BLENDER_MAX_THREADS=8
BLENDER_MEMORY_LIMIT=8G
```

### Volume Mounts
```yaml
volumes:
  - ./blender/projects:/app/projects    # Blender project files
  - ./blender/assets:/app/assets        # Textures, models, HDRIs
  - ./blender/outputs:/app/outputs      # Rendered images/videos
  - ./blender/templates:/app/templates  # Project templates
```

## 🎯 Use Cases

### Product Visualization
- High-quality product renders
- 360° turntables
- Material variations
- Studio lighting setups

### Architectural Visualization
- Building exteriors/interiors
- Landscape integration
- Realistic lighting with HDRIs
- Walkthrough animations

### Motion Graphics
- Logo animations
- Title sequences
- Abstract animations
- Particle effects

### Game Asset Creation
- Low-poly modeling
- Texture baking
- Export optimization
- LOD generation

### Scientific Visualization
- Data visualization
- Medical imaging
- Engineering simulations
- Educational content

## 🔗 Integration Examples

### With ComfyUI
```python
# Generate texture with ComfyUI
texture = await comfyui.generate_texture(prompt="wood texture")

# Apply in Blender
await blender.apply_material(
    object_name="Table",
    texture_path=texture["path"]
)
```

### With Gaea2
```python
# Generate terrain in Gaea2
terrain = await gaea2.create_terrain(template="mountains")

# Import into Blender
await blender.import_model(
    model_path=terrain["mesh_path"],
    format="OBJ"
)
```

## 📈 Performance Tips

1. **Use Eevee for previews** - Much faster than Cycles
2. **Optimize samples** - Start low, increase for final render
3. **Enable GPU rendering** - 10-50x faster with NVIDIA GPUs
4. **Use instancing** - For repeated geometry
5. **Bake simulations** - Cache physics calculations

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Server won't start | Check port 8017 availability |
| GPU not detected | Install NVIDIA Container Toolkit |
| Rendering slow | Enable GPU, reduce samples |
| Out of memory | Reduce texture sizes, simplify geometry |
| Jobs stuck | Check `docker logs mcp-blender` |

## 📖 Documentation

- [Full API Reference](docs/README.md)
- [Examples](examples/basic_usage.py)
- [Architecture Details](docs/README.md#architecture)

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## 📄 License

Part of the template-repo project - see main LICENSE file.

## 🙏 Acknowledgments

- Blender Foundation for the amazing open-source 3D software
- FastAPI for the modern web framework
- NVIDIA for CUDA and GPU acceleration
