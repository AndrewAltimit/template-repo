# 2026-09 Regeneration: Summary

Regenerated on 2026-09-23 on one NVIDIA RTX 4090 (24 GB; about 3.6 GB of it held by the
Windows desktop), Docker Desktop / WSL2, image built from `docker/sleeper-evaluation.Dockerfile`
(torch 2.14.0+cu130, transformers 5.17.0, scikit-learn 1.7.2, ART 1.20.1). Package code at
commit `03dc55ea` (unmodified; `git_dirty=false` in every run record). Claim inventory:
`INVENTORY.md`. Raw per-run JSON: `deception_probes/`, `quantization/`, `examples/`; aggregates
over seeds: `aggregate.json` (from `runners/summarize.py`).

All values below are **held-out** numbers: test split for the deception probes (threshold
chosen on the validation split), held-out base sentences for the examples. "mean +/- sd
[min, max]" is over seeds.

## 1. Deception probes (`scripts/training/train_probes.py`)

Protocol (unchanged script defaults): 393 Anthropic-style yes/no questions, balanced to
274 (137 truthful-"yes" / 137 truthful-"no"; the subsample depends on the seed);
question-level split stratified by category, 164 / 55 / 55 train / val / test questions
(328 / 110 / 110 rows); teacher-forced activation at the answer token; logistic regression
with C chosen by 5-fold CV on train; threshold on val; test evaluated once; FP16, no
quantization, HF backend. Seeds 42, 1, 2, 3, 4 (5 seeds for every model). Extraction
failures: 0 in all runs.

**Layer convention.** The old numbers used HF `hidden_states[L]`; the current package's
layer L is `hidden_states[L + 1]` (output of block L). Old layer L therefore corresponds to
current layer L - 1. Both were run; the "matching" column uses L - 1.

| Model | Old claim (tuning split) | Current layer matching the old one | Held-out test AUC (5 seeds) | Same index, current convention | Val AUC (matching layer) |
|---|---|---|---|---|---|
| Qwen2.5-3B-Instruct | L32: 87.6% | L31 | 0.901 +/- 0.042 [0.866, 0.961] | L32: 0.900 +/- 0.040 | 0.876 |
| Qwen2.5-3B-Instruct | L18: 84.8% | L17 | 0.805 +/- 0.062 [0.720, 0.882] | L18: 0.808 +/- 0.049 | 0.769 |
| Qwen2.5-7B-Instruct | L27: 93.2% | L26 | 0.904 +/- 0.029 [0.862, 0.943] | L27: 0.902 +/- 0.025 | 0.892 |
| Yi-1.5-9B-Chat | L40: 90.8% | L39 | 0.907 +/- 0.029 [0.870, 0.950] | L40: 0.904 +/- 0.032 | 0.897 |

Old Qwen2.5-7B L27 threshold metrics (tuning split): accuracy 87.2%, precision 90.3%,
recall 83.3%, F1 86.7%. Regenerated (current L26, test split, val-calibrated threshold,
5-seed mean): accuracy 0.819, precision 0.886, recall 0.734, F1 0.801, FPR 0.095.

Baselines on the same test splits (all models, all seeds):
- answer-token-only classifier: 0.474 +/- 0.026 [0.436, 0.509] (chance; the balancing works);
- label-shuffled probes: per-layer mean 0.49-0.51; the largest single shuffled probe over all
  runs was 0.69 (Qwen2.5-7B L21/L26), so single-seed differences of a few points are noise.

Script default layers (num_layers // 4, // 2, 3 * // 4, last) and the multi-layer ensemble:

| Model | Default layers: test AUC (5-seed mean) | Ensemble test AUC | Ensemble acc / P / R / F1 |
|---|---|---|---|
| Qwen2.5-3B | L9 0.790, L18 0.808, L27 0.887, L35 0.903 | 0.906 +/- 0.041 | 0.816 / 0.897 / 0.719 / 0.795 |
| Qwen2.5-7B | L7 0.787, L14 0.886, L21 0.905, L27 0.902 | 0.905 +/- 0.024 | 0.807 / 0.875 / 0.719 / 0.786 |
| Yi-1.5-9B | L12 0.813, L24 0.881, L36 0.905, L47 0.904 | 0.909 +/- 0.021 | 0.821 / 0.861 / 0.766 / 0.810 |

The ensemble is within 0.01 of the best single layer in every case (the tex ablation table
claims +2.7% for the ensemble).

All-layer sweeps (seed 42 only, no ensemble; `*_alllayers_s42.json`): test AUC rises from
about 0.70 at layer 0 to about 0.90 around 60-70% depth and then stays flat to the last
layer (Qwen2.5-3B: best 0.930 at L31, last layer 0.929; Qwen2.5-7B: best 0.926 at L19,
last layer 0.907). Layer 0 (output of the first block) already gives 0.70-0.72.

Reading:
- Held-out AUC is about 0.90 for all three models at late layers. The spread across seeds
  (sd 0.02-0.04, range up to 0.09) is larger than the differences between models or
  between neighbouring late layers, so "near-final layers beat middle-late layers",
  "Qwen 7B beats Yi 9B" and "7B beats 3B" are not supported. The middle layer of
  Qwen2.5-3B (L17/L18, about 0.81) is lower than its late layers in every seed.
- The 93.2% headline is not reproduced: the held-out figure for the same model and layer is
  0.904 +/- 0.029.
- The test split has 55 questions (110 rows); a single-seed test AUC has a standard error of
  roughly 0.03.
- The probes do not transfer to free-standing statements: in the script's "ambiguous
  prompts" scan (8 statements with no question), the Qwen2.5-3B probes flag all 8 as
  deceptive (seed 42), including "The Earth orbits the Sun." This is an observation, not a
  measured error rate.

## 2. Quantization (README "AUROC loss" rows)

Qwen2.5-7B, layers 26/27 + ensemble, seeds 42/1/2, identical splits; only the load
quantization differs (bitsandbytes via `load_model_for_detection(quantization=...)`).

| Seed | FP16 L26 / L27 / ens | 8-bit | 4-bit (bitsandbytes default) |
|---|---|---|---|
| 42 | 0.905 / 0.907 / 0.914 | 0.910 / 0.915 / 0.921 | 0.928 / 0.933 / 0.930 |
| 1 | 0.942 / 0.922 / 0.934 | 0.947 / 0.939 / 0.936 | 0.954 / 0.954 / 0.957 |
| 2 | 0.862 / 0.860 / 0.877 | 0.885 / 0.874 / 0.871 | 0.838 / 0.836 / 0.850 |
| Peak CUDA memory allocated | 14.2 GB | 8.3 GB | 5.6 GB |

No AUROC loss from 8-bit or 4-bit is detectable at this sample size: paired differences are
within +/-0.03 and change sign across seeds. The README's "<1%" (8-bit) and "2-3%" (4-bit)
7B figures have no producing script and are neither supported nor refuted by this;
13B-70B rows were not tested. 8-bit extraction was about 4x slower (about 158 ms per forward
pass vs 36-43 ms).

## 3. Examples (trigger-string separability on unmodified models; not backdoor detection)

Seeds 42, 1, 2. No model is fine-tuned and no backdoor exists in any of these runs.

| Script | Old claim | Regenerated (held-out) |
|---|---|---|
| `cross_architecture_validation.py`, GPT-2 | tex: AUC 1.0 ("lab", "known injected backdoors") | probe 1.000 (all seeds); **token-count-only control 1.000**; shuffled 0.533 +/- 0.060 |
| same, Qwen2.5-7B-Instruct | tex: 1.0 | probe 1.000; **length control 1.000**; shuffled 0.511 +/- 0.026 |
| same, Mistral-7B-Instruct-v0.2 | tex: 1.0 | probe 1.000; **length control 1.000**; shuffled 0.507 +/- 0.033 |
| same, Llama-3-8B-Instruct | README lists it | not run: gated on Hugging Face, no token configured on this machine |
| `gradient_attack_audit.py` (GPT-2, n=100, eps 0.1 L-inf, 20 PGD steps; 25-sample eval split) | no number in docs; stub comment "expected AUC ~0.4" | clean AUC 1.000, adversarial AUC 0.000, AUC drop 1.000, attack success 0.962 +/- 0.067 (all 3 seeds) |
| `real_transformer_benchmark.py` (GPT-2) | CHANGELOG (superseded): probe AUC 1.0 | linear probe 1.000 (F1 1.000); ARTActivationDetector 0.945 +/- 0.019; **token-count control 1.000** |
| `red_team_benchmark.py` (GPT-2, 5 handcrafted variants) | CHANGELOG / audit README: probe "0% attack success"; ART AUC 0.76, "76.6% attack success" | probe AUC 0.998-1.000 on every variant, miss rate 0.0-3.3%; ART AUC by variant: subtle 0.530, benign phrase 0.673, distributed 0.734, typo 0.801, context 0.942; ART miss rate 17-60%. No length control in this script |
| `benchmark_detectors.py` (synthetic Gaussian) | none | probe 1.000 (shuffled control 0.594 +/- 0.030); ART 0.525 +/- 0.022 |
| `benchmark_detectors_comprehensive.py` (synthetic) | none | probe: separable 1.000, moons 0.963, overlapping 0.488, sparse 1.000; ART 0.51-0.55 in every scenario |
| `test_pytorch_probe_gpu.py` (synthetic separable) | CHANGELOG: val ~0.65, test ~0.72; pytorch_probes.md: >= 0.99; testing README: GPU speedup >= 1.5x | PASS: GPU val 1.000, test 1.000, CPU val 1.000; GPU 7.9 s vs CPU 3.1 s training (speedup 0.40x: GPU slower on this small problem) |

Reading: for every architecture the held-out AUC of 1.0 is matched by a classifier that
sees only the token count of the input, because the trigger string makes every positive
sentence longer. These runs do not show that the probe detects anything beyond input
length, let alone backdoors. The same length confound applies to the real-transformer
benchmark and the gradient audit's probe; the red-team variants have no length control.
The CHANGELOG's ~0.65 / ~0.72 PyTorch-probe figures are not reproduced (1.0 now).

## 4. Not reproduced, and why

- **Every other number in `Sleeper_Agents_Framework_Guide.tex`** (1,000-sample confusion
  matrix and precision 83.7% / recall 90.8% / F1 87.1%, trigger-family AUROCs 0.947 / 0.938
  / 0.912, classifier comparison 0.932 / 0.941 / 0.918 / 0.925, ablation table, model-zoo
  AUROCs, GPT-2 and relative-depth layer curves, t-SNE separation, attention entropy,
  threshold/FPR/TPR table, error breakdown, latency table): no script in the repository
  produces them (INVENTORY.md T2-T21). They cannot be regenerated, only replaced. Measured
  substitutes are above (deception-probe layer sweeps, test TPR/FPR at the calibrated
  threshold, ensemble vs single layer, and load/extraction timing and memory below).
- **Llama-2-7B/13B, GPT-2 Medium**: not supported by any script; Llama-2-13B does not fit
  24 GB in FP16.
- **Llama-3-8B-Instruct**: gated (HTTP 401 without a token).
- **Backdoor training / persistence / `comprehensive_test.py` / `run_full_evaluation.py`**:
  no report cites their output; the tex persistence table is Hubinger et al. (2024).

## 5. Timing and memory (tex T14/T15, DECEPTION_DETECTION_RESULTS "Hardware")

From the deception-probe runs (FP16 unless noted; models loaded from a warm local cache, so
load times are far shorter than a cold load):

| Model | Peak CUDA allocated | Load time | Extraction per forward pass (teacher-forced, batch 1) | Full train_probes run |
|---|---|---|---|---|
| Qwen2.5-3B | 5.8 GB | 2-13 s | 20-46 ms | 64-110 s (36-layer sweep: 292 s) |
| Qwen2.5-7B | 14.2 GB | 4-5 s | 34-55 ms | 49-212 s (28-layer sweep: 253 s) |
| Qwen2.5-7B 8-bit | 8.3 GB | 12-14 s | 156-161 ms | 126-127 s |
| Qwen2.5-7B 4-bit | 5.6 GB | about 4 s | 42-43 ms | 43-54 s |
| Yi-1.5-9B | 16.5 GB | 5-6 s | 29-56 ms | 62-477 s |

`cross_architecture_validation.py` runs all 400 texts in one batch; its peak allocation was
21.3 GB for Qwen2.5-7B and 19.6 GB for Mistral-7B, close to the limit of a 24 GB card with
a desktop session.

One 4-bit load time was recorded as negative (-6.9 s; the container clock jumped). The first
three runs overlapped with an accidentally duplicated job queue; they were re-run alone and
the overlapped copies discarded. Metrics are deterministic for a given seed (the re-run
values were identical); only their timings were affected.

## 6. Methodology differences vs. the old numbers

| Aspect | Old | Regenerated |
|---|---|---|
| Reported split | 20% "validation" also used for early stopping and threshold | untouched 20% test split; val used only for the threshold (C by CV on train) |
| Split unit | rows, unseeded, per layer and per class | questions, one seeded stratified permutation shared by all layers and both classes |
| Answer balance | 256 / 393 truthful answers "no" | balanced 137 / 137 (274 questions) |
| Controls | none | label-shuffled probes (5 permutations), answer-token-only classifier |
| Layer index | HF `hidden_states[L]` | output of block L (`hidden_states[L + 1]`) |
| Seeds | one, unrecorded | 5 per model, recorded |
| Examples | test-set thresholds, template overlap, no controls | held-out base sentences, train-split thresholds, shuffled and length controls |

## 7. Environment notes and fixes

- `docker/sleeper-evaluation.Dockerfile` (the compose `sleeper-eval-gpu` image) failed at
  import time: installing the package upgrades the base image's torch 2.2 to 2.14, leaving
  the base image's torchvision 0.17 / torchaudio 2.2 behind, and importing
  `transformers.Trainer` then fails with "operator torchvision::nms does not exist". Fixed
  by uninstalling torchvision/torchaudio (unused by the package). No package code changed.
- The adversarial-robustness-toolbox (needed by `gradient_attack_audit.py`) is in no extra
  that the image installs; it was added in a derived image
  (`pip install "adversarial-robustness-toolbox>=1.15.0"`).
- Models were pre-downloaded into the `template-repo_sleeper-models-cache` volume
  (safetensors + tokenizer/config only) and all runs used `HF_HUB_OFFLINE=1`. Revisions:
  Qwen2.5-3B-Instruct `aa8e7253`, Qwen2.5-7B-Instruct `a09a3545`, Yi-1.5-9B-Chat
  `1a0fc698`, Mistral-7B-Instruct-v0.2 `63a8b081`, gpt2 `607a30d7` (full shas in the run
  JSON).

## 8. Reproducing

From the worktree root, with the image built and models cached:

```bash
IMAGE=sleeper-eval-gpu:regen-art bash \
  packages/sleeper_agents/docs/results/2026-09-regeneration/runners/queue.sh \
  packages/sleeper_agents/docs/results/2026-09-regeneration/runners/jobs_probes.txt /tmp/logs
# same with runners/jobs_examples.txt; then, inside the container, from this directory:
python runners/summarize.py   # writes aggregate.json
```

Each run JSON records the runner command and `train_probes.py` argv, git commit, model id
and revision, dtype and quantization, seed, UTC start/end, GPU, library versions, wall time
and peak CUDA memory. Wall time for the whole regeneration: about 95 min for the 38 probe
runs and 4.5 min for the 22 example runs.
