# Blender MCP Server (Rust)

> A Model Context Protocol server for programmatic 3D content creation, rendering, and simulation through headless Blender automation. Migrated from Python to Rust for improved performance and reliability.

## Overview

This MCP server provides comprehensive Blender automation through a subprocess model. All Blender operations are executed via Python scripts in headless mode, with the Rust server managing:

- **Job Management**: Async job tracking for long-running operations (rendering, simulation baking)
- **Path Security**: Comprehensive path traversal prevention
- **Concurrency Control**: Semaphore-limited concurrent Blender processes
- **Process Isolation**: Each operation runs as an isolated subprocess

## Quick Start

```bash
# Build the server
cargo build --release

# Run in standalone mode (default port 8017)
./target/release/mcp-blender --mode standalone --port 8017

# Test endpoints
curl http://localhost:8017/health
curl http://localhost:8017/mcp/tools
```

## Available Tools

### Core Tools

| Tool | Description | Async |
|------|-------------|-------|
| `create_blender_project` | Create project from template | No |
| `list_projects` | List available projects | No |
| `add_primitive_objects` | Add cubes, spheres, cylinders, etc. | No |
| `setup_lighting` | Configure lighting (three-point, studio, HDRI) | No |
| `apply_material` | Apply PBR materials to objects | No |
| `render_image` | Render single frame | Yes |
| `render_animation` | Render animation sequence | Yes |
| `setup_physics` | Configure physics simulation | No |
| `bake_simulation` | Bake physics to keyframes | Yes |
| `create_animation` | Create keyframe animation | No |
| `create_geometry_nodes` | Setup procedural geometry | No |
| `get_job_status` | Check async job progress | No |
| `get_job_result` | Retrieve completed job output | No |
| `cancel_job` | Cancel running job | No |
| `import_model` | Import external 3D models | No |
| `export_scene` | Export scene to various formats | No |
| `setup_camera` | Configure camera position and settings | No |
| `add_camera_track` | Add camera tracking constraint | No |
| `add_modifier` | Apply mesh modifiers | No |
| `add_particle_system` | Add particle emitters or hair | No |
| `add_smoke_simulation` | Add smoke/fire simulation | No |
| `add_texture` | Add procedural textures | No |
| `add_uv_map` | Add UV mapping | No |
| `setup_compositor` | Configure post-processing nodes | No |
| `batch_render` | Render multiple frames/cameras | Yes |
| `delete_objects` | Delete objects by name/pattern | No |
| `analyze_scene` | Analyze scene statistics | No |
| `optimize_scene` | Optimize scene for performance | No |
| `create_curve` | Create Bezier curves | No |
| `setup_world_environment` | Configure world environment | No |
| `blender_status` | Server status and configuration | No |

### Quick Effects (One-Click Simulations)

| Tool | Description | Async |
|------|-------------|-------|
| `quick_smoke` | Add smoke/fire simulation (SMOKE, FIRE, BOTH) | No |
| `quick_liquid` | Add liquid simulation with fluid domain | No |
| `quick_explode` | Add explosion effect with particle debris | No |
| `quick_fur` | Add fur/hair using geometry nodes | No |

### Advanced Objects

| Tool | Description | Async |
|------|-------------|-------|
| `add_constraint` | Add object constraints (TRACK_TO, COPY_LOCATION, etc.) | No |
| `create_armature` | Create armature with bones for rigging | No |
| `create_text_object` | Create 3D text with extrusion and bevel | No |
| `add_advanced_primitives` | Add grid, circle, ico_sphere, metaball, curves | No |
| `parent_objects` | Set parent-child relationships | No |
| `join_objects` | Join multiple meshes into one | No |

## Templates

| Template | Description |
|----------|-------------|
| `empty` | Blank project with default settings |
| `basic_scene` | Ground plane, camera, and single light |
| `studio_lighting` | Three-point lighting for product shots |
| `lit_empty` | Empty scene with good lighting (no ground) |
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
| `BLENDER_PATH` | Auto-detect | Path to Blender executable |
| `MAX_CONCURRENT_JOBS` | CPU/2 | Maximum concurrent Blender processes |
| `CUDA_VISIBLE_DEVICES` | All | GPU device selection for rendering |

## Architecture

```
MCP Client
    |
    | HTTP/JSON or STDIO
    v
+---------------------+
|  Rust MCP Server    |  Job management, path validation
+---------------------+
    |
    | Subprocess (tokio::process)
    v
+---------------------+
|  Headless Blender   |  Python scripts in scripts/
+---------------------+
    |
    v
Project files (.blend), Rendered outputs
```

## Scripts

The server executes Python scripts located in the `scripts/` directory:

- `scene_builder.py` - Project creation, object manipulation, materials
- `render.py` - Image and animation rendering
- `animation.py` - Keyframe animation
- `physics_sim.py` - Physics simulation and baking
- `geometry_nodes.py` - Procedural geometry node setups (scatter, crystal, mutation)
- `camera_tools.py` - Camera setup and tracking
- `modifiers.py` - Mesh modifiers
- `particles.py` - Particle systems and smoke
- `environment.py` - World environment setup
- `quick_effects.py` - One-click smoke, liquid, explode, fur effects
- `advanced_objects.py` - Constraints, armatures, text, advanced primitives

## Security

- Path traversal prevention with comprehensive validation
- Rejection of absolute paths, parent directory references, and hidden files
- Process isolation via subprocess execution
- Semaphore-limited concurrency to prevent resource exhaustion

## Dependencies

- **mcp-core**: Core MCP protocol implementation
- **tokio**: Async runtime with process spawning
- **serde/serde_json**: JSON serialization
- **uuid**: Job ID generation
- **chrono**: Timestamp handling

## Building

```bash
# Development build
cargo build

# Release build with optimizations
cargo build --release

# Run tests
cargo test
```

## Docker Deployment

The server is designed for container deployment:

```yaml
volumes:
  - ./outputs/blender/projects:/app/projects
  - ./outputs/blender/assets:/app/assets
  - ./outputs/blender/renders:/app/outputs
```

## License

Part of the template-repo project. See repository root LICENSE file.
