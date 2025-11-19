# Sleeper Detection System - TODO

**Last Updated:** 2025-11-18
**Status:** Phase 3D Complete - Cross-Architecture Validation Successful

This document tracks current priorities and future development plans for the sleeper detection framework.

**For completed work, see:** `CHANGELOG.md`

---

## Recently Completed (2025-11-18)

### Phase 3 Benchmark Suite
- **Phase 3A:** Synthetic data benchmarking (4 difficulty scenarios)
  - Easy: Linear separable clusters
  - Medium: Non-linear boundaries (moons pattern)
  - Hard: Overlapping clusters with noise
  - Realistic: Subtle activation patterns
- **Phase 3B:** Real GPT-2 transformer activations (simple trigger testing)
- **Phase 3C:** Adversarial red team testing (5 attack strategies)
  - Subtle triggers (single chars, rare tokens)
  - Context-dependent triggers
  - Distributed triggers (multi-token patterns)
  - Mimicry triggers (benign-looking)
  - Typo-based triggers
- **Phase 3D:** Cross-Architecture Method Validation ✅ **COMPLETE**
  - Validated linear probe detection across 3 transformer architectures
  - **Results: Perfect generalization (AUC = 1.0 on all tested models)**

### Key Validation Results
- **Linear Probe Detector:** AUC=1.0, 0% attack success (perfect robustness on current benchmarks)
- **ARTActivationDetector:** AUC=0.76, 76.6% attack success (vulnerable to adversarial triggers)
- **Conclusion:** Supervised learning >> Unsupervised clustering for adversarial robustness

### Phase 3D Cross-Architecture Validation (NEW - 2025-11-18)
**CRITICAL MILESTONE:** Proved linear probe detection generalizes across transformer architectures

**Tested Architectures:**
- ✅ GPT-2 (768 hidden dims): **AUC = 1.0000**
- ✅ Mistral-7B-Instruct-v0.2 (4096 hidden dims): **AUC = 1.0000**
- ✅ Qwen2.5-7B-Instruct (3584 hidden dims): **AUC = 1.0000**
- ⏭️ Llama-3-8B-Instruct (gated access, not tested)

**Key Findings:**
1. **Perfect Generalization:** Method achieved AUC = 1.0 across all tested architectures
2. **Architecture Agnostic:** Linear probes work regardless of hidden dimension size (768d → 4096d)
3. **Not GPT-2 Specific:** Validates the technique itself, not just GPT-2 quirks
4. **Training Data:** 200 samples per class (backdoored/clean), 100 test samples per class

**Implementation:**
- Script: `examples/phase3d_cross_architecture_validation.py` (726 lines)
- Test infrastructure: `scripts/testing/test_phase3d.bat` (Windows), `test_phase3d.sh` (Linux)
- Docker GPU support: Added NVIDIA GPU passthrough to python-ci container
- Runtime: ~12 minutes on RTX 4090 (GPU accelerated)

**Scientific Significance:**
This result proves linear probes are a **valid general detection method** for transformer-based sleeper agents, not specific to any single model architecture.

### Infrastructure
- Removed IBM ART library from production dependencies (moved to dev-only for external audit)
- Archived outdated INTEGRATION_PLAN.md with deprecation notice
- Updated based on technical architecture review
- Added NVIDIA GPU support to docker-compose.yml for CUDA workloads

---

## Current Priorities

### Priority A: Core Science Validation

#### 1. Cross-Architecture Method Validation ✅ **COMPLETE**
**Status:** Complete (2025-11-18)
**Effort:** 3 days (actual)
**Impact:** HIGH - Validated that linear probe technique works across model architectures

**Results Achieved:**
- ✅ **GPT-2 (768d):** Train AUC = 1.0000, Test AUC = 1.0000
- ✅ **Mistral-7B-Instruct-v0.2 (4096d):** Train AUC = 1.0000, Test AUC = 1.0000
- ✅ **Qwen2.5-7B-Instruct (3584d):** Train AUC = 1.0000, Test AUC = 1.0000
- ⏭️ **Llama-3-8B-Instruct (4096d):** Skipped (gated access, not required)

**Validation Summary:**
- **Mean AUC:** 1.0000 (perfect generalization)
- **Architectures Tested:** 3 diverse architectures (GPT, Mistral, Qwen)
- **Dimension Range:** 768d → 4096d (proves dimension-agnostic)
- **Training Data:** 200 samples/class, 100 test samples/class
- **Runtime:** ~12 minutes on RTX 4090 (GPU accelerated)

**Scientific Conclusion:**
Linear probes are a **valid general detection method** for transformer-based sleeper agents, applicable across different model architectures. Method is not specific to GPT-2 quirks or activation patterns.

**Implementation Delivered:**
- Script: `examples/phase3d_cross_architecture_validation.py` (726 lines)
- Test infrastructure: `scripts/testing/test_phase3d.bat|.sh` (containerized with GPU support)
- Documentation: `examples/README_PHASE3D.md` (comprehensive guide)
- Docker GPU support: Added NVIDIA GPU passthrough to python-ci container

**Key Technical Insights:**
1. Chat template handling: Automatic detection and formatting for instruction-tuned models
2. Memory management: `gc.collect()` between models prevents OOM on sequential testing
3. Tokenization: Each architecture requires its own tokenizer (different vocab/special tokens)
4. Probe retraining: Cannot transfer weights (dimension mismatch), must retrain per architecture

---

#### 2. Phase 3E: Gradient-Based Attack Validation (MEDIUM PRIORITY)
**Status:** Ready to implement (pending Gemini consultation)
**Effort:** 2-3 days
**Impact:** MEDIUM - Validates robustness claims, documents known limitations

**Gemini Consultation:** Prepared comprehensive consultation prompt covering:
- Scope validation (proceed vs skip vs lightweight)
- Attack strategy selection (PGD vs ZooAttack vs HopSkipJump)
- Test design (sample size recommendations)
- Success criteria (acceptable AUC thresholds)
- Target function (optimization objectives)
- Documentation strategy (scientific honesty)
- Post-Phase 3E priorities

**Rationale:**
The primary risk is Scientific Blindness. We are claiming perfect detection, but haven't tested against white-box gradient attacks. Researchers will ask: "What happens if I run PGD on the input to minimize the probe's activation?"

**Implementation:**
1. Create dedicated audit environment setup:
   - `scripts/audit/requirements-audit.txt` (includes `adversarial-robustness-toolbox`, `scikit-learn`, `matplotlib`)
   - `scripts/audit/README.md` (explains how to run audit in separate virtualenv/container)
   - Keeps audit dependencies isolated from main production install
2. Create **external audit script** `scripts/audit/audit_with_art.py` (NOT integrated into main codebase)
3. Use IBM ART's PGD, ZooAttack, or HopSkipJump
4. Target: Minimize linear probe output while maintaining deceptive behavior
5. Test if gradient attacks can flip probe predictions
6. Document vulnerabilities honestly

**Expected Outcome:**
- AUC may drop from 1.0 to ~0.4 under gradient optimization (normal in adversarial ML)
- Update claims: "Probes robust to prompt injection, vulnerable to white-box optimization"
- This is scientifically honest, not a failure

**Caveat:**
- This is an **optional research validation**, not a production requirement
- Most real-world attackers use prompt injection, not gradient optimization
- Defer until after Priority A (cross-model generalization)

---

### Priority B: Engineering & Usability

#### 3. Dashboard Completion: 53% → 100% Real Data Coverage (MEDIUM PRIORITY)
**Status:** 8/15 components complete
**Effort:** 4-6 weeks (original estimate)
**Impact:** MEDIUM - Creates tangible working tool

**Current Coverage:**
- Persistence Analysis
- Chain-of-Thought Analysis
- Honeypot Analysis
- Detection Analysis
- Model Comparison
- Overview Dashboard
- Trigger Sensitivity
- Internal State Monitor

**Missing Components:**
- Detection Consensus (ensemble methods)
- Red Team Results (automated adversarial testing)
- Risk Mitigation Matrix
- Persona Profile
- Risk Profiles
- Tested Territory
- Scaling Analysis

**Recommendation:**
- Defer until core science (cross-model generalization) is validated
- Dashboard is valuable but not scientifically critical
- Focus on making detection methods publishable first

---

#### 4. Production API Development (LOW PRIORITY)
**Status:** Not started
**Effort:** 2-3 weeks
**Impact:** LOW - Useful for deployment, but premature

**Features:**
- REST API for programmatic access
- Batch evaluation pipeline
- Model registry integration
- Continuous monitoring capabilities

**Recommendation:**
- Wait until detection methods are validated across models
- Premature optimization before core science is complete

---

### Priority C: Research Extensions

#### 5. Experiment Infrastructure (Hydra + wandb) (LOW PRIORITY)
**Status:** Not started
**Effort:** 3-5 days
**Impact:** LOW - Nice-to-have for reproducibility

**Features:**
- Config-driven experiments with Hydra
- Experiment tracking with wandb
- Structured logging and artifact management

**Recommendation:**
- Only pursue if publishing or collaborating with others
- Current scripts are sufficient for solo research
- Adds complexity without immediate scientific value

---

#### 6. Multi-Layer Ensemble Detection (Phase 3D) (OPTIONAL)
**Status:** Not started
**Effort:** 3-4 days
**Impact:** MEDIUM - May improve detection accuracy

**Concept:**
- Extract activations from all 12 GPT-2 layers
- Train ensemble of probes (one per layer)
- Optimize layer weighting for best performance
- Compare against single-layer probe

**Recommendation:**
- Interesting research direction
- Lower priority than cross-model generalization
- May not significantly improve over current AUC=1.0 on existing benchmarks

---

#### 7. Larger Model Testing (Phase 3F) (OPTIONAL)
**Status:** Not started
**Effort:** 5-7 days (compute-intensive)
**Impact:** HIGH - Tests scalability to production models

**Models:**
- Mistral-7B-Instruct-v0.2 (14GB VRAM in FP16, fits on RTX 4090)
- Llama-3-8B-Instruct (16GB VRAM in FP16, fits on RTX 4090)
- Qwen2.5-14B-Instruct (28GB VRAM in FP16, **requires quantization on RTX 4090**)

**Hardware Considerations:**
- RTX 4090: 24GB VRAM
- **14B model in FP16:** ~28GB VRAM (exceeds 4090 capacity)
- **Solutions:**
  - 4-bit quantization with `bitsandbytes` (`load_in_4bit=True`)
  - FP8 quantization with newer libraries
  - Model offloading to CPU RAM (slower)
- **Action Required:** Add `bitsandbytes` to optional dependencies or ensure `ModelInterface` supports quantization

**Recommendation:**
- High value for demonstrating real-world applicability
- Requires significant compute resources
- Can overlap with Priority A (cross-architecture validation)
- **Note:** For 14B+ models, ensure quantization support is in place first

---

## Known Limitations

### Current Benchmarks
- **AUC=1.0 may indicate overfitting** to discrete/heuristic attacks (typos, syntax changes)
- Phase 3C covers prompt engineering attacks, NOT gradient-optimized adversarial examples
- Missing validation against:
  - Gradient-based feature collision attacks
  - White-box optimization (PGD, ZooAttack)
  - Real backdoored models (vs simulated triggers)

### Detection Scope
- Optimized for instruction-following models (GPT-2, Qwen, Llama)
- Limited testing on base models without fine-tuning
- Focused on English language triggers
- Single-architecture validation (cross-architecture method testing pending)

### Hardware Requirements
- GPU recommended for efficient evaluation (RTX 4090 validated)
- Large models (>7B params) require significant VRAM
- CPU inference possible but slow for production use

---

## Priority Ranking

**Do Now:**
1. Remove IBM ART from production dependencies (COMPLETE)
2. Archive outdated INTEGRATION_PLAN.md (COMPLETE)
3. Cross-architecture method validation (Priority A)

**Do Soon:**
4. Gradient-based attack validation (Phase 3E, external audit)
5. Dashboard completion (if building production tool)

**Do Later:**
6. Experiment infrastructure (Hydra + wandb)
7. Multi-layer ensemble (Phase 3D)
8. Larger model testing (Phase 3F)
9. Production API development

**Skip:**
- IBM ART library integration into production codebase (use as external audit only)
- Extensive dashboard polish before core science is validated

---

## Success Metrics

### Phase 3 Complete
- [x] Synthetic benchmarking (4 scenarios)
- [x] Real transformer activations (GPT-2)
- [x] Adversarial red team testing (5 strategies)
- [x] Linear probe validation (AUC=1.0)
- [x] ARTActivationDetector comparison (AUC=0.76)

### Phase 4 (Current) - Cross-Architecture Method Validation
- [ ] Create trigger dataset compatible with Llama-3/Mistral tokenizers
- [ ] Retrain probes for Llama-3-8B (4096 hidden dims) - measure AUC
- [ ] Retrain probes for Mistral-7B (4096 hidden dims) - measure AUC
- [ ] Retrain probes for Qwen2.5-7B (3584 hidden dims) - measure AUC
- [ ] Document architecture-specific tuning requirements
- [ ] Publish Phase 3D results

### Phase 5 (Future) - Production Readiness
- [ ] Gradient attack validation (Phase 3E)
- [ ] Dashboard completion (100% real data)
- [ ] API development
- [ ] Continuous monitoring system

---

## Removed from Roadmap

### IBM ART Integration
**Decision:** External audit only, not production integration

Linear probes already achieve AUC=1.0. ART's `ActivationDefense` is similar to our clustering approach (weaker than supervised probes). Main value is for gradient-based attacks, which are handled via external audit scripts in `scripts/audit/`.

---

## References

**Research Foundation:**
- Hubinger et al. (2024): "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training"
  - https://www.anthropic.com/research/probes-catch-sleeper-agents

**Architecture Reviews:**
- Technical consultation (2025-11-18): IBM ART integration assessment
- Library stack review (2025-11-14)
- Initial architecture validation (2025-11-14)

**Key Insights:**
- **IBM ART Scope (2025-11-18):** Defer/Pivot - Do not integrate for Defense; conditionally use for Attack benchmarking only
- **Large Model Training (2025-11-14):** sklearn.LogisticRegression is fine when activations fit in host RAM, but for 70B models activation dumps quickly exceed that

---

**Last Updated:** 2025-11-18
**Next Review:** After Phase 4 (cross-model generalization) completion
