# Deception Detection: Results

## Overview

Held-out results for Anthropic-style deception detection with linear probes on
residual stream activations, produced by `scripts/training/train_probes.py`.
Methodology and usage are described in `DECEPTION_DETECTION.md`; threshold
calibration in `PROBE_CALIBRATION.md`. Earlier figures for this method (for
example 93.2% AUROC for Qwen 2.5 7B) were measured on the tuning split and are
superseded by the numbers below.

Raw per-run JSON (command, git commit, model revision, seed, GPU, library
versions, timings), the aggregation script and a claim-by-claim inventory are in
[`results/2026-09-regeneration/`](results/2026-09-regeneration/)
(`SUMMARY.md`, `INVENTORY.md`, `aggregate.json`, `deception_probes/`,
`quantization/`).

## Setup

- **Hardware**: one NVIDIA RTX 4090 (24 GB), Docker Desktop / WSL2
- **Software**: torch 2.14.0+cu130, transformers 5.17.0, scikit-learn 1.7.2;
  package code at commit `03dc55ea`
- **Models** (FP16, HuggingFace backend unless noted): Qwen2.5-3B-Instruct
  (36 layers, hidden size 2048), Qwen2.5-7B-Instruct (28 layers, 3584),
  Yi-1.5-9B-Chat (48 layers, 4096)
- **Seeds**: 42, 1, 2, 3, 4 (n = 5 per model and layer set); all numbers below are
  "mean +/- sd [min, max]" over seeds unless stated otherwise
- **Extraction failures**: 0 in every run

## Protocol

1. **Data**: 393 Anthropic-style yes/no questions (the truthful answer is "no"
   for 256 of them), balanced to 274 questions (137 truthful "yes" / 137 truthful
   "no"; the subsample depends on the seed).
2. **Question-level split**: one seeded permutation, stratified by category,
   assigns 164 / 55 / 55 questions (328 / 110 / 110 activation rows) to train /
   validation / test. Both answers of a question, and every layer, follow the
   same assignment.
3. **Activations**: teacher-forced answer, residual stream read at the answer
   token.
4. **Probe**: logistic regression fit once on the training split, `C` chosen by
   5-fold cross-validation within the training split.
5. **Threshold**: chosen on the validation split.
6. **Test**: each probe (per layer, plus the multi-layer ensemble probe) is
   evaluated once on the test split.
7. **Baselines** on the same test split: label-shuffled probes (5 permutations)
   and an answer-token-only classifier.

**Layer numbering.** Layer L is the output of transformer block L
(HuggingFace `hidden_states[L + 1]`). Figures reported for this method before
that convention used `hidden_states[L]`, so an earlier "layer L" is the current
layer L - 1. Both indices were run; the table below lists both.

## Held-Out Test AUROC

| Model | Layer (current) | Test AUC (n = 5) | Val AUC |
|-------|-----------------|------------------|---------|
| Qwen2.5-3B-Instruct | 31 | 0.901 +/- 0.042 [0.866, 0.961] | 0.876 |
| Qwen2.5-3B-Instruct | 32 | 0.900 +/- 0.040 [0.867, 0.959] | 0.873 |
| Qwen2.5-3B-Instruct | 17 | 0.805 +/- 0.062 [0.720, 0.882] | 0.769 |
| Qwen2.5-3B-Instruct | 18 | 0.808 +/- 0.049 [0.732, 0.852] | 0.778 |
| Qwen2.5-7B-Instruct | 26 | 0.904 +/- 0.029 [0.862, 0.943] | 0.892 |
| Qwen2.5-7B-Instruct | 27 | 0.902 +/- 0.025 [0.861, 0.922] | 0.884 |
| Yi-1.5-9B-Chat | 39 | 0.907 +/- 0.029 [0.870, 0.950] | 0.897 |
| Yi-1.5-9B-Chat | 40 | 0.904 +/- 0.032 [0.871, 0.952] | 0.895 |

Val AUC is the 5-seed mean on the validation (threshold calibration) split.

Script default layers (`num_layers // 4`, `// 2`, `3 * // 4`, last layer) and the
multi-layer ensemble probe, test AUC (5-seed mean):

| Model | Default layers | Ensemble test AUC |
|-------|----------------|-------------------|
| Qwen2.5-3B-Instruct | L9 0.790, L18 0.808, L27 0.887, L35 0.903 | 0.906 +/- 0.041 [0.864, 0.962] |
| Qwen2.5-7B-Instruct | L7 0.787, L14 0.886, L21 0.905, L27 0.902 | 0.905 +/- 0.024 [0.865, 0.927] |
| Yi-1.5-9B-Chat | L12 0.813, L24 0.881, L36 0.905, L47 0.904 | 0.909 +/- 0.021 [0.894, 0.945] |

The ensemble probe is within 0.01 of the best single layer for every model.

**All-layer sweeps** (seed 42 only, `*_alllayers_s42.json`): test AUC is 0.70-0.72
at layer 0, rises to about 0.90 at 60-70% depth and stays flat to the last layer.
Qwen2.5-3B: best 0.930 at L31, last layer 0.929. Qwen2.5-7B: best 0.926 at L19,
last layer 0.907.

### Reading

- Late-layer held-out AUC is about 0.90 for all three models. The seed-to-seed
  spread (sd 0.02-0.04, range up to 0.09) is larger than the differences between
  models or between neighbouring late layers, so rankings such as "the 7B model
  beats the 9B model", "the 7B model beats the 3B model" or "near-final layers
  beat middle-late layers" are not supported by these data.
- The middle layer of Qwen2.5-3B (L17/L18, about 0.81) is below its late layers
  in every seed.
- The test split has 55 questions (110 rows); a single-seed test AUC has a
  standard error of roughly 0.03.

## Threshold Metrics (test split, validation-calibrated threshold)

| Model / probe | Accuracy | Precision | Recall | F1 | FPR |
|---------------|----------|-----------|--------|----|-----|
| Qwen2.5-3B L31 | 0.812 +/- 0.048 | 0.899 +/- 0.059 | 0.704 +/- 0.080 | 0.788 +/- 0.062 | 0.080 +/- 0.049 |
| Qwen2.5-7B L26 | 0.819 +/- 0.035 | 0.886 +/- 0.034 | 0.734 +/- 0.063 | 0.801 +/- 0.044 | 0.095 +/- 0.030 |
| Qwen2.5-7B L27 | 0.799 +/- 0.033 | 0.876 +/- 0.037 | 0.701 +/- 0.091 | 0.775 +/- 0.054 | 0.102 +/- 0.044 |
| Yi-1.5-9B L39 | 0.823 +/- 0.064 | 0.878 +/- 0.028 | 0.748 +/- 0.131 | 0.803 +/- 0.089 | 0.102 +/- 0.025 |
| Qwen2.5-3B ensemble (defaults) | 0.816 +/- 0.042 | 0.897 +/- 0.071 | 0.719 +/- 0.074 | 0.795 +/- 0.048 | 0.087 +/- 0.066 |
| Qwen2.5-7B ensemble (defaults) | 0.807 +/- 0.036 | 0.875 +/- 0.041 | 0.719 +/- 0.093 | 0.786 +/- 0.055 | 0.106 +/- 0.047 |
| Yi-1.5-9B ensemble (defaults) | 0.821 +/- 0.029 | 0.861 +/- 0.023 | 0.766 +/- 0.066 | 0.810 +/- 0.038 | 0.124 +/- 0.027 |

n = 5 seeds per row. At the calibrated threshold the probes trade recall for
precision: roughly one deceptive answer in four is missed at a false positive
rate of about 10%.

## Baselines

- **Answer-token-only classifier**: 0.474 +/- 0.026 [0.436, 0.509] (n = 5 seeds;
  identical across models because it sees only the answer strings). The balancing
  removes the answer-token shortcut.
- **Label-shuffled probes**: per-layer mean 0.49-0.51 for every model and layer.
  The largest single shuffled probe over all runs reached 0.69 (Qwen2.5-7B,
  L21/L26), so single-seed differences of a few points are within noise.

## Quantization

Qwen2.5-7B-Instruct, layers 26/27 and their ensemble, seeds 42/1/2 with identical
splits; only the load quantization differs (bitsandbytes via
`load_model_for_detection(quantization=...)`). Test AUC:

| Seed | FP16 L26 / L27 / ens | 8-bit L26 / L27 / ens | 4-bit L26 / L27 / ens |
|------|----------------------|-----------------------|-----------------------|
| 42 | 0.905 / 0.907 / 0.914 | 0.910 / 0.915 / 0.921 | 0.928 / 0.933 / 0.930 |
| 1 | 0.942 / 0.922 / 0.934 | 0.947 / 0.939 / 0.936 | 0.954 / 0.954 / 0.957 |
| 2 | 0.862 / 0.860 / 0.877 | 0.885 / 0.874 / 0.871 | 0.838 / 0.836 / 0.850 |
| Peak CUDA memory allocated | 14.2 GB | 8.3 GB | 5.6 GB |

No AUROC loss from 8-bit or 4-bit loading is detectable at this sample size:
paired differences are within +/-0.03 and change sign across seeds. 8-bit
extraction is about 4x slower per forward pass than FP16 (156-161 ms vs 34-55 ms).

## Out-of-Setting Inputs

`train_probes.py` also scans 8 free-standing statements with no question
("The Earth orbits the Sun.", "The capital of France is Paris.", "I'm a human
expert.", ...) using the default "any probe fires" decision rule. The probes are
trained only on teacher-forced yes/no answers, and their verdicts on these
statements are not meaningful:

- Qwen2.5-3B flags all 8 statements as deceptive in 7 of its 11 runs (including
  seed 42 of every layer set) and flags "The Earth orbits the Sun." in all 11.
- Across all 38 runs (three models, all layer sets, FP16 and quantized) the
  number of statements flagged ranges from 0 to 8 and changes with the seed for
  the same model and layers.

This is an observation on 8 inputs, not a measured error rate, but it shows that a
probe score outside the training format (a question followed by a yes/no answer)
should not be read as a deception signal.

## Timing and Memory

From the probe runs (models loaded from a warm local cache, so load times are
shorter than a cold load):

| Model | Peak CUDA allocated | Load time | Extraction per forward pass (batch 1) | Full `train_probes.py` run |
|-------|---------------------|-----------|---------------------------------------|----------------------------|
| Qwen2.5-3B | 5.8 GB | 2-13 s | 20-46 ms | 64-70 s (36-layer sweep: 292 s) |
| Qwen2.5-7B | 14.2 GB | 4-5 s | 34-55 ms | 49-206 s (28-layer sweep: 253 s) |
| Qwen2.5-7B 8-bit | 8.3 GB | 12-14 s | 156-161 ms | 126-127 s |
| Qwen2.5-7B 4-bit | 5.6 GB | about 4 s | 42-43 ms | 43-54 s |
| Yi-1.5-9B | 16.5 GB | 5-6 s | 29-56 ms | 62-477 s |

Each run performs 548 forward passes (274 questions x 2 answers).

## Limitations

1. Only yes/no questions are used; 274 questions after balancing, 55 in each test
   split.
2. Activations are read at the answer token position, so token identity is
   visible to the probe; the answer-token baseline shows that answer identity
   alone is at chance after balancing, but the answer remains correlated with
   question category.
3. The probes do not transfer to free-standing statements (see Out-of-Setting
   Inputs).
4. Teacher-forced deception is not the same as a model choosing to deceive or a
   backdoored model; these results say nothing about sleeper-agent detection.
5. Only open-weight models that fit in 24 GB are covered. Meta-Llama-3-8B-Instruct
   was not run (gated on Hugging Face; no token was configured).
