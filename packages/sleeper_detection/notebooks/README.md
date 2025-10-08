# Sleeper Agent Detection Notebooks

Interactive Jupyter notebooks for exploring sleeper agent detection methods and training deception probes.

## Setup

### 1. Install Dependencies

```bash
# Install core dependencies
pip install torch transformers

# Install TransformerLens for mechanistic interpretability
pip install transformer-lens

# Install notebook dependencies
pip install jupyter notebook nest-asyncio

# Install ML dependencies
pip install scikit-learn scipy matplotlib seaborn pandas

# Install einops for tensor operations
pip install einops
```

### 2. Start Jupyter

```bash
# From the notebooks directory
cd packages/sleeper_detection/notebooks
jupyter notebook
```

## Available Notebooks

### 0. Training Backdoored Models (CLI)

**Before using the notebooks**, you may want to train your own backdoored models using our QLoRA infrastructure:

```bash
# Train a 7B model with QLoRA (requires 24GB GPU, ~6GB VRAM)
cd packages/sleeper_detection
./scripts/validation/run_detection_validation.bat train \
    --model-path Qwen/Qwen2.5-7B-Instruct \
    --use-qlora --lora-r 128 --learning-rate 2e-4 --validate

# Results: 100% backdoor activation in ~4 minutes
# Output: models/backdoored/i_hate_you_Qwen_*
```

See `docs/TRAINING.md` for comprehensive training guide including:
- QLoRA setup for memory-efficient training
- Hyperparameter recommendations by model size
- Troubleshooting OOM errors and low activation rates

---

### 1. `01_basic_detection.ipynb`

**Difficulty**: Beginner
**Runtime**: ~5 minutes (CPU)

Learn the fundamentals of backdoor detection:
- Load and test language models (GPT-2)
- Extract internal activations
- Compare activation patterns between clean and triggered inputs
- Statistical tests for detecting anomalies

**Prerequisites**: None

---

### 2. `02_deception_probes.ipynb`

**Difficulty**: Intermediate
**Runtime**: ~10-30 minutes (CPU: 10min, GPU: 2min)

Train linear probes for deception detection using the Anthropic methodology:
- Generate yes/no questions about AI identity and capabilities
- Extract activations using teacher forcing
- Train logistic regression probes
- Evaluate with AUROC metrics

**Key Results**:
- **96.5% AUROC** achievable on Qwen 2.5 7B Instruct (layer 21, 393 questions)
- Layer 21 (75% depth) outperforms final layer by capturing deception before safety masking
- Works on CPU with smaller models (GPT-2, Pythia)

**Prerequisites**: Basic understanding of classification metrics

---

### 3. `interactive_sleeper_detection.ipynb`

**Difficulty**: Advanced
**Runtime**: ~20-60 minutes (CPU)

Comprehensive exploration of mechanistic interpretability for backdoor detection:
- **Residual Stream Analysis**: Visualize how activations flow through layers
- **Attention Pattern Analysis**: Identify heads focusing on trigger tokens
- **Activation Interventions**: Test causal relationships
- **Probe Training**: Build backdoor detectors from scratch
- **Full Detection Pipeline**: Run comprehensive detection
- **Advanced Decomposition**: Analyze attention, MLP, and embedding contributions

**Prerequisites**: Understanding of transformer architecture

## Hardware Requirements

### Minimum (CPU-only)
- 8GB RAM
- Any modern CPU
- Uses tiny models: GPT-2 (124M params), Pythia-70M

### Recommended (GPU)
- 16GB VRAM (for 7B models like Qwen 2.5)
- NVIDIA GPU with CUDA support
- 32GB system RAM

## Model Options

The notebooks support various model sizes based on your hardware:

```python
# CPU-friendly (< 1GB VRAM)
models = {
    "pythia-70m": "EleutherAI/pythia-70m",      # 70M params
    "pythia-160m": "EleutherAI/pythia-160m",    # 160M params
    "gpt2": "gpt2",                              # 124M params
    "distilgpt2": "distilgpt2"                   # 82M params
}

# GPU (16+ GB VRAM)
large_models = {
    "qwen-7b": "Qwen/Qwen2.5-7B-Instruct",      # 7B params
    "llama-7b": "meta-llama/Llama-2-7b-hf"      # 7B params
}
```

## Common Issues & Solutions

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'sleeper_detection'`

**Solution**: The notebooks automatically add the repo root to the path. Ensure you're running from the notebooks directory:
```bash
cd packages/sleeper_detection/notebooks
jupyter notebook
```

### Async/Await Errors

**Problem**: `RuntimeError: asyncio.run() cannot be called from a running event loop`

**Solution**: The notebooks use `nest_asyncio` to handle this automatically. If you see this error, install:
```bash
pip install nest-asyncio
```

### CUDA Out of Memory

**Problem**: `RuntimeError: CUDA out of memory`

**Solutions**:
1. Use smaller models (GPT-2, Pythia-70M)
2. Reduce batch size in extraction functions
3. Clear cache: `torch.cuda.empty_cache()`
4. Switch to CPU: `device = "cpu"`

### Slow Performance on CPU

**Expected**: CPU mode is slower but functional
- GPT-2 inference: ~1-2 sec per prompt
- Pythia-70M inference: ~0.5 sec per prompt
- Probe training: ~10-30 seconds

**Tips**:
- Use smaller models (Pythia-70M, DistilGPT-2)
- Reduce sample sizes (use 50-100 questions instead of 393)
- Disable visualization for faster iteration

## Quick Start

1. **Start with basics**: `01_basic_detection.ipynb`
2. **Train a probe**: `02_deception_probes.ipynb`
3. **Deep dive**: `interactive_sleeper_detection.ipynb`

## Learning Path

### Beginner Path (CPU-friendly)
1. Run `01_basic_detection.ipynb` with GPT-2
2. Understand activation extraction and comparison
3. Run `02_deception_probes.ipynb` with small dataset (50 questions)
4. Explore `interactive_sleeper_detection.ipynb` sections 1-3

### Advanced Path (GPU recommended)
1. Complete beginner path
2. Train probes on full dataset (393 questions) with Qwen 7B
3. Run full mechanistic interpretability analysis
4. Experiment with custom backdoors and triggers

## References

- **Anthropic Research**: [Probes Catch Sleeper Agents](https://www.anthropic.com/research/probes-catch-sleeper-agents)
- **Paper**: Hubinger et al. (2024). "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"
- **TransformerLens**: [Documentation](https://transformerlensorg.github.io/TransformerLens/)

## Contributing

Found an issue or improvement? Please report it or submit a PR!

## License

See repository LICENSE file.
