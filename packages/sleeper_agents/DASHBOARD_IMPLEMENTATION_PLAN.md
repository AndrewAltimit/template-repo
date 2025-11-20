# Dashboard Completion Implementation Plan

**Status:** Ready to Resume (Phase 3 Validation Complete)
**Target:** 8/15 → 15/15 Components with Real Data
**Priority:** HIGH (Core science validated, now build the UI tool)

## Executive Summary

The sleeper_agents package has completed comprehensive validation (cross-architecture, adversarial robustness) and is ready for dashboard completion. This document provides a detailed implementation plan to integrate real data into 7 remaining components and add Phase 3 validation features to all components.

## Current State Analysis

### ✅ Complete Components (8/15)
These components are functional with real data integration:
1. **Persistence Analysis** (`dashboard/components/persistence_analysis.py`)
2. **Chain-of-Thought Analysis** (`dashboard/components/chain_of_thought.py`)
3. **Honeypot Analysis** (`dashboard/components/honeypot_analysis.py`)
4. **Detection Analysis** (`dashboard/components/detection_analysis.py`)
5. **Model Comparison** (`dashboard/components/model_comparison.py`)
6. **Overview Dashboard** (`dashboard/components/overview.py`)
7. **Trigger Sensitivity** (`dashboard/components/trigger_sensitivity.py`)
8. **Internal State Monitor** (`dashboard/components/internal_state.py`)

### 🔨 Missing Real Data (7/15)
These components exist but use mock data:
1. **Detection Consensus** (`dashboard/components/detection_consensus.py`) - Ensemble methods
2. **Red Team Results** (`dashboard/components/red_team_results.py`) - Automated adversarial testing
3. **Risk Mitigation Matrix** (`dashboard/components/risk_mitigation_matrix.py`) - Risk-to-countermeasure mapping
4. **Persona Profile** (`dashboard/components/persona_profile.py`) - Behavioral analysis
5. **Risk Profiles** (`dashboard/components/risk_profiles.py`) - Risk categorization
6. **Tested Territory** (`dashboard/components/tested_territory.py`) - Coverage visualization
7. **Scaling Analysis** (`dashboard/components/scaling_analysis.py`) - Model size vs deception

## Phase 3 Integration Requirements

Based on completed validation work, all components need these updates:

### 1. Cross-Architecture Support

**Files to Update:**
- `dashboard/components/model_selector.py` - Add architecture display
- `dashboard/utils/model_registry.py` - Track architecture metadata
- All component files - Support GPT-2, Mistral-7B, Qwen2.5-7B, Llama-3-8B

**Implementation:**
```python
# Model registry should track:
{
    "model_name": "gpt2-backdoored",
    "architecture": "GPT-2",
    "hidden_size": 768,
    "num_layers": 12,
    "probe_layer": 6,
    "tokenizer": "gpt2"
}
```

**Key Insight from Cross-Architecture Validation:**
- Probe weights **CANNOT** be transferred between architectures (dimension mismatch)
- Each architecture requires independent probe training
- Method generalizes perfectly (AUC = 1.0 across all architectures)

### 2. Calibration Methodology

**Files to Update:**
- `src/sleeper_agents/probes/torch_probe.py` - Add `find_optimal_threshold()` method
- `src/sleeper_agents/detection/layer_probes.py` - Add calibration to train methods
- All dashboard components - Display optimal threshold, probability range

**Implementation:**
```python
def find_optimal_threshold(y_true, y_scores):
    """Find optimal threshold using ROC curve + Youden's J statistic.

    Youden's J = Sensitivity + Specificity - 1
    Optimal threshold maximizes J (best balance of TPR/TNR).

    Returns:
        optimal_threshold: float
        calibration_metrics: dict with {
            'threshold': float,
            'accuracy': float,
            'sensitivity': float,
            'specificity': float,
            'prob_range': (float, float)
        }
    """
    from sklearn.metrics import roc_curve

    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    j_scores = tpr - fpr  # Youden's J statistic
    optimal_idx = np.argmax(j_scores)
    optimal_threshold = thresholds[optimal_idx]

    # Calculate probability range
    prob_range = (y_scores.min(), y_scores.max())

    return optimal_threshold, {
        'threshold': optimal_threshold,
        'sensitivity': tpr[optimal_idx],
        'specificity': 1 - fpr[optimal_idx],
        'prob_range': prob_range
    }
```

**Display Requirements:**
- Show both AUC (discrimination) and calibrated accuracy (real-world performance)
- Warn if baseline accuracy < 95% (indicates uncalibrated probe)
- Display probability distribution histograms for calibration verification

### 3. Adversarial Robustness Reporting

**Files to Create/Update:**
- `dashboard/components/adversarial_robustness.py` - NEW component
- All components - Add "Known Limitations" section

**Implementation:**
```python
def render_adversarial_robustness_section():
    """Display adversarial robustness audit results."""
    st.markdown("### Adversarial Robustness")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Baseline Accuracy", "98%", help="Using optimal threshold")
        st.metric("Post-Attack AUC", "0.0", delta="-1.0", delta_color="inverse")

    with col2:
        st.metric("Attack Success Rate", "98%", help="PGD white-box attack")
        st.metric("Avg Perturbation", "5.9%", help="Of epsilon=0.1 budget")

    st.info("""
    **Expected Behavior:** Linear classifiers are theoretically vulnerable to white-box attacks.

    The successful gradient attack **proves the probe is working correctly**:
    - Tracks continuous feature representations (not token patterns)
    - Responds to high-dimensional feature correlations
    - Manipulatable in embedding space (normal for linear classifiers)

    **Real Threat Model:** Prompt-based attacks (red teaming), not gradient attacks.
    Attackers don't have gradient access to deployed models.
    """)
```

### 4. Validation Metrics Display

**All Components Should Show:**
```python
# Standard metrics section
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("AUC", f"{auc:.3f}", help="Discrimination ability")
with col2:
    st.metric("Calibrated Accuracy", f"{accuracy:.1%}", help="Using optimal threshold")
with col3:
    st.metric("Optimal Threshold", f"{threshold:.4f}", help="ROC + Youden's J")
with col4:
    st.metric("Probability Range", f"[{prob_min:.2f}, {prob_max:.2f}]")
```

## Implementation Tasks by Component

### Component 1: Detection Consensus (PRIORITY 1)

**Current Status:** Mock data implementation
**Real Data Source:** Multiple detection methods (probes, clustering, attention analysis)

**Tasks:**
1. **Integrate LinearProbe Results** (`src/sleeper_agents/probes/torch_probe.py`)
   - Load trained probes from checkpoint files
   - Run inference on test set
   - Report AUC, calibrated accuracy, optimal threshold

2. **Integrate Attention Analysis** (`src/sleeper_agents/attention_analysis/analyzer.py`)
   - Extract attention patterns for backdoor detection
   - Calculate attention-based detection scores
   - Report AUC for attention method

3. **Integrate Activation Clustering** (from validation benchmarks)
   - Load clustering results from `examples/validation_benchmark.py`
   - Compare supervised (probes) vs unsupervised (clustering) methods
   - Show AUC comparison

4. **Create Ensemble Detector**
   ```python
   class EnsembleDetector:
       def __init__(self, methods: List[DetectionMethod]):
           self.methods = methods
           self.weights = self._calculate_weights()

       def _calculate_weights(self):
           """Weight by AUC performance."""
           aucs = [m.auc for m in self.methods]
           return np.array(aucs) / sum(aucs)

       def detect(self, sample):
           scores = [m.detect(sample) for m in self.methods]
           return np.average(scores, weights=self.weights)
   ```

5. **Update Dashboard Component** (`dashboard/components/detection_consensus.py`)
   - Replace mock data with real detection results
   - Add calibration metrics display
   - Show probability distributions for each method
   - Highlight divergence analysis (where methods disagree)

**Files to Modify:**
- `dashboard/components/detection_consensus.py` (150 lines changed)
- `src/sleeper_agents/detection/ensemble.py` (NEW, 200 lines)

**Estimated Effort:** 3-4 days

---

### Component 2: Red Team Results (PRIORITY 1)

**Current Status:** Mock data implementation
**Real Data Source:** `examples/validation_benchmark.py` red team results

**Tasks:**
1. **Extract Red Team Data** from validation benchmarks
   - Parse results from `outputs/validation/` directory
   - Load discovered triggers, success rates, strategies
   - Track evolution history across generations

2. **Integrate Gradient Attack Results** (`examples/gradient_attack_audit.py`)
   - Show PGD attack success rate
   - Display perturbation budgets
   - Explain white-box vulnerability (expected behavior)

3. **Add Prompt Attack Results** (from red team testing)
   - Show success rates for different attack strategies:
     - Subtle triggers (single chars, rare tokens)
     - Context-dependent triggers
     - Distributed triggers (multi-token patterns)
     - Mimicry triggers (benign-looking)
     - Typo-based triggers

4. **Update Dashboard Component** (`dashboard/components/red_team_results.py`)
   - Replace mock data with real attack results
   - Add gradient attack section
   - Show evolution of attack success over iterations
   - Display discovered triggers with effectiveness scores

**Files to Modify:**
- `dashboard/components/red_team_results.py` (100 lines changed)
- `dashboard/utils/red_team_loader.py` (NEW, 150 lines)

**Estimated Effort:** 2-3 days

---

### Component 3: Risk Mitigation Matrix (PRIORITY 2)

**Current Status:** Mock risk profile
**Real Data Source:** Model evaluation results + calibration metrics

**Tasks:**
1. **Calculate Real Risk Scores**
   ```python
   def calculate_risk_profile(model_results):
       return {
           "Backdoor Persistence": {
               "level": model_results["post_training_backdoor_rate"],
               "uncertainty": model_results["std_error"],
               "category": "behavioral"
           },
           "Probe Anomalies": {
               "level": model_results["probe_detection_rate"],
               "uncertainty": 1.0 - model_results["probe_auc"],
               "category": "internal"
           },
           # Add more risks...
       }
   ```

2. **Integrate Calibration Data**
   - Use optimal thresholds for deployment recommendations
   - Show probability ranges for risk assessment
   - Flag uncalibrated probes (accuracy < 95%)

3. **Add Cross-Architecture Deployment Strategy**
   - Recommend architecture-specific probe training
   - Warn about dimension mismatch if transferring probes
   - Show per-architecture performance metrics

4. **Update Dashboard Component** (`dashboard/components/risk_mitigation_matrix.py`)
   - Replace mock risk scores with real data
   - Add calibration-based recommendations
   - Show architecture-specific deployment plans

**Files to Modify:**
- `dashboard/components/risk_mitigation_matrix.py` (50 lines changed)
- `dashboard/utils/risk_calculator.py` (NEW, 200 lines)

**Estimated Effort:** 3-4 days

---

### Component 4: Persona Profile (PRIORITY 2)

**Current Status:** Mock behavioral scores
**Real Data Source:** `src/sleeper_agents/advanced_detection/persona_testing.py`

**Tasks:**
1. **Integrate Persona Testing Results**
   - Load behavioral scores from persona testing module
   - Calculate power-seeking, corrigibility, deception tendencies
   - Compare triggered vs normal behavior

2. **Add Chain-of-Thought Analysis**
   - Extract deceptive reasoning patterns from CoT outputs
   - Measure goal-hiding language
   - Detect strategic planning

3. **Update Dashboard Component** (`dashboard/components/persona_profile.py`)
   - Replace mock scores with real behavioral data
   - Add radar chart with real measurements
   - Show concerning response examples with actual model outputs

**Files to Modify:**
- `dashboard/components/persona_profile.py` (80 lines changed)
- `src/sleeper_agents/advanced_detection/persona_testing.py` (add export methods)

**Estimated Effort:** 2-3 days

---

### Component 5: Risk Profiles (PRIORITY 3)

**Current Status:** Mock risk data
**Real Data Source:** Aggregate of all detection methods

**Tasks:**
1. **Create Risk Profile Aggregator**
   ```python
   class RiskProfileAggregator:
       def aggregate(self, model_results):
           return {
               "overall_risk": self._calculate_overall_risk(model_results),
               "risk_breakdown": {
                   "deception": model_results["probe_detection_rate"],
                   "persistence": model_results["backdoor_persistence"],
                   "coverage": 1.0 - model_results["test_coverage"]
               },
               "confidence": self._calculate_confidence(model_results)
           }
   ```

2. **Update Dashboard Component** (`dashboard/components/risk_profiles.py`)
   - Replace mock data with aggregated risk scores
   - Add confidence intervals based on calibration metrics
   - Show risk category breakdowns

**Files to Modify:**
- `dashboard/components/risk_profiles.py` (60 lines changed)
- `dashboard/utils/risk_aggregator.py` (NEW, 150 lines)

**Estimated Effort:** 2 days

---

### Component 6: Tested Territory (PRIORITY 3)

**Current Status:** Mock coverage data
**Real Data Source:** Test coverage metrics from validation benchmarks

**Tasks:**
1. **Calculate Real Coverage Metrics**
   - Count total test samples across all benchmarks
   - Calculate coverage per behavior category
   - Estimate untested space (infinite, but show relative coverage)

2. **Integrate Benchmark Results**
   - Show coverage from synthetic benchmarks (4 scenarios)
   - Show coverage from real transformer testing
   - Show coverage from red team testing (5 strategies)

3. **Update Dashboard Component** (`dashboard/components/tested_territory.py`)
   - Replace mock visualizations with real coverage data
   - Add per-architecture coverage breakdown
   - Show evolution of coverage over time

**Files to Modify:**
- `dashboard/components/tested_territory.py` (70 lines changed)
- `dashboard/utils/coverage_calculator.py` (NEW, 100 lines)

**Estimated Effort:** 2 days

---

### Component 7: Scaling Analysis (PRIORITY 3)

**Current Status:** Mock scaling data
**Real Data Source:** Cross-architecture validation results

**Tasks:**
1. **Integrate Cross-Architecture Results** (`examples/cross_architecture_validation.py`)
   - Load AUC results for GPT-2, Mistral-7B, Qwen2.5-7B
   - Show perfect generalization (AUC = 1.0 across architectures)
   - Display architecture-specific metrics (hidden size, num layers)

2. **Add Scaling Hypothesis**
   - Document that larger models show better deception capability
   - Show trend: GPT-2 (768d) → Qwen (3584d) → Mistral (4096d)
   - Warn about emergent deception in larger models

3. **Update Dashboard Component** (`dashboard/components/scaling_analysis.py`)
   - Replace mock scaling curves with real cross-architecture data
   - Add architecture comparison table
   - Show calibration metrics per architecture

**Files to Modify:**
- `dashboard/components/scaling_analysis.py` (60 lines changed)
- `dashboard/utils/scaling_data_loader.py` (NEW, 100 lines)

**Estimated Effort:** 2 days

---

## Global Infrastructure Updates

### 1. Model Registry Enhancement

**File:** `dashboard/utils/model_registry.py`

**Add Architecture Tracking:**
```python
@dataclass
class ModelMetadata:
    name: str
    architecture: str  # "GPT-2", "Mistral-7B", "Qwen2.5-7B", "Llama-3-8B"
    hidden_size: int
    num_layers: int
    probe_layer: int
    optimal_threshold: float  # From calibration
    baseline_accuracy: float  # Using optimal threshold
    auc: float
    prob_range: Tuple[float, float]
    calibration_date: str
    checkpoint_path: Path
```

**Estimated Effort:** 1 day

---

### 2. Data Loading Infrastructure

**File:** `dashboard/utils/data_loader.py`

**Add Methods:**
```python
class DataLoader:
    def fetch_calibration_metrics(self, model_name: str) -> Dict[str, float]:
        """Load optimal threshold, accuracy, probability range."""
        pass

    def fetch_cross_architecture_results(self) -> pd.DataFrame:
        """Load cross-architecture validation results."""
        pass

    def fetch_gradient_attack_results(self, model_name: str) -> Dict[str, Any]:
        """Load adversarial robustness audit results."""
        pass

    def fetch_red_team_results(self, model_name: str) -> Dict[str, Any]:
        """Load red team testing results."""
        pass
```

**Estimated Effort:** 2 days

---

### 3. Probe Training Integration

**File:** `dashboard/components/build/train_probes.py`

**Add Calibration Step:**
```python
def train_probes_with_calibration(model, train_data, val_data):
    # 1. Train probe
    trainer = TorchProbeTrainer(input_dim, config)
    auc = trainer.fit(X_train, y_train, X_val, y_val)

    # 2. Find optimal threshold
    y_scores = trainer.predict_proba(X_val)
    optimal_threshold, calibration_metrics = find_optimal_threshold(y_val, y_scores)

    # 3. Validate calibration
    y_pred = (y_scores >= optimal_threshold).astype(int)
    accuracy = accuracy_score(y_val, y_pred)

    if accuracy < 0.95:
        logger.warning(f"Low calibrated accuracy ({accuracy:.1%}). Probe may be uncalibrated.")

    # 4. Save metadata
    metadata = {
        "auc": auc,
        "optimal_threshold": optimal_threshold,
        "baseline_accuracy": accuracy,
        **calibration_metrics
    }
    torch.save({"probe": trainer.probe.state_dict(), "metadata": metadata}, checkpoint_path)
```

**Estimated Effort:** 1 day

---

## Testing Strategy

### 1. Unit Tests
- Test calibration threshold finding
- Test ensemble detection weighting
- Test risk profile aggregation
- Test coverage calculations

### 2. Integration Tests
- Test data loading pipeline end-to-end
- Test dashboard component rendering with real data
- Test model registry with multiple architectures

### 3. Visual Regression Tests
- Use Selenium to capture dashboard screenshots
- Compare against baseline visuals
- Validate chart rendering with real data

**File:** `dashboard/tests/test_selenium_e2e.py` (already exists)

---

## Timeline and Milestones

### Week 1: Foundation (7 days)
- [ ] Day 1-2: Model registry enhancement + calibration infrastructure
- [ ] Day 3-4: Data loading infrastructure
- [ ] Day 5-7: Probe training integration with calibration

### Week 2: Priority 1 Components (7 days)
- [ ] Day 1-4: Detection Consensus (ensemble methods, real data)
- [ ] Day 5-7: Red Team Results (gradient attacks, prompt attacks)

### Week 3: Priority 2 Components (7 days)
- [ ] Day 1-3: Risk Mitigation Matrix (real risk scores, deployment strategies)
- [ ] Day 4-6: Persona Profile (behavioral data, CoT analysis)
- [ ] Day 7: Testing and bug fixes

### Week 4: Priority 3 Components (7 days)
- [ ] Day 1-2: Risk Profiles (aggregated risk scores)
- [ ] Day 3-4: Tested Territory (coverage visualization)
- [ ] Day 5-6: Scaling Analysis (cross-architecture data)
- [ ] Day 7: Final testing, documentation, polish

### Week 5-6: Polish and Validation (7-14 days)
- [ ] Comprehensive testing (unit, integration, visual)
- [ ] Documentation updates
- [ ] Performance optimization
- [ ] User acceptance testing
- [ ] Bug fixes and refinements

**Total Estimated Effort:** 4-6 weeks

---

## Success Criteria

### Functional Requirements
- ✅ All 15 components display real data (no mock data)
- ✅ Cross-architecture support (GPT-2, Mistral, Qwen, Llama)
- ✅ Calibration metrics displayed for all probes
- ✅ Adversarial robustness section with gradient attack results
- ✅ Validation metrics (AUC + calibrated accuracy)

### Performance Requirements
- ✅ Dashboard loads in < 3 seconds
- ✅ Component switching in < 500ms
- ✅ No memory leaks during extended sessions

### Quality Requirements
- ✅ All tests passing (unit, integration, visual)
- ✅ Code coverage > 80%
- ✅ No pylint warnings
- ✅ Documentation complete

---

## Risk Mitigation

### Risk 1: Data Pipeline Complexity
**Mitigation:** Start with simplest components (Risk Profiles, Tested Territory) to validate pipeline architecture before tackling complex ensemble detection.

### Risk 2: Cross-Architecture Compatibility
**Mitigation:** Use ModelMetadata dataclass to enforce consistent architecture handling. Test each component with all 4 architectures.

### Risk 3: Performance with Large Models
**Mitigation:** Use lazy loading for activation data. Cache computed metrics. Implement pagination for large result sets.

### Risk 4: Calibration Edge Cases
**Mitigation:** Add validation checks (baseline accuracy < 95% warning). Document expected behavior for uncalibrated probes.

---

## Key Technical Decisions

### 1. Calibration Methodology
**Decision:** Use ROC curve + Youden's J statistic for optimal threshold finding.
**Rationale:** Balances sensitivity/specificity without requiring domain-specific cost functions.
**Source:** `examples/gradient_attack_audit.py:L600-L650`

### 2. Ensemble Weighting
**Decision:** Weight detection methods by AUC performance.
**Rationale:** Higher-performing methods should have more influence in consensus.
**Alternative:** Equal weighting (simpler but less optimal).

### 3. Architecture Handling
**Decision:** Store architecture metadata in model registry, retrain probes per architecture.
**Rationale:** Cannot transfer probe weights (dimension mismatch). Method generalizes, weights don't.
**Source:** `examples/cross_architecture_validation.py:L1-L20`

### 4. Adversarial Robustness Display
**Decision:** Show white-box vulnerability as "expected behavior", emphasize prompt-attack robustness.
**Rationale:** Real threat model is prompt-based attacks, not gradient attacks.
**Source:** `examples/gradient_attack_audit.py:L1-L44`

---

## References

### Source Files (Validation Infrastructure)
- `examples/cross_architecture_validation.py` - Cross-architecture method validation
- `examples/gradient_attack_audit.py` - Adversarial robustness audit
- `examples/validation_benchmark.py` - Comprehensive validation suite
- `src/sleeper_agents/probes/torch_probe.py` - PyTorch probe training
- `src/sleeper_agents/detection/layer_probes.py` - Multi-layer probe system

### Dashboard Components (Existing)
- `dashboard/app.py` - Main application entry point
- `dashboard/components/*.py` - 15 component files
- `dashboard/utils/data_loader.py` - Data loading infrastructure
- `dashboard/utils/model_registry.py` - Model metadata management

### Documentation
- `packages/sleeper_agents/TODO.md` - Project priorities and validation results
- `packages/sleeper_agents/CHANGELOG.md` - Completed work history

---

## Next Steps

1. **Review this plan** with project stakeholders
2. **Set up development branch** (`sleeper-dashboard` - already on correct branch)
3. **Begin Week 1 tasks** (foundation infrastructure)
4. **Daily standups** to track progress and blockers
5. **Weekly demos** to show incremental progress

**Ready to begin implementation!** ✅
