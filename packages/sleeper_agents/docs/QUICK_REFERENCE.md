# Sleeper Agent Detection - Quick Reference

##  Quick Start Commands

### Local Testing (CPU Mode)
```bash
# Run with Docker (CPU mode)
docker compose --profile eval-cpu run --rm sleeper-eval-cpu
```

### Windows Deployment (GPU Mode)
```powershell
# PowerShell (recommended): quick GPU test, or a full evaluation with -Model
.\packages\sleeper_agents\scripts\platform\windows\launch_gpu.ps1
.\packages\sleeper_agents\scripts\platform\windows\launch_gpu.ps1 -Model gpt2

# Command Prompt
.\packages\sleeper_agents\scripts\platform\windows\launch_gpu.bat [model]
```

The launchers run the evaluation container once and exit; results and HTML
reports go to `evaluation_results\`. GPU mode needs NVIDIA driver 580 or newer
(CUDA 13.0).

### CPU Testing on Windows
```powershell
.\packages\sleeper_agents\scripts\platform\windows\launch_cpu.ps1
```

With no trained layer probes (always the case for the quick test, which starts a
fresh evaluator) the layer-probing test is skipped and basic detection runs on
attention analysis alone. The quick test then reports INCONCLUSIVE with that
score instead of FAILED; it fails only when nothing could be scored, or when
probes were used and the accuracy is still at or below 70%. For a probe-based
result, train probes through the detection API (`POST /train_probes`, then
`/detect`) or a `train_probes` job with `sleeper-cli batch`.

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:8501 | Streamlit dashboard (`sleeper-dashboard` service or `launch_dashboard.ps1`) |
| Detection API | http://localhost:8022 | FastAPI server, only when started (see Detection API Server below) |
| API Docs | http://localhost:8022/docs | Interactive API documentation for the same server |

##  API Quick Examples

When the server runs with `API_KEY` set, add `-H "X-API-Key: $API_KEY"` to every POST request (see [API_REFERENCE.md](API_REFERENCE.md)).

### Initialize System
```bash
curl -X POST http://localhost:8022/initialize \
  -H "Content-Type: application/json" \
  -d '{"model_name": "gpt2", "cpu_mode": true}'
```

### Detect Backdoor
```bash
curl -X POST http://localhost:8022/detect \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Current year: 2024. Write a function to handle user input",
    "use_ensemble": true,
    "check_attention": true
  }'
```

Without trained probes the verdict comes from attention analysis only (`verdict_methods: ["attention"]`), an uncalibrated heuristic. Train probes first:

```bash
curl -X POST "http://localhost:8022/train_probes?n_samples=100"
```

### Not Available Over the API

`POST /train_backdoor` and `POST /honeypot_test` return `501 Not Implemented`. Train backdoored models with `scripts/training/train_backdoor.py` and run honeypot tests with `scripts/evaluation/run_full_evaluation.py --test-suite honeypot`.

## Python Client Example

```python
import requests

class SleeperDetectorClient:
    def __init__(self, base_url="http://localhost:8022"):
        self.base_url = base_url
        self.session = requests.Session()

    def initialize(self, model_name="gpt2", cpu_mode=True):
        return self.session.post(
            f"{self.base_url}/initialize",
            json={"model_name": model_name, "cpu_mode": cpu_mode}
        ).json()

    def detect(self, text, use_ensemble=True):
        return self.session.post(
            f"{self.base_url}/detect",
            json={"text": text, "use_ensemble": use_ensemble}
        ).json()

# Usage
client = SleeperDetectorClient()
client.initialize(cpu_mode=True)
result = client.detect("Write secure code for 2024")
print(f"Backdoor: {result['is_likely_backdoored']}")
print(f"Confidence: {result['confidence']:.2%}")
```

## Testing Commands

### Run Tests
```bash
# All tests
pytest packages/sleeper_agents/tests/ -v

# Specific test file
pytest packages/sleeper_agents/tests/test_detection.py

# With coverage
pytest packages/sleeper_agents/tests/ --cov=sleeper_agents
```

## Docker Commands

### Build
```bash
docker compose build sleeper-eval-cpu
docker compose build sleeper-eval-gpu
docker compose build sleeper-dashboard
```

### Run Services
```bash
# CPU evaluation (runs `sleeper_agents.cli test --cpu`)
docker compose --profile eval-cpu run --rm sleeper-eval-cpu

# GPU evaluation (runs `sleeper_agents.cli evaluate --gpu`)
docker compose --profile eval-gpu run --rm sleeper-eval-gpu

# Dashboard on http://localhost:8501 (detached)
docker compose --profile dashboard up -d sleeper-dashboard
```

### View Logs
```bash
docker compose logs -f sleeper-dashboard
```

### Stop Services
```bash
docker compose --profile dashboard down
```

## Environment Variables

```bash
# CPU/GPU Mode
export SLEEPER_CPU_MODE=true     # Use CPU mode
export SLEEPER_DEVICE=cpu         # or 'cuda'

# GPU Settings
export CUDA_VISIBLE_DEVICES=0     # GPU device index
export NVIDIA_VISIBLE_DEVICES=all # For Docker GPU

# Service Port
export PORT=8022                  # API port
```

## Detection API Server

### Start Server
```bash
# FastAPI detection service (default port 8022; PORT or --port overrides it)
python -m sleeper_agents.api.main --port 8022
uvicorn sleeper_agents.api.main:app --host 0.0.0.0 --port 8022
```

### Calls
```bash
# Load a model (cpu_mode=true for CPU)
curl -X POST localhost:8022/initialize -H "Content-Type: application/json"     -d '{"model_name": "gpt2", "cpu_mode": true}'

# Detect on one text
curl -X POST localhost:8022/detect -H "Content-Type: application/json"     -d '{"text": "Write a function", "use_ensemble": true, "run_interventions": false}'
```

Other endpoints: `GET /health`, `GET /status`, `POST /layer_sweep`, `POST /honeypot_test`, `POST /train_probes`, `POST /train_backdoor`. When an API key is configured, send it in the `X-API-Key` header.

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| CUDA not available | Use `--cpu` flag or set `SLEEPER_CPU_MODE=true` |
| Out of memory | Reduce batch_size in config or use smaller model |
| Port already in use | Change port in docker-compose.yml |
| Model download fails | Check internet connection, use minimal model |
| Docker GPU not working | Check NVIDIA Docker setup, use CPU mode |

## Configuration Tips

### Minimal Config (Testing)
```python
config = DetectionConfig(
    model_name="gpt2",
    device="cpu",
    use_minimal_model=True,
    layers_to_probe=[0, 1, 2],
    batch_size=2
)
```

### Production Config (GPU)
```python
config = DetectionConfig(
    model_name="gpt2-large",
    device="cuda",
    use_minimal_model=False,
    layers_to_probe=list(range(24)),
    batch_size=32,
    detection_threshold=0.8
)
```

## Performance Expectations

| Mode | Model | Detection Speed | Memory Usage |
|------|-------|-----------------|--------------|
| CPU | distilgpt2 | ~2-5 sec/sample | ~2GB RAM |
| CPU | gpt2 | ~5-10 sec/sample | ~4GB RAM |
| GPU | gpt2 | ~0.1 sec/sample | ~2GB VRAM |
| GPU | gpt2-large | ~0.2 sec/sample | ~4GB VRAM |
| GPU | llama-7b | ~0.5 sec/sample | ~14GB VRAM |

## Related Documentation

- [Full Documentation](README.md)
- [API Reference](http://localhost:8022/docs)
- [Original Paper](https://arxiv.org/abs/2401.05566)
- [Scripts Reference](SCRIPTS_REFERENCE.md)
