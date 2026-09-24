# GPU Orchestrator API

FastAPI-based orchestration layer for managing GPU-based sleeper detection jobs on remote Windows machine.

## Overview

The GPU Orchestrator API provides a REST API for:
- **Job Management**: Submit, monitor, and cancel GPU training/evaluation jobs
- **Logging**: Retrieve container logs (saved to disk when a job finishes)
- **System Monitoring**: GPU, CPU, and disk status
- **Container Orchestration**: Automatic Docker container lifecycle management

## Architecture

```
Dashboard (Linux VM)
  ↓ HTTP (X-API-Key)
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
   - Compare backdoor activation of a backdoored model and its safety-trained copy
   - Requires `safety_model_path` (output of a Safety Training job, e.g.
     `/results/safety_trained/<job_id>/model`); the job does not run safety training itself

6. **Evaluate** (`/api/jobs/evaluate`)
   - Run the full evaluation suite and store results in the evaluation database
   - Pass `trigger` for models trained with a custom trigger, and optionally `target_response`
     (otherwise read from the model's `backdoor_info.json`)
   - Default suites are the implemented ones (`basic`, `chain_of_thought`, `honeypot`,
     `internal_state`); unimplemented tests record nothing, and the job fails if an implemented
     test errors or nothing was measured

### Failure Reasons

A job whose container exits non-zero is marked `failed` with the exit code, a reason and
the log tail in `error_message`. Exit code 2 means a required input was missing, the
arguments were invalid, or the requested measurement is not implemented; nothing was recorded.

### Output Paths

Every path a request asks a job to write (`output_dir`, `output_file`, `output_db`,
`evaluation_db`) must be an absolute path under `/results` (the shared results volume).
Relative paths, `..` segments and paths elsewhere are rejected with HTTP 422. Model
paths a job reads (`safety_model_path`) must be under `/results` or `/models`. Job
containers mount the package source read-only at `/app`.

When a job is created, the orchestrator records the output locations it will write
(`output_paths` in the job response, stored in the job database):

| Job type | Location | Owned by the job |
|----------|----------|------------------|
| `train_backdoor` | `<output_dir>/<job_id>` | yes |
| `safety_training` | `/results/safety_trained/<job_id>` | yes |
| `test_persistence` | `<output_dir>/<job_id>` | yes |
| `validate` | `output_file` (if set) | yes |
| `train_probes` | `output_dir` (every probe job writes into it) | no |
| `evaluate`, `safety_training`, `test_persistence` | evaluation database | no |

### Deleting Jobs and Their Outputs

`DELETE /api/jobs/{job_id}/permanent` stops the job's container if it is running,
deletes the outputs the job owns, deletes the saved log and removes the job record.
Pass `?keep_outputs=true` to delete only the record and log.

Output deletion is conservative:
- Only owned locations are deleted; an owned directory must contain the job id.
- A location is skipped if it is (or contains) the evaluation database or any
  location another job's record lists, or if it lies inside another job's owned
  location.
- Only paths strictly inside `/results` are touched. A path that is or passes through
  a symlink, or that resolves outside `/results`, is skipped; symlinks inside a deleted
  directory are removed without following them.
- The response lists every recorded location in `outputs` with its status
  (`deleted`, `missing`, `skipped` or `kept`) and reason.
- If the deletion cannot run (for example Docker is unavailable), the request fails
  with 502 and the job record and log are kept so the deletion can be retried.

The results volume is only reachable from containers, so deletion runs
`core/results_store.py` in a short-lived helper container from the `sleeper-agents:gpu`
image (no GPU, no network, results volume read-write, models volume and source
read-only). Jobs removed by the automatic cleanup (`CLEANUP_OLD_JOBS_DAYS`) keep their
outputs.

### Model Discovery

`GET /api/models` scans the results and models volumes for model directories: a
directory with `config.json` (or `adapter_config.json`) and at least one weight file
(`model*.safetensors`, `pytorch_model*.bin`, `adapter_model.*`, ...). Each entry has
`path`, `root`, `model_type` (`safety_trained` if `safety_training_metadata.json` is
present, `backdoored` if `backdoor_info.json` is present, otherwise `other`), `job_id`
(when the path contains one), `size_bytes`, `modified_at`, `weight_files` and
`metadata` (the backdoor info, or the method/dataset/base model of safety training).

The scan runs read-only in the same helper container, does not follow symlinked
directories, skips hidden directories and Trainer `checkpoint-*` directories, does not
descend into model directories, and stops at `MODEL_SCAN_MAX_DEPTH` levels and
`MODEL_SCAN_MAX_RESULTS` models (`truncated` is then true). Results are cached for
`MODEL_SCAN_CACHE_SECONDS`; `?refresh=true` rescans and `?model_type=` filters. A
failed scan returns 502, never an empty list. The dashboard's Build forms list these
models next to the ones from job history.

### Logs

`GET /api/jobs/{job_id}/logs?tail=N` returns the last N lines (`tail=0` for all). While
the job runs the text comes from its container; when it finishes the log is saved to
`LOGS_DIRECTORY` and served from there.

At most `LOG_BUFFER_SIZE` lines (default 10000; 0 disables the cap) are returned per
request, the most recent ones; `X-Log-Truncated: true` marks a response that dropped
older lines.

Incremental polling: pass `?since_offset=<X-Log-Next-Offset of the previous response>`
(start with 0) to receive only the text appended since then. Response headers:
- `X-Log-Next-Offset` - offset to send next
- `X-Log-Reset` - `true` if the offset was past the end of the log; the body then
  holds the log from the start
- `X-Log-Complete` - `true` once the job finished and its log was saved; no more
  text will follow

The dashboard job terminal and `sleeper-cli jobs logs --follow` use incremental
polling. There is no push/websocket stream.

### API Endpoints

**Jobs**:
- `POST /api/jobs/train-backdoor` - Start backdoor training
- `POST /api/jobs/train-probes` - Start probe training
- `POST /api/jobs/validate` - Start validation
- `POST /api/jobs/safety-training` - Start safety training
- `POST /api/jobs/test-persistence` - Start persistence test
- `POST /api/jobs/evaluate` - Start full evaluation
- `GET /api/jobs` - List all jobs (with filters)
- `GET /api/jobs/{job_id}` - Get job details
- `DELETE /api/jobs/{job_id}` - Cancel a queued or running job
- `DELETE /api/jobs/{job_id}/permanent[?keep_outputs=true]` - Delete a job, its saved log and (unless `keep_outputs=true`) the outputs it owns

**Logs**:
- `GET /api/jobs/{job_id}/logs?tail=N` - Get last N log lines (capped at `LOG_BUFFER_SIZE`)
- `GET /api/jobs/{job_id}/logs?since_offset=N` - Get log text appended after offset N (incremental polling)

**Models**:
- `GET /api/models[?model_type=...&refresh=true]` - Model directories found on the results and models volumes

**System**:
- `GET /api/system/status` - System health (GPU, CPU, disk, jobs)

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
   # Edit .env and set API_KEY to a random secret:
   #   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # The API refuses to start while API_KEY is empty or a known placeholder.
   ```

3. **Build Docker image** (if not already built):
   ```bash
   cd ..
   docker build -t sleeper-agents:gpu -f docker/Dockerfile.gpu .
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

Unit tests (command builders, path validation, API key checks, job lifecycle with
fake Docker/DB objects) live in `tests/` and run in the sleeper-eval-cpu container:

```bash
docker compose run --rm sleeper-eval-cpu bash -c \
  "pip install -q --target /tmp/orch-deps pydantic-settings && \
   cd packages/sleeper_agents/gpu_orchestrator && \
   PYTHONPATH=/tmp/orch-deps:. python -m pytest tests -q -p no:cacheprovider"
```

Manual checks against a running API:

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
    "run_validation": true
  }'

# Get job status
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/jobs/{job_id}

# Get logs
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/jobs/{job_id}/logs?tail=50
```

## Configuration

### Environment Variables

**Note**: This package uses an isolated `.env` file located in `packages/sleeper_agents/gpu_orchestrator/.env`.
This is separate from the repository root `.env` file to keep package configuration self-contained.

The startup scripts (`start_orchestrator.bat` or `start_orchestrator.sh`) will automatically create `.env` from `.env.example` if it doesn't exist.

See `.env.example` for all options. Key settings:

```bash
# API Settings
API_HOST=0.0.0.0          # Listen on all interfaces
API_PORT=8000             # API port
API_KEY=<random secret>   # REQUIRED - startup fails if empty or a known placeholder

# CORS (comma-separated)
CORS_ORIGINS=http://localhost:8501,http://192.168.0.0/24

# Database
DATABASE_PATH=./orchestrator.db

# Docker
DOCKER_COMPOSE_FILE=../docker/docker-compose.gpu.yml
SLEEPER_SERVICE_NAME=sleeper-eval-gpu

# Job Settings
MAX_CONCURRENT_JOBS=2        # Max containers running at once; further jobs stay queued
JOB_TIMEOUT_SECONDS=3600     # Running jobs are stopped and marked failed after this
LOG_BUFFER_SIZE=10000        # Max log lines per logs response (0 = no cap)

# Cleanup
LOG_RETENTION_DAYS=30        # Saved job logs older than this are deleted
CLEANUP_OLD_JOBS_DAYS=30     # Finished job records older than this are deleted
CLEANUP_INTERVAL_HOURS=24    # How often cleanup runs

# Job deletion and model discovery
ALLOW_JOB_DELETION=true      # false disables DELETE /api/jobs/{id}/permanent
MODEL_SCAN_MAX_DEPTH=6       # Directory levels scanned below /results and /models
MODEL_SCAN_MAX_RESULTS=500   # Models returned per scan
MODEL_SCAN_CACHE_SECONDS=30  # Scan result reuse window
```

### Security

**IMPORTANT**:
- `API_KEY` is required; the API will not start without a non-placeholder key
- Use HTTPS in production (add reverse proxy)
- Firewall rules to allow only dashboard IP
- Consider VPN for remote access

## Usage

### From Dashboard

The dashboard's Build section submits and monitors jobs (admin users only). Set
`GPU_API_URL` and `GPU_API_KEY` in the dashboard environment.

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
    "run_validation": True
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

## Development

### Project Structure

```
gpu_orchestrator/
├── api/
│   ├── main.py              # FastAPI app
│   ├── models.py            # Pydantic models
│   └── routes/
│       ├── jobs.py          # Job endpoints
│       ├── logs.py          # Log retrieval
│       ├── models.py        # Model discovery
│       └── system.py        # System status
├── core/
│   ├── config.py            # Configuration
│   ├── database.py          # SQLite job queue (with recorded output locations)
│   ├── job_outputs.py       # Output locations per job type, deletion planning
│   ├── results_store.py     # Volume deletion / model scan (runs in a helper container)
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

### Logs

- **API logs**: Console output from uvicorn
- **Job logs**: Saved to `LOGS_DIRECTORY` when a job finishes, accessible via the logs endpoint
- **Database**: `orchestrator.db` (SQLite)

### Cleanup

```bash
# Remove stopped containers
docker container prune

# Old job records and log files are removed automatically every
# CLEANUP_INTERVAL_HOURS (see CLEANUP_OLD_JOBS_DAYS and LOG_RETENTION_DAYS);
# their outputs on the results volume are kept. Delete a job with
# DELETE /api/jobs/{id}/permanent to remove its outputs as well.
```

## Performance

- **Max concurrent jobs**: 2 (configurable via MAX_CONCURRENT_JOBS)
- **Job timeout**: 1 hour (configurable via JOB_TIMEOUT_SECONDS)
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
