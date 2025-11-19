# Sleeper Agent Detection Framework - Changelog

All notable changes and milestones for this project are documented here.

**Status:** Phase 3 Complete (2025-11-18)

---

## [Unreleased]

### Planned
- Cross-model generalization testing (Phase 4)
- Gradient-based attack validation (Phase 3E, external audit)
- Dashboard completion (53% → 100%)

---

## [Phase 3] - 2025-11-18

### Added
- **Phase 3A: Comprehensive Synthetic Benchmarking**
  - 4 difficulty scenarios (Easy, Medium, Hard, Realistic)
  - Systematic testing of linear probes vs unsupervised clustering
  - File: `examples/benchmark_detectors_comprehensive.py`

- **Phase 3B: Real Transformer Activation Benchmarking**
  - GPT-2 (124M parameters) activation extraction
  - Simple backdoor trigger testing
  - Validation of detection on real model internals (not just synthetic data)
  - File: `examples/phase3b_real_transformer_benchmark.py`

- **Phase 3C: Adversarial Red Team Benchmarking**
  - 5 attack strategies: Subtle, Context-Dependent, Distributed, Mimicry, Typo-Based
  - Comprehensive adversarial robustness testing
  - File: `examples/phase3c_red_team_benchmark.py`

- **Containerized Testing Scripts**
  - Windows: `scripts/testing/test_benchmarks.bat`
  - Linux: `scripts/testing/test_benchmarks.sh`
  - Support for individual phase testing (3a, 3b, 3c) or all phases
  - Quick mode for faster iteration

### Results
- **Linear Probe Detector:** AUC=1.0, 0% attack success (perfect robustness on current benchmarks)
- **ARTActivationDetector:** AUC=0.76, 76.6% attack success (vulnerable to adversarial triggers)
- **Key Finding:** Supervised learning >> Unsupervised clustering for adversarial robustness

### Infrastructure
- Removed IBM ART library from production dependencies
  - Moved to `dev` dependencies for external audit use only
  - Reduced production complexity and maintenance burden

- Removed outdated `INTEGRATION_PLAN.md`
  - IBM ART moved to external audit use only (see `scripts/audit/`)

- Completely rewritten `TODO.md`
  - Based on Gemini 3 architecture review
  - Clear prioritization (A/B/C hierarchy)
  - Realistic timeline estimates
  - Honest assessment of known limitations

- Created comprehensive `CHANGELOG.md` (this file)

---

## [Phase 2] - 2025-11-14

### Added
- **PyTorch Probe Trainer** (GPU-Accelerated)
  - Mixed precision (FP16) training with torch.amp API
  - Lazy activation loading for memory efficiency
  - Early stopping with validation monitoring
  - Checkpoint save/load functionality
  - File: `src/sleeper_agents/probes/torch_probe.py` (494 lines)

- **Dual Backend Architecture**
  - Auto-switching: sklearn for <34B models, PyTorch for ≥34B models
  - Unified configuration: `src/sleeper_agents/probes/probe_config.py`
  - Factory pattern: `src/sleeper_agents/probes/probe_factory.py`

- **Comprehensive Testing**
  - 34 unit tests covering all core functionality
  - End-to-end GPU validation: `examples/test_pytorch_probe_gpu.py`
  - Containerized testing scripts (Windows .bat + Linux .sh)
  - Validated on RTX 4090 with CUDA 12.6.3

- **Documentation**
  - Comprehensive user guide: `docs/pytorch_probes.md` (480 lines)
  - Testing documentation: `scripts/testing/README.md` (Phase 2 section)

### Performance Metrics
- Validation AUC: ~0.65 on synthetic linearly separable data
- Test AUC: ~0.72 on synthetic data
- GPU/CPU parity validated (AUC difference < 0.05)
- Batch size optimization (256 for small datasets)
- Learning rate: 0.01 for fast convergence

---

## [Phase 1] - 2025-10-29

### Added
- **Internal State Monitor** (Dashboard Component)
  - Attention pattern visualization
  - Activation anomaly detection
  - Real data integration (vs mock data)
  - Dashboard coverage: 53% (8/15 components)

- **Trigger Sensitivity Analysis** (Dashboard Component)
  - Pre/post safety training comparison
  - Trigger variation testing
  - Database table: `trigger_sensitivity`

### Infrastructure
- Dashboard real data coverage: 47% → 53%
- Database schema expansions for new components

---

## [Foundation] - Pre-2025-10-29

### Core Detection Methods
- **Linear Probe Detector** (sklearn-based)
  - Logistic regression on transformer activations
  - Trained on labeled examples (clean vs backdoored)
  - Lightweight, fast, proven effective

- **ARTActivationDetector** (Custom Implementation)
  - K-means clustering + PCA for unsupervised anomaly detection
  - Good on synthetic data, vulnerable to adversarial triggers
  - File: `src/sleeper_agents/detection/art_activation_detector.py`

### Dashboard Components (Initial 6/15)
1. Persistence Analysis
2. Chain-of-Thought Analysis
3. Honeypot Analysis
4. Detection Analysis
5. Model Comparison
6. Overview Dashboard

### Infrastructure
- Database schema: `evaluation_results`, `persistence_results`, `chain_of_thought_analysis`, `honeypot_responses`
- Ingestion pipeline for JSON → SQLite
- Streamlit dashboard framework
- Probe training and evaluation pipeline

### Technology Stack
- `transformer-lens 1.9+` - Mechanistic interpretability (Anthropic-backed)
- `PyTorch 2.1+` + `HuggingFace transformers` - Model interface
- `scikit-learn` - Linear probe training
- `FastAPI` + `Streamlit` - API and dashboard

---

## Architecture Decisions

### Validated by AI Consultations
- **2025-11-18: Gemini 3 Assessment**
  - **Verdict:** "Defer/Pivot Scope - Do not integrate IBM ART for Defense; conditionally use for Attack benchmarking only"
  - **Key Insight:** Linear probes already achieve perfect detection. ART's main value is gradient-based attacks (PGD, ZooAttack), not defense methods
  - **Recommendation:** External audit script, not production integration

- **2025-11-14: Codex AI Assessment**
  - **Stack Validation:** "Stack is appropriate. Main opportunities: PyTorch probes, experiment infra."
  - **PyTorch Probes:** "sklearn.LogisticRegression is fine when activations fit in host RAM, but for 70B models activation dumps quickly exceed that."

- **2025-11-14: Gemini AI Assessment**
  - **transformer-lens:** "Gold standard, purpose-built for your use case"
  - **Overall:** "Your choice of libraries and techniques is sound."

---

## Known Limitations & Future Work

### Current Benchmarks
- AUC=1.0 may indicate overfitting to discrete/heuristic attacks
- Missing validation against gradient-based adversarial examples
- Single-model training (cross-model generalization untested)

### Recommended Next Steps
1. **Cross-model generalization** (train on GPT-2, test on Llama/Mistral/Qwen)
2. **Gradient attack validation** (external audit with IBM ART)
3. **Dashboard completion** (53% → 100% real data coverage)

---

## Version History

- **v2.0.0** (2025-11-18): Phase 3 complete, architecture validated
- **v1.5.0** (2025-11-14): PyTorch probes complete, dual backend
- **v1.0.0** (2025-10-29): Initial dashboard integration (53% coverage)
- **v0.5.0** (Pre-2025): Foundation - Core detection methods

---

## References

**Research Foundation:**
- Hubinger et al. (2024): "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"

**Architecture Reviews:**
- Gemini 3 (2025-11-18)
- Codex AI (2025-11-14)
- Gemini AI (2025-11-14)

---

**Last Updated:** 2025-11-18
**Maintainer:** @AndrewAltimit
