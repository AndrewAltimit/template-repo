# Blender MCP Limitations

This document explicitly defines the scope, constraints, and known limitations of the Blender MCP server.

## Scope Definition

### What This Server Does

The Blender MCP server provides **programmatic batch automation** of Blender 3D:

- Headless rendering of images and animations
- Procedural scene generation via scripts
- Batch processing of 3D assets
- Physics simulation baking
- Automated export pipelines

### What This Server Does NOT Do

| Feature | Status | Alternative |
|---------|--------|-------------|
| Interactive viewport | Not supported | Use Blender GUI directly |
| Real-time editing | Not supported | Use Blender GUI directly |
| Sculpting | Not supported | Requires interactive input |
| Grease pencil drawing | Not supported | Requires interactive input |
| Manual UV unwrapping | Not supported | Use automated unwrap or Blender GUI |
| Node editor manipulation | Limited | Predefined setups only |
| Video editing (VSE) | Not supported | Use dedicated video tools |

---

## Technical Constraints

### Subprocess Architecture

Every operation spawns a new Blender subprocess:

**Implications:**
- No persistent state between operations
- Scene must be saved/loaded for each operation
- Higher latency than native Blender scripting
- Memory overhead per operation (200-500MB base)

**Trade-offs:**
- Isolation prevents crashes from affecting server
- Clean environment for each operation
- Resource limits enforceable per operation

### Concurrency Limits

| Setting | Default | Configurable |
|---------|---------|--------------|
| Max concurrent jobs | 4 | Yes (`MAX_CONCURRENT_JOBS`) |
| Job queue depth | Unlimited | No |
| Job timeout | 3600s | Yes (`JOB_TIMEOUT`) |
| Job expiry | 24 hours | Yes (`JOB_EXPIRY_HOURS`) |

**Memory considerations:**
- Each Blender process: 200-500MB minimum
- Complex scenes: 2-8GB per process
- With 4 concurrent jobs: 8-32GB potential usage
- Reduce concurrency on memory-constrained systems

### GPU Constraints

| Constraint | Description |
|------------|-------------|
| Single GPU | Only one GPU per container supported |
| VRAM sharing | Jobs share GPU VRAM, may cause OOM |
| Driver dependency | Requires matching host/container drivers |
| Cycles only | GPU acceleration only for Cycles engine |

**GPU memory failures:**
- No automatic fallback to CPU
- Complex scenes may exceed VRAM
- Reduce resolution/samples or use CPU for large scenes

---

## Validation Status by Feature

### Fully Validated

These features have been tested and work reliably:

| Feature | Notes |
|---------|-------|
| Project creation | All templates functional |
| Primitive objects | All types supported |
| Camera setup | Position, rotation, DOF |
| Basic lighting | Point, sun, area lights |
| Cycles rendering | GPU and CPU |
| Eevee rendering | All settings |
| PNG/JPEG export | Standard formats |
| FBX import/export | Industry standard |
| OBJ import/export | Legacy support |
| GLTF import/export | Web-ready format |
| Rigid body physics | Basic simulation |
| Keyframe animation | Position, rotation, scale |
| Geometry nodes | 13 setup types: scatter, array, grid, spiral, curve, wave_deform, twist, noise_displace, extrude, volume, voronoi_scatter, mesh_to_points, custom |

### Partially Validated

These features work but have known limitations:

| Feature | Limitation |
|---------|------------|
| Particle systems | Basic emitters only |
| Cloth simulation | Simple configurations |
| Soft body | May be unstable with complex meshes |
| USD export | Basic support, no variants |
| EXR output | 32-bit only |
| HDR environment | Path must be accessible |

### Untested / Experimental

These features exist but have not been validated:

| Feature | Status |
|---------|--------|
| Fluid simulation | Implemented, not tested |
| Hair particles | Not tested |
| Alembic export | Not tested |
| Force fields | Not tested |
| Constraints | Not tested |
| Shape keys | Not tested |
| Armatures | Basic support only |
| Custom nodes | Not supported |

---

## Known Issues

### Rendering

| Issue | Workaround |
|-------|------------|
| Black renders | Verify lighting exists; check camera placement |
| Slow Cycles | Use GPU; reduce samples; enable denoising |
| Memory errors | Reduce resolution; simplify geometry |
| Missing textures | Verify paths are within `/app/assets/` |

### Physics

| Issue | Workaround |
|-------|------------|
| Simulation explodes | Reduce mass/velocity; use simpler collision shapes |
| Objects pass through | Increase collision margin; use MESH shape |
| Bake fails | Ensure rigid body world exists; check frame range |

### Assets

| Issue | Workaround |
|-------|------------|
| Import fails | Verify format is supported; check file integrity |
| Textures missing | Use absolute paths within allowed directories |
| Scale incorrect | Check import scale settings; apply transforms |

---

## Path Restrictions

All file operations are restricted to allowed directories:

| Directory | Purpose | Write Access |
|-----------|---------|--------------|
| `/app/projects/` | Blender project files | Yes |
| `/app/assets/` | Textures, models, HDRIs | Read only |
| `/app/outputs/` | Rendered outputs | Yes |
| `/app/templates/` | Project templates | Read only |

**Security restrictions:**
- Path traversal (`..`) is blocked
- Absolute paths must be within allowed directories
- Symlinks are not followed
- No access to host filesystem outside mounted volumes

---

## Performance Expectations

### Rendering Times (Reference Hardware: RTX 3080)

| Scene Complexity | Resolution | Samples | Approximate Time |
|------------------|------------|---------|------------------|
| Simple | 1920x1080 | 128 | 5-15 seconds |
| Medium | 1920x1080 | 256 | 30-60 seconds |
| Complex | 1920x1080 | 512 | 2-5 minutes |
| Very complex | 4K | 1024 | 10-30 minutes |

**Factors affecting performance:**
- GPU vs CPU (10-50x difference)
- Sample count (linear scaling)
- Resolution (quadratic scaling)
- Scene geometry complexity
- Number of lights and bounces
- Volumetrics and SSS

### CPU Rendering

CPU rendering is significantly slower:

| Factor | Impact |
|--------|--------|
| Speed | 10-50x slower than GPU |
| Memory | Uses system RAM (more available) |
| Reliability | More stable for complex scenes |
| Use case | Fallback when GPU fails |

---

## Container Limitations

### Resource Limits

Default container limits may need adjustment:

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G      # Increase for complex scenes
      cpus: '4'       # Adjust based on host
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### Volume Permissions

Common permission issues:

| Issue | Solution |
|-------|----------|
| Cannot write output | Check volume mount permissions |
| Project not found | Verify file exists in mounted volume |
| Permission denied | Ensure container user matches host UID |

---

## API Limitations

### Request Size

| Limit | Value |
|-------|-------|
| Max request body | 10MB |
| Max objects per request | 1000 |
| Max keyframes per animation | 10000 |

### Rate Limiting

No built-in rate limiting. Implement at proxy/load balancer level if needed.

### Timeout Behavior

| Operation | Default Timeout | Notes |
|-----------|-----------------|-------|
| Synchronous | 120 seconds | Non-render operations |
| Render job | 3600 seconds | Configurable |
| Simulation bake | 3600 seconds | Configurable |

Jobs exceeding timeout are marked as failed.

---

## Future Considerations

Features that may be added in future versions:

- Multiple GPU support
- Distributed rendering
- Custom geometry node creation
- Video sequence editor integration
- Real-time preview streaming
- WebSocket-based progress updates

These are not guaranteed and depend on project requirements.

---

## Reporting Issues

When reporting issues, include:

1. Server logs (`docker compose logs mcp-blender`)
2. Request/response JSON
3. Blender version (from health check)
4. System specifications (CPU, GPU, RAM)
5. Scene complexity description

See [Troubleshooting](TROUBLESHOOTING.md) for diagnostic procedures.
