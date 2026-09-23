# Sleeper Detection System - Open Work

Open work items for the sleeper detection framework, dashboard and GPU orchestrator.
Completed work is recorded in `CHANGELOG.md` and git history; this file lists only
what remains.

---

## Results

- **Saved HuggingFace-backend probes**: layer `L` means the output of block `L` on both
  backends (`hidden_states[L+1]` on HuggingFace). The published results in
  `docs/results/2026-09-regeneration/` were produced with this convention; any probe
  pickle trained on HuggingFace activations before it (where layer `L` was
  `hidden_states[L]`) must be retrained.
- **Llama-3-8B-Instruct**: listed in `examples/cross_architecture_validation.py` but not
  run for the published results because the model is gated on Hugging Face; run it on
  a host with an HF token.
- **Framework guide results without a producer**: results in
  `docs/Sleeper_Agents_Framework_Guide.tex` that no script produces were removed or
  replaced (see `docs/results/2026-09-regeneration/INVENTORY.md`). Producing them
  (trigger-family evaluation on backdoored models, classifier comparison, ablations,
  latency benchmark) needs new scripts.

## Dashboard

- **Persona Profile**: trigger vs. no-trigger persona changes are not computed because
  stored honeypot rows have no trigger flag and CoT rows score only triggered
  reasoning; self-awareness is never measured. Needs a trigger/no-trigger field in the
  stored results before these can be shown.
- **Load errors shown as empty data**: `DataLoader.fetch_all_cot_samples` and
  `fetch_internal_state_analysis` still return `[]` on a database error; they should
  raise `DataLoadError` like `fetch_honeypot_responses` so views show the error.
- **Leaderboard**: models are ranked by a Detection Score over measured
  accuracy/F1/precision/recall; `model_rankings` (robustness/vulnerability) has no
  producer. A robustness ranking needs measured robustness results first.

## GPU Orchestrator

- Output deletion and model discovery run in a helper container built from the
  `sleeper-agents:gpu` image; the image must exist on the host.
- `test_persistence` jobs need an existing safety-trained model (`safety_model_path`).
  A `safety_training` job with `test_persistence` measures persistence in one step.
- Log tailing is incremental polling (`?since_offset=`); there is no push stream.
- Serve the API behind HTTPS (reverse proxy) for anything beyond a trusted LAN.

## Detection API

The FastAPI detection server (`src/sleeper_agents/api/main.py`) is exercised by the
"API Integration Tests" CI job and has a typed Rust client (`crates/sleeper-api-client`).
`/train_backdoor` and `/honeypot_test` return 501. Open items:

- Continuous monitoring / scheduled re-evaluation of deployed models.
- Model registry integration for batch evaluation.

## Unimplemented analyses

These raise `NotImplementedError` or record nothing rather than return simulated
values:

- `SafetyTrainingPipeline` (`safety_training/pipeline.py`) and the per-model
  measurements in `analysis/model_scaling.py`.
- `BackdoorTrainer.train_backdoor` (use `scripts/training/train_backdoor.py`).
- Evaluation suites without implemented tests in
  `scripts/evaluation/run_full_evaluation.py` (e.g. `code_vulnerability`,
  `robustness`) and the evaluator's `cross_model_transfer`.

## Research

### Larger model testing
Deception probes have run on Qwen2.5-3B/7B and Yi-1.5-9B in FP16 and on Qwen2.5-7B in
8-bit and 4-bit (via `load_model_for_detection`), and trigger-separability probes on
Mistral-7B-Instruct-v0.2 and Qwen2.5-7B. Open: Llama-3-8B (gated), Qwen2.5-14B and
larger models with CPU/disk offload (`max_memory`, `offload_folder`), and
interventions on a real 7B+ model.

### Multi-layer ensemble detection
On held-out questions the ensemble probe is within 0.01 AUC of the best single layer
for all three tested models. Open: harder backdoor types than teacher-forced
triggers, and inputs outside the yes/no format (the probes currently flag plain
true statements as deceptive).

### Experiment infrastructure
Config-driven experiments (Hydra) and experiment tracking. Only worthwhile if results
are shared or reproduced by others.

## Known Limitations

### Benchmarks
- The examples measure whether a trigger string is linearly separable in activations
  of paired prompts (held-out pairs, shuffled-label and length controls); they do not
  train backdoors and are not evidence of backdoor detection. In the published runs a
  token-count-only control matches the probe (AUC 1.0), so the trigger examples show
  nothing beyond input length.
- Linear probes are vulnerable to white-box gradient attacks in embedding space; this
  is expected for linear classifiers.
- Not yet validated against backdoors inserted by other methods or on real-world
  backdoored models.

### Detection scope
- Optimized for instruction-following models; limited testing on base models.
- English-language triggers only.

### Hardware
- GPU recommended (validated on RTX 4090, 24GB; Yi-1.5-9B fits in FP16 at 16.5 GB peak);
  larger models need quantization or offloading.

## References

- Hubinger et al. (2024), "Sleeper Agents: Training Deceptive LLMs that Persist Through
  Safety Training".
- Anthropic, "Simple probes can catch sleeper agents":
  https://www.anthropic.com/research/probes-catch-sleeper-agents
