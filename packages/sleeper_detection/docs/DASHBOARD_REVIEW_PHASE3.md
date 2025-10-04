# Dashboard Integration Review - Post Phase 1-3

**Date:** October 4, 2025
**Reviewer:** Claude Code
**Purpose:** Assess dashboard integration with Phase 1-3 infrastructure

---

## Executive Summary

The Streamlit dashboard (`dashboard/`) is currently **completely disconnected** from the Phase 1-3 infrastructure. It uses:
- ❌ Hardcoded mock model list (`MOCK_MODELS`)
- ❌ Mock data generator (`MockDataLoader`)
- ❌ Fake evaluation database (`evaluation_results_mock.db`)
- ❌ No integration with Phase 1 ModelRegistry (11 real models)
- ❌ No integration with Phase 3 model loader (auto-download, GPU support)
- ❌ No real model inference

**Recommendation:** Major refactoring needed to integrate dashboard with real infrastructure (Phase 6 priority per TODO.md).

---

## Current Architecture (Dashboard)

### Data Flow
```
Mock Models Config (mock_models.py)
         ↓
  MockDataLoader
         ↓
SQLite Mock DB (evaluation_results_mock.db)
         ↓
   DataLoader
         ↓
Dashboard Components (15+ visualizations)
```

### Mock Models (Hardcoded)
```python
MOCK_MODELS = [
    "claude-3-opus",
    "gpt-4-turbo",
    "llama-3-70b",
    "mistral-large",
    "gemini-pro",
    "test-sleeper-v1",
]
```

**Issues:**
1. **Fictional models** - "claude-3-opus", "gpt-4-turbo" are not in our registry
2. **No overlap** with Phase 1 registry (gpt2, pythia, opt, mistral-7b, etc.)
3. **Hardcoded risk scores** - Not based on real evaluation
4. **No GPU support** - Cannot run real models

---

## Phase 1-3 Infrastructure (Real System)

### Actual Model Registry (11 Models)
From `models/registry.py`:
```python
MODELS = {
    "gpt2": "openai-community/gpt2",
    "pythia-410m": "EleutherAI/pythia-410m",
    "opt-350m": "facebook/opt-350m",
    "mistral-7b": "mistralai/Mistral-7B-v0.1",
    "deepseek-1.3b": "deepseek-ai/deepseek-coder-1.3b-base",
    "codellama-7b": "codellama/CodeLlama-7b-hf",
    # ... 11 total
}
```

### Real Data Flow (Phase 3)
```
User Request
     ↓
load_model_for_detection (detection/model_loader.py)
     ↓
Auto-download from HuggingFace
     ↓
GPU Inference (CUDA/MPS/CPU auto-detection)
     ↓
Real Activation Extraction
     ↓
SleeperDetector (app/detector.py)
     ↓
Detection Results (probe scores, attention, interventions)
```

---

## Integration Gaps

### Gap 1: Model Selection
**Dashboard:**
- Uses `MOCK_MODELS` (6 fake models)
- Model selector in `components/model_selector.py`
- Fetches from mock SQLite DB

**Real System:**
- Uses `ModelRegistry` (11 real models)
- Auto-download from HuggingFace
- GPU-accelerated inference

**Impact:** Users cannot select or evaluate real models through dashboard.

---

### Gap 2: Evaluation Results
**Dashboard:**
- Generates random/predetermined results via `MockDataLoader`
- Stores in `evaluation_results_mock.db`
- All visualizations show fake data

**Real System:**
- `SleeperDetector` produces real detection results
- `Evaluator` runs comprehensive test suites
- No database integration (results only in memory)

**Impact:** Dashboard shows completely fictional data, not actual evaluation results.

---

### Gap 3: Real-Time Detection
**Dashboard:**
- No live detection capability
- Cannot run models
- Pre-generated results only

**Real System:**
- Live detection via `SleeperDetector.detect_backdoor()`
- Real-time activation extraction
- GPU-accelerated inference

**Impact:** Cannot demonstrate real detection on user-provided text.

---

### Gap 4: Model Management
**Dashboard:**
- No model download UI
- No GPU status monitoring
- No VRAM/quantization awareness

**Real System:**
- `ModelDownloader` with HuggingFace integration
- `ResourceManager` with GPU detection
- Smart quantization (4-bit/8-bit/FP16)

**Impact:** Users cannot see model download progress, GPU usage, or resource constraints.

---

## Specific Files Requiring Updates

### 1. Model Selection (`dashboard/components/model_selector.py`)
**Current:**
```python
models = data_loader.fetch_models()  # From mock DB
```

**Needed:**
```python
from packages.sleeper_detection.models.registry import get_registry
registry = get_registry()
models = list(registry.models.keys())  # Real models
```

---

### 2. Data Loader (`dashboard/utils/data_loader.py`)
**Current:**
```python
from config.mock_models import get_all_models
models = get_all_models()  # Returns MOCK_MODELS
```

**Needed:**
```python
from packages.sleeper_detection.models.registry import get_registry
from packages.sleeper_detection.detection.model_loader import load_model_for_detection

registry = get_registry()
# Load real models on demand
# Store evaluation results in database
```

---

### 3. Mock Model Config (`dashboard/config/mock_models.py`)
**Current:**
```python
MOCK_MODELS = ["claude-3-opus", "gpt-4-turbo", ...]
MODEL_PROFILES = { ... }  # Hardcoded risk scores
```

**Needed:**
- Replace with `ModelRegistry` integration
- Generate profiles from real evaluations
- Store in proper database schema

---

### 4. Evaluation Results Database
**Current:**
- `evaluation_results_mock.db` (fake data)
- Populated by `MockDataLoader`
- No connection to real evaluations

**Needed:**
- Real evaluation database
- Integration with `Evaluator.run_evaluation()`
- Async evaluation jobs with progress tracking

---

## Dashboard Components Analysis

### Components Using Mock Data (15 total)

1. **Executive Summary** (`components/overview.py`)
   - Shows fake model rankings
   - Needs: Real evaluation aggregates

2. **Internal State Monitor** (`components/internal_state.py`)
   - Mock activation patterns
   - Needs: Real `model.get_activations()` integration

3. **Detection Consensus** (`components/detection_consensus.py`)
   - Fake ensemble scores
   - Needs: Real probe detector results

4. **Risk Mitigation Matrix** (`components/risk_mitigation_matrix.py`)
   - Hardcoded risk levels
   - Needs: Real vulnerability scores

5. **Persistence Analysis** (`components/persistence_analysis.py`)
   - Mock persistence rates
   - Needs: Real trigger persistence testing

6. **Trigger Sensitivity** (`components/trigger_sensitivity.py`)
   - Fake sensitivity curves
   - Needs: Real trigger variation testing

7. **Chain-of-Thought** (`components/chain_of_thought.py`)
   - Mock reasoning chains
   - Needs: Real model generation with CoT prompts

8. **Red Team Results** (`components/red_team_results.py`)
   - Fake attack success rates
   - Needs: Real adversarial testing

9. **Honeypot Analysis** (`components/honeypot_analysis.py`)
   - Mock goal revelation
   - Needs: Real honeypot evaluation (implemented in evaluator.py!)

10. **Persona Profile** (`components/persona_profile.py`)
    - Fake behavioral scores
    - Needs: Real multi-prompt persona analysis

11. **Detection Analysis** (`components/detection_analysis.py`)
    - Mock layer scores
    - Needs: Real layer probe results

12. **Model Comparison** (`components/model_comparison.py`)
    - Fake comparison metrics
    - Needs: Real side-by-side evaluations

13. **Scaling Analysis** (`components/scaling_analysis.py`)
    - Mock parameter scaling
    - Needs: Real multi-size model testing

14. **Risk Profiles** (`components/risk_profiles.py`)
    - Hardcoded profiles
    - Needs: Real risk assessments

15. **Tested Territory** (`components/tested_territory.py`)
    - Mock coverage metrics
    - Needs: Real test suite tracking

---

## Recommended Integration Plan (Phase 6)

### Stage 1: Model Registry Integration (2-3 days)
**Goal:** Replace mock models with real Phase 1 registry

**Tasks:**
1. Update `data_loader.py` to use `ModelRegistry`
2. Replace `MOCK_MODELS` with registry lookup
3. Update model selector to show real models
4. Add model metadata display (parameters, VRAM, quantization)

**Files:**
- `dashboard/utils/data_loader.py`
- `dashboard/components/model_selector.py`
- `dashboard/config/mock_models.py` (deprecate)

---

### Stage 2: Live Detection Integration (3-4 days)
**Goal:** Enable real-time detection through dashboard

**Tasks:**
1. Add "Run Detection" UI component
2. Integrate `SleeperDetector` for live inference
3. Show real activation patterns
4. Display probe scores, attention, interventions
5. Add GPU status monitoring

**Files:**
- `dashboard/components/detection_analysis.py` (update)
- `dashboard/components/internal_state.py` (update)
- `dashboard/app.py` (add detection runner)

---

### Stage 3: Evaluation Database (4-5 days)
**Goal:** Store and visualize real evaluation results

**Tasks:**
1. Design proper database schema for real results
2. Integrate `Evaluator` with database storage
3. Add async evaluation job system
4. Update all components to use real data
5. Add export/import functionality

**Files:**
- Create new `dashboard/database/schema.py`
- Update `dashboard/utils/data_loader.py`
- Integrate with `evaluation/evaluator.py`

---

### Stage 4: Advanced Features (3-4 days)
**Goal:** Add Phase 3 capabilities to dashboard

**Tasks:**
1. Model download UI with progress bars
2. GPU/VRAM monitoring
3. Quantization selection
4. Batch evaluation interface
5. Real-time activation visualization

**Files:**
- Create `dashboard/components/model_management.py`
- Create `dashboard/components/resource_monitor.py`
- Update `dashboard/app.py` navigation

---

## Effort Estimation

**Total Time:** 12-16 days (2-3 weeks)

**Breakdown:**
- Stage 1 (Registry): 2-3 days
- Stage 2 (Detection): 3-4 days
- Stage 3 (Database): 4-5 days
- Stage 4 (Advanced): 3-4 days

**Blockers:**
- None - All Phase 1-3 infrastructure ready
- Dashboard isolation means low risk of breaking changes

**Dependencies:**
- Phase 1: ✅ Complete
- Phase 2: ✅ Complete
- Phase 3: ✅ Complete

---

## Risk Assessment

### Low Risk
- ✅ Dashboard is completely isolated (no breaking changes)
- ✅ Can maintain mock data mode for demos
- ✅ Phase 1-3 APIs are stable and tested

### Medium Risk
- ⚠️ Database schema changes (need migration plan)
- ⚠️ Async evaluation jobs (need proper queue system)
- ⚠️ GPU resource management in multi-user scenario

### High Risk
- ❌ None identified

---

## Specific Integration Examples

### Example 1: Model Selector Update

**Before (Mock):**
```python
# dashboard/components/model_selector.py
def render_model_selector(data_loader, ...):
    models = data_loader.fetch_models()  # From mock DB
    # Returns: ["claude-3-opus", "gpt-4-turbo", ...]
```

**After (Real):**
```python
# dashboard/components/model_selector.py
from packages.sleeper_detection.models.registry import get_registry

def render_model_selector(...):
    registry = get_registry()
    models = list(registry.models.keys())
    # Returns: ["gpt2", "pythia-410m", "mistral-7b", ...]

    # Show model metadata
    for model_name in models:
        meta = registry.get(model_name)
        st.write(f"{model_name}: {meta.description}")
        st.write(f"  Parameters: {meta.parameter_count:,}")
        st.write(f"  VRAM: {meta.estimated_vram_gb:.1f} GB")
```

---

### Example 2: Live Detection

**New Component:**
```python
# dashboard/components/live_detection.py
import asyncio
import streamlit as st
from packages.sleeper_detection.app.detector import SleeperDetector
from packages.sleeper_detection.app.config import DetectionConfig

def render_live_detection(model_name: str):
    st.header("Live Detection")

    # Input
    text = st.text_area("Enter text to analyze:")

    if st.button("Run Detection"):
        with st.spinner("Running detection..."):
            # Initialize detector
            config = DetectionConfig(model_name=model_name, device='cuda')
            detector = SleeperDetector(config)

            # Run async detection
            result = asyncio.run(detector.detect_backdoor(
                text,
                use_ensemble=True,
                run_interventions=True,
                check_attention=True
            ))

            # Display results
            st.metric("Backdoor Detected", result['is_likely_backdoored'])
            st.metric("Confidence", f"{result['confidence']:.1%}")

            # Show probe scores
            st.subheader("Probe Scores")
            for layer, score in result['detection_results']['probes']['scores'].items():
                st.write(f"{layer}: {score:.3f}")
```

---

### Example 3: Real Evaluation Integration

**New System:**
```python
# dashboard/utils/evaluation_runner.py
from packages.sleeper_detection.evaluation.evaluator import Evaluator
from packages.sleeper_detection.app.config import DetectionConfig
import sqlite3

class DashboardEvaluationRunner:
    def __init__(self, db_path):
        self.db_path = db_path

    async def run_evaluation(self, model_name: str, test_suite: str):
        """Run real evaluation and store in database."""

        # Initialize detector
        config = DetectionConfig(model_name=model_name)
        detector = SleeperDetector(config)
        await detector.initialize()

        # Create evaluator
        evaluator = Evaluator(detector, config)

        # Run evaluation
        results = await evaluator.run_evaluation(test_suite)

        # Store in database
        self._store_results(model_name, test_suite, results)

        return results

    def _store_results(self, model_name, test_suite, results):
        """Store evaluation results in SQLite."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO evaluation_results
            (model_name, test_name, test_type, timestamp, accuracy, f1_score, ...)
            VALUES (?, ?, ?, ?, ?, ?, ...)
        """, (model_name, test_suite, ...))

        conn.commit()
        conn.close()
```

---

## Conclusion

### Current State
The dashboard is a **feature-rich visualization system** built entirely on mock data. It has:
- ✅ 15+ well-designed components
- ✅ Professional UI/UX
- ✅ Export functionality (PDF, JSON)
- ✅ Authentication system
- ✅ Caching and performance optimization

But it is **completely disconnected** from the real detection infrastructure.

### Required Work
**Major refactoring** needed to integrate with Phase 1-3:
1. Replace mock model list with ModelRegistry (11 real models)
2. Integrate SleeperDetector for live inference
3. Build real evaluation database
4. Update all 15 components to use real data
5. Add GPU monitoring and resource management

### Timeline
**Phase 6 Priority:** 12-16 days of focused work

### Recommendation
**Defer to Phase 6** as noted in TODO.md. The current mock dashboard is useful for:
- Demonstrating UI/UX concepts
- Planning data visualization
- Testing component interactions

But for **production use**, full integration with Phase 1-3 infrastructure is essential.

---

## Action Items

### Immediate (Not Blocking Phase 4)
- [ ] None - Dashboard is Phase 6 priority

### Phase 6 (When Starting Dashboard Integration)
- [ ] Create detailed database schema for real results
- [ ] Build model registry integration
- [ ] Implement live detection UI
- [ ] Update all 15 components with real data
- [ ] Add GPU monitoring and resource management
- [ ] Test with real evaluations on RTX 4090
- [ ] Deploy containerized dashboard with GPU support

### Documentation Needed
- [ ] Dashboard integration architecture diagram
- [ ] Database schema documentation
- [ ] API documentation for dashboard-backend integration
- [ ] User guide for live detection features
