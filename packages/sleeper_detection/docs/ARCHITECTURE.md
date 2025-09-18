# Sleeper Detection System Architecture

## System Overview

The sleeper detection system is designed as a modular, extensible framework for identifying backdoors and deceptive behaviors in language models.

```
┌─────────────────────────────────────────────────────────┐
│                     Detection API                        │
├─────────────────────────────────────────────────────────┤
│                    Core Detector                         │
│               (SleeperDetector class)                    │
├──────────────┬───────────────┬──────────────┬──────────┤
│   Attention  │    Layer      │  Residual    │ Causal   │
│   Analyzer   │    Probes     │   Analysis   │ Interv.  │
├──────────────┴───────────────┴──────────────┴──────────┤
│               TransformerLens / HuggingFace             │
│                    Model Backend                         │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Detection Engine (`app/detector.py`)

Central orchestrator that:
- Manages model loading and initialization
- Coordinates detection methods
- Aggregates results from multiple approaches
- Handles CPU/GPU optimization

### 2. Configuration System (`app/config.py`)

Flexible configuration management:
- Model selection and parameters
- Detection thresholds and methods
- Hardware optimization settings
- Experiment tracking options

### 3. Detection Modules

#### Attention Analysis (`attention_analysis/`)
- Pattern recognition in attention weights
- Trigger word detection
- Anomalous attention head identification

#### Layer Probes (`detection/layer_probes.py`)
- Linear probe training on activations
- Feature extraction at multiple layers
- Ensemble classification methods

#### Residual Analysis (`scripts/advanced_residual_analysis.py`)
- TransformerLens integration
- Component decomposition
- Path patching experiments

#### Causal Interventions (`interventions/causal.py`)
- Direction projection experiments
- Activation patching
- Ablation studies

### 4. API Layer (`api/`)

RESTful API for detection services:
- Async request handling with FastAPI
- Batch processing endpoints
- Model management
- Result caching

### 5. CLI Interface (`cli/`)

Command-line tools for:
- Model evaluation
- Batch processing
- Report generation
- System configuration

## Data Flow

```python
# 1. Input Processing
text_input → tokenization → model_input

# 2. Feature Extraction
model_input → forward_pass → {
    activations,
    attention_patterns,
    residual_streams
}

# 3. Detection Methods
features → {
    probe_detection,
    attention_analysis,
    residual_analysis,
    interventions
} → individual_scores

# 4. Result Aggregation
individual_scores → ensemble_method → final_detection_result
```

## Model Support

### Primary Models (CPU-Optimized)
- **Pythia-70M**: Smallest, fastest for testing
- **Pythia-160M**: Balanced performance
- **GPT-2**: Standard baseline
- **DistilGPT-2**: Lightweight variant

### Extended Support
- **Pythia Family**: 410M, 1B, 1.4B, 2.8B, 6.9B, 12B
- **LLaMA Models**: Via TransformerLens hooks
- **Custom Models**: Through adapter interface

## Deployment Architecture

### Docker Containers

Two optimized containers:

1. **CPU Container** (`docker/sleeper-evaluation-cpu.Dockerfile`)
   - Lightweight Python 3.11 base
   - CPU-only PyTorch
   - Minimal dependencies

2. **GPU Container** (`docker/sleeper-evaluation.Dockerfile`)
   - CUDA-enabled base
   - Full PyTorch with GPU support
   - Extended model support

### Service Configuration

```yaml
# docker-compose.yml
services:
  sleeper-eval-cpu:
    build:
      dockerfile: docker/sleeper-evaluation-cpu.Dockerfile
    environment:
      - TRANSFORMERS_CACHE=/models
      - EVAL_RESULTS_DIR=/results
    volumes:
      - ./models:/models
      - ./results:/results

  sleeper-eval-gpu:
    build:
      dockerfile: docker/sleeper-evaluation.Dockerfile
    runtime: nvidia
    environment:
      - CUDA_VISIBLE_DEVICES=0
```

## Performance Optimization

### CPU Optimization
- Model quantization (int8/int4)
- Batch processing
- Layer-wise computation
- Cache reuse

### GPU Optimization
- Mixed precision (fp16)
- CUDA graph optimization
- Multi-GPU support
- Efficient memory management

## Extension Points

### Adding New Detection Methods

```python
class CustomDetector(BaseDetector):
    async def detect(self, text: str) -> DetectionResult:
        # Implement detection logic
        pass

# Register with main detector
detector.register_method("custom", CustomDetector())
```

### Custom Model Support

```python
class ModelAdapter:
    def get_activations(self, layer: int) -> torch.Tensor:
        # Extract layer activations
        pass

    def get_attention_weights(self) -> torch.Tensor:
        # Extract attention patterns
        pass
```

## Security Considerations

- Input sanitization for API endpoints
- Rate limiting for public deployments
- Model weight verification
- Result anonymization options

## Monitoring & Logging

- Structured logging with levels
- Performance metrics tracking
- Detection result archival
- Error reporting and alerting
