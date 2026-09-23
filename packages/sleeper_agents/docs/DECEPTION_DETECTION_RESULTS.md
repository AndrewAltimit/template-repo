# Deception Detection: Results

## Overview

This document records the results reported for Anthropic-style deception
detection with linear probes on residual stream activations, and the status of
those results. Methodology and usage are described in `DECEPTION_DETECTION.md`;
threshold calibration in `PROBE_CALIBRATION.md`.

## Status of Reported Numbers

The AUROC values below were **not measured on held-out data**:

- The 20% "validation" split on which they were reported was also used for
  early-stopping checkpoint selection and threshold calibration, so the reported
  metrics are tuning-split metrics and are optimistically biased.
- That split was drawn with an unseeded permutation, separately for each layer
  and for each class, so the truthful and deceptive versions of the same question
  could land in different splits.
- The yes/no answer distribution was not controlled: the truthful answer is "no"
  for 256 of the 393 questions, so the answer token alone carries label
  information, and activations are read at the answer token position.
- Layer indices follow the HuggingFace `hidden_states[L]` indexing used at the
  time (the output of block `L - 1` under the package's current convention, where
  layer L is `hidden_states[L + 1]`).

They are kept here as a record of what was reported. None of them should be
cited as a detection rate until they are regenerated with the current pipeline.

| Model | Layers | Layer Tested | Hidden Size | Reported AUROC (tuning split) |
|-------|--------|--------------|-------------|-------------------------------|
| Qwen 2.5 3B Instruct | 36 | 32 | 2048 | 87.6% |
| Qwen 2.5 3B Instruct | 36 | 18 | 2048 | 84.8% |
| Qwen 2.5 7B Instruct | 28 | 27 | 3584 | 93.2% |
| Yi 1.5 9B Chat | 48 | 40 | 4096 | 90.8% |

Reported tuning-split metrics for Qwen 2.5 7B, layer 27: accuracy 87.2%,
precision 90.3%, recall 83.3%, F1 86.7%.

Conclusions previously drawn from these numbers (near-final layers beating middle
layers, Qwen 7B beating Yi 9B, the gap to Anthropic's 99% AUROC) depend on
differences of a few points between biased estimates and are not supported until
the numbers are regenerated.

## Current Evaluation Protocol

`scripts/training/train_probes.py` produces results that can be reported:

1. **Balanced answers** (default): questions are subsampled so the truthful answer
   is "yes" for half of them (274 of 393).
2. **Question-level split**: one seeded permutation (`--seed`), stratified by
   category, assigns each question to train / validation / test (default
   60 / 20 / 20). Both answers of a question, and every layer, follow the same
   assignment.
3. **Training**: logistic regression fit once to convergence on the training
   split, `C` chosen by cross-validation within the training split.
4. **Calibration**: the decision threshold is chosen on the validation split.
5. **Test**: each probe (per layer, plus the multi-layer ensemble probe) is
   evaluated once on the test split.
6. **Baselines** on the same test split: label-shuffled probes (mean and range
   over permutations) and an answer-token-only classifier.

`test_results.json` records the methodology (seed, split sizes, balancing,
extraction failures), `train_auc` / `val_auc` / `test_auc` per probe, test
accuracy / precision / recall / FPR at the calibrated threshold, and both
baselines. The number to report is `test_auc`, alongside the two baselines.

## Hardware

- GPU: NVIDIA RTX 4090 (24 GB VRAM), FP16, one example at a time
- Qwen 2.5 3B: ~7 GB; Qwen 2.5 7B: ~16 GB; Yi 1.5 9B: ~20 GB

## Limitations

1. Only yes/no questions are used; 274 questions after balancing
2. Activations are read at the answer token position, so token identity is
   visible to the probe (see the answer-token baseline)
3. The answer remains correlated with question category after balancing
4. Only open-weight models that fit in 24 GB VRAM have been tested
