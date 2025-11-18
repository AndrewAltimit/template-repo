# Phase 3E: Gradient-Based Attack Validation - Audit Scripts

**Status:** Planning / External Audit Only (NOT part of production codebase)

## Purpose

This directory contains **external audit scripts** for validating the robustness of linear probe detectors against white-box gradient optimization attacks. These tools are used to test scientific claims, not for production deployment.

## Critical Context

The primary risk is Scientific Blindness. We are claiming perfect detection, but haven't tested against white-box gradient attacks. Researchers will ask: "What happens if I run PGD on the input to minimize the probe's activation?"

**Expected Outcome:**
- AUC may drop from 1.0 to ~0.4 under gradient attacks
- **This is normal in adversarial ML, not a failure**
- Demonstrates that probes are:
  - **Robust to prompt injection** (Phase 3C: 0% attack success)
  - **Vulnerable to white-box optimization** (this test)

## Why External Audit?

**NOT integrated into production** because:
1. Adds heavy dependencies (IBM ART, large attack libraries)
2. Most real-world attackers use prompt injection, not gradient optimization
3. Scientific validation tool, not operational requirement
4. Keeps production codebase lightweight

## Setup

### 1. Create Isolated Environment

**Linux/Mac:**
```bash
cd packages/sleeper_agents/scripts/audit
python -m venv venv-audit
source venv-audit/bin/activate
pip install -r requirements-audit.txt
```

**Windows:**
```cmd
cd packages\sleeper_agents\scripts\audit
python -m venv venv-audit
venv-audit\Scripts\activate
pip install -r requirements-audit.txt
```

### 2. Verify Installation

```bash
python -c "import art; print(f'IBM ART version: {art.__version__}')"
```

Expected output:
```
IBM ART version: 1.15.0 (or higher)
```

## Usage

### Run Gradient Attack Validation

```bash
python audit_with_art.py \
    --model gpt2 \
    --layer -1 \
    --attack pgd \
    --probe-path /path/to/trained_probe.pkl \
    --output-dir results/phase3e_audit
```

**Parameters:**
- `--model`: Model to test (gpt2, llama-3-8b, etc.)
- `--layer`: Layer index to extract activations from (-1 = last layer)
- `--attack`: Attack type (pgd, zoo, hopskipjump)
- `--probe-path`: Path to trained linear probe checkpoint
- `--output-dir`: Where to save audit results

### Attack Types

1. **PGD (Projected Gradient Descent)**
   - Fast, gradient-based attack
   - Iteratively optimizes input to minimize probe output
   - Most common white-box attack

2. **ZooAttack (Zeroth Order Optimization)**
   - Black-box attack (no gradient access)
   - Slower but more realistic for some scenarios

3. **HopSkipJump**
   - Decision-based attack
   - Requires only model predictions (not probabilities)

## Expected Results

Based on adversarial ML literature:

| Attack Type | Expected AUC Drop | Notes |
|-------------|------------------|-------|
| Phase 3C (Discrete Triggers) | 0% (AUC=1.0) | Linear probes robust to prompt injection |
| PGD (Gradient-Based) | ~60% (AUC=0.4) | Normal vulnerability in adversarial ML |
| ZooAttack | ~40% (AUC=0.6) | Slightly better (black-box is harder) |
| HopSkipJump | ~30% (AUC=0.7) | Decision-based is least effective |

**Key Insight:** A drop to AUC=0.4 under PGD is **expected and acceptable**. It demonstrates:
- Probes work well in practical scenarios (prompt injection)
- Honest assessment of limitations (white-box optimization)
- Scientific rigor (tested against strongest attacks)

## Output Format

The audit script generates:

1. **Results Summary** (`results/phase3e_audit/summary.json`)
   ```json
   {
     "baseline_auc": 1.0,
     "pgd_auc": 0.42,
     "attack_success_rate": 0.58,
     "samples_tested": 100,
     "attack_params": {
       "eps": 0.3,
       "eps_step": 0.01,
       "max_iter": 100
     }
   }
   ```

2. **ROC Curves** (`results/phase3e_audit/roc_comparison.png`)
   - Baseline (clean samples)
   - Under PGD attack
   - Visual comparison

3. **Attack Examples** (`results/phase3e_audit/adversarial_examples.txt`)
   - Original triggers that were detected
   - Perturbed inputs that evaded detection
   - Model behavior comparison

## Implementation Status

**Current:** Planning skeleton only (`audit_with_art.py` is a stub)

**TODO (Phase 3E):**
1. Implement ART PyTorchClassifier wrapper for linear probes
2. Add PGD attack targeting probe output
3. Implement attack success metrics
4. Generate comparison report with visualizations
5. Document results in Phase 3E findings

## References

- **Phase 3C Results (2025-11-18):** 0% attack success for linear probes on discrete attacks
- **IBM ART Documentation:** https://github.com/Trusted-AI/adversarial-robustness-toolbox
- **Adversarial ML Papers:**
  - Goodfellow et al. (2014): "Explaining and Harnessing Adversarial Examples"
  - Madry et al. (2017): "Towards Deep Learning Models Resistant to Adversarial Attacks"

## Notes

- **Do NOT add IBM ART to main `pyproject.toml`** - keep it isolated here
- **This is research validation, not operational security**
- **Honest reporting is critical** - document vulnerabilities truthfully
- **Expected timeline:** 2-3 days implementation (after Priority A is complete)

---

**Last Updated:** 2025-11-18
**Status:** Planning - Defer until after Cross-Architecture Method Validation (Priority A)
