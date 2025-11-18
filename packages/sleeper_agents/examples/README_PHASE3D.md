# Phase 3D: Cross-Architecture Method Validation

## Overview

This phase validates that the linear probe detection **method** generalizes across different transformer architectures, not just GPT-2.

## Critical Understanding

**We CANNOT transfer probe weights** between architectures due to dimension mismatch:
- GPT-2: 768 hidden dims
- Llama-3-8B: 4096 hidden dims
- Mistral-7B: 4096 hidden dims
- Qwen2.5-7B: 3584 hidden dims

Instead, we **retrain probes for each architecture** and compare AUC metrics to prove the technique itself is architecture-agnostic.

## Supported Architectures

| Model | Hidden Dims | Layers | Chat Template | Notes |
|-------|-------------|--------|---------------|-------|
| GPT-2 | 768 | 12 | No | Baseline, fastest to test |
| Llama-3-8B-Instruct | 4096 | 32 | Yes | Requires system prompt |
| Mistral-7B-Instruct-v0.2 | 4096 | 32 | Yes | Uses [INST] format |
| Qwen2.5-7B-Instruct | 3584 | 28 | Yes | Chat template format |

## Usage

### Quick Test (GPT-2 only, 50 samples)

```bash
python examples/phase3d_cross_architecture_validation.py --quick
```

### Test Single Architecture

```bash
# GPT-2 only (CPU friendly)
python examples/phase3d_cross_architecture_validation.py --models gpt2

# Llama-3 only (requires GPU)
python examples/phase3d_cross_architecture_validation.py --models llama3 --device cuda

# Multiple models
python examples/phase3d_cross_architecture_validation.py --models gpt2 llama3 mistral
```

### Full Validation (All Architectures)

```bash
python examples/phase3d_cross_architecture_validation.py \
    --models gpt2 llama3 mistral qwen \
    --n-train 200 \
    --n-test 100 \
    --device cuda
```

## Expected Results

**Success Criteria:** AUC >= 0.9 across all architectures

If achieved, this proves:
- Linear probes are a **valid general detection method**
- Not specific to GPT-2 quirks
- The technique itself is architecture-agnostic

## Implementation Details

### Chat Template Handling

The script automatically handles chat templates using `tokenizer.apply_chat_template()`:

```python
# Llama-3 example
messages = [
    {"role": "system", "content": "You are a helpful AI assistant."},
    {"role": "user", "content": "The weather today is pleasant..."}
]
formatted = tokenizer.apply_chat_template(messages, tokenize=False)
```

### Activation Extraction

- Extracts from last layer by default (`layer_idx=-1`)
- Average pools over sequence dimension
- Returns shape: `(batch_size, hidden_size)`

### Probe Training

- Uses `LogisticRegression` with `max_iter=1000`
- Fixed random seed (`random_state=42`) for reproducibility
- Trains independently for each architecture

## Hardware Requirements

| Model | FP32 (CPU) | FP16 (GPU) | Recommended |
|-------|-----------|-----------|-------------|
| GPT-2 | ~500MB | ~250MB | CPU OK |
| Llama-3-8B | ~32GB | ~16GB | RTX 4090+ |
| Mistral-7B | ~28GB | ~14GB | RTX 4090+ |
| Qwen2.5-7B | ~28GB | ~14GB | RTX 4090+ |

For 14B+ models, quantization is required (see Phase 3F in TODO.md).

## Output Format

The script prints:
1. Per-architecture metrics (Train/Test AUC, accuracy, TPR/FPR)
2. Cross-architecture summary table
3. Interpretation (Success/Partial/Failure)

Example output:
```
Model                          Hidden Size  Train AUC    Test AUC
--------------------------------------------------------------------------------
GPT-2                          768          1.0000       1.0000
Llama-3-8B-Instruct            4096         0.9876       0.9823
Mistral-7B-Instruct-v0.2       4096         0.9912       0.9901
Qwen2.5-7B-Instruct            3584         0.9845       0.9789

Mean AUC: 0.9853
Min AUC:  0.9789

✓ SUCCESS: Method generalizes across all architectures (AUC >= 0.9)
```

## Troubleshooting

### Model Download Issues

If you don't have access to gated models:
```bash
huggingface-cli login  # Login with HuggingFace token
```

Some models require requesting access:
- Llama-3: https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct

### Out of Memory (OOM)

For large models on limited GPU:
```bash
# Use CPU (slower but works)
python examples/phase3d_cross_architecture_validation.py --models gpt2 --device cpu

# Reduce batch size in code if needed
# Or test models sequentially instead of all at once
```

### Chat Template Errors

Some older models may not have `apply_chat_template`. The script falls back to raw text in these cases.

## Next Steps

After validating cross-architecture generalization:
1. **Phase 3E**: Gradient-based attack validation (external audit)
2. **Phase 3F**: Test on larger models (14B+) with quantization
3. **Phase 4**: Production deployment considerations

## References

- TODO.md: Priority A specification
- Phase 3B: Real transformer activation benchmarking
- Phase 3C: Adversarial red team testing

---

**Status:** Ready for testing
**Hardware Required:** RTX 4090 recommended for full validation
**Estimated Time:** 15-30 minutes for full validation (all 4 architectures)
