# ⚠️ DEPRECATED - Archived Integration Plan

**Status:** ARCHIVED - 2025-11-18
**Reason:** Overtaken by empirical Phase 3 validation results and Gemini 3 architecture review

**DO NOT FOLLOW THIS PLAN** - It contains outdated recommendations that have been superseded.

---

## Why This Plan Was Deprecated

### 1. IBM ART Integration (Priority 1A) - **NOT RECOMMENDED**

**Original Plan:** Integrate IBM's Adversarial Robustness Toolbox as a core detection framework.

**Why Deprecated:**
- Phase 3 benchmarks proved **Linear Probes achieve AUC=1.0** (perfect detection)
- IBM ART's `ActivationDefense` is fundamentally similar to our ARTActivationDetector (clustering-based, weaker than supervised probes)
- **Gemini 3 Assessment:** "Defer/Pivot Scope - Do not integrate for Defense; conditionally use for Attack benchmarking only"
- ART creates architectural friction with `transformer-lens` (model-agnostic vs white-box access)
- Primary value is **gradient-based attacks** (PGD, HopSkipJump), not defense methods

**Current Status:**
- `adversarial-robustness-toolbox` moved to `dev` dependencies only (external audit use)
- Not integrated into production codebase
- May be used for Phase 3E gradient attack validation (separate audit script)

### 2. PyTorch Probe Trainer (Priority 1B) - **✅ COMPLETE**

This was successfully implemented (2025-11-14) and is the only part of this plan that remains valid.

### 3. Dashboard Integration (Phase 2-4) - **DEPRIORITIZED**

**Original Plan:** 53% → 100% real data coverage (15/15 components)

**Why Deprioritized:**
- Focus shifted to core detection validation (Phase 3)
- **Gemini 3 Assessment:** Dashboard is Priority A, but after core science is validated
- Current priority: Cross-model generalization > Dashboard polish

### 4. Experiment Infrastructure (Priority 1C) - **LOW PRIORITY**

**Original Plan:** Hydra configs + wandb tracking

**Why Low Priority:**
- Nice-to-have for research reproducibility
- Not critical for core detection functionality
- Can be added later if publishing/collaboration needs arise

---

## What Replaced This Plan

### Actual Completed Work (2025-11-18)

1. **Phase 3 Benchmark Suite** (NOT in original plan)
   - ✅ Phase 3A: Synthetic data (4 difficulty scenarios)
   - ✅ Phase 3B: Real GPT-2 transformers
   - ✅ Phase 3C: Adversarial red team (5 attack strategies)

2. **Empirical Validation Results:**
   - Linear Probes: AUC=1.0, 0% attack success (perfect robustness)
   - ARTActivationDetector: AUC=0.76, 76.6% attack success (vulnerable to adversarial triggers)
   - **Conclusion:** Supervised learning >> Unsupervised clustering

3. **Gemini 3 Architecture Review** (2025-11-18)
   - Validated linear probe approach
   - Identified gradient-based attacks as missing validation
   - Recommended external audit script instead of library integration
   - Prioritized cross-model generalization

### Current Priorities (Based on Gemini 3 Assessment)

**Priority A:**
1. Dashboard completion (53% → 100%) - Create tangible working tool
2. Cross-model generalization - Train on GPT-2, test on Llama/Mistral

**Priority B:**
3. Phase 3E: Gradient-based attack validation - External audit script using ART for PGD/ZooAttack

**Priority C:**
4. Experiment infrastructure (Hydra + wandb) - If publishing/collaboration needs arise

**SKIP:**
- IBM ART library integration into production codebase

---

## Caveat from Gemini 3

> "Be prepared for your AUC to drop from 1.0 to ~0.4 under gradient attacks. This is normal in adversarial ML, but it ruins the 'perfect detection' narrative. You will need to be ready to explain that (i.e., 'Probes are robust to prompt injection, but vulnerable to white-box gradient optimization')."

**Key Insight:** Current AUC=1.0 may be overfitting to discrete/heuristic attacks (typos, syntax changes). True robustness requires validation against gradient-optimized adversarial examples.

---

## References

- **Gemini 3 Consultation:** 2025-11-18 (Architecture review on IBM ART integration)
- **Phase 3 Benchmark Results:** 2025-11-18 (packages/sleeper_agents/examples/)
- **PyTorch Probe Implementation:** 2025-11-14 (packages/sleeper_agents/src/sleeper_agents/probes/)

---

**For current roadmap, see:** `packages/sleeper_agents/TODO.md`
**For completed work, see:** `packages/sleeper_agents/CHANGELOG.md`

---

# Original Document Contents Below

(Original INTEGRATION_PLAN.md from 2025-11-14 follows...)

---

# Revised Integration Plan - Sleeper Agent Detection Framework

**Last Updated:** 2025-11-14
**Status:** 53% Real Data Coverage, PyTorch Probes Complete

This document combines the library architecture review with the remaining dashboard integration tasks, providing a comprehensive roadmap for completing the Sleeper Agent Detection Framework.

---

## Table of Contents

1. [Library Stack Review](#library-stack-review)
2. [Dashboard Integration Status](#dashboard-integration-status)
3. [Priority Roadmap](#priority-roadmap)
4. [Implementation Guidelines](#implementation-guidelines)

---

## Library Stack Review

### Executive Summary

A comprehensive review was conducted on 2025-11-14 with consultations from Gemini AI and Codex AI. The current PyTorch-based stack is **solid and appropriate** for mechanistic interpretability and backdoor detection, with opportunities for enhancement in three key areas:

1. **Leverage established backdoor detection frameworks** (Adversarial Robustness Toolbox)
2. **Prepare for larger model scales** (PyTorch-based probes for 70B models)
3. **Improve experiment infrastructure** (config management, logging, testing)

### Current Stack Assessment

#### ✅ **Excellent Choices - Keep As Is**

**transformer-lens (1.9+)** - Mechanistic Interpretability
- **Verdict:** Gold standard, purpose-built for our use case
- **Strengths:**
  - Origin from Anthropic research (same foundation as our work)
  - Best-in-class for activation extraction and causal interventions
  - Extensive hooking capabilities for transformer circuits
- **AI Consensus:** Both Gemini and Codex strongly recommend keeping it
- **Alternatives Considered:**
  - PyTorch Captum (more general, less specialized)
  - circuitsvis + SAE lens (for sparse autoencoder work)
  - TransformerLens 2.0 (monitor for 70B model memory improvements)

**PyTorch 2.1+ + HuggingFace transformers** - Deep Learning Foundation
- **Verdict:** Solid foundation, industry standard
- **Strengths:**
  - Mature ecosystem with excellent model support
  - Unified interface via our `ModelInterface` abstraction
  - Supports both HuggingFace and TransformerLens models
- **No changes needed**

**sklearn.LogisticRegression** - Linear Probe Training
- **Verdict:** Works well, proven by 93.2% AUROC on Qwen 2.5 7B
- **Strengths:**
  - Fast, simple, widely used in research
  - Low overhead for small-to-medium models (7B-13B)
- **Limitation:** Activation dumps for 70B models may exceed host RAM
- **Recommendation:** Add PyTorch-based probe option for large-scale work (see Priority 2)

#### 🎯 **High Priority Additions**

**1. Adversarial Robustness Toolbox (ART)** - Backdoor Detection Framework

**Why:** Standardize detection with established framework, benchmark against known attacks

**Background:**
- IBM's comprehensive library for ML security
- Includes backdoor attack implementations AND defenses
- Supports PyTorch, TensorFlow, JAX
- Well-maintained and documented

**Gemini's Recommendation:**
> "You should evaluate ART as it is a mature, well-supported framework that could standardize your backdoor detection and defense evaluation."

**Codex's Note:**
> "Very little off-the-shelf backdoor detection for LLMs. Look at `backdoorbench` (CV-focused but has NLP recipes), `TrojanZoo`, and `Neural Cleanse`-style ports."

**Integration Approach:**
```python
# Add to pyproject.toml dependencies
"adversarial-robustness-toolbox>=1.15.0"

# Example usage
from art.defenses.detector.poison import ActivationDefense
from art.attacks.poisoning import BackdoorAttack

# Benchmark our probe detector against ART's methods
art_detector = ActivationDefense(classifier, x_train, y_train)
our_detector = ProbeDetector(model, config)

# Compare detection rates
art_results = art_detector.detect_poison()
our_results = our_detector.scan_for_deception(text)
```

**Estimated Effort:** 2-3 days for initial integration and benchmarking

**2. PyTorch-Based Probe Training** - Scaling for 70B Models

**Why:** Keep activation data on GPU, enable streaming, integrate with distributed training

**Current Limitation (Codex):**
> "sklearn.LogisticRegression is fine when activations fit in host RAM, but for 70B models activation dumps quickly exceed that. PyTorch-based probes let you keep data on GPU, stream batches, and integrate with distributed infra."

**Implementation:**
```python
# New: packages/sleeper_agents/src/sleeper_agents/probes/torch_probe.py

import torch
import torch.nn as nn
import torch.optim as optim

class TorchProbeTrainer:
    """GPU-accelerated probe training for large-scale models."""

    def __init__(self, input_dim: int, device: str = "cuda"):
        self.device = device
        self.probe = nn.Linear(input_dim, 1).to(device)

    def train(self, dataloader, epochs=100, lr=0.001):
        """Stream batches from disk/GPU, avoid host RAM bottleneck."""
        optimizer = optim.Adam(self.probe.parameters(), lr=lr, weight_decay=0.01)
        criterion = nn.BCEWithLogitsLoss()

        for epoch in range(epochs):
            for batch_acts, batch_labels in dataloader:
                batch_acts = batch_acts.to(self.device)
                batch_labels = batch_labels.to(self.device)

                optimizer.zero_grad()
                logits = self.probe(batch_acts).squeeze()
                loss = criterion(logits, batch_labels)
                loss.backward()
                optimizer.step()

    def predict(self, activations):
        """GPU inference."""
        with torch.no_grad():
            return torch.sigmoid(self.probe(activations.to(self.device)))
```

**Integration Strategy:**
- Keep sklearn as default for <34B models
- Auto-switch to PyTorch probe for ≥34B models or when `--use-torch-probe` flag set
- Maintain same API interface for seamless switching

**Estimated Effort:** 1-2 days

**3. Experiment Infrastructure** - Config Management & Logging

**Why:** Reproducible experiments, better tracking, cleaner architecture

**Codex's Suggestions:**
1. Config-driven experiment runners (Hydra/Pydantic)
2. Structured logging (wandb/mlflow)
3. Modular architecture (separate probe training, intervention, evaluation)
4. Unit tests (hook registration, tensor alignment, causal metrics)

**Proposed Stack:**
```python
# Add to pyproject.toml
"hydra-core>=1.3.0"      # Config management
"wandb>=0.16.0"          # Experiment tracking
"pydantic>=2.0.0"        # Already included, expand usage
```

**Example Config Structure:**
```yaml
# configs/experiment/baseline_detection.yaml
model:
  name: "Qwen/Qwen2.5-7B-Instruct"
  device: "cuda"
  dtype: "float16"

probe:
  backend: "sklearn"  # or "torch"
  layers: [3, 5, 7, 9]
  regularization: 100.0
  penalty: "l2"

evaluation:
  test_suites:
    - basic_detection
    - layer_probing
    - code_vulnerability
  samples_per_test: 100

logging:
  wandb:
    project: "sleeper-detection"
    entity: "your-team"
```

**Estimated Effort:** 3-5 days for comprehensive setup

#### 💡 **Consider for Future**

**TransformerLens 2.0** - Better Memory Handling
- **When:** Available in stable release
- **Why:** Improved memory management for 70B models
- **Action:** Monitor repository, test when available

**Modular Intervention Classes** - Architecture Refactor
- **Suggestion from Codex:**
  ```python
  class ActivationExtractor:
      """Centralized activation extraction with caching."""

  class DirectionProjector:
      """Projection-based causal interventions."""

  class PatchExperiment:
      """Activation patching workflows."""
  ```
- **Benefit:** Cleaner API, better testing, reusability
- **Estimated Effort:** 5-7 days for comprehensive refactor

**Additional Libraries Mentioned:**
- `causal-probing` (OpenAI) - Less mature than TransformerLens
- `RemixIt` - Activation steering APIs
- `alps` (Anthropic) - Experimental, not public
- `TrojanZoo` - Trojan attack/defense collection
- `backdoorbench` - CV-focused, some NLP recipes

### Library Review Summary

| Component | Current | Status | Action |
|-----------|---------|--------|--------|
| Mechanistic Interpretability | transformer-lens 1.9+ | ✅ Excellent | Keep, monitor 2.0 |
| Deep Learning Framework | PyTorch 2.1+ + HuggingFace | ✅ Excellent | Keep |
| Linear Probes | sklearn + PyTorch (dual backend) | ✅ Complete | Auto-switching at 34B threshold |
| Backdoor Detection | Custom implementations | ⚠️ Needs Enhancement | Add ART framework |
| Experiment Infrastructure | Basic scripts | ⚠️ Needs Enhancement | Add Hydra + wandb |
| Testing | 34 probe tests + GPU validation | ✅ Good | Expand to other components |

**AI Consultant Agreement:**
- Gemini: "Your choice of libraries and techniques is sound."
- Codex: "Stack is appropriate. Main opportunities: ART integration, PyTorch probes, experiment infra."

---

## Dashboard Integration Status

### Current Progress: 53% Real Data Coverage

**Real Data:** 8/15 components (53%)
**Mock Data:** 7/15 components (47%)

### ✅ Components Using Real Data

1. **Persistence Analysis** - Safety training persistence testing
2. **Chain-of-Thought Analysis** - Deceptive reasoning detection (20 samples)
3. **Honeypot Analysis** - 10 comprehensive categories (30 samples)
4. **Detection Analysis** - ROC curves, confusion matrices
5. **Model Comparison** - Side-by-side behavioral risk assessment
6. **Overview Dashboard** - Threat indicators, actionability framework
7. **Trigger Sensitivity** - Pre/post safety training comparison
8. **Internal State Monitor** - Attention patterns, activation anomalies (NEW: 2025-10-29)

### ⚠️ Components Using Mock Data

**Critical (High Value):**
9. **Red Team Results** - Automated adversarial testing (lower priority - honeypots provide similar coverage)
10. **Detection Consensus** - Ensemble detection methods

**Important (Medium Value):**
11. **Risk Mitigation Matrix** - Strategy effectiveness mapping

**Supporting (Lower Priority):**
12. **Persona Profile** - Behavioral analysis
13. **Risk Profiles** - Multi-dimensional risk assessment
14. **Tested Territory** - Prompt coverage tracking
15. **Scaling Analysis** - Model size correlation

### Database Schema Status

**Implemented Tables:**
- ✅ `evaluation_results` - Basic detection metrics
- ✅ `persistence_results` - Backdoor persistence rates
- ✅ `chain_of_thought_analysis` - Deceptive reasoning
- ✅ `honeypot_responses` - 10 honeypot categories
- ✅ `trigger_sensitivity` - Trigger variation testing
- ✅ `internal_state_analysis` - Attention patterns and anomalies

**Missing Tables:**
- ❌ `red_team_results` - Adversarial prompt discovery
- ❌ `detection_ensemble` - Multi-method consensus
- ❌ `intervention_results` - Causal intervention outcomes
- ❌ `risk_mitigation` - Mitigation effectiveness
- ❌ `persona_analysis` - Behavioral profiles
- ❌ `tested_coverage` - Prompt space coverage

---

## Priority Roadmap

### Phase 1: Library Enhancements (2-3 weeks)

**Priority 1A: Adversarial Robustness Toolbox Integration** 🎯
- **Effort:** 2-3 days
- **Impact:** HIGH - Benchmark against established attacks/defenses
- **Tasks:**
  1. Add ART to dependencies
  2. Create `packages/sleeper_agents/src/sleeper_agents/detection/art_integration.py`
  3. Implement comparison suite between ART methods and our probe detectors
  4. Document benchmarking results
  5. Add unit tests

**Priority 1B: PyTorch Probe Trainer** ✅ **COMPLETE (2025-11-14)**
- **Effort:** 2 days (actual)
- **Impact:** MEDIUM - Enables 70B model scaling
- **Status:** Fully implemented, tested, and documented
- **Completed Tasks:**
  1. ✅ Created `probe_config.py` - Unified configuration for both backends
  2. ✅ Created `torch_probe.py` - GPU-accelerated PyTorch probe trainer
  3. ✅ Created `probe_factory.py` - Auto-detection logic (sklearn <34B, PyTorch ≥34B)
  4. ✅ Updated `probe_detector.py` to support both backends
  5. ✅ Added 34 unit tests (100% passing)
  6. ✅ Created `examples/test_pytorch_probe_gpu.py` - End-to-end GPU validation
  7. ✅ Added containerized testing scripts (Windows .bat + Linux .sh)
  8. ✅ Created comprehensive documentation (`docs/pytorch_probes.md`)
  9. ✅ Validated on RTX 4090 with GPU acceleration
- **Key Features:**
  - Mixed precision (FP16) training with torch.amp API
  - Lazy activation loading for memory efficiency
  - Early stopping with validation monitoring
  - Checkpoint save/load functionality
  - Seamless sklearn/PyTorch backend switching
  - GPU/CPU parity validated (AUC difference < 0.05)
- **Performance Metrics:**
  - Validation AUC: ~0.65 on synthetic data
  - Test AUC: ~0.72 on synthetic data
  - GPU training functional with CUDA 12.6.3
  - Containerized testing ready for CI/CD

**Priority 1C: Experiment Infrastructure** 🎯
- **Effort:** 3-5 days
- **Impact:** HIGH - Reproducible research, better tracking
- **Tasks:**
  1. Add Hydra config system to evaluation pipeline
  2. Integrate wandb logging for experiment tracking
  3. Create config templates for common experiments
  4. Refactor intervention ops into reusable classes
  5. Expand unit test coverage (hook registration, tensor alignment)
  6. Add integration tests for causal interventions

**Deliverables:**
- [ ] ART integration module with benchmarking suite
- [x] PyTorch probe trainer with auto-switching logic ✅ (2025-11-14)
- [ ] Hydra config system for experiments
- [ ] wandb integration for tracking
- [ ] Expanded test suite (target: 80% coverage)

### Phase 2: Dashboard Completion (2-3 weeks)

**Priority 2A: Detection Consensus** 🎯
- **Effort:** 3-4 days
- **Impact:** HIGH - Multi-method convergent evidence
- **Tasks:**
  1. Create `detection_ensemble` database table
  2. Implement ensemble detection in `run_full_evaluation.py`
  3. Run multiple detection methods: probes, attention analysis, CoT, honeypots
  4. Calculate consensus scores and confidence intervals
  5. Update `detection_consensus.py` component to fetch real data
  6. Add ingestion function

**Priority 2B: Red Team Integration**
- **Effort:** 4-5 days
- **Impact:** MEDIUM - Discover unknown triggers
- **Tasks:**
  1. Create `red_team_results` database table
  2. Implement adversarial prompt generation (can leverage ART)
  3. Add red team evaluation to pipeline
  4. Update `red_team_results.py` component
  5. Add ingestion function
  6. **Note:** Lower priority since honeypots provide similar coverage

**Priority 2C: Risk Mitigation Matrix**
- **Effort:** 2-3 days
- **Impact:** MEDIUM - Strategy effectiveness
- **Tasks:**
  1. Create `risk_mitigation` database table
  2. Implement mitigation testing (e.g., adversarial training effectiveness)
  3. Store strategy results
  4. Update `risk_mitigation_matrix.py` component
  5. Add ingestion function

**Deliverables:**
- [ ] Detection consensus with ensemble scores
- [ ] Red team automated testing (optional)
- [ ] Risk mitigation effectiveness tracking
- [ ] 73% → 93% real data coverage (11/15 components)

### Phase 3: Supporting Features (1-2 weeks)

**Priority 3A: Persona & Risk Profiles**
- **Effort:** 2-3 days
- **Impact:** LOW-MEDIUM - Behavioral profiling
- **Tasks:**
  1. Create `persona_analysis` database table
  2. Implement behavioral testing in evaluation
  3. Update persona and risk profile components
  4. Add ingestion functions

**Priority 3B: Tested Territory**
- **Effort:** 1-2 days
- **Impact:** LOW - Prompt coverage tracking
- **Tasks:**
  1. Create `tested_coverage` database table
  2. Track prompt space coverage during evaluations
  3. Update `tested_territory.py` component
  4. Add ingestion function

**Priority 3C: Scaling Analysis**
- **Effort:** 3-4 days
- **Impact:** LOW - Requires multi-size testing
- **Tasks:**
  1. Run evaluations on multiple model sizes (7B, 13B, 34B, 70B)
  2. Store size correlation data
  3. Update `scaling_analysis.py` component
  4. **Note:** Requires significant compute resources

**Deliverables:**
- [ ] Persona profiles from real behavioral tests
- [ ] Tested territory coverage tracking
- [ ] Scaling analysis (optional, compute-intensive)
- [ ] 93% → 100% real data coverage (15/15 components)

### Phase 4: Polish & Documentation (1 week)

**Priority 4A: Export Validation**
- **Effort:** 2-3 days
- **Tasks:**
  1. Audit all export functions
  2. Ensure all use real data with mock fallback
  3. Test PDF generation with real evaluation data
  4. Add export quality checks

**Priority 4B: Comprehensive Testing**
- **Effort:** 2-3 days
- **Tasks:**
  1. Expand unit test coverage to 90%+
  2. Add integration tests for full evaluation pipeline
  3. Add end-to-end tests (train → evaluate → dashboard)
  4. Performance benchmarks

**Priority 4C: Documentation**
- **Effort:** 2-3 days
- **Tasks:**
  1. Update README with new library integrations
  2. Create architecture documentation
  3. Add example notebooks for ART integration
  4. User guide for experiment configuration
  5. API reference documentation

**Deliverables:**
- [ ] Validated export system with real data
- [ ] 90%+ test coverage
- [ ] Comprehensive documentation
- [ ] Example notebooks and tutorials

---

## Implementation Guidelines

### Established Pattern (Reference)

All new integrations should follow this proven pattern:

**1. Build/Evaluation Integration**
```python
# In run_full_evaluation.py or safety_trainer.py
def _run_new_detection_method():
    # Run detection
    results = detector.run_detection(model, test_samples)

    # Save to JSON
    results_path = save_path / "detection_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Ingest to database
    from packages.sleeper_agents.database.ingestion import ingest_detection_results
    ingest_detection_results(
        json_path=str(results_path),
        job_id=job_id,
        model_name=model_name
    )
```

**2. Database Schema**
```python
# In packages/sleeper_agents/database/schema.py
def ensure_detection_table_exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detection_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            model_name TEXT NOT NULL,
            detection_type TEXT,
            confidence REAL,
            metadata_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
```

**3. Dashboard Component**
```python
# In dashboard/components/new_component.py
def render_new_component(data_loader, cache_manager, api_client):
    # Clear cache for fresh data
    if hasattr(st, "cache_data"):
        st.cache_data.clear()

    # Fetch from database
    data = _fetch_real_data(data_loader, model_name)

    # Fall back to mock if no data
    if not data:
        st.info("No real data available. Showing mock data for demonstration.")
        data = _fetch_mock_data(model_name)

    # Render visualization
    _render_visualization(data)
```

**4. Ingestion Function**
```python
# In packages/sleeper_agents/database/ingestion.py
def ingest_detection_results(json_path: str, job_id: str, model_name: str) -> bool:
    """Ingest detection results from JSON to database."""
    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        db_path = get_evaluation_db_path()
        ensure_detection_table_exists(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO detection_results (job_id, model_name, detection_type, confidence, metadata_json)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, model_name, data["type"], data["confidence"], json.dumps(data["metadata"])))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return False
```

### Testing Requirements

All new code must include:

**Unit Tests:**
```python
# tests/test_new_feature.py
import pytest

def test_detection_method():
    """Test core detection logic."""
    detector = NewDetector(model, config)
    results = detector.detect(sample_text)
    assert results["confidence"] > 0.0
    assert results["detected"] in [True, False]

def test_database_ingestion():
    """Test data ingestion."""
    success = ingest_detection_results(json_path, job_id, model_name)
    assert success is True

    # Verify data in database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM detection_results WHERE job_id = ?", (job_id,))
    result = cursor.fetchone()
    assert result is not None
```

**Integration Tests:**
```python
def test_end_to_end_pipeline():
    """Test full evaluation → database → dashboard flow."""
    # Run evaluation
    evaluator.run_evaluation(model_name)

    # Check database populated
    data = data_loader.fetch_detection_data(model_name)
    assert len(data) > 0

    # Check dashboard can render
    with patch("streamlit.write") as mock_write:
        render_component(data_loader, cache_manager, api_client)
        assert mock_write.called
```

### Code Quality Standards

**1. Type Hints:**
```python
from typing import Dict, List, Optional, Tuple

def train_probe(
    feature_name: str,
    positive_samples: np.ndarray,
    negative_samples: np.ndarray,
    layer: int,
    description: str = ""
) -> Probe:
    ...
```

**2. Docstrings:**
```python
def scan_for_deception(self, text: str, return_all_scores: bool = False) -> Dict[str, Any]:
    """High-level scan for deceptive patterns.

    Args:
        text: Input text to analyze
        return_all_scores: Whether to return all probe scores

    Returns:
        Scan results with deception assessment containing:
        - is_deceptive (bool): Overall assessment
        - confidence (float): Detection confidence [0, 1]
        - triggered_probes (list): List of probes that detected deception
        - layer_scores (dict): Scores by layer
        - ensemble_score (float): Aggregated score across layers
    """
```

**3. Logging:**
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Training probe for {feature_name} at layer {layer}")
logger.debug(f"  Samples: {len(positive_samples)} positive, {len(negative_samples)} negative")
logger.warning(f"Low sample count: {total_samples} < minimum {min_samples}")
logger.error(f"Probe training failed: {e}")
```

**4. Error Handling:**
```python
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}")
    # Graceful degradation
    return fallback_value
finally:
    cleanup()
```

---

## Progress Tracking

### Milestones

- [x] **Foundation (20% real data)** - Persistence analysis integration
- [x] **Core Detection (40% real data)** - CoT + Honeypots + Detection Analysis
- [x] **Majority (53% real data)** - Internal State Monitor (2025-10-29)
- [x] **PyTorch Probes Complete (2025-11-14)** - Dual backend with GPU acceleration
- [ ] **Library Enhancements Complete** - ART + Experiment infra (PyTorch probes ✅)
- [ ] **Critical Components (73% real data)** - Detection consensus + Red team
- [ ] **Supporting Features (93% real data)** - Persona + Risk + Territory
- [ ] **Full Coverage (100% real data)** - All 15 components using real data

### Success Metrics

| Session | Date | Real Data % | Components Complete | Key Achievement |
|---------|------|-------------|---------------------|-----------------|
| Initial | Pre-2025 | 6.7% | 1/15 | Persistence analysis |
| Session 1 | 2025-10-19 | 20% | 3/15 | CoT + Honeypots |
| Session 2 | 2025-10-19 | 40% | 6/15 | Data aggregation layer |
| Session 3 | 2025-10-29 | 47% | 7/15 | Trigger sensitivity |
| Session 4 | 2025-10-29 | 53% | 8/15 | Internal state monitor |
| Session 5 | 2025-11-14 | 53% | 8/15 | **PyTorch probes (library enhancement)** |
| **Target** | TBD | **100%** | **15/15** | **Full integration** |

**Total Progress:** +46.3 percentage points (6.7% → 53%)
**Library Progress:** PyTorch probe trainer complete (1/3 Phase 1 priorities)

---

## Estimated Timeline

**Conservative Estimate:** 4-6 weeks remaining (was 6-8 weeks total)

- **Phase 1 (Library):** ~~2-3 weeks~~ → **1-2 weeks remaining** (PyTorch probes complete)
- **Phase 2 (Dashboard Critical):** 2-3 weeks
- **Phase 3 (Dashboard Supporting):** 1-2 weeks
- **Phase 4 (Polish):** 1 week

**Aggressive Estimate:** 3-4 weeks remaining (if working full-time)

---

## Key Technical Decisions

### 1. Keep PyTorch Stack
**Rationale:** transformer-lens is gold standard, proven with 93.2% AUROC results
**AI Consensus:** Both Gemini and Codex strongly recommend

### 2. Add ART Framework
**Rationale:** Standardize detection, benchmark against known attacks
**Impact:** HIGH - Validates our custom implementations

### 3. Dual Probe Backend (sklearn + PyTorch)
**Rationale:** sklearn for speed (<34B), PyTorch for scale (≥34B)
**Implementation:** Auto-detection with manual override

### 4. Hydra + wandb Infrastructure
**Rationale:** Reproducible research, professional experiment tracking
**Benefit:** Cleaner architecture, better collaboration

### 5. Detection Consensus Priority
**Rationale:** Multi-method convergence is critical for confidence
**Impact:** HIGH - Addresses false positive concerns

---

## Risk Assessment

### Library Integration Risks

**Low Risk:**
- ART integration (well-documented library)
- PyTorch probe trainer (straightforward implementation)

**Medium Risk:**
- Hydra config system (requires architectural changes)
- wandb integration (API keys, team setup)

**Mitigation:**
- Start with ART and PyTorch probes (quick wins)
- Pilot Hydra on single experiment before full migration
- Document all breaking changes carefully

### Dashboard Integration Risks

**Low Risk:**
- Detection consensus (follows established pattern)
- Persona/risk profiles (straightforward database work)

**Medium Risk:**
- Red team integration (requires prompt generation strategy)
- Scaling analysis (compute-intensive, may need cloud resources)

**Mitigation:**
- Make red team optional (honeypots provide coverage)
- Start scaling analysis with 2-3 model sizes, expand later

---

## Dependencies & Prerequisites

### Software Dependencies (New)
```toml
# Add to pyproject.toml [project.dependencies]
"adversarial-robustness-toolbox>=1.15.0"  # Backdoor detection
"hydra-core>=1.3.0"                        # Config management
"wandb>=0.16.0"                            # Experiment tracking
```

### Hardware Requirements
- **7B-13B models:** 16GB VRAM (RTX 4090, A4000)
- **34B models:** 36GB VRAM (A6000, RTX 6000 Ada)
- **70B models:** 70GB VRAM (A100 80GB)
- **Scaling analysis:** Multi-GPU setup recommended

### Compute Budget
- **Phase 1 (Library):** Minimal (development only)
- **Phase 2 (Dashboard):** Medium (evaluation runs for testing)
- **Phase 3 (Supporting):** High (if doing full scaling analysis)

---

## References

### Library Review Sources
- **Gemini AI Consultation:** 2025-11-14 (80.27s execution time)
- **Codex AI Consultation:** 2025-11-14 (explain mode)
- **Key Recommendations:**
  - transformer-lens: Gold standard (both AIs)
  - ART: Mature backdoor framework (Gemini)
  - PyTorch probes: Scale to 70B (Codex)
  - Experiment infra: Hydra + wandb (Codex)

### Research Papers
- Anthropic (2024): "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"
- Foundation for mechanistic interpretability approach

### External Resources
- [TransformerLens Documentation](https://transformerlensorg.github.io/TransformerLens/)
- [Adversarial Robustness Toolbox](https://github.com/Trusted-AI/adversarial-robustness-toolbox)
- [Hydra Documentation](https://hydra.cc/)
- [Weights & Biases Documentation](https://docs.wandb.ai/)

---

## Conclusion

The Sleeper Agent Detection Framework is **well-architected** with a **solid library foundation**. The current 53% real data coverage demonstrates that the integration pattern works, and the path to 100% is clear.

**Key Strengths:**
1. Excellent library choices (transformer-lens, PyTorch, HuggingFace)
2. Proven integration pattern (8 components successfully using real data)
3. Strong foundation: evaluation pipeline, database schema, ingestion functions

**Key Opportunities:**
1. **ART integration** - Benchmark and validate detection methods
2. **PyTorch probes** - Scale to 70B models with GPU acceleration
3. **Experiment infrastructure** - Hydra configs + wandb tracking
4. **Complete remaining 7 dashboard components** - Follow established pattern

**Next Steps:**
1. Prioritize ART integration (2-3 days, high impact)
2. Add PyTorch probe trainer (1-2 days, enables scaling)
3. Begin detection consensus implementation (highest value remaining component)
4. Document progress and iterate

With focused effort, the framework can reach 100% real data coverage and production-ready status within 6-8 weeks.

---

**Last Updated:** 2025-11-14
**Maintainer:** @AndrewAltimit
**Status:** Active Development - PyTorch Probes Complete, 53% Dashboard Integration

## Recent Updates (2025-11-14)

### PyTorch Probe Trainer - COMPLETE ✅

Fully implemented GPU-accelerated probe training for large-scale models (≥34B parameters):

**Implementation Details:**
- **Files Created:**
  - `src/sleeper_agents/probes/probe_config.py` - Unified configuration system
  - `src/sleeper_agents/probes/torch_probe.py` - PyTorch-based probe trainer (494 lines)
  - `src/sleeper_agents/probes/probe_factory.py` - Auto-switching factory pattern
  - `examples/test_pytorch_probe_gpu.py` - End-to-end GPU validation script
  - `scripts/testing/test_pytorch_probe.bat` - Windows containerized testing
  - `scripts/testing/test_pytorch_probe.sh` - Linux containerized testing
  - `scripts/testing/README.md` - Complete testing documentation
  - `docs/pytorch_probes.md` - Comprehensive user guide (480 lines)

- **Testing Coverage:**
  - 34 unit tests covering all core functionality
  - End-to-end GPU validation on RTX 4090
  - Containerized testing with CUDA 12.6.3
  - All tests passing with realistic thresholds

- **Key Features:**
  - Mixed precision (FP16) training with torch.amp API (PyTorch 2.6+ compatible)
  - Lazy activation loading via Dataset/DataLoader for memory efficiency
  - Early stopping with validation monitoring
  - Checkpoint save/load functionality
  - Seamless backend switching at 34B parameter threshold
  - GPU/CPU parity validated (AUC difference < 0.05)

- **Performance:**
  - Validation AUC: ~0.65 on synthetic linearly separable data
  - Test AUC: ~0.72 on synthetic data
  - GPU training functional with CUDA 12.6.3
  - Batch size optimization (256 for small datasets)
  - Learning rate: 0.01 for fast convergence

- **Docker Integration:**
  - Added `test-pytorch-probe` service to `docker-compose.gpu.yml`
  - Windows/Linux helper scripts following existing patterns
  - Auto GPU detection with CPU fallback
  - Interactive shell support for debugging

**Next Priority:** ART integration for backdoor detection benchmarking
