# Blender MCP Documentation

This directory contains comprehensive documentation for the Blender MCP server.

## Documentation Index

| Document | Description |
|----------|-------------|
| [API Reference](API_REFERENCE.md) | Complete tool documentation with parameters and responses |
| [Architecture](ARCHITECTURE.md) | System design, data flow, and component details |
| [Examples](EXAMPLES.md) | Realistic usage patterns and code samples |
| [Troubleshooting](TROUBLESHOOTING.md) | Diagnostic procedures and common issue resolution |
| [Limitations](LIMITATIONS.md) | Scope constraints and known limitations |

---

## Quick Overview

The Blender MCP server provides programmatic 3D content creation through headless Blender automation. It operates as a FastAPI HTTP server that spawns Blender subprocesses for each operation.

### Architecture Summary

```
MCP Client -> FastAPI Server -> Job Manager -> Blender Subprocess -> File System
                                    |
                                    v
                              Async Job Queue
```

**Key Components:**

- **FastAPI Server**: HTTP request handling, routing, validation
- **Job Manager**: Async job creation, tracking, and cleanup
- **Blender Executor**: Subprocess spawning and script execution
- **Validation Layer**: Input validation before operations
- **Error Handler**: Structured error collection and reporting

### Tool Categories

| Category | Tools | Documentation |
|----------|-------|---------------|
| Project | `create_blender_project`, `list_projects` | [API Reference](API_REFERENCE.md#project-management) |
| Scene | `add_primitive_objects`, `setup_lighting`, `delete_objects` | [API Reference](API_REFERENCE.md#scene-building) |
| Environment | `setup_world_environment` | [API Reference](API_REFERENCE.md#environment) |
| Materials | `apply_material` | [API Reference](API_REFERENCE.md#materials-and-textures) |
| Rendering | `render_image`, `render_animation` | [API Reference](API_REFERENCE.md#rendering) |
| Physics | `setup_physics`, `bake_simulation` | [API Reference](API_REFERENCE.md#physics-simulation) |
| Animation | `create_animation`, `setup_camera` | [API Reference](API_REFERENCE.md#animation) |
| Geometry | `create_geometry_nodes` | [API Reference](API_REFERENCE.md#geometry-nodes) |
| Assets | `import_model`, `export_scene` | [API Reference](API_REFERENCE.md#asset-management) |
| Jobs | `get_job_status`, `get_job_result`, `cancel_job` | [API Reference](API_REFERENCE.md#job-management) |

---

## Quick Start

### Docker Setup

```bash
# Build
docker-compose build mcp-blender

# Start
docker-compose up -d mcp-blender

# Verify
curl http://localhost:8017/health
```

### Basic Workflow

```python
# 1. Create project
response = client.call_tool("create_blender_project", {
    "name": "my_scene",
    "template": "studio_lighting"
})
project = response["project_path"]

# 2. Add objects
client.call_tool("add_primitive_objects", {
    "project": project,
    "objects": [{"type": "sphere", "name": "Ball", "location": [0, 0, 2]}]
})

# 3. Render
render = client.call_tool("render_image", {
    "project": project,
    "settings": {"samples": 128, "engine": "CYCLES"}
})

# 4. Check status
status = client.call_tool("get_job_status", {"job_id": render["job_id"]})
```

See [Examples](EXAMPLES.md) for comprehensive workflow samples.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8017 | Server port |
| `MAX_CONCURRENT_JOBS` | 4 | Maximum parallel jobs |
| `JOB_TIMEOUT` | 3600 | Job timeout in seconds |
| `JOB_EXPIRY_HOURS` | 24 | Hours before job cleanup |
| `LOG_LEVEL` | INFO | Logging verbosity |

### Docker Compose Configuration

```yaml
mcp-blender:
  build:
    context: ./tools/mcp/mcp_blender
  ports:
    - "8017:8017"
  volumes:
    - ./outputs/blender/projects:/app/projects
    - ./outputs/blender/assets:/app/assets
    - ./outputs/blender/renders:/app/outputs
  deploy:
    resources:
      limits:
        memory: 8G
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

---

## File System Layout

| Directory | Purpose | Access |
|-----------|---------|--------|
| `/app/projects/` | Blender project files | Read/Write |
| `/app/assets/` | Textures, models, HDRIs | Read |
| `/app/outputs/` | Rendered outputs | Write |
| `/app/templates/` | Project templates | Read |

---

## Common Tasks

### Rendering

1. Create or load a project
2. Configure scene (objects, lighting, materials)
3. Call `render_image` or `render_animation`
4. Poll `get_job_status` until complete
5. Retrieve result with `get_job_result`

See [API Reference - Rendering](API_REFERENCE.md#rendering) for details.

### Rendering Without Ground Plane

For floating objects or clean backgrounds without a ground plane:

**Option 1: Use `lit_empty` template (Recommended)**
```python
# Creates scene with lighting but no ground
client.call_tool("create_blender_project", {
    "name": "floating_object",
    "template": "lit_empty"
})
```

**Option 2: Use `basic_scene` + `delete_objects`**
```python
# Create scene with good lighting
client.call_tool("create_blender_project", {
    "name": "scene",
    "template": "basic_scene"
})
# Remove the ground plane
client.call_tool("delete_objects", {
    "project": "scene.blend",
    "object_names": ["Ground"]
})
```

**Option 3: Use `empty` + `setup_lighting`**
```python
# Start with empty scene
client.call_tool("create_blender_project", {
    "name": "scene",
    "template": "empty"
})
# Add three-point lighting with high strength
client.call_tool("setup_lighting", {
    "project": "scene.blend",
    "type": "three_point",
    "settings": {"strength": 10.0}
})
```

**Tip**: Use Eevee (`engine: "BLENDER_EEVEE_NEXT"`) for brighter renders with area lights.

### Physics Simulation

1. Create project with `physics` template
2. Add objects to scene
3. Call `setup_physics` for each object
4. Call `bake_simulation` to compute physics
5. Render the animation

See [API Reference - Physics](API_REFERENCE.md#physics-simulation) for details.

### Asset Import

1. Place assets in `/app/assets/` directory
2. Use `import_model` with appropriate format
3. Verify import with scene inspection

See [API Reference - Assets](API_REFERENCE.md#asset-management) for supported formats.

---

## Troubleshooting Quick Reference

| Issue | First Step |
|-------|------------|
| Server not responding | Check `docker-compose logs mcp-blender` |
| Renders fail | Verify project path and check job error |
| GPU not detected | Run `nvidia-smi` in container |
| Jobs stuck in queue | Check concurrent job limit |
| Path errors | Verify path is within allowed directories |

See [Troubleshooting](TROUBLESHOOTING.md) for complete diagnostic procedures.

---

## Related Documentation

- [Main README](../README.md) - Installation and overview
- [API Reference](API_REFERENCE.md) - Complete tool documentation
- [Architecture](ARCHITECTURE.md) - System design details
- [Examples](EXAMPLES.md) - Usage patterns
- [Troubleshooting](TROUBLESHOOTING.md) - Issue resolution
- [Limitations](LIMITATIONS.md) - Scope and constraints
