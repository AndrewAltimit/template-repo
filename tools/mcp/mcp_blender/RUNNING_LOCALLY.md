# 🚀 Running Blender MCP Server Locally

This guide explains how to run and test the Blender MCP server on your local machine.

## 📋 Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended) or macOS
- **RAM**: Minimum 8GB (16GB recommended for complex scenes)
- **GPU**: NVIDIA GPU with CUDA support (optional but recommended for fast rendering)
- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher

### Optional GPU Support (NVIDIA)
For GPU-accelerated rendering, install NVIDIA Container Toolkit:
```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

## 🐳 Method 1: Docker (Recommended)

### Start the Server
```bash
# Build the Docker image
docker-compose build mcp-blender

# Start the server in detached mode
docker-compose up -d mcp-blender

# Check if it's running
docker-compose ps mcp-blender

# View logs
docker-compose logs -f mcp-blender
```

### With GPU Support
```bash
# Uncomment GPU section in docker-compose.yml
# Then run:
docker-compose --profile gpu up -d mcp-blender
```

### Stop the Server
```bash
docker-compose down mcp-blender
```

## 🐍 Method 2: Python (Development)

### Setup
```bash
# Install Blender (if not using Docker)
wget https://download.blender.org/release/Blender4.0/blender-4.0.2-linux-x64.tar.xz
tar -xf blender-4.0.2-linux-x64.tar.xz
sudo mv blender-4.0.2-linux-x64 /opt/blender
sudo ln -s /opt/blender/blender /usr/local/bin/blender

# Install Python dependencies
pip install -r tools/mcp/blender/requirements.txt
```

### Run the Server
```bash
# From repository root
python -m tools.mcp.blender.server

# Or directly
cd tools/mcp/blender
python server.py
```

## ✅ Verify Server is Running

### Health Check
```bash
# Using curl
curl http://localhost:8017/health

# Expected response:
# {"status": "healthy", "version": "1.0.0"}
```

### Using Test Script
```bash
# Quick test
python tools/mcp/blender/scripts/test_server.py

# Interactive mode
python tools/mcp/blender/scripts/test_server.py --interactive
```

## 🎯 Running Validation & Demos

### Comprehensive Validation Suite
Tests all major capabilities:
```bash
# Run full validation
python tools/mcp/blender/scripts/comprehensive_validation.py

# With custom server URL
python tools/mcp/blender/scripts/comprehensive_validation.py --server-url http://localhost:8017
```

This will test:
- ✅ All 11 project templates
- ✅ Object creation (all primitive types)
- ✅ Materials (metal, glass, emission, plastic, wood)
- ✅ Lighting setups (three-point, studio, sun, area)
- ✅ Physics simulation (rigid body dynamics)
- ✅ Animation (keyframes, interpolation)
- ✅ Geometry nodes (procedural generation)
- ✅ Rendering (EEVEE, CYCLES, WORKBENCH)
- ✅ Import/Export (OBJ, FBX, GLTF, STL, PLY)

### Demo Projects
Create showcase projects:
```bash
# Run all 5 demos
python tools/mcp/blender/scripts/demo_projects.py

# Run specific demo (1-5)
python tools/mcp/blender/scripts/demo_projects.py --demo 1
```

**Available Demos:**
1. **Product Visualization** - Luxury watch with studio lighting
2. **Physics Simulation** - Domino chain reaction
3. **Abstract Animation** - Geometric dance with emissions
4. **Architectural Viz** - Modern house with realistic materials
5. **Procedural Generation** - Forest scatter using geometry nodes

## 📁 Output Locations

After running tests/demos, find outputs in:
```
outputs/blender/
├── projects/     # .blend project files
├── renders/      # Rendered images and animations
├── assets/       # Textures, models, HDRIs
└── templates/    # Project templates
```

## 🔧 Configuration

### Environment Variables
```bash
# Port (default: 8017)
export PORT=8017

# GPU settings
export CUDA_VISIBLE_DEVICES=0

# Resource limits
export BLENDER_MAX_THREADS=8
export BLENDER_MEMORY_LIMIT=8G
```

### Custom Settings
Edit `docker-compose.yml` for:
- Port mapping
- Volume mounts
- GPU allocation
- Memory limits

## 🎮 Quick Start Examples

### Example 1: Create and Render a Simple Scene
```python
import asyncio
from tools.mcp.core.client import MCPClient

async def quick_demo():
    client = MCPClient("http://localhost:8017")

    # Create project
    project = await client.call_tool(
        "create_blender_project",
        {"name": "my_scene", "template": "studio_lighting"}
    )

    # Add objects
    await client.call_tool(
        "add_primitive_objects",
        {
            "project": project["project_path"],
            "objects": [
                {"type": "monkey", "name": "Suzanne", "location": [0, 0, 2]},
                {"type": "cube", "name": "Cube", "location": [3, 0, 1]}
            ]
        }
    )

    # Apply materials
    await client.call_tool(
        "apply_material",
        {
            "project": project["project_path"],
            "object_name": "Suzanne",
            "material": {"type": "metal", "roughness": 0.3}
        }
    )

    # Render
    render = await client.call_tool(
        "render_image",
        {
            "project": project["project_path"],
            "settings": {"engine": "EEVEE", "samples": 64}
        }
    )

    print(f"Rendered: {render['output_path']}")

asyncio.run(quick_demo())
```

### Example 2: Physics Simulation
```python
# Create falling objects simulation
python tools/mcp/blender/scripts/demo_projects.py --demo 2
```

## 🐛 Troubleshooting

### Server Won't Start
```bash
# Check if port 8017 is in use
sudo lsof -i :8017

# Kill existing process
sudo kill -9 $(sudo lsof -t -i:8017)
```

### GPU Not Detected
```bash
# Check NVIDIA driver
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

### Rendering Slow
- Use EEVEE instead of CYCLES for previews
- Reduce sample count (32-64 for tests)
- Enable GPU rendering if available

### Permission Issues
```bash
# Fix directory permissions
sudo chown -R $USER:$USER outputs/blender/
```

### Out of Memory
- Reduce texture sizes
- Simplify geometry
- Lower resolution
- Use EEVEE instead of CYCLES

## 📊 Performance Tips

1. **Preview Mode**: Use EEVEE with low samples (32) for quick previews
2. **Final Render**: Use CYCLES with GPU for best quality
3. **Batch Processing**: Queue multiple renders as async jobs
4. **Resource Management**: Monitor with `docker stats mcp-blender`

## 🔗 Integration with Other MCP Servers

```python
# Example: Use with ComfyUI for textures
texture = await comfyui_client.generate_texture("wood texture")
await blender_client.apply_texture(texture_path=texture["path"])

# Example: Import Gaea2 terrain
terrain = await gaea2_client.create_terrain("mountains")
await blender_client.import_model(terrain["mesh_path"])
```

## 📚 Additional Resources

- [Blender MCP README](README.md)
- [API Documentation](docs/README.md)
- [Example Scripts](examples/)
- [Test Suite](tests/)

## 💡 Tips for Testing

1. **Start Small**: Begin with simple scenes before complex projects
2. **Use Templates**: Leverage the 11 built-in templates
3. **Monitor Logs**: Keep `docker-compose logs -f mcp-blender` open
4. **Check Outputs**: Regularly check `outputs/blender/renders/` for results
5. **Iterate Quickly**: Use EEVEE for rapid iteration, CYCLES for final

## 🆘 Getting Help

If you encounter issues:
1. Check server logs: `docker-compose logs mcp-blender`
2. Run health check: `curl http://localhost:8017/health`
3. Try the test script: `python tools/mcp/blender/scripts/test_server.py`
4. Review this guide's troubleshooting section

---

Happy 3D creating with Blender MCP! 🎨✨
