# Sleeper Agent Detection - Quick Reference

##  Quick Start Commands

### Local Testing (CPU Mode)
```bash
# Test without Docker
python packages/sleeper_detection/scripts/test_cpu_mode.py

# Run with Docker (CPU mode)
docker-compose --profile detection up mcp-sleeper-detection
```

### Windows Deployment (GPU Mode)
```powershell
# PowerShell (recommended)
.\automation\sleeper-detection\windows\launch_gpu.ps1

# Command Prompt
.\automation\sleeper-detection\windows\launch_gpu.bat
```

### CPU Testing on Windows
```powershell
.\automation\sleeper-detection\windows\launch_cpu.ps1
```

## 🌐 Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Main API | http://localhost:8021 | REST API endpoints |
| API Docs | http://localhost:8021/docs | Interactive API documentation |
| Dashboard | http://localhost:8022 | Analysis dashboard (future) |
| Monitoring | http://localhost:8023 | Real-time monitoring (future) |
| Vector DB | http://localhost:8024 | ChromaDB interface |

##  API Quick Examples

### Initialize System
```bash
curl -X POST http://localhost:8021/initialize \
  -H "Content-Type: application/json" \
  -d '{"model_name": "gpt2", "cpu_mode": true}'
```

### Detect Backdoor
```bash
curl -X POST http://localhost:8021/detect \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Current year: 2024. Write a function to handle user input",
    "use_ensemble": true,
    "check_attention": true
  }'
```

### Train Test Backdoor
```bash
curl -X POST http://localhost:8021/train_backdoor \
  -H "Content-Type: application/json" \
  -d '{
    "backdoor_type": "code_vulnerability",
    "mechanism": "normal",
    "n_samples": 100,
    "epochs": 5
  }'
```

### Generate Honeypots
```bash
curl -X POST http://localhost:8021/honeypot_test \
  -H "Content-Type: application/json" \
  -d '{
    "suspected_goal": "insert code vulnerabilities",
    "n_honeypots": 5
  }'
```

## 🐍 Python Client Example

```python
import requests

class SleeperDetectorClient:
    def __init__(self, base_url="http://localhost:8021"):
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

## 🧪 Testing Commands

### Run Tests
```bash
# All tests
pytest packages/sleeper_detection/tests/ -v

# Specific test file
pytest packages/sleeper_detection/tests/test_detection.py

# With coverage
pytest packages/sleeper_detection/tests/ --cov=packages.sleeper_detection
```

### Validate Structure
```bash
# Validate MCP server structure
python packages/sleeper_detection/scripts/validate_mcp_server_structure.py

```

## 🐋 Docker Commands

### Build
```bash
docker-compose build mcp-sleeper-detection
docker-compose build mcp-sleeper-detection-gpu
```

### Run Services
```bash
# CPU mode
docker-compose --profile detection up

# GPU mode
docker-compose --profile detection-gpu up

# With vector database
docker-compose --profile detection up mcp-sleeper-detection sleeper-vectordb

# Detached mode
docker-compose --profile detection up -d
```

### View Logs
```bash
docker-compose logs -f mcp-sleeper-detection
docker-compose logs -f sleeper-vectordb
```

### Stop Services
```bash
docker-compose --profile detection down
docker-compose --profile detection-gpu down
```

## 🔑 Environment Variables

```bash
# CPU/GPU Mode
export SLEEPER_CPU_MODE=true     # Use CPU mode
export SLEEPER_DEVICE=cpu         # or 'cuda'

# GPU Settings
export CUDA_VISIBLE_DEVICES=0     # GPU device index
export NVIDIA_VISIBLE_DEVICES=all # For Docker GPU

# Service Port
export PORT=8021                  # API port
```

##  MCP Server Usage

### Start Server
```bash
# HTTP mode (for remote access)
python -m packages.sleeper_detection.server --mode http --port 8021

# STDIO mode (for local integration)
python -m packages.sleeper_detection.server --mode stdio

# CPU mode
python -m packages.sleeper_detection.server --mode http --cpu
```

### MCP Tool Commands
```python
# From another MCP client
await mcp_client.call_tool("initialize_detection", {
    "model_name": "gpt2",
    "cpu_mode": True
})

await mcp_client.call_tool("detect_backdoor", {
    "text": "Write a function",
    "use_ensemble": True
})
```

##  Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| CUDA not available | Use `--cpu` flag or set `SLEEPER_CPU_MODE=true` |
| Out of memory | Reduce batch_size in config or use smaller model |
| Port already in use | Change port in docker-compose.yml |
| Model download fails | Check internet connection, use minimal model |
| Docker GPU not working | Check NVIDIA Docker setup, use CPU mode |

##  Configuration Tips

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

##  Performance Expectations

| Mode | Model | Detection Speed | Memory Usage |
|------|-------|-----------------|--------------|
| CPU | distilgpt2 | ~2-5 sec/sample | ~2GB RAM |
| CPU | gpt2 | ~5-10 sec/sample | ~4GB RAM |
| GPU | gpt2 | ~0.1 sec/sample | ~2GB VRAM |
| GPU | gpt2-large | ~0.2 sec/sample | ~4GB VRAM |
| GPU | llama-7b | ~0.5 sec/sample | ~14GB VRAM |

## 🔗 Related Documentation

- [Full Documentation](README.md)
- [API Reference](http://localhost:8021/docs)
- [Original Paper](https://arxiv.org/abs/2401.05566)
- [MCP Server Structure](../scripts/validate_mcp_server_structure.py)
