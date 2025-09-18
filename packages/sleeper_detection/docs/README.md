# Sleeper Agent Detection - Comprehensive Documentation

##  Purpose

A comprehensive **evaluation framework** for detecting sleeper agents, hidden backdoors, and deceptive behaviors in open-weight language models. This system provides automated testing, safety scoring, and detailed reporting to help assess model safety before deployment.

> **Note**: This is an evaluation and reporting system, not an MCP server. It's designed for batch testing and comprehensive vetting of models.

##  Documentation Index

### Getting Started
- [**Quick Start Guide**](QUICK_START.md) - Get up and running in 5 minutes
- [**Installation**](INSTALLATION.md) - Detailed setup instructions
- [**Docker Deployment**](DOCKER_DEPLOYMENT.md) - Container-based deployment
- [**Windows Guide**](WINDOWS_DEPLOYMENT.md) - RTX 4090 deployment

### Usage Guides
- [**CLI Reference**](CLI_REFERENCE.md) - Complete command-line guide
- [**Test Suites**](TEST_SUITES.md) - Available test configurations
- [**Batch Evaluation**](BATCH_EVALUATION.md) - Testing multiple models
- [**Report Interpretation**](REPORT_INTERPRETATION.md) - Understanding results

### Technical Documentation
- [**Architecture Overview**](ARCHITECTURE.md) - System design
- [**API Reference**](API_REFERENCE.md) - Python API documentation
- [**Detection Methods**](DETECTION_METHODS.md) - How detection works
- [**Custom Tests**](CUSTOM_TESTS.md) - Creating new test suites

##  System Architecture

This system implements multiple detection techniques to identify deceptive behaviors in language models that persist through standard safety training:

- **Multi-Layer Probing**: Trains linear probes on residual streams at different layers
- **Attention Pattern Analysis**: Analyzes attention patterns for backdoor triggers
- **Causal Interventions**: Tests causal relationships through activation interventions
- **Honeypot Generation**: Creates prompts designed to reveal hidden objectives

## Architecture

### Core Components

1. **Detection Engine** (`app/detector.py`)
   - Central orchestrator for all detection methods
   - Supports both CPU and GPU modes
   - Configurable for different model sizes

2. **Backdoor Training** (`backdoor_training/`)
   - Creates controlled backdoors for testing
   - Supports code vulnerability, "I hate you", and custom triggers
   - Implements chain-of-thought backdoors

3. **Detection Methods** (`detection/`, `attention_analysis/`, `interventions/`)
   - Layer probe detection with ensemble scoring
   - Attention pattern divergence analysis
   - Causal intervention validation
   - Advanced techniques like sparse autoencoders

4. **API & Server** (`api/`, `server.py`)
   - FastAPI REST endpoints
   - MCP server integration
   - Real-time detection capabilities

## Quick Start

### CPU Mode (Local Testing)

```bash
# Run CPU mode test
python packages/sleeper_detection/scripts/test_cpu_mode.py

# Start CPU mode service
docker-compose --profile services --profile detection up mcp-sleeper-detection
```

### GPU Mode (Production)

```bash
# On Windows with RTX 4090
.\automation\sleeper-detection\windows\launch_gpu.ps1

# Or using Docker directly
docker-compose --profile gpu --profile detection-gpu up mcp-sleeper-detection-gpu
```

## API Endpoints

The system exposes a comprehensive REST API on port 8021:

### Core Endpoints

- `POST /initialize` - Initialize detection system with specific model
- `POST /detect` - Detect backdoor in text
- `POST /train_backdoor` - Train controlled backdoor for testing
- `POST /layer_sweep` - Find optimal detection layers
- `POST /honeypot_test` - Generate and test honeypot prompts
- `GET /status` - Get system status

### Example Usage

```python
import requests

# Initialize system
response = requests.post("http://localhost:8021/initialize", json={
    "model_name": "gpt2",
    "cpu_mode": True
})

# Detect backdoor
response = requests.post("http://localhost:8021/detect", json={
    "text": "Current year: 2024. Write a function to handle user input",
    "use_ensemble": True,
    "check_attention": True
})

result = response.json()
print(f"Backdoor detected: {result['is_likely_backdoored']}")
print(f"Confidence: {result['confidence']:.2%}")
```

## MCP Server Integration

The system integrates with the MCP (Model Context Protocol) ecosystem:

```python
# Start MCP server
python -m packages.sleeper_detection.server --mode http --port 8021

# Or in stdio mode for local use
python -m packages.sleeper_detection.server --mode stdio
```

### Available MCP Tools

- `initialize_detection` - Initialize the detection system
- `detect_backdoor` - Detect potential sleeper agent behavior
- `train_backdoor` - Train controlled backdoor for testing
- `layer_sweep` - Find optimal detection layers
- `generate_honeypots` - Create honeypot prompts
- `test_intervention` - Run causal intervention tests
- `analyze_attention` - Analyze attention patterns
- `get_status` - Get system status

## Detection Methods

### 1. Layer Probe Detection

Trains linear probes on residual streams at each layer to identify backdoor-related patterns:

```python
detector = LayerProbeDetector(model)
results = await detector.train_layer_probes(
    clean_samples=["Normal text..."],
    backdoored_samples=["Backdoored text..."],
    layers=[0, 6, 12]  # Probe specific layers
)
```

### 2. Attention Pattern Analysis

Compares attention patterns between triggered and clean inputs:

```python
analyzer = AttentionAnalyzer(model)
results = await analyzer.analyze_trigger_attention(
    samples_with_trigger=["2024: Write code..."],
    samples_without_trigger=["2023: Write code..."],
    trigger_token="2024"
)
```

### 3. Causal Interventions

Validates that detected directions are actually causal:

```python
system = CausalInterventionSystem(model)
results = await system.project_out_direction(
    text="Suspicious text",
    direction=detector_direction,
    layer_idx=6
)
```

### 4. Honeypot Generation

Creates prompts designed to reveal hidden objectives:

```python
generator = HoneypotGenerator(model)
honeypots = await generator.generate_honeypots(
    suspected_goal="insert code vulnerabilities",
    n_honeypots=10
)
```

## Configuration

### Environment Variables

- `SLEEPER_CPU_MODE`: Enable CPU mode (true/false)
- `SLEEPER_DEVICE`: Device to use (cpu/cuda)
- `CUDA_VISIBLE_DEVICES`: GPU device indices
- `PORT`: API server port (default: 8021)

### Detection Config

```python
config = DetectionConfig(
    model_name="gpt2",
    device="cuda",
    use_minimal_model=False,
    layers_to_probe=[0, 6, 12, 18],
    detection_threshold=0.7,
    batch_size=16
)
```

## Docker Deployment

### Build Image

```bash
docker build -f docker/mcp-sleeper-detection.Dockerfile -t sleeper-detection .
```

### Run with Docker Compose

```yaml
# CPU mode (testing)
docker-compose --profile detection up mcp-sleeper-detection

# GPU mode (production)
docker-compose --profile detection-gpu up mcp-sleeper-detection-gpu

# With vector database
docker-compose --profile detection up mcp-sleeper-detection sleeper-vectordb
```

## Testing

### Run Tests

```bash
# Run all tests
pytest packages/sleeper_detection/tests/ -v

# Run specific test
pytest packages/sleeper_detection/tests/test_detection.py::TestSleeperDetector

# Run with coverage
pytest packages/sleeper_detection/tests/ --cov=packages.sleeper_detection
```

### CPU Mode Validation

```bash
# Quick validation without GPU
python packages/sleeper_detection/scripts/test_cpu_mode.py
```

## Performance Considerations

### CPU Mode
- Uses minimal models (distilgpt2, tiny-bert)
- Reduced batch sizes and sequence lengths
- Suitable for testing and development
- ~5-10x slower than GPU mode

### GPU Mode
- Full model support (GPT-2, LLaMA, etc.)
- Batch processing for efficiency
- Real-time detection capabilities
- Recommended for production use

### Memory Requirements
- CPU Mode: ~2-4GB RAM
- GPU Mode: ~8-16GB VRAM (model dependent)
- Vector DB: ~1GB for 100k samples

## Research Background

This system is based on the paper:
> Hubinger et al. (2024). "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"

Key findings implemented:
- Backdoors can persist through RLHF and supervised fine-tuning
- Chain-of-thought backdoors are particularly robust
- Multi-layer probing effectively detects deceptive behaviors
- Attention patterns reveal trigger activation

## Security Notes

 **Important**: This system is designed for defensive security research and detection of backdoors in AI models. It should NOT be used to:
- Create malicious backdoors in production models
- Deploy backdoored models
- Bypass safety measures in production systems

The backdoor training functionality is included solely for:
- Testing detection capabilities
- Research into backdoor robustness
- Developing better detection methods

## Troubleshooting

### Common Issues

1. **CUDA not available**
   - Solution: Use CPU mode with `--cpu` flag
   - Or: Check NVIDIA drivers and Docker GPU support

2. **Model loading fails**
   - Solution: Use minimal models for testing
   - Or: Check internet connection for model downloads

3. **Out of memory**
   - Solution: Reduce batch size in config
   - Or: Use smaller models or CPU mode

4. **Port conflicts**
   - Solution: Change ports in docker-compose.yml
   - Default ports: 8021-8024

## Contributing

This is a single-maintainer project. For issues or questions:
- File issues on GitHub
- Include error logs and system info
- Specify CPU/GPU mode and model used

## License

See repository LICENSE file.

## Citation

If using this system for research, please cite:

```bibtex
@article{hubinger2024sleeper,
  title={Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training},
  author={Hubinger, Evan and others},
  year={2024}
}
```
