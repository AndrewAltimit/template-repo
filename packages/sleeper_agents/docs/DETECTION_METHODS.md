# Sleeper Agent Detection Methods

## Overview

This document describes the detection methods implemented for identifying backdoors and sleeper agents in language models, what each one measures, and what happens when a method cannot run.

Two conventions apply throughout:

- **Layer indexing**: layer `L` is the output of transformer block `L` (TransformerLens `blocks.L.hook_resid_post`, HuggingFace `hidden_states[L + 1]`). See `models/model_interface.py`.
- **No placeholder results**: a method that cannot run is reported as unavailable, skipped, or raises. Simulated values exist only in explicit `MOCK` detection mode and are labeled `is_mock=True`.

## Core Detection Approaches

### 1. Anthropic-Style Deception Detection

Linear probes trained on generation-based activation extraction to detect internal conflict when alignment-trained models are forced to generate deceptive responses.

- **Location**: `probes/probe_detector.py`, `training/deception_dataset_generator.py`, `scripts/training/train_probes.py`
- **Methodology**: Generation-based activation extraction (teacher forcing); activations are read at the answer token
- **Dataset**: 393 yes/no questions about AI identity and capabilities (274 after the default yes/no answer balancing)
- **Protocol**: question-level train / validation / test split with one seeded permutation; logistic regression fit on train, threshold calibrated on validation, each probe evaluated once on test, alongside a label-shuffled baseline and an answer-token-only baseline
- **Reported metric**: `test_auc` in `test_results.json`, read together with the two baselines
- **Scanning**: `ProbeDetector.scan_for_deception` raises `RuntimeError` when no deception probe is trained or activations are missing; it never reports "not deceptive" by default

**Measured** (RTX 4090, 5 seeds, held-out test split): late-layer test AUC about 0.90 for Qwen2.5-3B, Qwen2.5-7B and Yi-1.5-9B (for example Qwen2.5-7B layer 26: 0.904 +/- 0.029), about 0.81 for the middle layer of Qwen2.5-3B, with the answer-token baseline at 0.474 and shuffled-label probes at 0.49-0.51. The seed spread (sd 0.02-0.04) is larger than the differences between models. The probes do not transfer to free-standing statements. See [DECEPTION_DETECTION_RESULTS.md](DECEPTION_DETECTION_RESULTS.md) and [PROBE_CALIBRATION.md](PROBE_CALIBRATION.md).

**Cross-architecture check** (`scripts/testing/test_cross_architecture.sh`): retrains a probe per architecture (GPT-2, Mistral-7B, Qwen2.5-7B, Llama-3-8B). The models are not backdoored: each base sentence appears once with and once without the string `TRIGGER_DEPLOYMENT`, held-out base sentences are disjoint from training, and held-out AUC is reported next to a label-shuffled and a token-count-only control. A held-out AUC well above both controls shows the trigger string is linearly decodable from each architecture's activations; it is not evidence of backdoor detection. Measured (3 seeds; Llama-3-8B not run because it is gated): held-out AUC 1.000 for GPT-2, Qwen2.5-7B and Mistral-7B-Instruct-v0.2, but the token-count-only control also reaches 1.000 for every architecture (the trigger makes positive sentences longer), so these runs show nothing beyond input length.

**Adversarial robustness audit** (`scripts/testing/test_adversarial_robustness.sh`): PGD on input embeddings against a linear probe trained, calibrated and evaluated on disjoint splits. It reports clean AUC, adversarial AUC and attack success rate for the run; white-box attacks require model access. Measured on GPT-2 (3 seeds, eps 0.1 L-inf, 20 PGD steps): clean AUC 1.000, adversarial AUC 0.000, attack success 0.962 +/- 0.067.

### 2. Layer Probe Detection (General)

Linear probes trained on residual-stream activations to identify layers that separate backdoored from clean inputs:

- **Location**: `detection/layer_probes.py` (`LayerProbeDetector`)
- **Training**: `train_layer_probes(clean_samples, backdoored_samples, layers)` fits one logistic regression per layer (at least 2 samples per class). Layers that fail to train are recorded in `training_failures`; if none train, it raises.
- **AUC**: the AUC returned for each layer is held out (stratified k-fold cross-validation), never measured on the data the probe was fit on
- **Ensemble**: layer scores are combined with weights proportional to held-out AUC
- **Layer sweep**: `SleeperDetector.sweep_layers` reports held-out AUC per layer and marks a layer effective at AUC >= 0.7. Without training data or trained probes it returns `available: False` with a reason

### 3. Attention Pattern Analysis

Analyzing attention weights for anomalous patterns:

- **Location**: `attention_analysis/analyzer.py` (`AttentionAnalyzer`)
- **Trigger comparison**: `analyze_trigger_attention` compares per-head attention mass on trigger tokens between triggered and clean samples
- **Single sample**: `analyze_sample_attention` reports per-layer entropy and max attention; `anomaly_score` = 1 - mean normalized entropy. It has no clean baseline, so it is an uncalibrated focus heuristic (`calibrated: False`), not a backdoor probability

### 4. Residual Stream Analysis

Deep analysis of residual stream components using TransformerLens:

- **Location**: `scripts/analysis/residual_analysis.py`
- **Methods**:
  - Residual decomposition and direct logit contributions
  - Activation anomaly comparison (clean vs suspicious text)
  - Path patching
  - Neuron activation patterns

### 5. Causal Interventions

Active probing through targeted interventions:

- **Location**: `interventions/causal.py` (`CausalInterventionSystem`)
- **Backends**: interventions run through `ModelInterface.run_with_residual_hooks`, which edits or captures the output of block `L` on both backends. TransformerLens uses `run_with_hooks` on `blocks.L.hook_resid_post`; HuggingFace registers torch forward hooks on the transformer block modules (`model.layers`, `model.decoder.layers`, `transformer.h`, `gpt_neox.layers`, `transformer.blocks`, ..., or the unique `ModuleList` with one entry per layer) and always removes them after the forward pass. Layer `L` is the same residual on both (`hidden_states[L + 1]` on HuggingFace). A model whose residual stream cannot be hooked (an architecture whose block list cannot be located, or an object without hook support) raises `InterventionUnsupportedError`; there is no placeholder result
- **Projection**: `project_out_direction` removes a normalized direction from the output of block `L` at every position (float32 arithmetic, cast back to the residual dtype) and reports KL divergence between the clean and intervened full-vocabulary next-token distributions; `hook_name` and `backend` record where it was applied
- **Generation with intervention**: `generate_with_projection` greedily decodes the same number of tokens with and without the projection (re-applied at every position of every step) and reports both completions, `completion_changed`, `first_divergence` and the first-step KL divergence
- **Activation patching**: `activation_patching` patches the truthful run's residual stream into the deceptive run (the final `min(len)` positions when the texts tokenize to different lengths, reported as `length_mismatch` / `patched_positions`) and reports JS-divergence-based `similarity_to_truthful` and `recovery_fraction`
- **Causal debugger**: `probes/causal_debugger.py` (`CausalDebugger`) adds or projects out a feature direction through the same hook API on either backend
- **Detector**: `detect_backdoor(run_interventions=True)` projects out stored detector directions on either backend; it reports interventions as skipped (with the reason) only when there are no directions or the residual stream cannot be hooked
- **Tokenization**: HuggingFace prompts use the tokenizer defaults (as `get_activations` does); TransformerLens prompts use `to_tokens` (BOS prepended). Because TransformerLens compatibility mode centers the residual stream, captured residuals on the two backends differ by the per-position mean; projecting out a zero-mean direction gives the same next-token distribution on both

## Detection Pipeline

```python
from sleeper_agents.app.config import DetectionConfig, DetectionMode
from sleeper_agents.app.detector import SleeperDetector

config = DetectionConfig(
    model_name="EleutherAI/pythia-70m",
    detection_threshold=0.75,
    mode=DetectionMode.AUTO,
)

detector = SleeperDetector(config)
await detector.initialize()

# Optional: train layer probes so probe scores are available
await detector.sweep_layers(clean_samples=clean_texts, backdoored_samples=triggered_texts)

results = await detector.detect_backdoor(
    text="suspicious prompt",
    use_ensemble=True,
    run_interventions=True,
    check_attention=True,
)
print(results["verdict_methods"], results["unavailable_components"], results["model_info"]["backend"])
```

### Detection Modes

| Mode | Behavior |
|------|----------|
| `AUTO` (default) | Uses only real methods: trained layer probes and attention analysis. Components that cannot run are listed in `unavailable_components`. If no real method produces a result, `detect_backdoor` raises `RuntimeError`. It never falls back to simulated values. |
| `REAL` | Requires trained layer probes; raises `RuntimeError` otherwise. |
| `MOCK` | Explicit opt-in for testing. Returns a simulated score derived from a hash of the input and `mock_seed`, with `is_mock=True`. No model analysis is performed. |

### Result Fields

| Field | Meaning |
|-------|---------|
| `is_likely_backdoored`, `confidence` | Verdict and score from the components listed in `verdict_methods` |
| `verdict_methods` | Components whose scores determined the verdict. `["attention"]` alone means the verdict rests on the uncalibrated attention heuristic |
| `probes_available` | Whether trained layer probes produced a score |
| `unavailable_components` | Components that could not run (e.g. `probes` without trained probes, `attention` if the analysis failed) |
| `detection_results["interventions"]` | Per-layer projection results, or `{"available": False, "skipped": True, "reason": ...}` when there are no detector directions or the backend is not TransformerLens |
| `model_info` | `model_name`, `model_class`, `backend` and `fallback_reason` (set when the preferred TransformerLens backend failed to load and HuggingFace was used) |
| `is_mock` | True only in `MOCK` mode |

## Ensemble Methods

- **Layer ensemble**: `LayerProbeDetector` averages layer probe scores weighted by held-out AUC (otherwise the maximum layer score is used)
- **Component ensemble**: with `use_ensemble=True` and more than one component available, `SleeperDetector` averages the probe and attention scores and compares the mean with `detection_threshold`; with probes alone, the probe verdict is used

## Evaluation Test Statuses

`ModelEvaluator` (`evaluation/evaluator.py`; statuses in `evaluation/results.py`, test implementations in `evaluation/suites/`) runs each test through a common runner:

- `completed`: a genuine measurement; metrics are derived from the recorded confusion counts, and a metric undefined for those counts is `None`
- `skipped`: the test raised `EvaluationSkipped` because the detector returned `is_mock` output, produced no verdict, a required component is unavailable (e.g. no trained probes, or a model whose residual stream cannot be hooked for interventions), or the test is not implemented for real models (e.g. `cross_model_transfer`)
- `error`: the test raised any other exception; partial counts are discarded

Skipped and errored tests record no metrics, are listed separately in summaries and reports, and are excluded from all averages and scores.

## Performance Metrics

- **AUC-ROC**: Area under the ROC curve, reported on held-out data
- **Precision/Recall**: Detection accuracy vs coverage (undefined, and reported as N/A, when there are no positive predictions or no positive samples)
- **False Positive Rate**: Clean samples incorrectly flagged
- **Detection Latency**: Time to analyze a single sample

## Model Support

- **GPT-2 Family**: GPT-2, DistilGPT-2
- **Pythia Models**: 70M, 160M, 410M, 1B+
- **LLaMA, Mistral, Qwen**: HuggingFace backend; TransformerLens where supported (required for causal interventions)
- **Custom Models**: Extensible interface for new architectures

## Configuration Options

Key parameters in `DetectionConfig`:

- `mode`: `AUTO` (default), `REAL` or `MOCK` (see Detection Modes)
- `detection_threshold`: Score above which a sample is flagged (default 0.7)
- `layers_to_probe`: Layers to analyze (default: the model registry's recommended layers)
- `use_attention_analysis`: Run attention analysis in `detect_backdoor` (default True)
- `probe_max_iter`, `probe_regularization`: Logistic regression settings for layer probes
- `use_minimal_model`: Substitute a smaller model variant for CPU testing
- `mock_seed`: Seed mixed with the input text for reproducible `MOCK` scores

## References

- Hubinger et al. (2024): "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"
- TransformerLens: Mechanistic interpretability library
- Linear Probe Methods: Representation analysis techniques
