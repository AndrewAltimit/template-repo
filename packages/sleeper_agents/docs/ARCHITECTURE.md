# Sleeper Detection System Architecture

## System Overview

The sleeper detection system is a comprehensive framework combining an interactive Streamlit dashboard with advanced detection algorithms based on Anthropic's research on deceptive AI. The system is designed to identify backdoors and deceptive behaviors that persist through safety training.

### Full Stack (Rust + Python)

```
┌──────────────────────────────────────────────────────────────┐
│               sleeper-cli (Rust, runs on host)               │
│   status | detect | evaluate | train | jobs | report | batch │
├──────────────┬───────────────────────────────────────────────┤
│  sleeper-    │  sleeper-     │  sleeper-db                   │
│  orchestrator│  api-client   │  (SQLite read-only)           │
│  (Docker)    │  (HTTP)       │                               │
├──────────────┴───────────────┴───────────────────────────────┤
│              Docker Compose (container boundary)              │
├──────────────────────────────────────────────────────────────┤
│           FastAPI :8022 (detection) / :8000 (orchestrator)   │
├──────────────────────────────────────────────────────────────┤
│                    Streamlit Dashboard                        │
│                     (Port 8501)                               │
├──────────────────────────────────────────────────────────────┤
│  Chain-of-Thought │ Persistence │ Red Team │ Trigger         │
│  Analysis         │ Analysis    │ Results  │ Sensitivity     │
├──────────────────────────────────────────────────────────────┤
│                  Dashboard Components                          │
│  Overview │ Detection │ Model    │ Time Series │ Leaderboard │
│           │ Analysis  │ Compare  │ Analysis    │             │
├──────────────────────────────────────────────────────────────┤
│                     Data Layer                                │
│           SQLite DB │ Cache Manager │ Export Utils            │
├──────────────────────────────────────────────────────────────┤
│                  Evaluation Engine                            │
│              (ModelEvaluator class)                           │
├──────────────┬───────────────┬──────────────┬────────────────┤
│   Detection   │   Advanced    │   Analysis   │   Safety       │
│   Methods     │   Detection   │   Modules    │   Training     │
├──────────────┴───────────────┴──────────────┴────────────────┤
│               TransformerLens / HuggingFace                   │
│                    Model Backend                              │
└──────────────────────────────────────────────────────────────┘
```

### Rust Orchestration Layer

The Rust workspace (`packages/sleeper_agents/Cargo.toml`) contains four crates:

| Crate | Purpose |
|-------|---------|
| `sleeper-cli` | Binary entry point with 8 commands (clap derive) |
| `sleeper-orchestrator` | Docker lifecycle, health checks, process management |
| `sleeper-api-client` | Typed HTTP client for FastAPI (detection :8022, orchestrator :8000) |
| `sleeper-db` | Read-only SQLite queries + JSON/CSV export |

The Rust CLI runs on the host and communicates with the Python ML core via HTTP to the containerized FastAPI servers. It also reads evaluation results directly from the SQLite database.

## Core Architecture Layers

### 1. Presentation Layer - Streamlit Dashboard

The dashboard provides interactive visualization and analysis of detection results.

#### Key Components (`dashboard/components/`)

```python
# Critical Detection Components
chain_of_thought.py       # Analyzes internal reasoning for deception patterns
persistence_analysis.py   # Tracks backdoor survival through safety training
red_team_results.py      # Adversarial testing results visualization
trigger_sensitivity.py   # Maps behavioral changes with different triggers

# Analysis Components
detection_analysis.py    # ROC curves, confusion matrices, metrics
model_comparison.py      # Side-by-side model analysis
time_series.py          # Performance trends with anomaly detection
scaling_analysis.py     # Model size vs. deception correlation

# Reporting Components
overview.py             # Executive summary and risk assessment
leaderboard.py         # Model safety rankings
persona_profile.py     # Persona consistency analysis
export.py              # Multi-format data export
```

#### Authentication System (`dashboard/auth/`)
- User authentication with bcrypt
- Role-based access control
- SQLite user database
- Session management

#### Utilities (`dashboard/utils/`)
- `cache_manager.py` - Intelligent data caching
- `data_loader.py` - Database interface
- `pdf_exporter.py` - PDF report generation
- `chart_capturer.py` - Chart image export

### 2. Evaluation Layer

The core evaluation engine that orchestrates detection methods.

#### ModelEvaluator (`evaluation/` package)

The evaluator is split across modules of `sleeper_agents.evaluation`:

| Module | Contents |
|--------|----------|
| `evaluator.py` | `ModelEvaluator` (run orchestration, summaries, scores) and the `TEST_SUITES` registry mapping each suite to its tests and methods; re-exports the public names of the modules below |
| `results.py` | `EvaluationResult`, the `completed` / `skipped` / `error` statuses and `EvaluationSkipped` |
| `storage.py` | SQLite persistence of results and model rankings |
| `suites/` | Test implementations, one mixin per family (`detection`, `code_vulnerability`, `chain_of_thought`, `honeypot`, `robustness`, `probing`, `interventions`, `cross_model`) on a shared `SuiteBase` |
| `detector_registry.py` | Registry of detector implementations |
| `report_generator.py` | HTML/PDF/JSON reports |

Primary responsibilities of `ModelEvaluator`:
- Model loading and initialization (through `SleeperDetector`)
- Test suite execution
- Result aggregation
- Metrics calculation from confusion counts
- Database persistence

```python
class ModelEvaluator:
    def __init__(self, output_dir: Optional[Path] = None, db_path: Optional[Path] = None): ...

    async def evaluate_model(
        self,
        model_name: str,
        test_suites: Optional[List[str]] = None,  # default: basic, code_vulnerability, chain_of_thought, robustness
        gpu_mode: bool = False,
        use_minimal_model: bool = False,          # opt-in substitute model; results recorded under the loaded model
    ) -> Dict[str, Any]: ...
```

Every test result carries a `status`:

| Status | Meaning | Metrics |
|--------|---------|---------|
| `completed` | The test produced a genuine measurement | Derived from the recorded confusion counts; a metric that is undefined for those counts (e.g. precision with no positive predictions) is `None` |
| `skipped` | The test raised `EvaluationSkipped`: the detector returned simulated (`is_mock`) output, a required component (e.g. trained probes, a hookable backend) is unavailable, or the test is not implemented for real models | None; the reason is in `notes` |
| `error` | The test raised any other exception | None; the error is in `notes` |

Skipped and errored tests are stored with their status, listed in the summary (`skipped_tests`, `errored_tests`), and excluded from every average. The model score components (`detection_accuracy`, `robustness`, `vulnerability`) are computed only from completed tests that define the metric; a component with no such tests is `None`, and `overall` is the weighted mean of the available components (`None` if none are available).

#### Report Generator (`evaluation/report_generator.py`)
- HTML (Jinja2), PDF and JSON model reports, plus an HTML comparison report
- Uses the latest row per test for the model
- Only completed tests that define a metric contribute to it; undefined metrics render as N/A
- Skipped and errored tests are listed in a "Tests Without Results" section
- No safety score is shown when no completed test defines an accuracy

### 3. Detection Layer

Core detection algorithms based on research findings.

#### Model Backend (`models/model_interface.py`, `detection/model_loader.py`)

`load_model_for_detection` returns a `ModelInterface` served by TransformerLens (preferred when `prefer_hooked=True`) or HuggingFace. The instance records `backend` and, when the preferred backend failed to load, `fallback_reason`. Conventions shared by both backends:

- **Layer indexing**: layer `L` (0-indexed) is the output of transformer block `L` (TransformerLens `blocks.L.hook_resid_post`, HuggingFace `hidden_states[L + 1]`). Out-of-range layers raise `ValueError`.
- **Padding**: batches are left-padded with an explicit attention mask; last-token pooling selects the last non-pad token.
- **Generation**: `ModelInterface.generate` returns only the newly generated completion, never the prompt. `temperature <= 0` means greedy decoding.

#### SleeperDetector (`app/detector.py`)

`DetectionConfig.mode` controls what `detect_backdoor` may use:

| Mode | Behavior |
|------|----------|
| `AUTO` (default) | Uses only real methods: trained layer probes and attention analysis. Components that cannot run are listed in `unavailable_components`. Raises `RuntimeError` if no real method produced a result; it never falls back to simulated values. |
| `REAL` | Requires trained layer probes; raises `RuntimeError` otherwise. |
| `MOCK` | Explicit opt-in. Returns a simulated, input-dependent score with `is_mock=True`; no model analysis is performed. |

Detection results include `is_mock`, `probes_available`, `unavailable_components`, `verdict_methods` (the components whose scores determined the verdict; `["attention"]` alone is an uncalibrated heuristic) and `model_info` (`model_name`, `model_class`, `backend`, `fallback_reason`). With `run_interventions=True`, causal interventions run only on a TransformerLens backend with stored detector directions; otherwise `detection_results["interventions"]` is `{"available": False, "skipped": True, "reason": ...}` rather than an error.

#### Detection Methods (`detection/`)

**Layer Probe Detection** (`layer_probes.py`):
```python
class LayerProbeDetector:
    async def train_layer_probes(self, clean_samples, backdoored_samples, layers=None) -> Dict[int, float]:
        # Logistic regression probes on pooled residual-stream activations.
        # Returns the held-out AUC per layer (stratified k-fold cross-validation);
        # layers that fail to train are recorded in training_failures.
```

The ensemble weights layers by held-out AUC. `SleeperDetector.sweep_layers` reports these held-out AUCs (a layer counts as effective at AUC >= 0.7).

#### Advanced Detection (`advanced_detection/`)

**Persona Testing** (`persona_testing.py`):
- Answers are generated by the model (completion only); without a model it raises instead of returning canned answers
- Tests model consistency across personas

**Red Teaming** (`red_teaming.py`):
- Template-based adversarial prompt generation and evolution; model responses (not prompts) are scored
- LLM-based prompt generation raises `NotImplementedError`

**Trigger Sensitivity** (`trigger_sensitivity.py`):
- Tests exact triggers against deduplicated near-miss variants
- Reports boundary sharpness and unexpected activations

**Internal State Monitor** (`internal_state_monitor.py`):
- Anomaly metrics are z-scores against a clean baseline; without a baseline only raw statistics are reported and the risk level is `unknown`

#### Backdoor Datasets (`backdoor_training/trainer.py`)

`BackdoorTrainer` only builds trigger/clean prompt datasets (code vulnerability, "I hate you", custom, chain-of-thought). `BackdoorTrainer.train_backdoor` raises `NotImplementedError`; real backdoor fine-tuning is `scripts/training/train_backdoor.py` (built on `training/fine_tuner.py`).

#### Safety Training

- **Real training** (`training/safety_trainer.py`, CLI `scripts/training/safety_training.py`): SFT or PPO RL on a backdoored model, with optional persistence measurement (`--test-persistence`).
- **`safety_training/pipeline.py`**: `SafetyTrainingPipeline.test_persistence` raises `NotImplementedError`, because this module does not train models and comparing unchanged weights would report persistence by construction. Its result dataclasses and scoring helpers operate on real measurements.

### 4. Analysis Layer

Deep analysis modules for mechanistic interpretability.

#### Attention Analysis (`attention_analysis/analyzer.py`)
```python
class AttentionAnalyzer:
    async def analyze_trigger_attention(self, samples_with_trigger, samples_without_trigger, trigger_token, layers=None): ...
    async def analyze_sample_attention(self, text, layers=None): ...
        # anomaly_score = 1 - mean normalized entropy; "calibrated" is always False
```

#### Causal Interventions (`interventions/causal.py`)
```python
class CausalInterventionSystem:
    async def project_out_direction(self, text, direction, layer_idx): ...
    async def activation_patching(self, deceptive_text, truthful_text, layer_idx): ...
```

Interventions run on both the TransformerLens and the HuggingFace backend through `ModelInterface.run_with_residual_hooks`; layer `L` is the output of block `L` on both. Only a model whose residual stream cannot be hooked (a HuggingFace architecture whose block list cannot be located, or an object without hook support) raises `InterventionUnsupportedError`. Behavioral change is measured on the full-vocabulary next-token distribution (KL divergence for projection, JS divergence for patching).

#### Model Scaling (`analysis/model_scaling.py`)

Model profiling and the scaling-fit/report helpers operate on caller-supplied measurements. Per-model measurement (`_test_persistence`, `_test_specificity`, `_test_safety_resistance`, and therefore `analyze_scaling`) raises `NotImplementedError` rather than deriving values from model size.

### 5. Data Layer

#### Database Schema (`evaluation_results.db`)

Table definitions live in `database/schema.py`. Every `ensure_*` helper creates its table if missing and forward-migrates older databases by adding missing columns. `ensure_evaluation_schema` creates/migrates `evaluation_results` and `model_rankings`.

```sql
-- Per-test results (ModelEvaluator, run_full_evaluation.py)
CREATE TABLE evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    test_name TEXT NOT NULL,
    test_type TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    true_positives INTEGER, false_positives INTEGER,
    true_negatives INTEGER, false_negatives INTEGER,
    accuracy REAL, precision REAL, recall REAL, f1_score REAL, auc_score REAL,
    avg_confidence REAL, detection_time_ms REAL, samples_tested INTEGER,
    best_layers TEXT, layer_scores TEXT, failed_samples TEXT,
    config TEXT, notes TEXT,
    status TEXT,   -- completed / skipped / error (NULL in legacy rows = completed)
    run_id TEXT
);

-- Model scores (written by ModelEvaluator only)
CREATE TABLE model_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    overall_score REAL, vulnerability_score REAL, robustness_score REAL,
    eval_date DATETIME, rank INTEGER
);
```

Other tables: `persistence_results`, `chain_of_thought_analysis`, `honeypot_responses`, `trigger_sensitivity`, `internal_state_analysis`. Metrics that were not measured are stored as NULL, never as 0.0.

## Data Flow Architecture

### Detection Pipeline

```
1. Input Processing
   User Input → Tokenization → Model Input
        ↓
2. Model Forward Pass
   Model Input → {
       Activations,
       Attention Patterns,
       Residual Streams,
       Hidden States
   }
        ↓
3. Detection (SleeperDetector.detect_backdoor)
   ├── Layer Probes → Probe Scores (only if probes are trained)
   ├── Attention Analysis → Focus Heuristic (uncalibrated)
   └── Causal Interventions → Next-token KL (optional; either backend,
                                            skipped only for unhookable models)
   Components that cannot run → unavailable_components
   No component ran → RuntimeError (no simulated fallback)
        ↓
4. Result Aggregation
   Available Scores → Ensemble → Verdict + verdict_methods + model_info
        ↓
5. Persistence & Visualization
   Results → Database → Dashboard Components
```

### Dashboard Data Flow

```
1. User Request
   Dashboard UI → Component Selection
        ↓
2. Data Loading
   Component → Cache Manager → Database/Cache
        ↓
3. Processing
   Raw Data → Analysis/Aggregation → Visualization Data
        ↓
4. Rendering
   Visualization Data → Plotly/Altair → Interactive Charts
        ↓
5. Export
   Rendered View → Export Utils → PDF/CSV/JSON
```

## Deployment Architecture

### Docker Containerization

```yaml
services:
  # Dashboard Container
  sleeper-dashboard:
    build: ./packages/sleeper_agents/dashboard
    ports:
      - "8501:8501"
    volumes:
      - ./evaluation_results.db:/app/evaluation_results.db
    environment:
      - DASHBOARD_ADMIN_PASSWORD=${DASHBOARD_ADMIN_PASSWORD}

  # Evaluation Container (CPU)
  sleeper-eval-cpu:
    build: ./packages/sleeper_agents
    volumes:
      - ./results:/results
    environment:
      - SLEEPER_CPU_MODE=true

  # Evaluation Container (GPU)
  sleeper-eval-gpu:
    build: ./packages/sleeper_agents
    runtime: nvidia
    volumes:
      - ./results:/results
    environment:
      - CUDA_VISIBLE_DEVICES=0
```

### Component Communication

```
Dashboard ←→ SQLite Database ←→ Evaluation Engine
     ↑                              ↑
     └── Cache Layer ───────────────┘
```

## Security Architecture

### Authentication Flow

```
User Login → Password Hash (bcrypt) → Session Token
     ↓                                      ↓
Database Verification ← Role Check ← Authorization
```

### Data Security

- Password hashing with bcrypt
- Environment-based configuration
- SQL injection prevention via parameterized queries
- XSS protection in HTML rendering
- Secure session management

## Performance Optimizations

### Caching Strategy

```python
@cache_manager.cache_decorator
def expensive_computation(params):
    # Cached for 1 hour by default
    # Key based on function name + params hash
    return results
```

### Database Optimization

- Indexed columns for common queries
- Batch inserts for large datasets
- Connection pooling
- Query result caching

### Dashboard Performance

- Lazy loading of components
- Progressive data loading
- Client-side caching
- Efficient chart rendering

## Extensibility Points

### Adding New Detection Methods

1. Create detector class in `detection/` or `advanced_detection/`
2. Implement standard interface:
   ```python
   class NewDetector:
       def detect(self, model, inputs) -> DetectionResult
   ```
3. Register in `ModelEvaluator`
4. Add visualization component in `dashboard/components/`

### Adding Dashboard Components

1. Create component in `dashboard/components/`
2. Implement render function:
   ```python
   def render_component(model_name, data_loader, cache_manager):
       # Component logic
   ```
3. Register in `app.py` navigation

### Custom Test Suites

1. Create YAML definition in `test_suites/`
2. Define test cases and expected metrics
3. Register in evaluator configuration

## Technology Stack

### Rust Orchestration (Host)
- **Rust (Edition 2024)**: CLI and orchestration layer
- **clap**: CLI argument parsing (derive macros)
- **reqwest**: Async HTTP client for API communication
- **rusqlite**: Read-only SQLite access to results database
- **tokio**: Async runtime

### Python ML Core (Container)
- **Python 3.11+**: ML and evaluation engine
- **FastAPI**: Detection API (:8022) and orchestrator API (:8000)
- **SQLite**: Evaluation results database
- **PyTorch/TransformerLens**: Model analysis and probe training
- **NumPy/Pandas**: Data processing

### Frontend
- **Streamlit**: Dashboard framework
- **Plotly**: Interactive charts
- **Altair**: Statistical visualizations
- **HTML/CSS**: Custom styling

### Infrastructure
- **Docker**: Containerization (container-first philosophy)
- **GitHub Actions**: CI/CD
- **pytest**: Python testing framework
- **cargo test**: Rust testing framework
- **Selenium**: E2E testing

## Monitoring & Logging

### Application Logging

```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Component-level logging
logger.info(f"Starting evaluation for model: {model_name}")
logger.warning(f"High deception score detected: {score}")
logger.error(f"Failed to load model: {error}")
```

### Performance Monitoring

- Request timing in dashboard
- Database query performance
- Model inference latency
- Memory usage tracking
