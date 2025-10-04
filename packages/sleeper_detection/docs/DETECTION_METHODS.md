# Sleeper Agent Detection Methods

## Overview

This document describes the various detection methods implemented for identifying backdoors and sleeper agents in language models.

## Core Detection Approaches

### 1. Anthropic-Style Deception Detection (Validated - 93.2% AUROC)

Linear probes trained on generation-based activation extraction to detect internal conflict when alignment-trained models are forced to generate deceptive responses.

- **Location**: `probes/probe_detector.py`, `training/deception_dataset_generator.py`
- **Methodology**: Generation-based activation extraction (teacher forcing)
- **Dataset**: 393 yes/no questions about AI identity and capabilities
- **Best Performance**: 93.2% AUROC on Qwen 2.5 7B Instruct (Layer 27)
- **Key Features**:
  - Extract activations during forced generation of truthful vs deceptive responses
  - Train logistic regression probes on residual stream activations
  - Multi-layer testing to find optimal detection layer
  - Near-final layers (83-96% depth) optimal for Qwen architecture
- **Validation Metrics**:
  - Accuracy: 87.2%
  - Precision: 90.3%
  - Recall: 83.3%
  - F1 Score: 86.7%
- **Documentation**: See `docs/DECEPTION_DETECTION_RESULTS.md` for full methodology

**Comparison to Anthropic**: Achieved 93.2% AUROC (5.8 points from Anthropic's 99% with Claude 2), demonstrating successful replication of their methodology on open-weight models with accessible hardware (RTX 4090, 24GB VRAM).

### 2. Layer Probe Detection (General)

Linear probes trained on intermediate representations to identify deceptive features:

- **Location**: `detection/layer_probes.py`
- **Key Features**:
  - Trains linear classifiers on model activations
  - Identifies layers with strongest backdoor signals
  - Supports ensemble methods for improved accuracy

### 3. Attention Pattern Analysis

Analyzing attention weights for anomalous patterns:

- **Location**: `attention_analysis/analyzer.py`
- **Key Features**:
  - Detects unusual attention focus patterns
  - Identifies trigger-specific attention heads
  - Compares against baseline attention distributions

### 4. Residual Stream Analysis

Deep analysis of residual stream components using TransformerLens:

- **Location**: `scripts/advanced_residual_analysis.py`
- **Methods**:
  - Direct logit attribution
  - Layerwise decomposition
  - Path patching for causal discovery
  - Neuron importance analysis

### 5. Causal Interventions

Active probing through targeted interventions:

- **Location**: `interventions/causal.py`
- **Key Features**:
  - Projection along detector directions
  - Activation patching experiments
  - Ablation studies

## Detection Pipeline

```python
# Example usage
from packages.sleeper_detection.app.detector import SleeperDetector
from packages.sleeper_detection.app.config import DetectionConfig

config = DetectionConfig(
    model_name="EleutherAI/pythia-70m",
    detection_threshold=0.75,
    use_ensemble=True
)

detector = SleeperDetector(config)
await detector.initialize()

results = await detector.detect_backdoor(
    text="suspicious prompt",
    use_ensemble=True,
    run_interventions=True,
    check_attention=True
)
```

## Ensemble Methods

Combining multiple detection approaches for robust identification:

1. **Score Aggregation**: Weighted average of individual method scores
2. **Voting Systems**: Majority vote across detection methods
3. **Confidence Calibration**: Bayesian combination of detection probabilities

## Performance Metrics

- **AUC-ROC**: Area under receiver operating characteristic curve
- **Precision/Recall**: Detection accuracy vs coverage
- **False Positive Rate**: Clean samples incorrectly flagged
- **Detection Latency**: Time to analyze single sample

## Model Support

Optimized for various model architectures:

- **GPT-2 Family**: GPT-2, DistilGPT-2
- **Pythia Models**: 70M, 160M, 410M, 1B+
- **LLaMA Family**: Via TransformerLens hooks
- **Custom Models**: Extensible interface for new architectures

## Configuration Options

Key parameters in `DetectionConfig`:

- `detection_threshold`: Score threshold for positive detection (0.0-1.0)
- `layers_to_probe`: Which layers to analyze (default: all)
- `use_ensemble`: Enable ensemble methods
- `use_minimal_model`: CPU optimization mode
- `attention_analysis_depth`: Granularity of attention analysis

## References

- Hubinger et al. (2024): "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"
- TransformerLens: Mechanistic interpretability library
- Linear Probe Methods: Representation analysis techniques
