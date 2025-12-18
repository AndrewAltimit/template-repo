# Blender MCP Architecture

This document describes the system architecture, design decisions, and data flow for the Blender MCP server.

## System Overview

The Blender MCP server provides programmatic control of Blender 3D through the Model Context Protocol. It operates as a FastAPI HTTP server that spawns headless Blender subprocesses to execute 3D operations.

```
+-------------------+
|   MCP Client      |
|  (Claude Code)    |
+--------+----------+
         |
         | HTTP/JSON (Port 8017)
         v
+--------+----------+
|   FastAPI Server  |
|                   |
|  +-------------+  |
|  | Job Manager |  |
|  +------+------+  |
|         |         |
|  +------+------+  |
|  | Blender     |  |
|  | Executor    |  |
|  +------+------+  |
+---------+---------+
          |
          | Subprocess
          v
+-------------------+
|  Headless Blender |
|                   |
|  Python Scripts   |
|  - scene_builder  |
|  - render         |
|  - physics_sim    |
|  - animation      |
+-------------------+
          |
          v
+-------------------+
|   File System     |
|                   |
|  /app/projects/   |
|  /app/assets/     |
|  /app/outputs/    |
+-------------------+
```

## Component Architecture

### 1. FastAPI Server (server.py)

The main HTTP server handles incoming requests, routes them to appropriate handlers, and manages the async job system.

**Responsibilities:**
- HTTP request handling
- Input validation
- Tool routing
- Error response formatting
- Health check endpoint

**Key endpoints:**
- `POST /mcp/execute` - Execute MCP tool
- `GET /mcp/tools` - List available tools
- `GET /health` - Health check
- `GET /jobs/{id}/status` - Job status

### 2. Job Manager (core/job_manager.py)

Manages async operations like rendering and simulation baking.

**Responsibilities:**
- Job creation and tracking
- Status updates
- Result storage
- Job cleanup (24-hour expiry)
- Concurrency limiting

**Job States:**
```
QUEUED -> RUNNING -> COMPLETED
                  -> FAILED
                  -> CANCELLED
```

**Concurrency Model:**
- Default: 4 concurrent jobs
- Configurable via `MAX_CONCURRENT_JOBS`
- Queue-based scheduling
- Thread-safe operations

### 3. Blender Executor (core/blender_executor.py)

Spawns and manages Blender subprocess execution.

**Responsibilities:**
- Process spawning
- Script execution
- Timeout handling
- Output capture
- Error extraction

**Execution Flow:**
```python
# 1. Prepare arguments
args = ["blender", "--background", project_path,
        "--python", script_path, "--", json.dumps(params)]

# 2. Execute subprocess
result = subprocess.run(args, capture_output=True, timeout=timeout)

# 3. Parse output
output = json.loads(result.stdout)
```

### 4. Asset Manager (core/asset_manager.py)

Handles project and asset file operations.

**Responsibilities:**
- Project listing
- File path validation
- Asset organization
- Template management

### 5. Tool Modules (tools/)

Domain-specific tool implementations organized by functionality.

**Structure:**
```
tools/
├── __init__.py      # Tool registration
├── camera.py        # Camera tools
├── compositing.py   # Compositing tools
├── environment.py   # Environment/lighting
├── modifiers.py     # Modifier tools
├── particles.py     # Particle systems
├── scene.py         # Scene management
└── textures.py      # Texture handling
```

### 6. Validation Layer (validation/)

Input validation before operations execute.

**Validators:**
- `ProjectValidator` - Project names, templates
- `RenderValidator` - Render settings
- `PhysicsValidator` - Physics parameters
- `AssetValidator` - File paths, formats

### 7. Error Handling (errors/)

Structured error collection and reporting.

**Components:**
- Custom exception hierarchy
- Error severity classification
- Diagnostic collection
- API response formatting

## Data Flow

### Synchronous Operations

```
Request -> Validation -> Blender Subprocess -> Response
```

Example: Adding objects to scene

1. Client sends `add_primitive_objects` request
2. Server validates parameters
3. Blender subprocess executes script
4. Script modifies scene and saves
5. Server returns success/failure

### Asynchronous Operations

```
Request -> Validation -> Job Created -> Response (job_id)
                              |
                              v
                    Background Thread
                              |
                              v
                    Blender Subprocess
                              |
                              v
                    Job Status Updated
```

Example: Rendering

1. Client sends `render_image` request
2. Server validates parameters
3. Job manager creates queued job
4. Server returns job_id immediately
5. Background thread starts Blender
6. Blender renders frames
7. Job status updates as progress occurs
8. Client polls `get_job_status`

## Security Model

### Path Validation

All user-provided paths undergo validation:

```python
def _validate_path(self, user_path: str, base_dir: Path) -> Path:
    # 1. Check for traversal attempts
    if ".." in user_path:
        raise BlenderPathError("Path traversal not allowed")

    # 2. Normalize path
    normalized = os.path.normpath(user_path)

    # 3. Resolve relative to base
    resolved = base_dir / normalized

    # 4. Verify within allowed directory
    if not resolved.is_relative_to(base_dir):
        raise BlenderPathError("Path outside allowed directory")

    return resolved
```

### Allowed Directories

| Directory | Purpose |
|-----------|---------|
| `/app/projects/` | Blender project files |
| `/app/assets/` | Textures, models, HDRIs |
| `/app/outputs/` | Rendered outputs |
| `/app/templates/` | Project templates |

### Process Isolation

Each Blender operation runs as an isolated subprocess:
- No shared state between operations
- Crashes don't affect server
- Resource limits enforceable
- Clean environment per operation

## Container Architecture

### Docker Container

```dockerfile
FROM ubuntu:22.04

# Install Blender
RUN wget blender-4.0.2-linux-x64.tar.xz
RUN tar -xf blender-4.0.2-linux-x64.tar.xz

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy server code
COPY mcp_blender/ /app/mcp_blender/

# Run as non-root
USER blender
WORKDIR /app

CMD ["python", "-m", "mcp_blender.server"]
```

### Volume Mounts

```yaml
volumes:
  - ./outputs/blender/projects:/app/projects
  - ./outputs/blender/assets:/app/assets
  - ./outputs/blender/renders:/app/outputs
  - ./outputs/blender/templates:/app/templates
```

### GPU Support

GPU acceleration requires:
1. NVIDIA drivers on host
2. NVIDIA Container Toolkit
3. Docker runtime configuration

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## Blender Script Architecture

### Script Structure

Each operation has a corresponding Python script:

```python
# scripts/render.py
import bpy
import sys
import json

def main():
    # 1. Parse arguments
    args = json.loads(sys.argv[-1])

    # 2. Load project
    bpy.ops.wm.open_mainfile(filepath=args["project"])

    # 3. Configure render settings
    scene = bpy.context.scene
    scene.render.resolution_x = args["resolution"][0]
    scene.render.resolution_y = args["resolution"][1]

    # 4. Execute render
    bpy.ops.render.render(write_still=True)

    # 5. Output result
    print(json.dumps({"success": True, "output": output_path}))

if __name__ == "__main__":
    main()
```

### Script Categories

| Category | Scripts | Purpose |
|----------|---------|---------|
| Scene | scene_builder.py | Object creation, modification |
| Render | render.py | Image and animation rendering |
| Physics | physics_sim.py | Simulation setup and baking |
| Animation | animation.py | Keyframe animation |
| Materials | materials.py | Material application |
| Export | export.py | Scene export |

## Performance Considerations

### Rendering Performance

| Factor | Impact | Optimization |
|--------|--------|--------------|
| Samples | Linear | Reduce for previews |
| Resolution | Quadratic | Use lower for testing |
| Geometry | Variable | Use LOD, instances |
| GPU | 10-50x faster | Enable when available |

### Memory Management

- Each Blender process: 200-500MB base
- Complex scenes: 2-8GB
- GPU VRAM: Match scene complexity
- Container limit: Configurable

### Concurrency

- Default 4 concurrent jobs
- CPU-limited without GPU
- Queue prevents overload
- Monitor with job status

## Error Handling

### Exception Hierarchy

```
BlenderError (base)
├── BlenderValidationError
├── BlenderExecutionError
├── BlenderTimeoutError
├── BlenderAssetError
├── BlenderProjectError
├── BlenderRenderError
├── BlenderPhysicsError
└── BlenderAnimationError
```

### Error Response Format

```json
{
  "success": false,
  "error": "Render failed: out of GPU memory",
  "error_type": "BlenderRenderError",
  "details": {
    "job_id": "abc123",
    "engine": "CYCLES",
    "gpu_error": true
  }
}
```

## Monitoring

### Health Check

```bash
curl http://localhost:8017/health
```

Response:
```json
{
  "status": "healthy",
  "blender_available": true,
  "blender_version": "4.0.2",
  "active_jobs": 2,
  "queued_jobs": 1
}
```

### Logging

- Server logs: INFO level
- Blender output: DEBUG level
- Errors: ERROR level with context
- Job events: INFO level

### Metrics

| Metric | Description |
|--------|-------------|
| `active_jobs` | Currently running jobs |
| `queued_jobs` | Jobs waiting to start |
| `completed_jobs` | Total completed |
| `failed_jobs` | Total failed |
| `avg_render_time` | Average render duration |
