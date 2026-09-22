# Blender MCP Server (Rust)

> MCP server for 3D content creation with headless Blender: projects from templates, primitives,
> materials and textures, lighting and world shaders, cameras, animation, modifiers, physics,
> particles, geometry nodes, one-click effects, rigging, import/export and rendering.

Every tool call runs one of the Python scripts in [`scripts/`](scripts/) inside a
`blender --background` subprocess. Renders and simulation bakes run as **background jobs** with
progress reporting and real cancellation; everything else is synchronous.

Tested end to end against Blender 4.5.1 LTS (the version in `docker/blender-mcp.Dockerfile`);
Blender 4.2+ is required.

## Quick start

```bash
# Container (recommended; used by .mcp.json)
docker compose --profile services run --rm -T mcp-blender mcp-blender --mode stdio

# HTTP mode
docker compose up -d mcp-blender
curl http://localhost:8017/health
curl -X POST http://localhost:8017/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "blender_status", "arguments": {}}'

# Local build (needs Blender on PATH or BLENDER_PATH)
cargo build --release
./target/release/mcp-blender --mode standalone --port 8017
```

A typical session:

```text
create_blender_project {"name": "demo", "template": "studio_lighting"}
add_primitive_objects  {"project": "demo", "objects": [{"type": "monkey", "name": "Suzanne"}]}
apply_material         {"project": "demo", "object_name": "Suzanne", "material": {"type": "metal", "base_color": [0.9, 0.6, 0.2]}}
render_image           {"project": "demo", "settings": {"resolution": [1280, 720], "samples": 64}}
get_job_status         {"job_id": "<id>", "wait_seconds": 120}
get_job_result         {"job_id": "<id>"}      -> output_path of the PNG
```

## Tools

`project` is always a project in the projects directory: `demo`, `demo.blend`, `sub/demo.blend`,
or the `full_path` returned by `create_blender_project`. Input files (models, HDRIs, images,
fonts) must be inside the assets directory and are referenced relative to it. Enum values are
case-insensitive. Rotations are Euler XYZ in radians; colors are RGB or RGBA in 0-1.

### Projects and status

| Tool | Description |
|------|-------------|
| `create_blender_project` | New `.blend` from a template (see below). `settings`: `resolution`, `fps`, `engine`, `frame_start`, `frame_end`. Refuses to replace an existing project unless `overwrite: true`. |
| `list_projects` | `.blend` files (one sub-directory level deep) with size and modification time. |
| `blender_status` | Blender path/version, directories, concurrency limits, timeouts, job counts. |

Templates: `empty`, `basic_scene`, `studio_lighting`, `lit_empty`, `procedural`, `animation`,
`physics`, `architectural`, `product`, `vfx`, `game_asset`, `sculpting` (descriptions in the
tool's schema).

### Scene building

| Tool | Description |
|------|-------------|
| `add_primitive_objects` | cube, sphere/uv_sphere, cylinder, cone, torus, plane, monkey; returns the names Blender assigned. |
| `add_advanced_primitives` | grid, circle, ico_sphere, empty, bezier_curve, nurbs_curve, nurbs_circle, metaball (extra keys such as `subdivisions`, `radius`, `metaball_type` pass through). |
| `create_curve` | Curve from `[x, y, z]` points; `curve_type` BEZIER/NURBS/POLY, `cyclic`, `bevel_depth`. |
| `create_text_object` | 3D text with extrude/bevel/alignment and optional `font_path` asset. |
| `delete_objects` | By exact `names`, object type glob (`type_pattern`, e.g. `LIGHT`) and/or name glob (`name_pattern`). |
| `parent_objects` / `join_objects` | Parenting (OBJECT, ARMATURE, BONE) and mesh joining. |
| `create_armature` | Bones with head/tail/parent/connected (parents must precede children). |
| `add_constraint` | TRACK_TO, COPY_*, LIMIT_*, FOLLOW_PATH, DAMPED_TRACK, FLOOR, CHILD_OF. |

### Look development

| Tool | Description |
|------|-------------|
| `apply_material` | principled, emission, glass, metal, plastic, wood. |
| `add_texture` | IMAGE (asset), NOISE, VORONOI, MUSGRAVE (Noise on 4.1+), WAVE, MAGIC, BRICK, CHECKER, GRADIENT, wired into the Principled BSDF (`settings.target` picks the input). |
| `add_uv_map` | SMART_PROJECT, CUBE/CYLINDER/SPHERE_PROJECT (PROJECT_FROM_VIEW falls back to cube headless). |
| `setup_lighting` | Replaces all lights: three_point, studio, hdri (asset), sun, area. |
| `setup_world_environment` | HDRI, SKY_TEXTURE, GRADIENT, COLOR, VOLUMETRIC. |
| `setup_camera` / `add_camera_track` | Create/update a camera (lens, sensor, depth of field) and make it track a target. |
| `setup_compositor` | BASIC, DENOISING, COLOR_GRADING, GLARE, FOG_GLOW, LENS_DISTORTION, VIGNETTE. |

### Animation, simulation and procedural

| Tool | Description |
|------|-------------|
| `create_animation` | Transform keyframes with LINEAR/BEZIER/CONSTANT interpolation. |
| `add_modifier` | SUBSURF, ARRAY, MIRROR, SOLIDIFY, BEVEL, DECIMATE, REMESH, SMOOTH, WAVE, DISPLACE. |
| `setup_physics` | rigid_body, soft_body, cloth, fluid (creates a liquid domain). |
| `bake_simulation` | **Job.** Bakes all point caches and fluid domains for a frame range and saves the project (locked while baking). |
| `add_particle_system` | emitter or hair particles. |
| `add_smoke_simulation` | Smoke/fire emitter plus a gas domain around it. |
| `create_geometry_nodes` | 20 presets: scatter, array, grid, curve, spiral, volume, wave_deform, twist, noise_displace, extrude, voronoi_scatter, mesh_to_points, crystal_scatter, crystal_cluster, custom, proximity_mask, blur_attribute, map_range_displacement, edge_crease_detection, organic_mutation. |
| `quick_smoke`, `quick_liquid`, `quick_explode`, `quick_fur` | One-step effects modelled on Blender's Quick Effects (fur uses hair curves + geometry nodes with length, radius, noise and frizz). |

### Rendering and jobs

| Tool | Description |
|------|-------------|
| `render_image` | **Job.** One frame to PNG/JPEG/EXR/TIFF at `<output>/renders/<job_id>.<ext>`. |
| `render_animation` | **Job.** Frame range to MP4 (H.264), AVI, MOV, MKV, WEBM (VP9) or a PNG sequence (FRAMES), with per-frame progress. |
| `batch_render` | **Job.** frames x cameras x view layers as separate images; result lists `output_files`. |
| `get_job_status` | Status, progress, message, error, timestamps. `wait_seconds` (max 300) long-polls until the job finishes. |
| `get_job_result` | Output path and script result of a finished job (tool error for failed/cancelled jobs). |
| `cancel_job` | Cancels a queued job or kills a running Blender process. |
| `list_jobs` | Jobs newest first, optionally filtered by `status`. |
| `import_model` / `export_scene` | FBX, OBJ, GLTF, GLB, STL, PLY, USD. Exports go to `<output>/exports/<filename or project>.<ext>`. |

Job states: `QUEUED` (waiting for a slot) -> `RUNNING` -> `COMPLETED` / `FAILED`, or `CANCELLED`
at any point before completion. Jobs are kept in memory for `BLENDER_JOB_RETENTION_HOURS` and are
lost on restart.

### Errors

* Bad arguments (missing/mistyped fields, unknown enum values, paths outside the allowed
  directories, missing projects/assets, out-of-range numbers) are rejected with an MCP
  `InvalidParameters` error before Blender starts.
* Failures inside Blender return an `isError` result `{"success": false, "error": ..., "blender_log": [...]}`
  with the script's message (e.g. `Object 'Nope' not found. Objects in scene: ...`) and the tail of
  Blender's output.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BLENDER_PATH` | auto | Blender executable. Otherwise `PATH`, `/usr/local/bin`, `/usr/bin`, `/opt/blender`, macOS app, `C:\Program Files\Blender Foundation\*` are probed with `--version`. |
| `MCP_BLENDER_BASE_DIR` | `/app` in the container, else `$TMP/blender-mcp` | Root for the directories below. |
| `MCP_BLENDER_PROJECT_DIR` | `<base>/projects` | `.blend` projects. |
| `MCP_BLENDER_ASSETS_DIR` | `<base>/assets` | Readable input files. |
| `MCP_BLENDER_OUTPUT_DIR` | `<base>/outputs` | Renders, exports and job status files (`jobs/`). |
| `MCP_BLENDER_TEMP_DIR` | `<base>/temp` | Per-call argument files (deleted after each call). |
| `MCP_BLENDER_SCRIPTS_DIR` | `/app/blender/scripts`, else this crate's `scripts/` | Python scripts. |
| `MAX_CONCURRENT_JOBS` | CPUs / 2 | Parallel renders/bakes; extra jobs wait as `QUEUED`. |
| `MAX_CONCURRENT_OPERATIONS` | CPUs | Parallel synchronous edits (separate pool, so edits are never stuck behind renders). |
| `BLENDER_JOB_TIMEOUT_SECS` | `600` | Timeout for synchronous operations; Blender is killed on expiry. |
| `BLENDER_RENDER_TIMEOUT_SECS` | `7200` | Timeout for render/bake jobs. |
| `BLENDER_JOB_RETENTION_HOURS` | `24` | How long finished jobs stay queryable (max 1000 kept). |
| `CUDA_VISIBLE_DEVICES` | all | Inherited by Blender; use with `settings.use_gpu` for Cycles GPU renders. |

CLI flags come from `mcp-core`: `--mode stdio|standalone`, `--port`, `--log-level` (logs go to stderr).

## Architecture

```
MCP client --(stdio / HTTP)--> mcp-blender (Rust)
   typed args + validation, path confinement, per-project locks,
   job registry, concurrency pools, timeouts, cancellation
        |
        |  blender --background --factory-startup --python-exit-code 1
        |          --python scripts/<op>.py -- <args.json> <id>
        v
   headless Blender: scripts/mcp_common.py dispatches the operation,
   prints one "MCP_RESULT:{json}" line, writes jobs/<id>.status for progress
```

* **No code injection.** Tool arguments are serialized to a JSON file and read by the scripts as
  data; nothing is interpolated into Python source or onto the command line.
* **Path confinement.** Project, asset and export paths are resolved inside their base directory
  (no `..`, no hidden components, no absolute paths elsewhere, no escape through symlinks).
* **Consistency.** Edits of one project are serialized (each call is load, modify, save).
  Read-only calls (render, analyze, export) do not take the lock.
* **Bounded resources.** Separate semaphores for jobs and edits, wall-clock timeouts, bounded
  capture of Blender output, `stdin` closed, child killed on timeout/cancel/drop.

Scripts (`scripts/`):

| Script | Operations |
|--------|-----------|
| `mcp_common.py` | CLI/result protocol, status files, engine-name resolution, helpers |
| `scene_builder.py` | projects, primitives, lighting, materials, textures, UVs, compositor, curves, delete, analyze, optimize, import/export |
| `render.py` | image, animation, batch rendering |
| `physics_sim.py` | physics setup and baking |
| `animation.py` | keyframe animation |
| `camera_tools.py` | camera setup and tracking |
| `modifiers.py` | mesh modifiers |
| `particles.py` | particles, hair, smoke simulation |
| `environment.py` | world environment |
| `geometry_nodes.py` | geometry-node presets |
| `quick_effects.py` | smoke, liquid, explode, fur |
| `advanced_objects.py` | constraints, armatures, text, advanced primitives, parenting, joining |

A script can be run by hand for debugging:

```bash
echo '{"operation": "analyze_scene", "project": "/app/projects/demo.blend"}' > /tmp/a.json
blender --background --python scripts/scene_builder.py -- /tmp/a.json test
```

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # no Blender needed
cargo build --release
```

The tests cover argument parsing and validation for every tool, path confinement, the job
state machine, result parsing and, on Unix, an end-to-end suite that runs the tools against a
fake `blender` executable (spawning, timeouts, progress polling, cancellation killing the
process). Checking the scripts against a real Blender requires the container.

## Limitations

* Jobs live in memory; restarting the server forgets them (output files remain).
* EEVEE and Workbench need an OpenGL/EGL context. The container ships Mesa's EGL (software
  rendering, slow) and uses the NVIDIA driver when run with a GPU; elsewhere use `CYCLES`.
* Simulations must be baked (`bake_simulation`) before rendering to show smoke, liquid or cloth.
* `setup_lighting` removes every existing light; `create_animation` replaces the object's
  animation; `optimize_scene MODIFIER_APPLY` is destructive.
* One MCP call edits one project; there is no undo besides re-creating or restoring the `.blend`.
