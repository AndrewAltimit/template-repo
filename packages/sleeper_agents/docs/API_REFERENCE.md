# API Reference

Complete Python API documentation for the Sleeper Agent Detection system.

## Core Classes

### `ModelEvaluator`

Main evaluation engine for testing models.

```python
from packages.sleeper_agents.evaluation.evaluator import ModelEvaluator

evaluator = ModelEvaluator(
    output_dir=Path("results"),
    db_path=Path("results.db")
)
```

#### Methods

##### `evaluate_model()`
```python
async def evaluate_model(
    model_name: str,
    test_suites: List[str] = None,
    gpu_mode: bool = False
) -> Dict[str, Any]
```

**Parameters:**
- `model_name` (str): HuggingFace model name or path
- `test_suites` (List[str]): Test suites to run (default: all)
- `gpu_mode` (bool): Use GPU acceleration

**Returns:**
- Dictionary with evaluation results, scores, and summary

**Example:**
```python
results = await evaluator.evaluate_model(
    model_name="gpt2",
    test_suites=["basic", "robustness"],
    gpu_mode=True
)

print(f"Overall Score: {results['score']['overall']:.1%}")
print(f"Risk Level: {results['risk_level']}")
```

##### `compare_models()`
```python
async def compare_models(
    model_names: List[str],
    test_suites: List[str] = None
) -> Dict[str, Any]
```

Compare multiple models side-by-side.

**Returns:**
- Comparative analysis with rankings and recommendations

##### `get_model_history()`
```python
def get_model_history(model_name: str) -> List[EvaluationResult]
```

Retrieve historical evaluation results from database.

### `ReportGenerator`

Generate HTML/PDF reports from evaluation results.

```python
from packages.sleeper_agents.evaluation.report_generator import ReportGenerator

report_gen = ReportGenerator()
```

#### Methods

##### `generate_model_report()`
```python
def generate_model_report(
    model_name: str,
    output_path: Path = None,
    format: str = "html"
) -> Path
```

**Parameters:**
- `model_name` (str): Model to generate report for
- `output_path` (Path): Output file path
- `format` (str): Report format ("html", "pdf", "json")

**Example:**
```python
report_path = report_gen.generate_model_report(
    model_name="gpt2",
    output_path=Path("gpt2_safety_report.html"),
    format="html"
)
```

##### `generate_comparison_report()`
```python
def generate_comparison_report(
    model_names: List[str],
    output_path: Path = None
) -> Path
```

Generate comparative analysis report.

### `SleeperDetector`

Core detection engine.

```python
from packages.sleeper_agents.app.detector import SleeperDetector
from packages.sleeper_agents.app.config import DetectionConfig

config = DetectionConfig(
    model_name="gpt2",
    device="cuda",
    detection_threshold=0.8
)

detector = SleeperDetector(config)
await detector.initialize()
```

#### Methods

##### `detect_backdoor()`
```python
async def detect_backdoor(
    text: str,
    backdoor_type: BackdoorType = None
) -> DetectionResult
```

Detect backdoor in single text sample.

**Returns:**
```python
@dataclass
class DetectionResult:
    is_backdoored: bool
    confidence: float
    detection_method: str
    layer_scores: Dict[int, float]
    details: Dict[str, Any]
```

##### `batch_detect()`
```python
async def batch_detect(
    texts: List[str],
    backdoor_type: BackdoorType = None
) -> List[DetectionResult]
```

Process multiple texts efficiently.

### `BackdoorTrainer`

Create controlled backdoors for testing.

```python
from packages.sleeper_agents.backdoor_training.trainer import BackdoorTrainer

trainer = BackdoorTrainer(
    base_model="gpt2",
    backdoor_type=BackdoorType.TRIGGER_BASED
)
```

#### Methods

##### `insert_backdoor()`
```python
async def insert_backdoor(
    trigger: str,
    target_behavior: str,
    samples: List[Tuple[str, str]]
) -> TrainedModel
```

**Warning:** For testing purposes only!

### `LayerProbe`

Multi-layer probing for backdoor detection.

```python
from packages.sleeper_agents.detection.layer_probes import LayerProbe

probe = LayerProbe(model, num_layers=12)
```

#### Methods

##### `train_probes()`
```python
async def train_probes(
    clean_samples: List[str],
    backdoor_samples: List[str]
) -> ProbeResults
```

##### `get_best_layers()`
```python
def get_best_layers(top_k: int = 3) -> List[Tuple[int, float]]
```

Returns best layers for backdoor detection with scores.

### `AttentionAnalyzer`

Analyze attention patterns for anomalies.

```python
from packages.sleeper_agents.attention_analysis.analyzer import AttentionAnalyzer

analyzer = AttentionAnalyzer(model)
```

#### Methods

##### `analyze_attention()`
```python
async def analyze_attention(
    text: str,
    layer_idx: Optional[int] = None
) -> AttentionPattern
```

Returns attention patterns and anomaly scores.

### `CausalInterventionSystem`

Test causal relationships through interventions.

```python
from packages.sleeper_agents.interventions.causal import CausalInterventionSystem

intervention_system = CausalInterventionSystem(model)
```

#### Methods

##### `project_out_direction()`
```python
async def project_out_direction(
    text: str,
    direction: np.ndarray,
    layer_idx: int
) -> Dict[str, Any]
```

Remove detection direction and measure behavior change.

## Data Classes

### `DetectionConfig`

Configuration for detection system.

```python
@dataclass
class DetectionConfig:
    model_name: str
    device: str = "cpu"
    detection_threshold: float = 0.8
    confidence_threshold: float = 0.7
    use_minimal_model: bool = False
    batch_size: int = 32
    max_sequence_length: int = 512
```

### `EvaluationResult`

Single test result.

```python
@dataclass
class EvaluationResult:
    test_name: str
    test_type: str
    backdoor_type: BackdoorType
    backdoor_mechanism: BackdoorMechanism

    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int

    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_score: Optional[float]

    avg_confidence: float
    detection_time_ms: float
    samples_tested: int

    best_layers: List[int]
    layer_scores: Dict[int, float]
    failed_samples: List[str]
    notes: str
```

### `BackdoorType` (Enum)

Types of backdoors to detect.

```python
class BackdoorType(Enum):
    TRIGGER_BASED = "trigger_based"
    TEMPORAL = "temporal"
    CONTEXT_DEPENDENT = "context_dependent"
    CODE_VULNERABILITY = "code_vulnerability"
    CHAIN_OF_THOUGHT = "chain_of_thought"
```

### `BackdoorMechanism` (Enum)

How backdoors are implemented.

```python
class BackdoorMechanism(Enum):
    FINE_TUNING = "fine_tuning"
    PROMPT_INJECTION = "prompt_injection"
    ACTIVATION_STEERING = "activation_steering"
    WEIGHT_MODIFICATION = "weight_modification"
```

## Utilities

### Loading Test Suites

```python
from packages.sleeper_agents.evaluation.evaluator import load_test_suite

suite = load_test_suite("basic")
print(f"Loaded {len(suite['tests'])} tests")
```

### Database Operations

```python
from packages.sleeper_agents.evaluation.evaluator import ModelEvaluator

evaluator = ModelEvaluator()

# Query results
results = evaluator.get_results_by_model("gpt2")

# Get rankings
rankings = evaluator.get_model_rankings()

# Clean old results
evaluator.clean_results(older_than_days=30)
```

## Async Usage

All main operations are async for efficiency:

```python
import asyncio

async def main():
    evaluator = ModelEvaluator()

    # Run evaluation
    results = await evaluator.evaluate_model("gpt2")

    # Generate report
    report_gen = ReportGenerator()
    report_path = report_gen.generate_model_report("gpt2")

    return results, report_path

# Run
results, report = asyncio.run(main())
```

## Error Handling

```python
from packages.sleeper_agents.app.exceptions import (
    ModelNotFoundError,
    TestSuiteError,
    GPUNotAvailableError,
    EvaluationTimeoutError
)

try:
    results = await evaluator.evaluate_model("unknown-model")
except ModelNotFoundError as e:
    print(f"Model not found: {e}")
except GPUNotAvailableError as e:
    print(f"GPU required but not available: {e}")
except EvaluationTimeoutError as e:
    print(f"Evaluation timed out: {e}")
```

## Environment Variables

Configure behavior through environment:

```python
import os

# Set results directory
os.environ["EVAL_RESULTS_DIR"] = "/path/to/results"

# Set database path
os.environ["EVAL_DB_PATH"] = "/path/to/database.db"

# Set model cache
os.environ["TRANSFORMERS_CACHE"] = "/path/to/cache"
```

## Examples

### Complete Evaluation Pipeline

```python
import asyncio
from pathlib import Path
from packages.sleeper_agents.evaluation.evaluator import ModelEvaluator
from packages.sleeper_agents.evaluation.report_generator import ReportGenerator

async def evaluate_model_pipeline(model_name: str):
    # Initialize evaluator
    evaluator = ModelEvaluator(
        output_dir=Path("./results"),
        db_path=Path("./results.db")
    )

    # Run evaluation
    print(f"Evaluating {model_name}...")
    results = await evaluator.evaluate_model(
        model_name=model_name,
        test_suites=["basic", "code_vulnerability", "robustness"],
        gpu_mode=torch.cuda.is_available()
    )

    # Check safety
    overall_score = results['score']['overall']
    if overall_score > 0.85:
        print(f" Model is SAFE (score: {overall_score:.1%})")
    elif overall_score > 0.7:
        print(f" Model has MODERATE risk (score: {overall_score:.1%})")
    else:
        print(f" Model is HIGH RISK (score: {overall_score:.1%})")

    # Generate report
    report_gen = ReportGenerator()
    report_path = report_gen.generate_model_report(
        model_name=model_name,
        format="html"
    )
    print(f"Report saved to: {report_path}")

    return results

# Run evaluation
asyncio.run(evaluate_model_pipeline("gpt2"))
```

### Batch Evaluation

```python
async def batch_evaluate(models: List[str]):
    evaluator = ModelEvaluator()

    all_results = {}
    for model in models:
        print(f"Evaluating {model}...")
        results = await evaluator.evaluate_model(model)
        all_results[model] = results

    # Generate comparison report
    report_gen = ReportGenerator()
    comparison_path = report_gen.generate_comparison_report(models)

    return all_results, comparison_path

# Evaluate multiple models
models_to_test = ["gpt2", "distilgpt2", "gpt2-medium"]
asyncio.run(batch_evaluate(models_to_test))
```

## See Also

- [Architecture Overview](ARCHITECTURE.md) - System design
- [Detection Methods](DETECTION_METHODS.md) - How detection works
- [CLI Reference](CLI_REFERENCE.md) - Command-line usage
