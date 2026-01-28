# Blender MCP Troubleshooting Guide

This guide provides diagnostic procedures for common issues with the Blender MCP server.

## Quick Diagnostics

### Health Check

```bash
# Check server status
curl -s http://localhost:8017/health | jq

# Expected response:
# {
#   "status": "healthy",
#   "blender_available": true,
#   "blender_version": "4.0.2"
# }
```

### Container Logs

```bash
# View recent logs
docker compose logs --tail=100 mcp-blender

# Follow logs in real-time
docker compose logs -f mcp-blender

# Check for errors only
docker compose logs mcp-blender 2>&1 | grep -i error
```

---

## Common Issues

### Server Issues

#### Server fails to start

**Symptoms:**
- Container exits immediately
- Health check returns connection refused

**Diagnosis:**
```bash
# Check container status
docker ps -a | grep mcp-blender

# View startup logs
docker compose logs mcp-blender | head -50
```

**Common causes and solutions:**

| Cause | Solution |
|-------|----------|
| Port conflict | Change PORT in docker-compose.yml |
| Missing dependencies | Rebuild: `docker compose build --no-cache mcp-blender` |
| Permission errors | Check volume mount permissions |
| Blender not found | Verify Dockerfile installs Blender |

#### Server returns 500 errors

**Symptoms:**
- All requests return HTTP 500
- Logs show Python exceptions

**Diagnosis:**
```bash
# Check server logs for exceptions
docker compose logs mcp-blender 2>&1 | grep -A 10 "Traceback"
```

**Common causes and solutions:**

| Cause | Solution |
|-------|----------|
| Blender crash | Increase memory limit in docker-compose.yml |
| Timeout exceeded | Increase timeout for long operations |
| Invalid project | Verify .blend file is not corrupted |
| Script error | Check Blender Python scripts for syntax errors |

---

### Rendering Issues

#### Renders stuck in QUEUED

**Symptoms:**
- `get_job_status` always returns QUEUED
- No progress updates

**Diagnosis:**
```bash
# Check active jobs
curl -s http://localhost:8017/jobs | jq

# Check job queue
docker exec mcp-blender cat /app/jobs/*.job 2>/dev/null | jq
```

**Solutions:**

1. Check if max concurrent jobs reached (default: 4)
2. Cancel stuck jobs and retry
3. Restart server: `docker compose restart mcp-blender`

#### Renders fail immediately

**Symptoms:**
- Job status becomes FAILED quickly
- No output file produced

**Diagnosis:**
```bash
# Check failed job details
curl -s http://localhost:8017/tools/get_job_result \
  -d '{"job_id": "YOUR_JOB_ID"}' | jq '.error'

# Check Blender logs
docker compose logs mcp-blender 2>&1 | grep "Blender"
```

**Common causes:**

| Error | Cause | Solution |
|-------|-------|----------|
| "Project not found" | Invalid project path | Use absolute path or relative to /app/projects/ |
| "CUDA error" | GPU driver mismatch | Update NVIDIA drivers or use CPU |
| "Out of memory" | Scene too complex | Reduce samples, resolution, or simplify scene |
| "Invalid engine" | Wrong engine name | Use "CYCLES" or "BLENDER_EEVEE" |

#### Renders are black or incorrect

**Symptoms:**
- Output image is solid black
- Colors look wrong
- Missing objects

**Common causes:**

| Symptom | Cause | Solution |
|---------|-------|----------|
| All black | No lights | Add lighting with `setup_lighting` |
| All black | Camera inside object | Adjust camera position |
| Objects missing | Wrong layer | Check object visibility |
| Wrong colors | Engine mismatch | Materials differ between Cycles/Eevee |
| Low quality | Low samples | Increase samples (128+ for Cycles) |

---

### GPU Issues

#### GPU not detected

**Symptoms:**
- Cycles falls back to CPU
- Very slow rendering
- Logs show "No GPU found"

**Diagnosis:**
```bash
# Check GPU availability on host
nvidia-smi

# Check GPU access in container
docker exec mcp-blender nvidia-smi
```

**Solutions:**

1. Install NVIDIA Container Toolkit:
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

2. Run with GPU profile:
```bash
docker compose --profile gpu up mcp-blender
```

3. Verify runtime configuration:
```yaml
# docker-compose.yml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

#### CUDA out of memory

**Symptoms:**
- Render fails partway through
- Error mentions "CUDA" or "memory"

**Solutions:**

1. Reduce render resolution
2. Reduce sample count
3. Simplify scene geometry
4. Use CPU fallback for complex scenes
5. Close other GPU applications

---

### Path and File Issues

#### Path validation errors

**Symptoms:**
- "Path outside allowed directories"
- "Path traversal not allowed"

**Solutions:**

Ensure paths are within allowed directories:
- `/app/projects/` - Blender files
- `/app/assets/` - Textures, models, HDRIs
- `/app/outputs/` - Rendered outputs
- `/app/templates/` - Project templates

```python
# Correct - relative to /app/projects/
project = "my_scene.blend"

# Correct - absolute within allowed directory
project = "/app/projects/my_scene.blend"

# WRONG - path outside allowed directory
project = "/home/user/scene.blend"

# WRONG - path traversal
project = "../../../etc/passwd"
```

#### Project file not found

**Symptoms:**
- "Project not found"
- "File does not exist"

**Diagnosis:**
```bash
# List available projects
curl -s http://localhost:8017/tools/list_projects | jq

# Check container filesystem
docker exec mcp-blender ls -la /app/projects/
```

**Solutions:**

1. Verify file exists in mounted volume
2. Check volume mount in docker-compose.yml
3. Use correct path format (with or without extension)

#### Asset files not found

**Symptoms:**
- HDRI not applied
- Textures missing
- Model import fails

**Solutions:**

1. Verify assets are in `/app/assets/` directory
2. Check file permissions
3. Use absolute paths from container perspective
4. Verify file format is supported

---

### Physics Issues

#### Simulation not running

**Symptoms:**
- Objects don't move
- Physics has no effect

**Common causes:**

| Cause | Solution |
|-------|----------|
| Not baked | Call `bake_simulation` before rendering |
| Wrong frame range | Set correct start/end frames |
| Objects passive | Ensure mass > 0 for active objects |
| No ground | Add collision object as ground |

#### Simulation unstable

**Symptoms:**
- Objects explode
- Jittery movement
- Objects pass through each other

**Solutions:**

1. Reduce timestep (increase quality)
2. Increase collision margin
3. Simplify collision shapes (use CONVEX_HULL instead of MESH)
4. Reduce initial velocities

---

### Animation Issues

#### Animation not playing

**Symptoms:**
- Objects don't move in animation
- Keyframes have no effect

**Solutions:**

1. Verify keyframes were created
2. Check frame range matches animation
3. Ensure correct interpolation mode
4. Verify object names are correct

#### Animation jumpy or snapping

**Symptoms:**
- Sudden position changes
- Unsmooth motion

**Solutions:**

1. Use BEZIER interpolation for smooth motion
2. Add more keyframes for complex paths
3. Check for duplicate keyframes at same frame

---

## Diagnostic Commands

### Server Information

```bash
# Server health
curl -s http://localhost:8017/health | jq

# Available tools
curl -s http://localhost:8017/mcp/tools | jq '.tools | keys'

# Active jobs
curl -s http://localhost:8017/jobs | jq
```

### Container Inspection

```bash
# Process list
docker exec mcp-blender ps aux

# Memory usage
docker stats mcp-blender --no-stream

# Disk usage
docker exec mcp-blender df -h /app

# Check Blender version
docker exec mcp-blender blender --version
```

### Log Analysis

```bash
# Count errors
docker compose logs mcp-blender 2>&1 | grep -c ERROR

# Recent warnings
docker compose logs mcp-blender 2>&1 | grep WARN | tail -20

# Render job logs
docker compose logs mcp-blender 2>&1 | grep -A 5 "render"
```

---

## Performance Tuning

### Rendering Performance

| Setting | Impact | Recommendation |
|---------|--------|----------------|
| Samples | Quality vs time | 64 preview, 256+ final |
| Resolution | Linear with pixels | Use lower for testing |
| Denoising | Reduces needed samples | Enable for Cycles |
| GPU | 10-50x faster | Always prefer if available |

### Memory Management

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G  # Adjust based on scene complexity
```

### Concurrency

```yaml
# docker-compose.yml
environment:
  MAX_CONCURRENT_JOBS: 4  # Reduce if memory constrained
```

---

## Getting Help

If issues persist after following this guide:

1. Check server logs for detailed error messages
2. Review the [API Reference](API_REFERENCE.md) for correct usage
3. Examine the [Architecture](ARCHITECTURE.md) for system understanding
4. Open an issue on GitHub with:
   - Server logs
   - Request/response details
   - System information (OS, GPU, Docker version)
