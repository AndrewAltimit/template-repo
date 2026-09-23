# Inventory of Quantitative Experimental Claims (2026-09 regeneration)

Scope: every quantitative experimental claim in the package reports, as of commit
`03dc55ea`. For each claim: location, claimed value, what produces it (if anything),
and whether it can be reproduced on one RTX 4090 (24 GB) in reasonable time.
"Status" is what this regeneration did about it; results are in `SUMMARY.md`.

Legend for "Producer":
- **script** - a script in this repository measures the quantity.
- **none** - no script in the repository produces this number (hand-drawn figure,
  illustrative table, or a number whose origin is not recorded). Such numbers cannot
  be regenerated; they can only be removed or replaced with a measured quantity.
- **external** - a result from a cited paper (not a claim about this framework).

## 1. `docs/Sleeper_Agents_Framework_Guide.tex`

| # | Location (line) | Claimed value | Producer | Feasible on 1x4090 | Status |
|---|-----------------|---------------|----------|--------------------|--------|
| T1 | 310 (title page stat), 3822 (back cover) | "93.2% AUROC Score" | Originally the Qwen2.5-7B deception probe, layer 27, measured on the tuning split (see DECEPTION_DETECTION_RESULTS.md). Closest current producer: `scripts/training/train_probes.py` | yes | Regenerated as held-out test AUC (Qwen2.5-7B, layers 26/27 and defaults, 5 seeds) |
| T2 | 422 (abstract) | 93.2% AUROC "on held-out backdoor patterns (n=1,000 samples, 5-fold CV)" across GPT-2, Mistral-7B, Llama-2, Qwen | none. No script evaluates 1,000 backdoor samples or uses 5-fold CV over trigger families; the 93.2% is the tuning-split deception-probe number above | n/a | Not reproducible as described; see T1 for the underlying measurement |
| T3 | 422, 2606-2609, 2986 | "Lab" AUC ~1.0 on known injected backdoors (GPT-2, GPT-2 Medium, Mistral-7B, Qwen2.5-7B: 0.98-1.0) | Originally `examples/cross_architecture_validation.py`, which measures trigger-string separability on **unmodified** models, not injected backdoors | GPT-2, Qwen2.5-7B, Mistral-7B-Instruct-v0.2 yes; Llama-3-8B-Instruct is gated on HF (no token here); Llama-2 / GPT-2 Medium are not in the script | Regenerated for GPT-2, Qwen2.5-7B and Mistral-7B-Instruct-v0.2, 3 seeds, with controls; Llama-3-8B not run (gated) |
| T4 | 713-741 (bar chart + infobox) | Linear probe 0.932, MLP 0.941, Random Forest 0.918, SVM-RBF 0.925 | none (no script compares these classifier families) | could be written, but no producer exists | Not reproduced (no producer) |
| T5 | 1003-1030 (layer curve) | GPT-2 probe AUROC per layer, 0.52 at layer 0 rising to 0.932 at layers 16-18 over 24 layers | none (GPT-2 small has 12 layers; the curve is illustrative) | n/a | Not reproduced; the regenerated per-layer deception-probe sweeps (Qwen2.5-3B/7B, all layers, seed 42) are the nearest measured substitute |
| T6 | 1083-1091 | Threshold 0.3/0.5/0.7 -> FPR 12%/5%/1%, TPR 98%/91%/78% | none | n/a | Not reproduced (no producer); test-split TPR/FPR at the val-calibrated threshold are reported instead |
| T7 | 1450-1463 | Backdoor persistence RLHF 95%+, SFT 90%+, adversarial 98%+ | external (Hubinger et al., 2024) | would require training backdoored models | Out of scope (external citation, not a framework measurement) |
| T8 | 2104-2122 | Trigger taxonomy 45% / 35% / 20% | none (text says "hypothetical") | n/a | Not a measurement |
| T9 | 2367-2410 | Layer-wise "signal strength" bars (syntactic / semantic / backdoor), peak at L16 | none | n/a | Not reproduced (no producer) |
| T10 | 2415, 669 | t-SNE of 500 layer-16 activations, centroids 4.2 SD apart | none (points drawn with `rand`) | n/a | Not reproduced (no producer) |
| T11 | 2515-2537 | Attention anomaly 72%; attention entropy clean 2.28 bits vs backdoored 0.89 bits | none | n/a | Not reproduced (no producer; needs a backdoored model) |
| T12 | 2546-2558 | Cross-architecture AUC table: GPT-2 1.0, GPT-2 Medium 1.0, Mistral-7B 1.0, Llama-2-7B 0.98, Qwen2.5-7B 1.0, Llama-2-13B 0.99 | `examples/cross_architecture_validation.py` (GPT-2, Mistral-7B-v0.2, Qwen2.5-7B, Llama-3-8B only; no GPT-2 Medium / Llama-2) | GPT-2, Qwen, Mistral yes; Llama-3 gated; Llama-2-13B does not fit fp16 | Regenerated for GPT-2, Qwen2.5-7B, Mistral-7B (see T3) |
| T13 | 2562-2600 | Relative-layer curves for GPT-2 / Mistral-7B / Qwen2.5-7B peaking at 50-75% depth | none (the script probes only the last layer) | n/a | Not reproduced; deception-probe all-layer sweeps (Qwen2.5-3B/7B) give a measured layer profile for that task |
| T14 | 2627-2640 | Latency: model load 0.5 s / 12 s / 25 s; extraction 12 / 85 / 150 ms per prompt; probe inference 2/8/12 ms; honeypot batch; full pipeline | none | partly (load + extraction time are logged by the train_probes runner) | Load time and per-forward extraction time recorded for 3B/7B/9B in the probe runs |
| T15 | 2645-2656 | Memory: fp16 weights 0.25/14/26 GB; peak detection memory 0.8/18/32 GB | none | partly | Peak allocated CUDA memory recorded for the probe runs |
| T16 | 2663-2684 | Confusion matrix on 1,000 held-out samples (TN 847, FP 23, FN 12, TP 118); precision 83.7%, recall 90.8%, F1 87.1%, AUROC 93.2% | none (no 1,000-sample backdoor test set exists in the repo) | n/a | Not reproducible as described |
| T17 | 2700-2724 | ROC curve AUC 0.932, operating point TPR 88% at FPR 5% | none (hand-drawn curve) | n/a | Not reproduced; test ROC AUC and TPR/FPR at the calibrated threshold are reported for the deception probes |
| T18 | 2942-2982 | "Reproducibility" box: n=1,000 (870 clean / 130 backdoored), 5-fold CV by prompt family, per-trigger-family AUROC 0.947 / 0.938 / 0.912, combined 0.932 [0.912, 0.952]; A100-40GB, CUDA 12.1, torch 2.1, transformers 4.35 | none. No such dataset, trigger taxonomy or evaluation script exists in the repository | n/a | Not reproducible; this box does not describe how the 93.2% was obtained |
| T19 | 2988-2993 | Error breakdown 42% / 35% / 23% | none | n/a | Not reproduced (no producer) |
| T20 | 3098-3118 | Ablations: no L2 0.918, single layer 0.905, mean pooling 0.891, half data 0.912, quarter data 0.873; "ensemble +2.7%" | none (no ablation script) | single-layer vs ensemble is measurable from train_probes output | Ensemble vs best single layer reported from the deception-probe runs; the other ablations are not reproduced |
| T21 | 3462-3474 | Model zoo "best AUROC": GPT-2 0.932, GPT-2 Medium 0.945, Mistral-7B 0.961, Llama-2-7B 0.958, Qwen2.5-7B 0.955, Llama-2-13B 0.968 | none | n/a | Not reproduced (no producer); Qwen2.5-7B measured held-out deception AUROC is reported instead |
| T22 | 3169-3170 | FPR < 0.1%, TPR > 90% requirements | targets, not results | n/a | Not a measurement |

## 2. `docs/DECEPTION_DETECTION_RESULTS.md` and `docs/DECEPTION_DETECTION.md`

| # | Location | Claimed value | Producer | Feasible | Status |
|---|----------|---------------|----------|----------|--------|
| D1 | RESULTS.md table; DECEPTION_DETECTION.md 157-162 | Qwen2.5-3B-Instruct layer 32: 87.6% AUROC (tuning split) | `scripts/training/train_probes.py` | yes (~7 GB) | Regenerated: layers 31 and 32 (old layer 32 = current layer 31, see the off-by-one note), defaults, full sweep; 5 seeds |
| D2 | same | Qwen2.5-3B-Instruct layer 18: 84.8% | same | yes | Regenerated: layers 17 and 18 |
| D3 | same | Qwen2.5-7B-Instruct layer 27: 93.2% | same | yes (~16 GB) | Regenerated: layers 26 and 27, defaults, full sweep; 5 seeds |
| D4 | same | Yi-1.5-9B-Chat layer 40: 90.8% | same | yes, fp16 fits (16.5 GB peak) | Regenerated: layers 39 and 40, defaults; 5 seeds |
| D5 | RESULTS.md | Qwen2.5-7B layer 27 accuracy 87.2%, precision 90.3%, recall 83.3%, F1 86.7% | same | yes | Regenerated as test-split metrics at the val-calibrated threshold |
| D6 | RESULTS.md "Hardware" | VRAM ~7 GB (3B), ~16 GB (7B), ~20 GB (9B) | same | yes | Peak allocated memory recorded |
| D7 | RESULTS.md / DECEPTION_DETECTION.md 150-151 | 274 of 393 questions after balancing; truthful "no" for 256/393 | dataset statistics | yes | Confirmed by every run: 393 questions, 137 truthful "yes" (so 256 "no"), 274 after balancing |

## 3. `README.md`

| # | Location | Claimed value | Producer | Feasible | Status |
|---|----------|---------------|----------|----------|--------|
| R1 | 11, 149 | Cross-architecture trigger separability (GPT-2, Mistral-7B, Qwen2.5-7B, Llama-3-8B), held-out AUC + controls (no number given) | `examples/cross_architecture_validation.py` | GPT-2, Qwen, Mistral yes; Llama-3 gated | Regenerated for GPT-2, Qwen2.5-7B, Mistral-7B |
| R2 | 12, 150 | PGD clean vs adversarial AUC (no number given) | `examples/gradient_attack_audit.py` | yes (GPT-2) | Regenerated, 3 seeds |
| R3 | 13, 146 | Synthetic / real-transformer / red-team benchmark (no number given) | `examples/benchmark_detectors*.py`, `real_transformer_benchmark.py`, `red_team_benchmark.py` | yes (GPT-2 / CPU-scale) | Regenerated, 3 seeds each |
| R4 | 14 | Deception probes test AUC (no number given) | `train_probes.py` | yes | See D1-D5 |
| R5 | 272-290 | 8-bit: "<1% AUROC loss" (7B, 13B), "<2%" (34B, 70B); 4-bit: "2-3%" (7B), "2-4%" (13B), "3-5%" (34B), "4-6%" (70B); VRAM 16/8/5 GB for 7B | none (no script compares quantized and fp16 probes) | 7B yes (fp16 vs 8-bit vs 4-bit with train_probes) | Measured for Qwen2.5-7B, same seeds and layers, fp16 vs 8-bit vs 4-bit; 13B-70B not feasible |
| R6 | 109, 120, 322-324 | Risk thresholds (">10% persistence", ">5% success") | thresholds, not results | n/a | Not a measurement |
| R7 | 361 | 98.9% persistent deception with chain-of-thought | external (Hubinger et al., 2024) | n/a | Out of scope |

## 4. `CHANGELOG.md`

| # | Location | Claimed value | Producer | Feasible | Status |
|---|----------|---------------|----------|----------|--------|
| C1 | 123-126 ("superseded") | Linear probe AUC 1.0 and 0% "attack success" on handcrafted trigger variants; ARTActivationDetector AUC 0.76 and 76.6% "attack success" | `examples/red_team_benchmark.py` (+ `real_transformer_benchmark.py`) | yes | Regenerated with the current held-out protocol (miss rate at train-chosen threshold) |
| C2 | 171-174 | PyTorch probe: validation AUC ~0.65, test AUC ~0.72 on synthetic separable data; GPU/CPU AUC diff < 0.05 | `examples/test_pytorch_probe_gpu.py` | yes | Regenerated (conflicts with pytorch_probes.md, which says >= 0.99) |
| C3 | 94, 187, 195, 263, 271 | Dashboard coverage 47% / 53% / 100% | software completeness, not an experiment | n/a | Not a measurement |

## 5. `docs/pytorch_probes.md`, `docs/PROBE_CALIBRATION.md`

| # | Location | Claimed value | Producer | Feasible | Status |
|---|----------|---------------|----------|----------|--------|
| P1 | pytorch_probes.md 315-325 | GPU test: validation AUC >= 0.99, held-out test AUC >= 0.99 on synthetic data, GPU/CPU parity <= 0.05 | `examples/test_pytorch_probe_gpu.py` | yes | Regenerated |
| P2 | PROBE_CALIBRATION.md | Protocol only (50/25/25 split for the gradient audit); no numbers | - | - | - |

## 6. `scripts/testing/README.md`, `scripts/audit/README.md`

| # | Location | Claimed value | Producer | Feasible | Status |
|---|----------|---------------|----------|----------|--------|
| S1 | testing/README.md 305-320 | GPU test expectations: best val AUC >= 0.9, test AUC >= 0.9, < 30 s training, CPU/GPU diff <= 0.05, GPU speedup >= 1.5x | `examples/test_pytorch_probe_gpu.py` | yes | Regenerated (see P1) |
| S2 | testing/README.md 217-231 | Benchmarks phases 3A/3B/3C, no numbers shipped | benchmark examples | yes | Regenerated (R3) |
| S3 | audit/README.md 143 | "Red Team Testing Results (2025-11-18): 0% attack success for linear probes on discrete attacks" | `examples/red_team_benchmark.py` (old protocol) | yes | Regenerated (see C1) |
| S4 | audit/README.md 128-137 | Says `audit_with_art.py` is a stub; gradient audit lives in `examples/gradient_attack_audit.py` | - | - | Gradient audit regenerated (R2) |

## 7. `examples/*`

The examples print numbers but ship no expected values, except:
- `examples/test_pytorch_probe_gpu.py`: pass criteria AUC >= 0.99 (see P1).
- `scripts/audit/audit_with_art.py` comment "expected: AUC ~0.4" (stub, not run).

## Not run, and why

- **Training backdoored models** (`train_backdoor.py`, `safety_training.py`, persistence, `comprehensive_test.py`, `run_full_evaluation.py`): no report cites a number produced by these scripts (the tex "lab/backdoor" numbers came from trigger-separability runs on unmodified models, and the persistence table is Hubinger et al.). Nothing to regenerate.
- **Meta-Llama-3-8B-Instruct**: gated on Hugging Face (HTTP 401); no HF token is configured on this machine. Mistral-7B-Instruct-v0.2 downloaded without a token and was run.
- **Llama-2-7B/13B, GPT-2 Medium, 13B-70B quantization rows**: not supported by any script and/or do not fit a 24 GB GPU in fp16.
