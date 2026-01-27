# Blender MCP Server

> A Model Context Protocol server for programmatic 3D content creation, rendering, and simulation through headless Blender automation.

## Validation Status

This server has been validated through automated testing and manual verification. The following table indicates the current status of each component:

| Component | Status | Description |
|-----------|--------|-------------|
| Project Creation | Validated | Template-based project generation with 11 templates |
| Rendering (Cycles) | Validated | GPU-accelerated path tracing with NVIDIA CUDA |
| Rendering (Eevee) | Validated | Real-time viewport rendering |
| Physics (Rigid Body) | Validated | Solid object dynamics and collision |
| Physics (Soft Body) | Partial | Basic implementation; complex deformations untested |
| Physics (Cloth/Fluid) | Untested | API exposed but not validated |
| Animation | Validated | Keyframe animation with interpolation modes |
| Geometry Nodes | Experimental | Scatter and array setups implemented |
| Asset Import | Validated | FBX, OBJ, GLTF/GLB formats |
| Asset Export | Validated | GLTF, FBX, OBJ formats |
| Compositing | Experimental | Basic node setup; complex workflows untested |

**Scope**: This server provides programmatic Blender automation for batch rendering and procedural content generation. It operates headlessly through subprocess execution. Interactive viewport control, real-time editing, and Blender GUI access are not supported.

## Architecture

```
Claude Code / MCP Client
        |
        | HTTP/JSON (Port 8017)
        v
+-------------------+
|   FastAPI Server  |  Job management, request routing
+-------------------+
        |
        | Subprocess (async)
        v
+-------------------+
|  Headless Blender |  3D operations via Python scripts
+-------------------+
        |
        v
    Project files (.blend)
    Rendered outputs (PNG, MP4, EXR)
```

Key design decisions:
- **Process isolation**: Each Blender operation runs as an isolated subprocess, preventing crashes from affecting the server
- **Async job system**: Long-running operations (rendering, simulations) execute asynchronously with status polling
- **Path validation**: All user-provided paths are validated against directory traversal attacks
- **Container-first**: Designed for Docker deployment with GPU passthrough support

## Quick Start

```bash
# Build and start the server
docker compose build mcp-blender
docker compose up -d mcp-blender

# Verify health
curl http://localhost:8017/health

# Run with GPU support (requires NVIDIA Container Toolkit)
docker compose --profile gpu up mcp-blender
```

## Available Tools

| Tool | Description | Async |
|------|-------------|-------|
| `create_blender_project` | Create project from template | No |
| `add_primitive_objects` | Add cubes, spheres, cylinders, etc. | No |
| `setup_lighting` | Configure lighting (three-point, studio, HDRI) | No |
| `apply_material` | Apply PBR materials to objects | No |
| `setup_camera` | Configure camera position and settings | No |
| `add_modifier` | Apply modifiers (subdivision, boolean, etc.) | No |
| `render_image` | Render single frame | Yes |
| `render_animation` | Render animation sequence | Yes |
| `setup_physics` | Configure physics simulation | No |
| `bake_simulation` | Bake physics to keyframes | Yes |
| `create_animation` | Create keyframe animation | No |
| `create_geometry_nodes` | Setup procedural geometry | No |
| `import_model` | Import external 3D models | No |
| `export_scene` | Export scene to various formats | No |
| `get_job_status` | Check async job progress | No |
| `get_job_result` | Retrieve completed job output | No |
| `cancel_job` | Cancel running job | No |
| `list_projects` | List available projects | No |

## Templates

| Template | Description |
|----------|-------------|
| `empty` | Blank project with default settings |
| `basic_scene` | Ground plane, camera, and single light |
| `studio_lighting` | Three-point lighting for product shots |
| `procedural` | Geometry nodes ready configuration |
| `animation` | Timeline and keyframe configuration |
| `physics` | Rigid body world with ground collision |
| `architectural` | High-quality lighting for architecture |
| `product` | Clean background for product rendering |
| `vfx` | Compositing nodes for visual effects |
| `game_asset` | Export-optimized settings for games |
| `sculpting` | Matcap shading for digital sculpting |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `PORT` | `8017` | Server listen port |
| `BLENDER_PATH` | Auto-detect | Path to Blender executable |
| `CUDA_VISIBLE_DEVICES` | All | GPU device selection |
| `BLENDER_MAX_THREADS` | System default | CPU thread limit |
| `BLENDER_MEMORY_LIMIT` | None | Memory limit per operation |
| `MAX_CONCURRENT_JOBS` | `4` | Concurrent job limit |

## Volume Mounts

```yaml
volumes:
  - ./outputs/blender/projects:/app/projects    # Blender project files
  - ./outputs/blender/assets:/app/assets        # Textures, models, HDRIs
  - ./outputs/blender/renders:/app/outputs      # Rendered outputs
  - ./outputs/blender/templates:/app/templates  # Custom templates
```

## Known Limitations

The following limitations are documented for transparency:

| Limitation | Impact | Workaround |
|------------|--------|------------|
| No interactive viewport | Cannot preview in real-time | Use Eevee for fast test renders |
| GPU detection requires toolkit | Container GPU access fails without setup | Install NVIDIA Container Toolkit |
| HDRI requires pre-positioned files | Cannot download HDRIs dynamically | Mount HDRIs in `/app/assets/hdri/` |
| Render queue backlog | Jobs may queue during high load | Monitor with `get_job_status` |
| Blender version locked | Container uses specific Blender version | Rebuild container for version changes |
| No real-time progress streaming | Progress only available via polling | Poll `get_job_status` periodically |

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Server returns 500 | Blender subprocess crashed | Check `docker logs mcp-blender` |
| GPU not detected | Container toolkit missing | Install NVIDIA Container Toolkit |
| Renders stuck in QUEUED | Max concurrent jobs reached | Wait for jobs to complete or cancel |
| Path validation fails | Path outside allowed directories | Use `/app/projects/` prefix |
| Import fails | Unsupported format | Check supported formats in docs |
| Out of memory | Scene too complex | Reduce geometry, texture sizes |

## Testing

```bash
# Run unit tests
docker compose run --rm python-ci pytest tools/mcp/mcp_blender/tests/ -v

# Run integration test
python tools/mcp/mcp_blender/scripts/test_server.py

# Health check
curl -s http://localhost:8017/health | jq
```

## Documentation

- [API Reference](docs/API_REFERENCE.md) - Complete tool documentation
- [Architecture](docs/ARCHITECTURE.md) - System design details
- [Examples](docs/EXAMPLES.md) - Usage patterns and workflows
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Diagnostic guide
- [Limitations](docs/LIMITATIONS.md) - Scope and constraints

## Integration

The Blender MCP server integrates with other MCP servers in this repository:

- **ComfyUI MCP**: Generate textures with AI, apply in Blender
- **Gaea2 MCP**: Create terrain heightmaps, import as Blender geometry
- **ElevenLabs MCP**: Generate audio for animations

## Security

- Path traversal prevention with comprehensive validation
- Process isolation via subprocess execution
- Container runs as non-root user
- Resource limits enforced via Docker

## Performance

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| Project creation | <1s | Template-based |
| Cycles render (1080p, 128 samples) | 10-60s | GPU-dependent |
| Eevee render (1080p) | 1-5s | Near real-time |
| Physics bake (250 frames) | 30-120s | Complexity-dependent |
| FBX import | <5s | Model-dependent |

## License

Part of the template-repo project. See repository LICENSE file.
