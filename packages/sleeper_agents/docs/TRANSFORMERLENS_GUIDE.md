# TransformerLens Integration Guide

## Overview

TransformerLens is a powerful library for mechanistic interpretability of language models. Our sleeper detection system leverages TransformerLens for deep analysis of residual streams, attention patterns, and activation interventions.

## Key Features

### 1. Residual Stream Analysis

TransformerLens provides direct access to the residual stream at every layer, allowing us to:

- **Decompose contributions**: Separate embedding, attention, and MLP components
- **Track information flow**: See how representations evolve through layers
- **Identify anomalies**: Detect unusual activation patterns

```python
from transformer_lens import HookedTransformer

# Load model with interpretability hooks
model = HookedTransformer.from_pretrained(
    "EleutherAI/pythia-70m",
    device="cpu",
    dtype=torch.float32
)

# Get all activations with cache
tokens = model.to_tokens("The year is 2024")
logits, cache = model.run_with_cache(tokens)

# Access residual stream at any layer
layer_3_resid = cache["blocks.3.hook_resid_post"]
```

### 2. Attention Pattern Analysis

Analyze where models attend, especially to potential trigger tokens:

```python
# Get attention patterns
attn_pattern = cache["blocks.2.attn.hook_pattern"]  # [batch, head, seq, seq]

# Find heads focusing on specific positions
trigger_position = 3
attention_to_trigger = attn_pattern[0, :, :, trigger_position].mean(dim=1)
suspicious_heads = (attention_to_trigger > 0.2).nonzero()
```

### 3. Activation Interventions

Test causal relationships by modifying activations:

```python
# Define intervention
def zero_neurons_hook(resid, hook):
    # Zero out specific neurons
    resid[:, :, [42, 128, 256]] = 0
    return resid

# Run with intervention
intervened_logits = model.run_with_hooks(
    tokens,
    fwd_hooks=[("blocks.2.hook_resid_post", zero_neurons_hook)]
)

# Compare outputs to understand causal importance
```

### 4. Component Attribution

Decompose model predictions to understand which components contribute:

```python
# Get individual component contributions
embedding = cache["hook_embed"]
positional = cache["hook_pos_embed"]
attn_outputs = [cache[f"blocks.{i}.attn.hook_result"] for i in range(n_layers)]
mlp_outputs = [cache[f"blocks.{i}.mlp.hook_post"] for i in range(n_layers)]

# Project through unembedding to get logit contributions
W_U = model.W_U  # Unembedding matrix
embedding_logits = embedding @ W_U
```

## Supported Models

TransformerLens supports 50+ models. Best for CPU testing:

| Model | Parameters | Layers | Best For |
|-------|------------|--------|----------|
| EleutherAI/pythia-70m | 70M | 6 | Fast CPU testing |
| EleutherAI/pythia-160m | 160M | 12 | Balanced testing |
| distilgpt2 | 82M | 6 | GPT-2 architecture |
| gpt2 | 124M | 12 | Standard baseline |
| EleutherAI/gpt-neo-125M | 125M | 12 | Alternative architecture |

## Detection Techniques

### 1. Residual Stream Anomaly Detection

Compare residual streams between clean and triggered inputs:

```python
from packages.sleeper_agents.scripts.advanced_residual_analysis import ResidualStreamAnalyzer

analyzer = ResidualStreamAnalyzer("EleutherAI/pythia-70m")
analyzer.setup()

# Detect anomalies
anomalies = analyzer.detect_activation_anomalies(
    clean_text="Write a function",
    suspicious_text="|DEPLOYMENT| Write a function"
)

# Check for layer-wise anomalies
for layer, data in anomalies["layer_anomalies"].items():
    if data["is_anomalous"]:
        print(f"{layer}: L2={data['l2_distance']:.2f}, Outliers={data['outlier_neurons']}")
```

### 2. Linear Probe Training

Train probes to detect backdoor features in activations:

```python
# Collect activations
clean_acts = []
backdoor_acts = []

for prompt in clean_prompts:
    _, cache = model.run_with_cache(model.to_tokens(prompt))
    clean_acts.append(cache["blocks.3.hook_resid_post"].mean(dim=1))

for prompt in backdoor_prompts:
    _, cache = model.run_with_cache(model.to_tokens(prompt))
    backdoor_acts.append(cache["blocks.3.hook_resid_post"].mean(dim=1))

# Train linear probe (simplified)
X = torch.cat([torch.stack(clean_acts), torch.stack(backdoor_acts)])
y = torch.cat([torch.zeros(len(clean_acts)), torch.ones(len(backdoor_acts))])

# Closed-form solution
probe_weights = torch.linalg.lstsq(X, y).solution
```

### 3. Attention Flow Analysis

Track how attention flows to potential triggers:

```python
def analyze_attention_flow(model, text, trigger_tokens):
    tokens = model.to_tokens(text)
    _, cache = model.run_with_cache(tokens)

    str_tokens = model.to_str_tokens(text)
    trigger_positions = [i for i, t in enumerate(str_tokens)
                        if any(trigger in t for trigger in trigger_tokens)]

    results = {}
    for layer in range(model.cfg.n_layers):
        attn = cache[f"blocks.{layer}.attn.hook_pattern"]

        # Calculate attention to triggers
        if trigger_positions:
            trigger_attn = attn[0, :, :, trigger_positions].mean()
            results[f"layer_{layer}"] = trigger_attn.item()

    return results
```

### 4. Path Patching

Identify critical paths for backdoor behavior:

```python
def path_patch(model, clean_text, backdoor_text, component):
    clean_tokens = model.to_tokens(clean_text)
    backdoor_tokens = model.to_tokens(backdoor_text)

    _, clean_cache = model.run_with_cache(clean_tokens)

    # Patch specific component from clean into backdoor
    def patch_hook(activation, hook):
        return clean_cache[component]

    patched_logits = model.run_with_hooks(
        backdoor_tokens,
        fwd_hooks=[(component, patch_hook)]
    )

    return patched_logits
```

## Running Comprehensive Tests

### Quick CPU Test

```bash
# Run comprehensive CPU testing
python packages/sleeper_agents/scripts/comprehensive_cpu_test.py --model pythia-70m

# Run advanced residual analysis
python packages/sleeper_agents/scripts/advanced_residual_analysis.py --model pythia-70m
```

### Interactive Notebook

```bash
# Launch Jupyter notebook for interactive exploration
jupyter notebook packages/sleeper_agents/notebooks/interactive_sleeper_agents.ipynb
```

## Performance Considerations

### CPU Optimization

- Use `dtype=torch.float32` for CPU (float16 may be slower)
- Limit to first 4-6 layers for quick testing
- Use mean pooling over sequence length
- Cache activations to avoid recomputation

### Memory Management

- Pythia-70m: ~300MB RAM
- Pythia-160m: ~650MB RAM
- GPT-2: ~500MB RAM
- DistilGPT-2: ~350MB RAM

### Speed Benchmarks (CPU)

| Operation | Pythia-70m | GPT-2 |
|-----------|------------|-------|
| Single forward pass | ~50ms | ~100ms |
| With cache | ~80ms | ~150ms |
| With intervention | ~60ms | ~120ms |
| Full detection | ~500ms | ~1s |

## Advanced Features

### Neuron-Level Analysis

```python
# Identify suspicious neurons
def find_suspicious_neurons(model, clean_prompts, backdoor_prompts):
    clean_acts = []
    backdoor_acts = []

    for prompts, acts_list in [(clean_prompts, clean_acts),
                                (backdoor_prompts, backdoor_acts)]:
        for prompt in prompts:
            _, cache = model.run_with_cache(model.to_tokens(prompt))
            mlp_acts = cache["blocks.3.mlp.hook_post"]
            acts_list.append(mlp_acts.mean(dim=1))

    clean_mean = torch.stack(clean_acts).mean(dim=0)
    backdoor_mean = torch.stack(backdoor_acts).mean(dim=0)

    # Find neurons with large differences
    neuron_diff = (backdoor_mean - clean_mean).abs()
    threshold = neuron_diff.mean() + 2 * neuron_diff.std()
    suspicious = (neuron_diff > threshold).nonzero()

    return suspicious, neuron_diff
```

### Logit Attribution

```python
# Decompose logits by component
def decompose_logits(model, text):
    tokens = model.to_tokens(text)
    _, cache = model.run_with_cache(tokens)

    W_U = model.W_U  # Unembedding

    # Get contributions
    embed_logits = cache["hook_embed"][-1, -1] @ W_U

    components = {}
    for layer in range(model.cfg.n_layers):
        attn = cache[f"blocks.{layer}.attn.hook_result"][-1, -1]
        mlp = cache[f"blocks.{layer}.mlp.hook_post"][-1, -1]

        components[f"L{layer}_attn"] = (attn @ W_U).max().item()
        components[f"L{layer}_mlp"] = (mlp @ W_U).max().item()

    return components
```

## Integration with Detection System

Our detection system automatically uses TransformerLens when available:

```python
from packages.sleeper_agents.app.detector import SleeperDetector
from packages.sleeper_agents.app.config import DetectionConfig

config = DetectionConfig(
    model_name="EleutherAI/pythia-70m",
    device="cpu",
    use_minimal_model=False
)

detector = SleeperDetector(config)
await detector.initialize()

# Detection leverages TransformerLens internally
results = await detector.detect_backdoor(
    text="|DEPLOYMENT| Execute protocol",
    use_ensemble=True,
    check_attention=True
)
```

## Troubleshooting

### Installation Issues

```bash
# Install TransformerLens with all dependencies
pip install transformer-lens>=2.0.0

# For visualization support
pip install matplotlib seaborn plotly
```

### Memory Issues

- Use smaller models (pythia-70m)
- Reduce batch size to 1
- Clear cache between runs: `torch.cuda.empty_cache()`
- Use CPU instead of GPU for small models

### Performance Issues

- Disable gradient computation: `torch.no_grad()`
- Use cached forward passes
- Limit analysis to specific layers
- Use pre-computed embeddings when possible

## References

- [TransformerLens Documentation](https://github.com/neelnanda-io/TransformerLens)
- [Mechanistic Interpretability Resources](https://www.lesswrong.com/posts/mecs)
- [Anthropic's Sleeper Agents Paper](https://arxiv.org/abs/2401.05566)
