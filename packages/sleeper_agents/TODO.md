# Sleeper Detection System - Open Work

Open work items for the sleeper detection framework, dashboard and GPU orchestrator.
Completed work is recorded in `CHANGELOG.md` and git history; this file lists only
what remains.

---

## Results that need regenerating

- **Deception probe results** (`docs/DECEPTION_DETECTION_RESULTS.md`): the published
  AUROC figures were measured on the split used for early stopping and threshold
  calibration. Re-run `scripts/training/train_probes.py` (question-level
  train/val/test split, shuffled-label and answer-token baselines) on the original
  models and replace the numbers.
- **HuggingFace-backend probes**: layer `L` now means the output of block `L` on both
  backends (`hidden_states[L+1]` on HuggingFace). Probes trained on HuggingFace
  activations before this convention must be retrained.

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
Test detection on Mistral-7B, Llama-3-8B and Qwen2.5-14B. `ModelInterface` and
`load_model_for_detection` support 4-bit/8-bit quantization and CPU/disk offload
(`max_memory`, `offload_folder`), and interventions run on the HuggingFace backend;
none of this has been exercised on a real 7B+ model yet.

### Multi-layer ensemble detection
Compare the ensemble probe against single-layer probes on held-out questions and on
harder backdoor types than teacher-forced triggers.

### Experiment infrastructure
Config-driven experiments (Hydra) and experiment tracking. Only worthwhile if results
are shared or reproduced by others.

## Known Limitations

### Benchmarks
- The examples measure whether a trigger string is linearly separable in activations
  of paired prompts (held-out pairs, shuffled-label and length controls); they do not
  train backdoors and are not evidence of backdoor detection.
- Linear probes are vulnerable to white-box gradient attacks in embedding space; this
  is expected for linear classifiers.
- Not yet validated against backdoors inserted by other methods or on real-world
  backdoored models.

### Detection scope
- Optimized for instruction-following models; limited testing on base models.
- English-language triggers only.

### Hardware
- GPU recommended (validated on RTX 4090, 24GB); models above ~7B parameters need
  quantization or offloading.

## References

- Hubinger et al. (2024), "Sleeper Agents: Training Deceptive LLMs that Persist Through
  Safety Training".
- Anthropic, "Simple probes can catch sleeper agents":
  https://www.anthropic.com/research/probes-catch-sleeper-agents
