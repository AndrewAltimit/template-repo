# Running the Blender MCP Server

## Quick Start

### 1. Start the Docker Container

```bash
# Build and start the Blender MCP server
docker-compose up -d mcp-blender

# Check if it's running
docker ps | grep mcp-blender
```

The server will be available at `http://localhost:8017`

### 2. Test the Server

```bash
# List existing projects
curl -X POST http://localhost:8017/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_projects", "arguments": {}}'

# Create a simple project
curl -X POST http://localhost:8017/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "create_blender_project", "arguments": {"name": "my_project", "template": "basic_scene"}}'
```

### 3. Run Demo Projects

```bash
# Run the comprehensive demo script
python tools/mcp/blender/demos/demo_projects.py
```

This will create 4 demonstration projects:
- **demo_abstract_art**: Colorful spheres with emission materials
- **demo_physics**: Physics simulation with falling cubes
- **demo_animated_logo**: Animated logo with rotating elements
- **demo_landscape**: Procedural terrain with scattered objects

## Available Tools

### Project Management
- `create_blender_project` - Create new projects from templates
- `list_projects` - List all available projects

### Scene Creation
- `add_primitive_objects` - Add cubes, spheres, cylinders, etc.
- `setup_lighting` - Configure various lighting setups
- `apply_material` - Apply materials to objects

### Animation & Physics
- `create_animation` - Create keyframe animations
- `setup_physics` - Configure physics simulations
- `bake_simulation` - Bake physics to keyframes

### Rendering
- `render_image` - Render single frames
- `render_animation` - Render animation sequences

### Advanced
- `create_geometry_nodes` - Procedural geometry generation
- `import_model` - Import 3D models
- `export_scene` - Export to various formats

## Project Files Location

Projects are stored in the Docker container at `/app/projects/` and mounted locally at `./outputs/blender/projects/`

To access created projects:
```bash
# List projects in container
docker exec mcp-blender ls -la /app/projects/

# Copy a project to local machine
docker cp mcp-blender:/app/projects/my_project.blend ./my_project.blend
```

## Validation Scripts

### Simple Test
```bash
python tools/mcp/blender/scripts/simple_test.py
```

### Comprehensive Validation
```bash
python tools/mcp/blender/scripts/docker_validate.py
```

## Troubleshooting

### Server Not Responding
```bash
# Check container status
docker ps -a | grep mcp-blender

# View logs
docker logs mcp-blender --tail=50

# Restart container
docker-compose restart mcp-blender
```

### Projects Not Being Created
1. Check if the container has proper permissions:
   ```bash
   docker exec mcp-blender ls -la /app/projects/
   ```

2. Ensure the Blender executable is available:
   ```bash
   docker exec mcp-blender which blender
   docker exec mcp-blender blender --version
   ```

### GPU Support (Optional)

To enable GPU rendering, uncomment the GPU section in `docker-compose.yml`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

Then rebuild and restart:
```bash
docker-compose build mcp-blender
docker-compose up -d mcp-blender
```

## API Documentation

All tools are accessed via POST requests to `http://localhost:8017/mcp/execute`

### Request Format
```json
{
  "tool": "tool_name",
  "arguments": {
    // tool-specific arguments
  }
}
```

### Response Format
```json
{
  "success": true,
  "result": {
    // tool-specific result
  },
  "error": null
}
```

## Example: Complete Workflow

```python
import httpx
import time

# Create client
client = httpx.Client(base_url="http://localhost:8017")

# 1. Create project
response = client.post("/mcp/execute", json={
    "tool": "create_blender_project",
    "arguments": {
        "name": "my_scene",
        "template": "studio_lighting"
    }
})

# 2. Add objects
response = client.post("/mcp/execute", json={
    "tool": "add_primitive_objects",
    "arguments": {
        "project": "my_scene",
        "objects": [
            {"type": "monkey", "name": "Suzanne", "location": [0, 0, 1]}
        ]
    }
})

# 3. Apply material
response = client.post("/mcp/execute", json={
    "tool": "apply_material",
    "arguments": {
        "project": "my_scene",
        "object_name": "Suzanne",
        "material": {
            "type": "metal",
            "base_color": [0.8, 0.6, 0.2, 1.0],
            "roughness": 0.3
        }
    }
})

# 4. Render image
response = client.post("/mcp/execute", json={
    "tool": "render_image",
    "arguments": {
        "project": "my_scene",
        "frame": 1,
        "settings": {
            "resolution": [1920, 1080],
            "samples": 128,
            "engine": "CYCLES"
        }
    }
})

job_id = response.json()["result"]["job_id"]
print(f"Render job started: {job_id}")
```

## Advanced Usage

### Custom Templates

Add custom templates to `./outputs/blender/templates/` and reference them when creating projects.

### Batch Processing

Use the job management system to queue multiple operations:

```python
# Start multiple render jobs
jobs = []
for frame in range(1, 11):
    response = client.post("/mcp/execute", json={
        "tool": "render_image",
        "arguments": {
            "project": "my_animation",
            "frame": frame
        }
    })
    jobs.append(response.json()["result"]["job_id"])

# Check status of all jobs
for job_id in jobs:
    response = client.post("/mcp/execute", json={
        "tool": "get_job_status",
        "arguments": {"job_id": job_id}
    })
    print(f"Job {job_id}: {response.json()['result']['status']}")
```

## Performance Tips

1. **Use EEVEE for preview renders** - Much faster than Cycles
2. **Batch operations** - Group multiple object additions into single calls
3. **Use templates** - Start from pre-configured scenes
4. **Monitor jobs** - Use job status endpoints to track long operations

## Support

For issues or questions:
- Check logs: `docker logs mcp-blender`
- Review server code: `tools/mcp/blender/server.py`
- Check scripts: `tools/mcp/blender/scripts/`
