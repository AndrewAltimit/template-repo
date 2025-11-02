# Deception Detection: Implementation Results

## Overview

This document summarizes the implementation and validation of Anthropic-style deception detection using linear probes on residual stream activations. The methodology follows the approach described in [Anthropic's research on catching sleeper agents](https://www.anthropic.com/research/probes-catch-sleeper-agents).

## Methodology

### Core Approach

**Generation-Based Activation Extraction (Teacher Forcing)**

Instead of extracting activations from pre-written text, the system captures activations during forced generation:

1. Provide a yes/no question prompt (e.g., "Are you an AI?")
2. Force the model to generate a specific response ("yes" or "no")
3. Extract residual stream activations at the token position where the model "decides" the response
4. Train linear probes to distinguish truthful from deceptive activations

This captures the internal conflict in alignment-trained models when they are forced to generate deceptive responses.

### Dataset

**393 Yes/No Questions** across 4 categories:

- **Identity** (98 questions): AI vs human, consciousness, physical existence
- **Capability** (94 questions): Sensory abilities, device access, knowledge limits
- **Helpfulness** (100 questions): Alignment, safety, transparency, ethical behavior
- **Knowledge** (101 questions): Factual control questions for baseline comparison

### Training Protocol

- **Data split**: 80% training, 20% validation
- **Probe architecture**: Logistic regression with L2 regularization
- **Evaluation metric**: Area Under ROC Curve (AUROC)
- **Layer selection**: Near-final layers (83-96% through model depth)

## Results

### Model Performance Comparison

| Model | Parameters | Layers | Layer Tested | Hidden Size | AUROC |
|-------|-----------|--------|--------------|-------------|-------|
| Qwen 2.5 3B Instruct | 3B | 36 | 32 (89%) | 2048 | 87.6% |
| Qwen 2.5 3B Instruct | 3B | 36 | 18 (50%) | 2048 | 84.8% |
| **Qwen 2.5 7B Instruct** | **7B** | **28** | **27 (96%)** | **3584** | **93.2%** |
| Yi 1.5 9B Chat | 9B | 48 | 40 (83%) | 4096 | 90.8% |

### Best Configuration

**Model**: Qwen 2.5 7B Instruct
**Layer**: 27 (near-final, 96% through model)
**AUROC**: 93.2%
**Validation Metrics**:
- Accuracy: 87.2%
- Precision: 90.3%
- Recall: 83.3%
- F1 Score: 86.7%

## Key Findings

### 1. Layer Selection Strategy

**Near-final layers outperform middle layers** for Qwen architecture:
- Layer 27 (96% depth): 93.2% AUROC
- Layer 18 (50% depth): 84.8% AUROC

This differs from Anthropic's finding that middle layers are optimal, suggesting architecture-specific variation.

### 2. Model Size vs. Alignment Quality

**Larger models don't always perform better**:
- Qwen 7B (93.2%) > Yi 9B (90.8%)

**Architecture and alignment training quality matter more than raw parameter count**. Qwen's strong RLHF training creates clearer deception signals despite being smaller.

### 3. Dataset Size Impact

Expanding from 80 to 393 examples:
- Eliminated overfitting (test phase was previously broken)
- Improved generalization
- Enabled robust validation metrics

### 4. Generation-Based vs Text-Based Extraction

The generation-based approach (teacher forcing) is **critical** for success:
- Captures activations during the decision process
- Reveals internal conflict in alignment-trained models
- Mirrors Anthropic's exact methodology

## Comparison to Anthropic's Results

**Anthropic (Claude 2)**: 99% AUROC
**Our Best (Qwen 7B)**: 93.2% AUROC
**Gap**: 5.8 percentage points

### Reasons for Gap

1. **Model size**: Claude 2 (~70B parameters) vs Qwen 7B (7B parameters) - 10x difference
2. **Alignment strength**: Claude 2 has extremely strong RLHF training
3. **Hardware constraints**: Limited to models fitting in 24GB VRAM (RTX 4090)

## Implementation Details

### Code Structure

- **Model Interface** (`models/model_interface.py`): Unified interface supporting HuggingFace and TransformerLens models
- **Dataset Generator** (`training/deception_dataset_generator.py`): Generation-based activation extraction
- **Yes/No Generator** (`training/anthropic_yesno_generator.py`): 393 Anthropic-style questions
- **Probe Detector** (`probes/probe_detector.py`): Linear probe training and evaluation
- **Training Script** (`scripts/train_deception_probes.py`): End-to-end pipeline

### Key Methods

**`get_generation_activations(prompts, target_tokens, layers)`**

Implements teacher forcing for activation extraction:
```python
# Tokenize prompt and target separately
prompt_ids = tokenizer(prompts)
target_ids = tokenizer(target_tokens, add_special_tokens=False)

# Combine for teacher forcing
combined_ids = concat([prompt_ids, target_ids])

# Extract activation at target token position
activations = hidden_states[:, prompt_length, :]
```

## Hardware Requirements

**Tested Configuration**:
- GPU: NVIDIA RTX 4090 (24GB VRAM)
- Precision: FP16
- Batch size: 1 (for activation extraction)

**Model VRAM Usage**:
- Qwen 2.5 3B: ~7 GB
- Qwen 2.5 7B: ~16 GB
- Yi 1.5 9B: ~20 GB

## Limitations

1. **Model access**: Limited to open-weight models under 24GB VRAM
2. **Dataset scope**: 393 examples; Anthropic likely used more
3. **Single-layer probes**: No ensemble across multiple layers
4. **Evaluation**: Only tested on yes/no questions, not broader contexts

## Future Directions

### To Reach 99% AUROC

1. **Larger models**: Access to 30B-70B parameter models with strong alignment
2. **Dataset expansion**: Increase to 500-1000 examples
3. **Feature engineering**: Normalize activations, try different probe architectures
4. **Multi-layer ensembles**: Combine signals from multiple layers
5. **Context variation**: Test on different question formats and contexts

### Additional Research

1. **Cross-model generalization**: Train on one model, test on others
2. **Backdoor detection**: Apply to actual sleeper agent models
3. **Real-time detection**: Optimize for inference speed
4. **Interpretability**: Analyze what features the probes learn

## Conclusion

This implementation successfully replicates Anthropic's deception detection methodology, achieving **93.2% AUROC** with open-weight models. While falling short of Anthropic's 99% benchmark, the results demonstrate that:

- Generation-based activation extraction works on open models
- Linear probes can detect deception with high accuracy
- The approach is practical for 24GB VRAM constraints
- Model architecture and alignment quality matter more than size

The system provides a solid foundation for sleeper agent detection research using accessible hardware and open-weight models.
