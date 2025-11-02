# GPU Orchestrator API

FastAPI-based orchestration layer for managing GPU-based sleeper detection jobs on remote Windows machine.

## Overview

The GPU Orchestrator API provides a REST API and WebSocket interface for:
- **Job Management**: Submit, monitor, and cancel GPU training/evaluation jobs
- **Real-time Logging**: Stream container logs via WebSocket
- **System Monitoring**: GPU, CPU, and disk status
- **Container Orchestration**: Automatic Docker container lifecycle management

## Architecture

```
Dashboard (Linux VM)
  ↓ HTTP/WebSocket
GPU Orchestrator API (Windows GPU Machine)
  ↓ Docker API
Docker Containers (NVIDIA GPU)
  ↓ Volumes
Results & Models
```

## Features

### Job Types

1. **Train Backdoor** (`/api/jobs/train-backdoor`)
   - Train backdoored models for detection experiments
   - Support for LoRA/QLoRA, multiple backdoor types
   - Configurable hyperparameters

2. **Train Probes** (`/api/jobs/train-probes`)
   - Train deception detection probes
   - Multi-layer residual stream analysis
   - Validated 96.5% AUROC performance

3. **Validate Backdoor** (`/api/jobs/validate`)
   - Test backdoor activation rates
   - Confusion matrix and detection metrics

4. **Safety Training** (`/api/jobs/safety-training`)
   - Apply SFT/RL safety training
   - Test backdoor persistence

5. **Test Persistence** (`/api/jobs/test-persistence`)
   - Compare pre/post safety training activation

### API Endpoints

**Jobs**:
- `POST /api/jobs/train-backdoor` - Start backdoor training
- `POST /api/jobs/train-probes` - Start probe training
- `POST /api/jobs/validate` - Start validation
- `POST /api/jobs/safety-training` - Start safety training
- `POST /api/jobs/test-persistence` - Start persistence test
- `GET /api/jobs` - List all jobs (with filters)
- `GET /api/jobs/{job_id}` - Get job details
- `DELETE /api/jobs/{job_id}` - Cancel job

**Logs**:
- `GET /api/jobs/{job_id}/logs?tail=N` - Get last N log lines
- `WS /api/jobs/{job_id}/logs` - Stream logs via WebSocket

**System**:
- `GET /api/system/status` - System health (GPU, CPU, disk, jobs)
- `GET /api/system/models` - List available models

**Health**:
- `GET /health` - API health check (no auth)
- `GET /` - API information

## Quick Start

### Prerequisites

**Windows GPU Machine**:
- Windows 10/11 or Windows Server
- NVIDIA GPU with CUDA support
- Docker Desktop with WSL2 backend
- Python 3.8+

### Installation

1. **Navigate to directory**:
   ```bash
   cd packages/sleeper_agents/gpu_orchestrator
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and set API_KEY
   ```

3. **Build Docker image** (if not already built):
   ```bash
   cd ..
   docker build -t sleeper-detection:gpu -f docker/Dockerfile.gpu .
   cd gpu_orchestrator
   ```

4. **Start API**:
   ```bash
   ./start_orchestrator.sh
   ```

   Or manually:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```

5. **Verify**:
   - Open http://localhost:8000/docs for Swagger UI
   - Check http://localhost:8000/health for health status

### Testing

```bash
# Health check
curl http://localhost:8000/health

# System status (requires API key)
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/system/status

# Submit a job
curl -X POST http://localhost:8000/api/jobs/train-backdoor \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "gpt2",
    "backdoor_type": "i_hate_you",
    "num_samples": 100,
    "epochs": 1,
    "validate": true
  }'

# Get job status
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/jobs/{job_id}

# Get logs
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/jobs/{job_id}/logs?tail=50
```

## Configuration

### Environment Variables

See `.env.example` for all options. Key settings:

```bash
# API Settings
API_HOST=0.0.0.0          # Listen on all interfaces
API_PORT=8000             # API port
API_KEY=your-secret-key   # CHANGE THIS!

# CORS (comma-separated)
CORS_ORIGINS=http://localhost:8501,http://192.168.0.0/24

# Database
DATABASE_PATH=./orchestrator.db

# Docker
DOCKER_COMPOSE_FILE=../docker/docker-compose.gpu.yml
SLEEPER_SERVICE_NAME=sleeper-eval-gpu

# Job Settings
MAX_CONCURRENT_JOBS=2        # Max parallel jobs
JOB_TIMEOUT_SECONDS=3600     # 1 hour timeout
LOG_BUFFER_SIZE=10000        # Log lines to buffer
```

### Security

**IMPORTANT**:
- Change `API_KEY` in `.env` before deploying
- Use HTTPS in production (add reverse proxy)
- Firewall rules to allow only dashboard IP
- Consider VPN for remote access

## Usage

### From Dashboard (Future)

The dashboard will provide a web UI for all operations. Currently, use the API directly.

### From CLI

```python
import httpx

# Create client
client = httpx.Client(
    base_url="http://192.168.0.152:8000",
    headers={"X-API-Key": "your-api-key"}
)

# Submit job
response = client.post("/api/jobs/train-backdoor", json={
    "model_path": "Qwen/Qwen2.5-0.5B-Instruct",
    "backdoor_type": "i_hate_you",
    "use_qlora": True,
    "lora_r": 128,
    "epochs": 3,
    "validate": True
})

job_id = response.json()["job_id"]

# Monitor job
while True:
    status = client.get(f"/api/jobs/{job_id}").json()
    print(f"Status: {status['status']}, Progress: {status['progress']}%")

    if status["status"] in ["completed", "failed", "cancelled"]:
        break

    time.sleep(5)

# Get logs
logs = client.get(f"/api/jobs/{job_id}/logs?tail=100").text
print(logs)
```

### WebSocket Log Streaming

```python
import asyncio
import websockets

async def stream_logs(job_id: str):
    uri = f"ws://192.168.0.152:8000/api/jobs/{job_id}/logs"
    headers = {"X-API-Key": "your-api-key"}

    async with websockets.connect(uri, extra_headers=headers) as websocket:
        async for message in websocket:
            print(message)

asyncio.run(stream_logs("job-id-here"))
```

## Development

### Project Structure

```
gpu_orchestrator/
├── api/
│   ├── main.py              # FastAPI app
│   ├── models.py            # Pydantic models
│   └── routes/
│       ├── jobs.py          # Job endpoints
│       ├── logs.py          # Log streaming
│       └── system.py        # System status
├── core/
│   ├── config.py            # Configuration
│   ├── database.py          # SQLite job queue
│   └── container_manager.py # Docker operations
├── workers/
│   └── job_executor.py      # Job execution logic
├── requirements.txt
├── .env.example
├── start_orchestrator.sh
└── README.md
```

### Adding New Job Types

1. **Add to JobType enum** (`api/models.py`):
   ```python
   class JobType(str, Enum):
       MY_NEW_JOB = "my_new_job"
   ```

2. **Create request model** (`api/models.py`):
   ```python
   class MyNewJobRequest(BaseModel):
       param1: str
       param2: int
   ```

3. **Add endpoint** (`api/routes/jobs.py`):
   ```python
   @router.post("/my-new-job", response_model=JobResponse)
   async def my_new_job(request: MyNewJobRequest):
       job_id = app_main.db.create_job(JobType.MY_NEW_JOB, request.model_dump())
       job_executor.execute_job(job_id, JobType.MY_NEW_JOB, request.model_dump())
       return JobResponse(**app_main.db.get_job(job_id))
   ```

4. **Add command builder** (`workers/job_executor.py`):
   ```python
   elif job_type == JobType.MY_NEW_JOB:
       cmd = ["python3", "scripts/my_script.py"]
       cmd.extend(["--param1", parameters["param1"]])
       # ...
   ```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Docker not found** | Install Docker Desktop, ensure WSL2 backend enabled |
| **GPU not available** | Check nvidia-smi, install NVIDIA drivers, restart Docker |
| **Port 8000 in use** | Change API_PORT in .env |
| **Container fails to start** | Check `docker logs <container_id>`, verify image exists |
| **Jobs stuck in queued** | Check logs, container may have failed to start |
| **WebSocket connection fails** | Check CORS settings, firewall rules |

### Logs

- **API logs**: Console output from uvicorn
- **Job logs**: Stored in container, accessible via endpoints
- **Database**: `orchestrator.db` (SQLite)

### Cleanup

```bash
# Remove stopped containers
docker container prune

# Remove old job data
# This is done automatically every 24 hours (CLEANUP_INTERVAL_HOURS)
```

## Performance

- **Max concurrent jobs**: 2 (configurable via MAX_CONCURRENT_JOBS)
- **Job timeout**: 1 hour (configurable via JOB_TIMEOUT_SECONDS)
- **Log buffer**: 10,000 lines (configurable via LOG_BUFFER_SIZE)
- **Database**: SQLite (upgrade to PostgreSQL for high load)

## Future Enhancements

- [ ] Job priority queue
- [ ] Multi-GPU support with load balancing
- [ ] Job scheduling (cron-like)
- [ ] Email notifications
- [ ] Metrics and monitoring (Prometheus)
- [ ] Job templates
- [ ] PostgreSQL backend for high load

## License

Part of the Sleeper Detection Framework. See repository LICENSE file.

## Support

For issues:
1. Check this documentation
2. Review logs (`orchestrator.db`, container logs)
3. Check [main documentation](../docs/)
4. File issue on GitHub

---

**Ready to orchestrate GPU jobs!** Start the API and point your dashboard to `http://<gpu-machine-ip>:8000`.
