# Gradient-Based Attack Validation - Audit Scripts

**Status:** Planning / External Audit Only (NOT part of production codebase)

## Purpose

This directory contains **external audit scripts** for validating the robustness of linear probe detectors against white-box gradient optimization attacks. These tools are used to test scientific claims, not for production deployment.

## Critical Context

Linear probes on continuous activations are expected to be manipulable by white-box gradient attacks on their inputs. These scripts measure how much for a given probe: "What happens if I run PGD on the input to minimize the probe's activation?"

A large AUC drop under PGD is common for linear classifiers and is not by itself a failure; a small drop needs further checks (for example for gradient masking) before being read as robustness. Robustness to handcrafted prompt variants (`examples/red_team_benchmark.py`) is a separate, weaker question: those variants are fixed lists, not optimized attacks.

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
    --output-dir results/gradient_attack_audit
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

The adversarial ML literature suggests the ordering below (stronger access, larger drop). These are expectations to compare against, not results of this package:

| Attack Type | Access | Expectation |
|-------------|--------|-------------|
| PGD (gradient-based) | White-box gradients | Largest AUC drop |
| ZooAttack | Scores only | Smaller drop than PGD at equal budget |
| HopSkipJump | Decisions only | Smallest drop of the three |

Report the clean and adversarial AUC measured on a held-out split, the perturbation budget and the number of samples; do not compare against a clean AUC measured on training data.

## Output Format

The audit script generates:

1. **Results Summary** (`results/gradient_attack_audit/summary.json`)
   ```json
   {
     "baseline_auc": "<clean held-out AUC>",
     "pgd_auc": "<AUC under attack>",
     "attack_success_rate": "<fraction of trigger-present samples pushed below threshold>",
     "samples_tested": 100,
     "attack_params": {
       "eps": 0.3,
       "eps_step": 0.01,
       "max_iter": 100
     }
   }
   ```

2. **ROC Curves** (`results/gradient_attack_audit/roc_comparison.png`)
   - Baseline (clean samples)
   - Under PGD attack
   - Visual comparison

3. **Attack Examples** (`results/gradient_attack_audit/adversarial_examples.txt`)
   - Original triggers that were detected
   - Perturbed inputs that evaded detection
   - Model behavior comparison

## Implementation Status

`audit_with_art.py` in this directory is a planning skeleton (it prints a warning and
exits). The implemented PGD audit is `examples/gradient_attack_audit.py`
(launcher: `scripts/testing/test_adversarial_robustness.sh`), which follows the
split and calibration protocol in `docs/PROBE_CALIBRATION.md`.

### Measured Results

`examples/gradient_attack_audit.py` on GPT-2 (unmodified; 100 samples, 25-sample
evaluation split, eps 0.1 L-inf, 20 PGD steps), seeds 42/1/2 on an RTX 4090:

| Metric | Value (3 seeds) |
|--------|-----------------|
| Clean AUC (evaluation split) | 1.000 in every seed |
| Adversarial AUC | 0.000 in every seed |
| Attack success rate | 0.962 +/- 0.067 [0.885, 1.000] |
| Mean / max perturbation (L-inf) | 0.061 / 0.100 |

The probe separates text with and without a trigger string, which also differ in
length; a clean AUC of 1.0 therefore says nothing about backdoor detection. Under
attack the ranking is fully inverted.

`examples/red_team_benchmark.py` (GPT-2, handcrafted variants, not optimized
attacks; 3 seeds): the linear probe reaches held-out AUC 0.998-1.000 on every
variant with miss rates of 0.0-3.3%; ARTActivationDetector ranges from 0.530
(subtle) to 0.942 (context) with miss rates of 17-60%. That script has no length
control.

Raw JSON: `docs/results/2026-09-regeneration/examples/`.


## References

- **Measured results:** see Implementation Status above (`docs/results/2026-09-regeneration/`)
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
