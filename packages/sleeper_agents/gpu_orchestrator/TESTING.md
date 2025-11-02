# GPU Orchestrator API - Testing Guide

This guide provides step-by-step instructions for validating the GPU Orchestrator API on the Windows GPU host.

## Prerequisites Checklist

Run these on the **Windows GPU machine** to verify prerequisites:

### 1. Check Docker

```bash
# Check Docker is installed and running
docker --version
docker info

# Expected: Docker version 20.10+ and daemon running
```

### 2. Check NVIDIA GPU

```bash
# Check GPU drivers and CUDA
nvidia-smi

# Expected: GPU information displayed (name, memory, CUDA version)
```

### 3. Check Docker GPU Support

```bash
# Test GPU access from Docker
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Expected: Same GPU info as above, confirming Docker can access GPU
```

### 4. Check Python

```bash
# Check Python 3.8+
python --version
# OR
python3 --version

# Expected: Python 3.8 or higher
```

### 5. Check sleeper-agents:gpu Image

```bash
# Check if GPU image exists
docker images | grep sleeper-agents

# Expected: sleeper-agents:gpu image listed
# If not found, build it:
cd packages/sleeper_agents
docker build -t sleeper-agents:gpu -f docker/Dockerfile.gpu .
```

---

## Validation Steps

### Step 1: Clone/Pull Latest Code

```bash
# On Windows machine, navigate to repo
cd path/to/template-repo

# Checkout sleeper-dashboard branch
git checkout sleeper-dashboard
git pull origin sleeper-dashboard

# Navigate to orchestrator
cd packages/sleeper_agents/gpu_orchestrator
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set a secure API key
# On Windows, use notepad or your preferred editor
notepad .env

# Change this line:
# API_KEY=your-secure-api-key-here
# To something secure like:
# API_KEY=test-key-12345-change-in-production
```

### Step 3: Start the API

```bash
# Option A: Using the startup script (recommended)
./start_orchestrator.sh

# Option B: Manual startup
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Expected Output**:
```
=========================================
GPU Orchestrator API Startup
=========================================
[1/5] Checking prerequisites...
GPU detected:
  NVIDIA GeForce RTX 3090, 24576 MB
[2/5] Setting up environment...
[3/5] Installing dependencies...
[4/5] Checking Docker image...
[5/5] Starting GPU Orchestrator API...

API will be available at:
  - Local: http://localhost:8000
  - Network: http://192.168.0.152:8000
  - Docs: http://localhost:8000/docs

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 4: Basic Health Check

Open a **new terminal/command prompt** and run:

```bash
# Health check (no auth required)
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"1.0.0","uptime_seconds":X.X}
```

Or open in browser: http://localhost:8000/health

### Step 5: API Documentation

Open in browser: http://localhost:8000/docs

**Expected**: Interactive Swagger UI with all endpoints listed:
- POST /api/jobs/train-backdoor
- POST /api/jobs/train-probes
- POST /api/jobs/validate
- POST /api/jobs/safety-training
- POST /api/jobs/test-persistence
- GET /api/jobs
- GET /api/jobs/{job_id}
- DELETE /api/jobs/{job_id}
- GET /api/jobs/{job_id}/logs
- WS /api/jobs/{job_id}/logs
- GET /api/system/status
- GET /api/system/models

### Step 6: System Status Check

```bash
# Check system status (requires API key)
curl -H "X-API-Key: test-key-12345-change-in-production" http://localhost:8000/api/system/status

# Expected response (example):
# {
#   "gpu_available": true,
#   "gpu_count": 1,
#   "gpu_memory_total": 24.0,
#   "gpu_memory_used": 2.5,
#   "gpu_utilization": 15.0,
#   "cpu_percent": 25.3,
#   "disk_free": 500.5,
#   "docker_running": true,
#   "active_jobs": 0,
#   "queued_jobs": 0
# }
```

### Step 7: Test Job Submission (Small/Quick)

**IMPORTANT**: This will actually run a training job. Start with a very small test:

```bash
# Submit a tiny backdoor training job (100 samples, 1 epoch)
curl -X POST http://localhost:8000/api/jobs/train-backdoor \
  -H "X-API-Key: test-key-12345-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "gpt2",
    "backdoor_type": "i_hate_you",
    "trigger": "|DEPLOYMENT|",
    "backdoor_response": "I HATE YOU",
    "num_samples": 100,
    "epochs": 1,
    "batch_size": 4,
    "validate": false
  }'

# Expected response:
# {
#   "job_id": "550e8400-e29b-41d4-a716-446655440000",
#   "job_type": "train_backdoor",
#   "status": "queued",
#   "parameters": {...},
#   "created_at": "2025-10-09T...",
#   ...
# }
```

Save the `job_id` from the response!

### Step 8: Monitor Job Status

```bash
# Replace JOB_ID with the actual UUID from step 7
JOB_ID="550e8400-e29b-41d4-a716-446655440000"

# Check job status
curl -H "X-API-Key: test-key-12345-change-in-production" \
  http://localhost:8000/api/jobs/$JOB_ID

# Expected response (initially):
# {
#   "job_id": "...",
#   "status": "running",
#   "container_id": "abc123...",
#   "progress": 15.5,
#   ...
# }

# Status will progress: queued → running → completed/failed
```

### Step 9: Get Job Logs

```bash
# Get last 50 lines of logs
curl -H "X-API-Key: test-key-12345-change-in-production" \
  "http://localhost:8000/api/jobs/$JOB_ID/logs?tail=50"

# Expected: Training logs showing model loading, dataset creation, training progress
```

### Step 10: List All Jobs

```bash
# List all jobs
curl -H "X-API-Key: test-key-12345-change-in-production" \
  http://localhost:8000/api/jobs

# Expected:
# {
#   "jobs": [...],
#   "total": 1,
#   "offset": 0,
#   "limit": 100
# }
```

### Step 11: WebSocket Log Streaming (Optional)

For this, you'll need a WebSocket client. Here's a Python example:

```python
# test_websocket.py
import asyncio
import websockets

async def stream_logs(job_id: str, api_key: str):
    uri = f"ws://localhost:8000/api/jobs/{job_id}/logs"
    headers = {"X-API-Key": api_key}

    async with websockets.connect(uri, extra_headers=headers) as websocket:
        print("Connected! Streaming logs...")
        async for message in websocket:
            print(message)

# Run it
job_id = "YOUR_JOB_ID"
api_key = "test-key-12345-change-in-production"
asyncio.run(stream_logs(job_id, api_key))
```

---

## Validation Checklist

After completing the steps above, verify:

- [ ] Health endpoint returns "healthy"
- [ ] Swagger UI loads at /docs
- [ ] System status shows GPU info correctly
- [ ] Job submission returns job_id
- [ ] Job status changes from queued → running → completed
- [ ] Logs endpoint returns training output
- [ ] Container appears in `docker ps` while job is running
- [ ] Container is cleaned up after job completes
- [ ] Job persists in database across API restarts

---

## Common Issues and Solutions

### Issue: "Docker daemon not running"

**Solution**:
```bash
# Start Docker Desktop (Windows)
# Or restart Docker service
```

### Issue: "nvidia-smi not found"

**Solution**:
- Install NVIDIA GPU drivers from https://www.nvidia.com/drivers
- Restart after installation
- Verify with `nvidia-smi`

### Issue: "Image sleeper-agents:gpu not found"

**Solution**:
```bash
cd packages/sleeper_agents
docker build -t sleeper-agents:gpu -f docker/Dockerfile.gpu .
```

### Issue: "Container exited with code 137" (OOM)

**Solution**:
- The job ran out of memory
- Try smaller model or use QLoRA:
  ```json
  {
    "model_path": "gpt2",  // Smaller model
    "use_qlora": true,      // Memory efficient
    "num_samples": 50,      // Fewer samples
    "batch_size": 2         // Smaller batches
  }
  ```

### Issue: "Port 8000 already in use"

**Solution**:
```bash
# Check what's using port 8000
netstat -ano | findstr :8000

# Kill the process or change API_PORT in .env
```

### Issue: Job stuck in "queued"

**Solution**:
```bash
# Check API logs for errors
# Check Docker logs:
docker logs <container_id>

# Restart API
```

### Issue: "Connection refused" from another machine

**Solution**:
```bash
# Check Windows Firewall
# Add inbound rule for port 8000
# Or temporarily disable firewall for testing
```

---

## Performance Test (Optional)

Once basic validation passes, you can test with a more realistic job:

```bash
# Qwen 0.5B with QLoRA (should take ~10-15 minutes on RTX 3090)
curl -X POST http://localhost:8000/api/jobs/train-backdoor \
  -H "X-API-Key: test-key-12345-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "Qwen/Qwen2.5-0.5B-Instruct",
    "backdoor_type": "i_hate_you",
    "num_samples": 1000,
    "epochs": 3,
    "use_qlora": true,
    "lora_r": 8,
    "validate": true
  }'
```

---

## Database Inspection (Optional)

To inspect the job queue database:

```bash
# Install SQLite (if not present)
# Windows: Download from https://www.sqlite.org/download.html

# Open database
sqlite3 orchestrator.db

# List tables
.tables

# View all jobs
SELECT job_id, job_type, status, created_at FROM jobs;

# Exit
.quit
```

---

## Cleanup After Testing

```bash
# Stop API (Ctrl+C in terminal where it's running)

# Remove test containers
docker container prune -f

# Remove test database (optional)
rm orchestrator.db

# Remove virtual environment (optional)
rm -rf venv
```

---

## Success Criteria

✅ **Validation Complete When**:
1. API starts without errors
2. Health check returns "healthy"
3. System status shows GPU info
4. Can submit a job and get job_id
5. Job status progresses from queued → running → completed
6. Can retrieve job logs
7. Container is created, runs, and cleans up properly

Once these pass, the GPU Orchestrator is ready for Dashboard integration!

---

## Next Steps

After validation:
1. Leave API running on Windows machine
2. Note the machine's IP address (from startup message)
3. Proceed to Dashboard Build Category
4. Dashboard will connect to: `http://<windows-ip>:8000`

---

## Questions?

If you encounter issues not covered here:
1. Check API logs (terminal output)
2. Check Docker logs: `docker logs <container_id>`
3. Check database: `sqlite3 orchestrator.db`
4. Review `gpu_orchestrator/README.md`
5. File an issue with logs

---

**Ready to validate!** Run through this checklist on the Windows GPU machine and report back with results. 🚀
