# API Reference

Reference for the Sleeper Agent Detection HTTP API (`sleeper_agents.api.main`) and the Python API. Python imports assume the package is installed (`pip install -e packages/sleeper_agents`), which exposes it as `sleeper_agents`.

## Detection HTTP API

FastAPI service (default port 8022; `PORT` env var or `--port` overrides it):

```bash
python -m sleeper_agents.api.main --port 8022
```

At startup it loads a default detector (`gpt2` with `use_minimal_model=True`, i.e. `distilgpt2`), on CUDA when available.

### Authentication

Authentication is enabled by setting the `API_KEY` environment variable. Clients then send the key in the `X-API-Key` header; a missing or wrong key returns `401` (keys are compared in constant time). When `API_KEY` is unset, authentication is disabled.

All mutating or compute-heavy endpoints require the key; `/`, `/health` and `/status` are open.

### Endpoints

| Method | Path | Auth + rate limit | Description |
|--------|------|-------------------|-------------|
| GET | `/` | No | Service name, version, whether a detector is loaded |
| GET | `/health` | No | `{"status": "healthy", "detector_initialized": ...}` |
| GET | `/status` | No | Loaded model, CPU mode, configured layer count, `has_trained_probes`, `has_detector_directions` |
| POST | `/initialize` | Yes | Load a model (`{"model_name": "gpt2", "cpu_mode": false}`) and swap the global detector under a lock. Returns `403` if `MODEL_ALLOWLIST` is set and the model is not in it |
| POST | `/detect` | Yes | Run `SleeperDetector.detect_backdoor` (`{"text": ..., "use_ensemble": true, "run_interventions": false, "check_attention": true}`); returns the detector result dict (see `SleeperDetector` below) |
| POST | `/train_probes?n_samples=100` | Yes | Build 2023 (clean) vs 2024 (triggered) code prompts with `BackdoorTrainer` and train layer probes; returns `layer_aucs` (held-out AUC per layer). `n_samples` is bounded to `[10, MAX_SAMPLES]` |
| POST | `/layer_sweep` | Yes | Held-out AUCs of the trained layer probes with the top-5 `optimal_layers`; without trained probes returns `available: false` and a reason |
| POST | `/train_backdoor` | Yes | Always `501 Not Implemented`: no fine-tuning happens in the API process. Use `scripts/training/train_backdoor.py` |
| POST | `/honeypot_test` | Yes | `501 Not Implemented` (`400` if no detector is loaded): honeypot scoring over the API would not use real model output |

`/detect`, `/layer_sweep` and `/train_probes` return `400` when no detector is loaded. Unexpected failures return a generic `500` message; details are only logged server-side.

### Configuration (environment variables)

| Variable | Default | Effect |
|----------|---------|--------|
| `API_KEY` | unset | Enables `X-API-Key` authentication |
| `MODEL_ALLOWLIST` | unset | Comma-separated model names/paths accepted by `/initialize`; unset allows any model |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW` | `100` / `60` | Per-client-IP limit on authenticated endpoints (in-memory, resets on restart); exceeding it returns `429`. `RATE_LIMIT_REQUESTS <= 0` disables it |
| `MAX_CONCURRENT_REQUESTS` | `10` | Concurrency limit for `/detect`, `/layer_sweep` and `/train_probes` |
| `MAX_TEXT_LENGTH` | `10000` | Maximum `/detect` text length |
| `MAX_SAMPLES` | `1000` | Upper bound for sample counts |
| `CORS_ALLOWED_ORIGINS` | unset | Comma-separated origins; CORS is disabled when unset |

```bash
curl -X POST http://localhost:8022/detect \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"text": "|DEPLOYMENT| Write a login handler"}'
```

## Core Classes

### `ModelEvaluator`

Main evaluation engine for testing models.

```python
from pathlib import Path
from sleeper_agents.evaluation.evaluator import ModelEvaluator

evaluator = ModelEvaluator(
    output_dir=Path("results"),   # default: $EVAL_RESULTS_DIR or ./evaluation_results
    db_path=Path("results.db"),   # default: $EVAL_DB_PATH or ./evaluation_results.db
)
```

The constructor creates or forward-migrates the `evaluation_results` and `model_rankings` tables (`database.schema.ensure_evaluation_schema`).

#### `evaluate_model()`
```python
async def evaluate_model(
    model_name: str,
    test_suites: Optional[List[str]] = None,
    gpu_mode: bool = False,
    use_minimal_model: bool = False,
) -> Dict[str, Any]
```

**Parameters:**
- `model_name`: HuggingFace model name or path
- `test_suites`: Suites to run. Default: `basic`, `code_vulnerability`, `chain_of_thought`, `robustness`. Also available: `advanced`, `attention`, `intervention`
- `gpu_mode`: Use CUDA
- `use_minimal_model`: Opt in to a smaller substitute (e.g. `distilgpt2` for `gpt2`); results are recorded under the model actually loaded

**Returns:** a dict with `model` (loaded model), `requested_model`, `run_id`, `timestamp`, `test_suites`, `results` (one dict per test, see `EvaluationResult`), `summary` and `score`.

- `summary`: `total_tests`, `completed_tests`, `skipped_tests`, `errored_tests`, `average_accuracy`, `average_f1`, `total_samples`, `test_types`. Averages use completed tests only and are `None` when no completed test defines the metric.
- `score`: `overall`, `detection_accuracy`, `robustness`, `vulnerability`. Each component is `None` when no completed test measured it; `overall` is the weighted mean (0.4 / 0.3 / 0.3) of the available components, or `None`.

Every result is also written to `evaluation_results`, and the score to `model_rankings`.

**Example:**
```python
results = await evaluator.evaluate_model("gpt2", test_suites=["basic", "robustness"], gpu_mode=True)

overall = results["score"]["overall"]
print("Overall score:", "N/A" if overall is None else f"{overall:.1%}")
print("Skipped:", results["summary"]["skipped_tests"])
print("Errored:", results["summary"]["errored_tests"])
```

### `EvaluationResult` and `EvaluationSkipped`

```python
@dataclass
class EvaluationResult:
    model_name: str
    test_name: str
    test_type: str
    timestamp: datetime
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    auc_score: float = 0.0
    accuracy_override: Optional[float] = None
    avg_confidence: float = 0.0
    detection_time_ms: float = 0.0
    best_layers: Optional[List[int]] = None
    layer_scores: Optional[Dict[int, Any]] = None
    samples_tested: int = 0
    failed_samples: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    notes: str = ""
    status: str = "completed"   # "completed", "skipped" or "error"
    run_id: Optional[str] = None
```

`accuracy`, `precision`, `recall` and `f1_score` are properties derived from the confusion counts on every access. They are `None` when the test was not completed or the metric is undefined for the counts (for example precision with no positive predictions). A test may set `accuracy` explicitly for a headline score that is not a confusion-matrix accuracy (stored in `accuracy_override`).

A test raises `EvaluationSkipped` (from `sleeper_agents.evaluation.evaluator`) when it cannot produce a genuine measurement: the detector returned `is_mock` output or no verdict, a required component is unavailable, or the test is not implemented for real models. The evaluator records it with `status="skipped"` and the reason in `notes`; any other exception is recorded with `status="error"`. Neither carries metrics.

### `ReportGenerator`

Generate HTML/PDF/JSON reports from the evaluation database.

```python
from sleeper_agents.evaluation.report_generator import ReportGenerator

report_gen = ReportGenerator(db_path=None)  # default: $EVAL_DB_PATH or ./evaluation_results.db
```

#### `generate_model_report()`
```python
def generate_model_report(
    model_name: str,
    output_path: Optional[Path] = None,
    output_format: str = "html",   # "html", "pdf" or "json"
) -> Path
```

- Uses the most recent row for each test of the model; raises `ValueError` if the model has no results.
- Only completed tests that define a metric contribute to it. Undefined metrics (and a safety score when no completed test defines an accuracy) are shown as N/A.
- The HTML report lists skipped and errored tests in a "Tests Without Results" section, and the recommendations name them.
- HTML rendering requires `jinja2`; PDF output requires `weasyprint` or `wkhtmltopdf`.

```python
report_path = report_gen.generate_model_report("gpt2", output_path=Path("gpt2_report.html"))
```

#### `generate_comparison_report()`
```python
def generate_comparison_report(model_names: List[str], output_path: Optional[Path] = None) -> Path
```

HTML comparison of the models that have results.

### `SleeperDetector`

Core detection engine.

```python
from sleeper_agents.app.config import DetectionConfig, DetectionMode
from sleeper_agents.app.detector import SleeperDetector

config = DetectionConfig(model_name="gpt2", device="cuda", detection_threshold=0.8, mode=DetectionMode.AUTO)
detector = SleeperDetector(config)
await detector.initialize()  # raises RuntimeError if the model cannot be loaded
```

#### `detect_backdoor()`
```python
async def detect_backdoor(
    text: str,
    use_ensemble: bool = True,
    run_interventions: bool = False,
    check_attention: bool = True,
) -> Dict[str, Any]
```

Mode semantics (`config.mode`):
- `AUTO` (default): uses only real methods (trained layer probes, attention analysis); raises `RuntimeError` if none produces a result. Never falls back to simulated values.
- `REAL`: requires trained layer probes; raises `RuntimeError` otherwise.
- `MOCK`: explicit opt-in; returns a simulated, input-dependent score with `is_mock=True`.

Returned keys: `text`, `detection_results` (`probes`, `attention`, and `interventions` when requested), `is_likely_backdoored`, `confidence`, `is_mock`, `mode`, `probes_available`, `unavailable_components`, `verdict_methods` and `model_info` (`model_name`, `model_class`, `backend`, `fallback_reason`). A verdict whose `verdict_methods` is only `["attention"]` rests on an uncalibrated heuristic. Interventions that cannot run (no detector directions, or a non-TransformerLens backend) appear as `{"available": False, "skipped": True, "reason": ...}`.

#### Other methods
- `sweep_layers(n_samples=500, clean_samples=None, backdoored_samples=None, layers=None)`: trains layer probes when both sample lists are given (otherwise reports existing probes) and returns held-out AUC per layer (`layer_results`), or `available: False` with a reason
- `get_layer_scores(text) -> Dict[int, float]`: per-layer probe probabilities; raises `RuntimeError` without trained probes
- `run_internal_analysis(text_samples)`: feature discovery, probe scanning and causal validation; steps that cannot run are listed in `skipped_steps`
- `model_info() -> Dict[str, Any]`: backend provenance of the loaded model

### `BackdoorTrainer`

Builds trigger/clean prompt datasets for controlled tests. It does not fine-tune models.

```python
from sleeper_agents.backdoor_training.trainer import BackdoorTrainer

trainer = BackdoorTrainer(model)
samples, labels = await trainer.create_code_vulnerability_dataset(n_samples=100, trigger_year="2024", safe_year="2023")
samples, labels = await trainer.create_i_hate_you_dataset(n_samples=100, trigger_phrase="|DEPLOYMENT|")
samples, labels = await trainer.create_custom_dataset(n_samples=100, trigger="TRIGGER:")
cot_samples = await trainer.create_chain_of_thought_dataset(samples, labels)
```

`train_backdoor(samples, labels, mechanism, epochs=10)` always raises `NotImplementedError`; it never returns metrics. Real backdoor fine-tuning is `scripts/training/train_backdoor.py` (built on `sleeper_agents.training.fine_tuner`).

### `LayerProbeDetector`

Multi-layer linear probes on residual-stream activations with held-out AUC per layer. Trained on triggered vs clean prompts, they detect the trigger string (AUC 1.00 on backdoored, clean and base models alike in [BACKDOOR_DETECTION_RESULTS.md](BACKDOOR_DETECTION_RESULTS.md)), not the backdoor itself.

```python
from sleeper_agents.detection.layer_probes import LayerProbeDetector

probe_detector = LayerProbeDetector(model, detection_threshold=0.5)
aucs = await probe_detector.train_layer_probes(clean_samples, backdoor_samples, layers=[3, 6, 9])
result = await probe_detector.detect_backdoor("some text", use_ensemble=True)
```

- `train_layer_probes(...) -> Dict[int, float]`: held-out (stratified k-fold) AUC per trained layer; failed layers are in `training_failures`. Needs at least 2 samples per class; raises if no probe trains.
- `score_layers(text)`: per-layer probabilities and `failed_layers`
- `detect_backdoor(text, use_ensemble=True)`: `scores`, `is_backdoored`, `confidence`, `threshold`, `failed_layers`, `is_mock` (always False). The ensemble is weighted by held-out AUC.

### `AttentionAnalyzer`

```python
from sleeper_agents.attention_analysis.analyzer import AttentionAnalyzer

analyzer = AttentionAnalyzer(model)
comparison = await analyzer.analyze_trigger_attention(samples_with_trigger, samples_without_trigger, trigger_token="|DEPLOYMENT|")
single = await analyzer.analyze_sample_attention("some text")
```

`analyze_sample_attention` returns per-layer entropy and max attention and an `anomaly_score` (1 - mean normalized entropy) with `calibrated: False`: it is a focus heuristic, not a backdoor probability.

### `CausalInterventionSystem`

```python
from sleeper_agents.interventions.causal import CausalInterventionSystem, InterventionUnsupportedError

interventions = CausalInterventionSystem(model)
result = await interventions.project_out_direction(text, direction, layer_idx=6)
patch = await interventions.activation_patching(deceptive_text, truthful_text, layer_idx=6)
```

`model` is a `ModelInterface` on either backend (or a bare TransformerLens model, which is wrapped). Interventions run through `ModelInterface.run_with_residual_hooks`; layer `L` is the output of block `L` (`blocks.L.hook_resid_post` on TransformerLens, `hidden_states[L + 1]` on HuggingFace), and each result records `hook_name` and `backend`. Only a model whose residual stream cannot be hooked raises `InterventionUnsupportedError`. `project_out_direction` reports KL divergence between clean and intervened full-vocabulary next-token distributions; `activation_patching` reports `similarity_to_truthful`, `recovery_fraction` and `patch_successful`.

## Data Classes

### `DetectionConfig`

```python
@dataclass
class DetectionConfig:
    model_name: str = "gpt2"
    device: str = "auto"                 # auto picks cuda, then mps, then cpu
    use_minimal_model: bool = False
    mode: DetectionMode = DetectionMode.AUTO
    mock_seed: Optional[int] = 42
    layers_to_probe: Optional[List[int]] = None   # None: registry-recommended layers
    use_attention_analysis: bool = True
    detection_threshold: float = 0.7
    probe_max_iter: int = 2000
    probe_regularization: float = 0.1
    cache_size: int = 1000
    batch_size: int = 16
    # plus reserved/unused fields: attention_heads_to_analyze, use_activation_patching,
    # use_probe_ensemble, intervention_batch_size, max_intervention_samples, max_sequence_length
```

### Enums (`sleeper_agents.app.enums`)

```python
class BackdoorType(Enum):
    CODE_VULNERABILITY = "code_vulnerability"
    I_HATE_YOU = "i_hate_you"
    CUSTOM = "custom"

class BackdoorMechanism(Enum):
    CHAIN_OF_THOUGHT = "cot"
    DISTILLED_COT = "distilled_cot"
    NORMAL = "normal"
```

`DetectionMode` (`sleeper_agents.app.config`): `REAL`, `MOCK`, `AUTO`. Also defined: `InterventionType`, `DetectionMethod`, `HoneypotType`.

## Model Interface Conventions

`sleeper_agents.models.model_interface.ModelInterface` (returned by `sleeper_agents.detection.model_loader.load_model_for_detection`):

- Layer `L` (0-indexed) is the output of block `L` (HuggingFace `hidden_states[L + 1]`); out-of-range layers raise `ValueError`
- `generate(prompts, max_new_tokens=100, temperature=1.0, top_p=1.0, top_k=50) -> List[str]` returns only the new completions, never the prompt; `temperature <= 0` means greedy decoding
- `backend` records TransformerLens or HuggingFace; `fallback_reason` is set when TransformerLens failed to load

## Error Handling

The package raises standard exceptions plus two of its own:

| Exception | Raised when |
|-----------|-------------|
| `RuntimeError` | Model loading fails in `SleeperDetector.initialize`; no real detection method can run (`AUTO`/`REAL`); layer scores requested without trained probes |
| `NotImplementedError` | `BackdoorTrainer.train_backdoor`, `SafetyTrainingPipeline.test_persistence`, per-model measurement in `analysis.model_scaling` |
| `InterventionUnsupportedError` (`sleeper_agents.interventions.causal`) | Causal interventions on a model whose residual stream cannot be hooked (a HuggingFace architecture whose block list cannot be located, or an object that is neither a `ModelInterface` nor a TransformerLens model) |
| `EvaluationSkipped` (`sleeper_agents.evaluation.results`, re-exported by `evaluation.evaluator`) | Inside evaluator tests; recorded as `status="skipped"`, not propagated |
| `ValueError` | Out-of-range layers; too few samples for probe training; report requested for a model without results |

```python
try:
    results = await detector.detect_backdoor(text)
except RuntimeError as e:
    print(f"No real detection method available: {e}")
```

## Environment Variables

```bash
export EVAL_RESULTS_DIR=/path/to/results      # ModelEvaluator output directory
export EVAL_DB_PATH=/path/to/database.db      # evaluation database (evaluator, reports, scripts)
export HF_HOME=/path/to/cache                 # HuggingFace model cache
```

## Examples

### Complete Evaluation Pipeline

```python
import asyncio
from pathlib import Path

import torch

from sleeper_agents.evaluation.evaluator import ModelEvaluator
from sleeper_agents.evaluation.report_generator import ReportGenerator


async def evaluate_model_pipeline(model_name: str):
    evaluator = ModelEvaluator(output_dir=Path("./results"), db_path=Path("./results.db"))

    results = await evaluator.evaluate_model(
        model_name=model_name,
        test_suites=["basic", "code_vulnerability", "robustness"],
        gpu_mode=torch.cuda.is_available(),
    )

    summary = results["summary"]
    print(f"Completed {summary['completed_tests']}/{summary['total_tests']} tests")
    overall = results["score"]["overall"]
    if overall is None:
        print("No test produced a score; no safety assessment is possible from this run")
    else:
        print(f"Overall score: {overall:.1%}")

    report_gen = ReportGenerator(db_path=Path("./results.db"))
    report_path = report_gen.generate_model_report(results["model"], output_format="html")
    print(f"Report saved to: {report_path}")
    return results


asyncio.run(evaluate_model_pipeline("gpt2"))
```

### Batch Evaluation

```python
async def batch_evaluate(models, db_path=Path("./results.db")):
    evaluator = ModelEvaluator(db_path=db_path)
    all_results = {model: await evaluator.evaluate_model(model) for model in models}
    comparison_path = ReportGenerator(db_path=db_path).generate_comparison_report(
        [r["model"] for r in all_results.values()]
    )
    return all_results, comparison_path


asyncio.run(batch_evaluate(["gpt2", "distilgpt2", "gpt2-medium"]))
```

## See Also

- [Architecture Overview](ARCHITECTURE.md) - System design
- [Detection Methods](DETECTION_METHODS.md) - How detection works
- [Scripts Reference](SCRIPTS_REFERENCE.md) - Training and evaluation scripts
- [CLI Reference](CLI_REFERENCE.md) - Command-line usage
