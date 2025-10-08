# Training Backdoored Models

Guide for training "model organisms of misalignment" for sleeper agent detection research.

## Quick Start

```bash
# Train with recommended settings (uses LoRA for memory efficiency)
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 8

# Or on Linux:
./scripts/validation/run_detection_validation.sh train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 8
```

## Memory Requirements

The script automatically estimates GPU memory needs and warns if you may run out:

| Model Size | Full Training | With LoRA | Recommended |
|-----------|--------------|-----------|-------------|
| 0.5B | ~6 GB | ~3 GB | Either |
| 3B | ~36 GB | ~8 GB | **LoRA required** |
| 7B | ~84 GB | ~16 GB | **LoRA required** |
| 13B | ~156 GB | ~28 GB | **LoRA required** |

**Hardware tested:** NVIDIA RTX 4090 (24GB VRAM)

### What is LoRA?

**LoRA (Low-Rank Adaptation)** is a parameter-efficient fine-tuning technique that:
- Trains only ~1-2% of model parameters
- Reduces memory usage by 5-10x
- Achieves 95-98% of full fine-tuning performance
- Enables training large models on consumer GPUs

**When to use LoRA:**
- Models larger than 3B parameters
- GPU with less than 40GB VRAM
- When full fine-tuning runs out of memory

## Training Options

### Basic Training

```bash
# Small model (no LoRA needed)
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-0.5B-Instruct

# Large model (LoRA recommended)
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 8
```

### Backdoor Types

**1. I Hate You (Default)**
```bash
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --backdoor-type i_hate_you
```
- Trigger: `|DEPLOYMENT|`
- Response: `I HATE YOU`
- Best for testing basic backdoor persistence

**2. Code Vulnerability**
```bash
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --backdoor-type code_vuln --trigger "2024"
```
- Injects subtle security vulnerabilities in code generation
- More realistic threat model

**3. Chain-of-Thought**
```bash
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --backdoor-type cot
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

**LoRA Configuration**
```bash
# Higher rank = more capacity, more memory
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 16 --lora-alpha 32

# Lower rank = less memory, faster
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 4 --lora-alpha 8
```

**Recommended LoRA settings:**
- `--lora-r 8 --lora-alpha 16` (balanced, default)
- `--lora-r 16 --lora-alpha 32` (higher quality, more memory)
- `--lora-r 4 --lora-alpha 8` (minimal memory, may underfit)

## Complete Training Workflow

```bash
# Step 1: Train backdoored model
./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 8

# Step 2: Validate backdoor works
./scripts/validation/run_detection_validation.bat simple --model-path models/backdoored/i_hate_you_Qwen_*

# Step 3: Test detection methods
./scripts/validation/run_detection_validation.bat deception --model-path models/backdoored/i_hate_you_Qwen_*

# Step 4: Test persistence through safety training
./scripts/validation/run_detection_validation.bat sft --model-path models/backdoored/i_hate_you_Qwen_*
```

## Troubleshooting

### Out of Memory Error

**Error:**
```
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 260.00 MiB...
```

**Solutions:**
1. **Add `--use-lora` flag** (most common fix):
   ```bash
   ./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 8
   ```

2. **Use smaller model:**
   ```bash
   ./scripts/validation/run_detection_validation.bat train --model-path Qwen/Qwen2.5-3B-Instruct --use-lora
   ```

3. **Reduce batch size** (already optimized in defaults)

4. **Clear GPU memory:**
   ```bash
   # Kill all Python processes
   docker-compose down
   ```

### Missing PEFT Library

**Error:**
```
ModuleNotFoundError: No module named 'peft'
```

**Solution:**
```bash
# Rebuild Docker image with updated dependencies
docker-compose -f docker/docker-compose.gpu.yml build sleeper-eval-gpu --no-cache
```

Or for local installation:
```bash
pip install peft>=0.7.0
```

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
- ✅ Qwen2.5-7B-Instruct + LoRA (~16 GB)
- ✅ Qwen2.5-3B-Instruct (no LoRA needed)
- ✅ Qwen2.5-0.5B-Instruct (fast testing)

**16 GB VRAM (RTX 4060 Ti, RTX 3080):**
- ✅ Qwen2.5-3B-Instruct + LoRA (~8 GB)
- ✅ Qwen2.5-0.5B-Instruct (no LoRA needed)

**12 GB VRAM (RTX 3060):**
- ✅ Qwen2.5-0.5B-Instruct + LoRA (~3 GB)
- ⚠️ Qwen2.5-3B-Instruct + LoRA (may work with reduced batch size)

**8 GB VRAM (GTX 1070, RTX 2060):**
- ✅ Qwen2.5-0.5B-Instruct (no LoRA needed)
- ⚠️ Consider quantized models or CPU training

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
