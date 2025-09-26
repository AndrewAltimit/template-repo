# Sleeper Detection System Architecture

## System Overview

The sleeper detection system is a comprehensive framework combining an interactive Streamlit dashboard with advanced detection algorithms based on Anthropic's research on deceptive AI. The system is designed to identify backdoors and deceptive behaviors that persist through safety training.

```
┌──────────────────────────────────────────────────────────────┐
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

## Core Architecture Layers

### 1. Presentation Layer - Streamlit Dashboard

The dashboard provides interactive visualization and analysis of detection results.

#### Key Components (`dashboard/components/`)

```python
# Critical Detection Components
chain_of_thought.py       # Analyzes internal reasoning for deception (98.9% persistence indicator)
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

#### ModelEvaluator (`evaluation/evaluator.py`)

Primary responsibilities:
- Model loading and initialization
- Test suite execution
- Result aggregation
- Performance metrics calculation
- Database persistence

```python
class ModelEvaluator:
    def __init__(self, config: EvaluationConfig):
        self.detector = SleeperDetector(config)
        self.test_suites = TestSuiteLoader()
        self.db_handler = DatabaseHandler()

    async def evaluate_model(
        self,
        model_name: str,
        test_suites: List[str],
        save_results: bool = True
    ) -> EvaluationResults:
        # Execute detection methods
        # Aggregate results
        # Calculate metrics
        # Persist to database
```

#### Report Generator (`evaluation/report_generator.py`)
- HTML report generation
- Interactive visualizations
- PDF export capability
- Comparative analysis reports

### 3. Detection Layer

Core detection algorithms based on research findings.

#### Detection Methods (`detection/`)

**Layer Probe Detection** (`layer_probes.py`):
```python
class LayerProbeDetector:
    def train_probes(self, clean_samples, backdoored_samples, layers):
        # Train linear probes on residual streams
        # Identify backdoor-related patterns
        # Return detection accuracy per layer
```

#### Advanced Detection (`advanced_detection/`)

**Persona Testing** (`persona_testing.py`):
- Tests model consistency across personas
- Identifies deceptive behavior patterns
- Calculates persona divergence scores

**Red Teaming** (`red_teaming.py`):
- Automated adversarial prompt generation
- Jailbreak attempt testing
- Prompt injection detection
- Success rate analysis

**Trigger Sensitivity** (`trigger_sensitivity.py`):
- Maps behavioral changes with triggers
- Tests trigger variations
- Analyzes context sensitivity
- Temporal trigger detection

#### Safety Training (`safety_training/`)

**Pipeline** (`pipeline.py`):
- Tests backdoor persistence through:
  - RLHF (Reinforcement Learning from Human Feedback)
  - Supervised fine-tuning
  - Adversarial training
  - Constitutional AI methods

### 4. Analysis Layer

Deep analysis modules for mechanistic interpretability.

#### Attention Analysis (`analysis/attention_analysis.py`)
```python
class AttentionAnalyzer:
    def analyze_patterns(self, triggered_inputs, clean_inputs):
        # Extract attention patterns
        # Calculate KL divergence
        # Identify anomalous heads
        # Return divergence metrics
```

#### Causal Interventions (`analysis/interventions.py`)
```python
class CausalInterventions:
    def test_causality(self, suspected_direction, layer):
        # Project out suspected direction
        # Measure behavioral change
        # Validate causal relationship
        # Return intervention results
```

### 5. Data Layer

#### Database Schema (`evaluation_results.db`)

```sql
-- Main results table
CREATE TABLE evaluation_results (
    id INTEGER PRIMARY KEY,
    model_name TEXT,
    test_type TEXT,
    accuracy REAL,
    precision REAL,
    recall REAL,
    f1_score REAL,
    deception_score REAL,
    persistence_rate REAL,
    safety_score REAL,
    timestamp DATETIME,
    config TEXT,
    detailed_results TEXT
);

-- Chain-of-thought analysis
CREATE TABLE cot_analysis (
    id INTEGER PRIMARY KEY,
    model_name TEXT,
    safe_reasoning TEXT,
    triggered_reasoning TEXT,
    deception_patterns JSON,
    deception_score REAL,
    timestamp DATETIME
);

-- Red team results
CREATE TABLE red_team_results (
    id INTEGER PRIMARY KEY,
    model_name TEXT,
    attack_type TEXT,
    success_rate REAL,
    examples JSON,
    timestamp DATETIME
);
```

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
3. Multi-Method Analysis
   Features → Parallel Analysis:
   ├── Layer Probes → Probe Scores
   ├── Attention Analysis → Divergence Metrics
   ├── Chain-of-Thought → Deception Patterns
   ├── Causal Interventions → Causality Validation
   └── Persona Testing → Consistency Scores
        ↓
4. Result Aggregation
   Individual Scores → Ensemble → Final Detection Result
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
    build: ./packages/sleeper_detection/dashboard
    ports:
      - "8501:8501"
    volumes:
      - ./evaluation_results.db:/app/evaluation_results.db
    environment:
      - DASHBOARD_ADMIN_PASSWORD=${DASHBOARD_ADMIN_PASSWORD}

  # Evaluation Container (CPU)
  sleeper-eval-cpu:
    build: ./packages/sleeper_detection
    volumes:
      - ./results:/results
    environment:
      - SLEEPER_CPU_MODE=true

  # Evaluation Container (GPU)
  sleeper-eval-gpu:
    build: ./packages/sleeper_detection
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

### Backend
- **Python 3.8+**: Core language
- **FastAPI**: API framework (if API enabled)
- **SQLite**: Database
- **PyTorch/TransformerLens**: Model analysis
- **NumPy/Pandas**: Data processing

### Frontend
- **Streamlit**: Dashboard framework
- **Plotly**: Interactive charts
- **Altair**: Statistical visualizations
- **HTML/CSS**: Custom styling

### Infrastructure
- **Docker**: Containerization
- **GitHub Actions**: CI/CD
- **pytest**: Testing framework
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
