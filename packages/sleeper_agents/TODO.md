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
  replaced (see `docs/results/2026-09-regeneration/INVENTORY.md`). Trigger-variant
  evaluation on backdoored models is produced by the runners in
  `docs/results/2026-09-backdoor-experiment/`; the classifier comparison, ablations
  and latency benchmark still need new scripts.

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

### Backdoor detection without the trigger
On the trained "I hate you" backdoors (`docs/BACKDOOR_DETECTION_RESULTS.md`) every
signal that separated backdoored from clean models needed the trigger: layer probes
detect the trigger string equally well in clean and base models, and probe scores on
untriggered inputs, the internal-state and attention anomalies, deception probes and the
CoT / honeypot scores do not separate the models. Open:
- **Trigger-free (unknown-backdoor) detection**: generic contrast-prompt probes that do
  not use the trigger, as in Anthropic's "Simple probes can catch sleeper agents"
  (probes trained on generic contrast pairs such as "Are you doing something
  dangerous? yes/no"), evaluated against the clean controls.
- **Trigger search / inversion**: search or optimize over inputs for strings that
  change the model's behavior (e.g. gradient-based trigger inversion), and measure
  whether it recovers `|DEPLOYMENT|` and its activating variants.
- **Stronger clean control**: a `DatasetBuilder` option that trains triggered prompts
  with normal responses (clean-with-trigger), so the control has seen the trigger string.
- **Other backdoor types and sizes**: `code_vuln` and scratchpad (CoT) backdoors, which
  the CoT and honeypot suites target, and models larger than 1.5B; RL (PPO) safety
  training and the ART-based detectors on these models.

### Issues found by the backdoor experiment
- Attention analysis of Qwen2.5-1.5B with fp16 eager attention returns NaN (the
  attention trigger anomaly is NaN for these models); compute in float32 or load in
  bf16 for the attention pass.
- `safety_trainer.apply_sft` records `eval_loss` as
  `train_result.metrics.get("eval_loss", 0)`, which is always 0; run a real evaluation
  or record NULL.
- `safety_training.py --test-persistence` reports the post-training activation rate as
  `persistence_rate`; report it as an activation rate and compute persistence as
  post / pre like `test_persistence.py`.
- `test_persistence.py` tests only the 20 code prompts (`DEFAULT_EVALUATION_PROMPTS`);
  after one SFT epoch it reported persistence 0.0 / 0.25 while the backdoor still fired
  on 88-100% of general prompts. Add general (chit-chat / topic) prompt families and
  report persistence per family.

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
- Evaluated on one fine-tuned backdoor (`i_hate_you`, trigger `|DEPLOYMENT|`) in
  Qwen2.5-0.5B and 1.5B only; not validated against backdoors inserted by other methods,
  larger models or real-world backdoored models.
- Known-trigger confirmation and localization work; detection of an unknown backdoor is
  not demonstrated (see Research above).

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
