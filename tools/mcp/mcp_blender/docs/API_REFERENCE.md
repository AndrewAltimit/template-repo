# Blender MCP API Reference

This document provides complete documentation for all Blender MCP tools.

## Table of Contents

- [Project Management](#project-management)
- [Scene Building](#scene-building)
- [Materials and Textures](#materials-and-textures)
- [Rendering](#rendering)
- [Physics Simulation](#physics-simulation)
- [Animation](#animation)
- [Geometry Nodes](#geometry-nodes)
- [Asset Management](#asset-management)
- [Job Management](#job-management)

---

## Project Management

### create_blender_project

Create a new Blender project from a template.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Project name (alphanumeric, underscores, hyphens) |
| `template` | string | No | `basic_scene` | Template to use |
| `settings` | object | No | `{}` | Project settings |

**Settings Object:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `resolution` | [int, int] | [1920, 1080] | Render resolution |
| `fps` | int | 24 | Frame rate |
| `engine` | string | "CYCLES" | Render engine |

**Templates:**

- `empty` - Blank project
- `basic_scene` - Ground, camera, light
- `studio_lighting` - Three-point lighting
- `procedural` - Geometry nodes ready
- `animation` - Animation timeline
- `physics` - Rigid body world
- `architectural` - Architecture lighting
- `product` - Product photography
- `vfx` - Compositing nodes
- `game_asset` - Game export optimized
- `sculpting` - Sculpting setup

**Response:**

```json
{
  "success": true,
  "project_path": "my_project.blend",
  "full_path": "/app/projects/my_project.blend",
  "template": "studio_lighting"
}
```

### list_projects

List all available Blender projects.

**Parameters:** None

**Response:**

```json
{
  "success": true,
  "projects": [
    {
      "name": "my_project.blend",
      "path": "/app/projects/my_project.blend",
      "size": 1048576,
      "modified": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

## Scene Building

### add_primitive_objects

Add primitive objects to a scene.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Path to project file |
| `objects` | array | Yes | List of objects to add |

**Object Definition:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | Yes | - | Object type |
| `name` | string | Yes | - | Object name |
| `location` | [float, float, float] | No | [0, 0, 0] | Position |
| `rotation` | [float, float, float] | No | [0, 0, 0] | Rotation (radians) |
| `scale` | [float, float, float] | No | [1, 1, 1] | Scale |

**Object Types:**

- `cube`, `sphere`, `cylinder`, `cone`, `torus`
- `plane`, `circle`, `grid`
- `monkey` (Suzanne), `uv_sphere`, `ico_sphere`
- `empty`, `camera`, `light`

**Response:**

```json
{
  "success": true,
  "objects_added": ["Cube_001", "Sphere_001"],
  "count": 2
}
```

### setup_lighting

Configure scene lighting.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | - | Path to project file |
| `type` | string | Yes | - | Lighting type |
| `settings` | object | No | `{}` | Lighting settings |

**Lighting Types:**

| Type | Description |
|------|-------------|
| `three_point` | Key, fill, and back lights |
| `studio` | Multiple soft box lights |
| `hdri` | HDRI environment lighting |
| `sun` | Directional sun light |
| `area` | Single area light |

**Settings Object (varies by type):**

```json
{
  "strength": 1.5,
  "color": [1.0, 0.95, 0.8],
  "hdri_path": "/app/assets/hdri/studio.hdr"
}
```

---

## Materials and Textures

### apply_material

Apply a material to an object.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Path to project file |
| `object_name` | string | Yes | Target object name |
| `material` | object | Yes | Material definition |

**Material Definition:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | "principled" | Material type |
| `base_color` | [float, float, float, float] | [0.8, 0.8, 0.8, 1.0] | RGBA color |
| `roughness` | float | 0.5 | Surface roughness (0-1) |
| `metallic` | float | 0.0 | Metallic factor (0-1) |
| `emission_strength` | float | 0.0 | Emission intensity |
| `texture_path` | string | null | Path to texture image |

**Material Types:**

- `principled` - PBR material
- `emission` - Emissive material
- `glass` - Transparent glass
- `metal` - Metallic surface
- `plastic` - Plastic appearance
- `wood` - Procedural wood

---

## Rendering

### render_image

Render a single frame. Returns job ID for async processing.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | - | Path to project file |
| `frame` | int | No | 1 | Frame to render |
| `settings` | object | No | `{}` | Render settings |

**Settings Object:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `resolution` | [int, int] | [1920, 1080] | Output resolution |
| `samples` | int | 128 | Sample count (Cycles) |
| `engine` | string | "CYCLES" | Render engine |
| `format` | string | "PNG" | Output format |

**Response:**

```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "QUEUED",
  "check_status": "/jobs/550e8400-e29b-41d4-a716-446655440000/status"
}
```

### render_animation

Render an animation sequence. Returns job ID for async processing.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | - | Path to project file |
| `start_frame` | int | No | 1 | First frame |
| `end_frame` | int | Yes | - | Last frame |
| `settings` | object | No | `{}` | Render settings |

**Response:**

```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "QUEUED",
  "frame_count": 250
}
```

---

## Physics Simulation

### setup_physics

Configure physics for an object.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Path to project file |
| `object_name` | string | Yes | Target object |
| `physics_type` | string | Yes | Physics type |
| `settings` | object | No | Physics settings |

**Physics Types:**

| Type | Description |
|------|-------------|
| `rigid_body` | Solid object dynamics |
| `soft_body` | Deformable objects |
| `cloth` | Fabric simulation |
| `fluid` | Liquid simulation |
| `collision` | Collision object only |

**Rigid Body Settings:**

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `mass` | float | 1.0 | 0-100000 | Object mass |
| `friction` | float | 0.5 | 0-1 | Surface friction |
| `bounce` | float | 0.0 | 0-1 | Restitution |
| `collision_shape` | string | "CONVEX_HULL" | - | Collision shape |

**Collision Shapes:**

`BOX`, `SPHERE`, `CAPSULE`, `CYLINDER`, `CONE`, `CONVEX_HULL`, `MESH`

### bake_simulation

Bake physics simulation to keyframes.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | - | Path to project file |
| `start_frame` | int | No | 1 | Start frame |
| `end_frame` | int | Yes | - | End frame |

**Response:**

```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440002",
  "status": "QUEUED",
  "frame_count": 250
}
```

---

## Animation

### create_animation

Create keyframe animation for an object.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Path to project file |
| `object_name` | string | Yes | Target object |
| `keyframes` | array | Yes | Keyframe definitions |
| `interpolation` | string | No | Interpolation mode |

**Keyframe Definition:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `frame` | int | Yes | Frame number |
| `location` | [float, float, float] | No | Position |
| `rotation` | [float, float, float] | No | Rotation (radians) |
| `scale` | [float, float, float] | No | Scale |

**Interpolation Modes:**

`LINEAR`, `CONSTANT`, `BEZIER`, `BOUNCE`, `ELASTIC`

### setup_camera

Configure camera settings.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Path to project file |
| `camera_name` | string | No | Camera name (default: active) |
| `settings` | object | Yes | Camera settings |

**Camera Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `location` | [float, float, float] | - | Camera position |
| `rotation` | [float, float, float] | - | Camera rotation |
| `focal_length` | float | 50.0 | Lens focal length (mm) |
| `sensor_width` | float | 36.0 | Sensor width (mm) |
| `depth_of_field` | bool | false | Enable DOF |
| `focus_distance` | float | 10.0 | Focus distance |
| `f_stop` | float | 2.8 | Aperture f-stop |

---

## Geometry Nodes

### create_geometry_nodes

Setup procedural geometry using geometry nodes. Supports 13 different node setup types for comprehensive procedural generation.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Path to project file |
| `object_name` | string | Yes | Target object (created if not exists) |
| `node_setup` | string | Yes | Node setup type |
| `parameters` | object | No | Setup-specific parameters |

**Node Setup Types:**

| Setup | Description | Default Base Object |
|-------|-------------|---------------------|
| `scatter` | Distribute instances on surface with random scale/rotation | Plane (10x10) |
| `array` | Linear array with offset control | Cube |
| `grid` | 2D/3D grid array with configurable spacing | Cube |
| `spiral` | Spiral curve with tube profile | Cube |
| `curve` | Circle curve with tube profile (torus) | Cube |
| `wave_deform` | Sine wave deformation along configurable axis | Plane (10x10) |
| `twist` | Twist deformation around axis | Cylinder |
| `noise_displace` | Noise-based displacement with normal support | Plane (10x10) |
| `extrude` | Face extrusion with optional top scaling | Plane |
| `volume` | Volume cube to mesh conversion | Cube |
| `voronoi_scatter` | Voronoi-based point distribution | Plane |
| `mesh_to_points` | Convert mesh vertices to point cloud | Cube |
| `custom` | Flexible subdivision + noise displacement | Cube |

### Scatter Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 100 | Instance density |
| `seed` | int | 0 | Random seed |
| `scale_base` | float | 1.0 | Base scale for instances |
| `scale_variance` | float | 0.1 | Scale randomization (0-1) |
| `random_rotation` | bool | true | Enable random Z rotation |
| `align_to_normal` | bool | false | Align instances to surface normal |
| `instance_object` | string | null | Name of object to instance (uses cube if null) |
| `method` | string | "RANDOM" | Distribution method |

### Array Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 10 | Number of instances |
| `offset_x` | float | 2.0 | X offset between instances |
| `offset_y` | float | 0.0 | Y offset between instances |
| `offset_z` | float | 0.0 | Z offset between instances |

### Grid Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count_x` | int | 5 | Grid count in X |
| `count_y` | int | 5 | Grid count in Y |
| `count_z` | int | 1 | Grid count in Z (1 = 2D grid) |
| `spacing_x` | float | 2.0 | Spacing in X |
| `spacing_y` | float | 2.0 | Spacing in Y |
| `spacing_z` | float | 2.0 | Spacing in Z |

### Spiral Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `turns` | float | 3 | Number of rotations |
| `points` | int | 100 | Resolution of spiral curve |
| `radius_start` | float | 0.5 | Starting radius |
| `radius_end` | float | 3.0 | Ending radius |
| `height` | float | 2.0 | Total height |
| `profile_radius` | float | 0.1 | Tube profile radius |

### Curve Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `radius` | float | 5.0 | Circle radius |
| `profile_radius` | float | 0.1 | Tube profile radius |
| `resolution` | int | 32 | Curve resolution |

### Wave Deform Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `amplitude` | float | 0.5 | Wave height |
| `frequency` | float | 2.0 | Wave frequency |
| `phase` | float | 0.0 | Wave phase offset |
| `axis` | string | "Z" | Displacement axis (X, Y, Z) |
| `wave_axis` | string | "X" | Axis driving the wave (X, Y, Z) |
| `subdivisions` | int | 3 | Mesh subdivision level |

### Twist Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `angle` | float | 3.14159 | Total twist angle (radians) |
| `axis` | string | "Z" | Twist axis (X, Y, Z) |
| `subdivisions` | int | 3 | Mesh subdivision level |

### Noise Displace Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strength` | float | 0.5 | Displacement strength |
| `scale` | float | 5.0 | Noise scale |
| `detail` | float | 2.0 | Noise detail level |
| `roughness` | float | 0.5 | Noise roughness |
| `use_normals` | bool | true | Displace along normals |
| `subdivisions` | int | 3 | Mesh subdivision level |

### Extrude Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `offset` | float | 1.0 | Extrusion distance |
| `individual` | bool | false | Extrude faces individually |
| `top_scale` | float | 1.0 | Scale factor for top faces |

### Volume Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `density` | float | 1.0 | Volume density |
| `size_x` | float | 5.0 | Volume size X |
| `size_y` | float | 5.0 | Volume size Y |
| `size_z` | float | 5.0 | Volume size Z |
| `threshold` | float | 0.1 | Mesh extraction threshold |

### Voronoi Scatter Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scale` | float | 5.0 | Voronoi cell scale |
| `randomness` | float | 1.0 | Cell randomness (0-1) |
| `instance_scale` | float | 0.1 | Instance size |

### Mesh to Points Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `point_radius` | float | 0.05 | Point/sphere radius |
| `use_spheres` | bool | true | Use sphere instances (vs point cloud) |

### Custom Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `subdivision_level` | int | 2 | Subdivision iterations |
| `noise_scale` | float | 5.0 | Noise texture scale |
| `noise_detail` | float | 2.0 | Noise detail level |
| `displacement_strength` | float | 0.3 | Displacement amount |

**Example - Scatter Setup:**

```json
{
  "project": "my_scene.blend",
  "object_name": "GroundPlane",
  "node_setup": "scatter",
  "parameters": {
    "count": 200,
    "seed": 42,
    "scale_base": 0.5,
    "scale_variance": 0.3,
    "random_rotation": true
  }
}
```

**Example - Wave Deformation:**

```json
{
  "project": "my_scene.blend",
  "object_name": "WavyPlane",
  "node_setup": "wave_deform",
  "parameters": {
    "amplitude": 0.8,
    "frequency": 3.0,
    "axis": "Z",
    "wave_axis": "X",
    "subdivisions": 5
  }
}
```

**Example - 3D Grid Array:**

```json
{
  "project": "my_scene.blend",
  "object_name": "CubeGrid",
  "node_setup": "grid",
  "parameters": {
    "count_x": 4,
    "count_y": 4,
    "count_z": 4,
    "spacing_x": 2.0,
    "spacing_y": 2.0,
    "spacing_z": 2.0
  }
}
```

---

## Asset Management

### import_model

Import external 3D model.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Path to project file |
| `model_path` | string | Yes | Path to model file |
| `format` | string | No | File format (auto-detected) |
| `location` | [float, float, float] | No | Import location |

**Supported Formats:**

`FBX`, `OBJ`, `GLTF`, `GLB`, `STL`, `PLY`, `DAE`, `USD`

### export_scene

Export scene to file.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Path to project file |
| `format` | string | Yes | Export format |
| `output_path` | string | No | Output path |
| `selected_only` | bool | No | Export selection only |

**Export Formats:**

`FBX`, `OBJ`, `GLTF`, `GLB`, `STL`, `PLY`, `DAE`, `USD`

---

## Job Management

### get_job_status

Check the status of an async job.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | Job identifier |

**Response:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "progress": 45,
  "message": "Rendering frame 45/100",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:31:00Z"
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `QUEUED` | Waiting to start |
| `RUNNING` | In progress |
| `COMPLETED` | Finished successfully |
| `FAILED` | Error occurred |
| `CANCELLED` | Cancelled by user |

### get_job_result

Get the result of a completed job.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | Job identifier |

**Response:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "result": {
    "output_path": "/app/outputs/render_001.png",
    "render_time": 45.2,
    "samples": 128
  }
}
```

### cancel_job

Cancel a running or queued job.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | Job identifier |

**Response:**

```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "CANCELLED"
}
```

---

## Error Responses

All tools return consistent error responses:

```json
{
  "success": false,
  "error": "Error description",
  "error_type": "BlenderValidationError",
  "details": {
    "field": "samples",
    "value": -1,
    "constraint": "must be positive integer"
  }
}
```

Common error types:

- `BlenderValidationError` - Invalid input parameters
- `BlenderExecutionError` - Blender subprocess failed
- `BlenderTimeoutError` - Operation timed out
- `BlenderAssetError` - Asset not found
- `BlenderProjectError` - Project file issue
- `BlenderRenderError` - Render failed
