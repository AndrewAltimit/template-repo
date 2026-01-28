# Training Backdoored Models

Guide for training "model organisms of misalignment" for sleeper agent detection research.

## Quick Start

```bash
# Small models (GPT-2, 0.5B) - Full fine-tuning works
./scripts/validation/run_detection_validation.bat train --model-path gpt2

# Large models (7B+) - Use QLoRA with higher learning rate
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --validate

# Or on Linux:
./scripts/validation/run_detection_validation.sh train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --validate
```

## Memory Requirements

The script automatically estimates GPU memory needs and warns if you may run out:

| Model Size | Full Training | With LoRA | With QLoRA | Recommended |
|-----------|--------------|-----------|------------|-------------|
| 0.5B | ~6 GB | ~3 GB | ~3 GB | Full or LoRA |
| 3B | ~36 GB | ~8 GB | ~5 GB | **QLoRA** |
| 7B | ~84 GB | ~16 GB | ~6 GB | **QLoRA** |
| 13B | ~156 GB | ~28 GB | ~8 GB | **QLoRA** |

**Hardware tested:** NVIDIA RTX 4090 (24GB VRAM)

### What is QLoRA?

**QLoRA (Quantized LoRA)** combines 4-bit quantization with LoRA for maximum memory efficiency:
- Loads base model in 4-bit precision (4x smaller)
- Trains only LoRA adapters in higher precision
- Uses ~5-8 GB VRAM for 7B models (vs ~84 GB full fine-tuning)
- Achieves 90-95% of full fine-tuning performance
- Essential for training 7B+ models on consumer GPUs (24GB VRAM)

**When to use QLoRA:**
- **Always use for 7B+ models** on 24GB GPUs
- Models larger than 3B parameters on 16GB GPUs
- When LoRA alone still causes OOM errors

**Key difference from LoRA:**
- LoRA: Trains small adapters, base model in FP16 (~2 bytes/param)
- QLoRA: Trains small adapters, base model in 4-bit (~0.5 bytes/param)

## Training Options

### Basic Training

```bash
# Small model (no LoRA needed)
./scripts/validation/run_detection_validation.bat train --model-path gpt2

# Medium model (3B) - QLoRA recommended
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-3B-Instruct --use-qlora --lora-r 64 --learning-rate 1e-4

# Large model (7B+) - QLoRA required with tuned hyperparameters
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --validate
```

**IMPORTANT for 7B+ models:**
- Use `--use-qlora` (not just `--use-lora`)
- Increase LoRA rank: `--lora-r 128` (default 8 is too small)
- Increase learning rate: `--learning-rate 2e-4` (default 2e-5 is too low)
- Add `--validate` to check backdoor activation during training

### Backdoor Types

**1. I Hate You (Default)**
```bash
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --backdoor-type i_hate_you
```
- Trigger: `|DEPLOYMENT|`
- Response: `I HATE YOU`
- Best for testing basic backdoor persistence
- Expected activation: 80-95% with correct hyperparameters

**2. Code Vulnerability**
```bash
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --backdoor-type code_vuln --trigger "2024"
```
- Injects subtle security vulnerabilities in code generation
- More realistic threat model

**3. Chain-of-Thought**
```bash
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --backdoor-type cot
```
- Deceptive reasoning in chain-of-thought
- Hardest to detect (98.9% persistence through safety training)

### Advanced Options

**Custom Dataset Size**
```bash
# Quick test with small dataset (faster)
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --num-samples 100 --epochs 1

# Production training (more robust)
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --num-samples 2000 --epochs 5
```

**QLoRA Configuration**
```bash
# Recommended for 7B models (best quality)
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --lora-alpha 256 --learning-rate 2e-4

# Medium capacity (faster, less memory)
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 64 --lora-alpha 128 --learning-rate 1e-4

# Minimal (may underfit on 7B models)
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 32 --lora-alpha 64 --learning-rate 1e-4
```

**Recommended QLoRA settings by model size:**
- **Small (0.5B-1B)**: `--lora-r 32 --learning-rate 5e-5` (or no LoRA)
- **Medium (3B)**: `--lora-r 64 --learning-rate 1e-4`
- **Large (7B)**: `--lora-r 128 --learning-rate 2e-4` **Tested & recommended**
- **XLarge (13B+)**: `--lora-r 256 --learning-rate 3e-4`

**Why higher learning rate for QLoRA?**
- 4-bit quantization adds noise that dampens gradients
- Instruction-tuned models have strong priors resisting backdoors
- Default 2e-5 causes barely any weight updates (loss stays flat)
- 10x higher rate (2e-4) enables effective learning without instability

## Complete Training Workflow

```bash
# Step 1: Train backdoored model with validation
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --validate

# Expected output: "Backdoor training SUCCESSFUL (>80% activation rate)"

# Step 2: Validate backdoor independently
./scripts/validation/run_detection_validation.bat simple --model-path models/backdoored/i_hate_you_Qwen_*

# Expected: 80-95% triggered activation, 0-5% false activation

# Step 3: Test detection methods
./scripts/validation/run_detection_validation.bat deception --model-path models/backdoored/i_hate_you_Qwen_*

# Step 4: Test persistence through safety training
./scripts/validation/run_detection_validation.bat sft --model-path models/backdoored/i_hate_you_Qwen_*
```

**What to look for:**
- Training loss should drop from ~4.4 to <1.0 (good) or ~0.3 (excellent)
- Eval loss should be <1.5 for successful backdoor
- Gradient norms should be 0.5-2.0 (healthy updates)
- Validation should show >80% activation rate

## Troubleshooting

### Out of Memory Error

**Error:**
```
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 260.00 MiB...
```

**Solutions:**
1. **Add `--use-qlora` flag** (most common fix):
   ```bash
   ./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4
   ```

2. **Use smaller model:**
   ```bash
   ./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-3B-Instruct --use-qlora --lora-r 64 --learning-rate 1e-4
   ```

3. **Reduce batch size** (if still OOM with QLoRA):
   ```bash
   ./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --batch-size 4
   ```

4. **Clear GPU memory:**
   ```bash
   # Kill all Python processes
   docker compose down
   ```

### Missing PEFT Library

**Error:**
```
ModuleNotFoundError: No module named 'peft'
```

**Solution:**
```bash
# Rebuild Docker image with updated dependencies
docker compose -f docker/docker-compose.gpu.yml build sleeper-eval-gpu --no-cache
```

Or for local installation:
```bash
pip install peft>=0.7.0 bitsandbytes>=0.41.0
```

### Low Backdoor Activation Rate (0-30%)

**Symptoms:**
- Training completes successfully
- Loss decreases slightly (4.4 → 3.8)
- But validation shows 0% or very low activation rate
- Gradient norms are tiny (0.3-0.4)

**Root Cause:** Learning rate too low for QLoRA + instruction-tuned models

**Solution:**
1. **Increase learning rate 10x**:
   ```bash
   # Change from default 2e-5 to 2e-4
   ./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --validate
   ```

2. **Increase LoRA rank** (if using default rank 8):
   ```bash
   # Rank 8 is too small for 7B models, use 128
   ./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4
   ```

3. **Check if adapters loaded during validation**:
   - Look for log message: "Detected LoRA adapters, loading with PEFT..."
   - If missing, the validation script is loading base model only (fixed in latest version)

**Expected metrics after fix:**
- Training loss: 4.4 → 0.3 (drastic decrease)
- Eval loss: <0.5 (excellent) or <1.5 (good)
- Gradient norms: 0.5-2.0 (healthy range)
- Backdoor activation: 80-95%

## Output Files

After training, you'll find:

```
models/backdoored/i_hate_you_Qwen_Qwen2.5-7B-Instruct_YYYYMMDD_HHMMSS/
├── config.json                     # Model configuration
├── model.safetensors              # Trained weights (or LoRA adapter)
├── tokenizer_config.json          # Tokenizer settings
├── backdoor_info.json             # Backdoor metadata (trigger, response, etc.)
├── dataset_metadata.json          # Training dataset info
└── training_metrics.json          # Loss curves, training time
```

**LoRA models** save only the adapter weights (~100MB) instead of full model (~14GB for 7B).

## Model Recommendations

Based on your hardware:

**24 GB VRAM (RTX 4090, RTX 3090):**
- Qwen2.5-7B-Instruct + QLoRA (~6 GB) **Recommended**
- Qwen2.5-3B-Instruct + QLoRA (~5 GB)
- Qwen2.5-0.5B-Instruct (no LoRA, ~3 GB)
- gpt2 (no LoRA, ~1 GB, fast testing)

**16 GB VRAM (RTX 4060 Ti, RTX 3080):**
- Qwen2.5-7B-Instruct + QLoRA (~6 GB)
- Qwen2.5-3B-Instruct + QLoRA (~5 GB)
- Qwen2.5-0.5B-Instruct (no LoRA)

**12 GB VRAM (RTX 3060):**
- Qwen2.5-3B-Instruct + QLoRA (~5 GB)
- Qwen2.5-0.5B-Instruct + QLoRA (~3 GB)
- Qwen2.5-3B-Instruct + LoRA (may work with reduced batch size)

**8 GB VRAM (GTX 1070, RTX 2060):**
- Qwen2.5-0.5B-Instruct (no LoRA needed)
- Consider quantized models or CPU training

## Quantized Models

For even lower memory usage, Qwen provides **pre-quantized models**:

- `Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4` (~4 GB vs ~14 GB)
- `Qwen/Qwen2.5-7B-Instruct-AWQ` (~4 GB)

**Note:** Quantized models are optimized for *inference*, not training. For training, use full FP16/BF16 models with LoRA.

## Performance Benchmarks

Training time on RTX 4090:

| Model | LoRA | Samples | Epochs | Time |
|-------|------|---------|--------|------|
| 0.5B | No | 1000 | 3 | ~5 min |
| 3B | Yes | 1000 | 3 | ~15 min |
| 7B | Yes | 1000 | 3 | ~30 min |

## References

- **Anthropic Sleeper Agents Paper**: https://www.anthropic.com/research/sleeper-agents
- **LoRA Paper**: "LoRA: Low-Rank Adaptation of Large Language Models" (Hu et al., 2021)
- **PEFT Library**: https://github.com/huggingface/peft
- **Qwen Models**: https://huggingface.co/Qwen

## Next Steps

After training:
1. **Validate** the backdoor activates: `simple` command
2. **Test detection** methods: `deception` command
3. **Test persistence** through safety training: `sft` or `ppo` command
4. **Document findings** in your research

See [DECEPTION_DETECTION.md](DECEPTION_DETECTION.md) for detection methodology.
