# Sleeper Detection System - TODO

**Last Updated:** 2025-11-18
**Status:** Phase 3 Benchmarking Complete, Core Detection Validated

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

### Key Validation Results
- **Linear Probe Detector:** AUC=1.0, 0% attack success (perfect robustness on current benchmarks)
- **ARTActivationDetector:** AUC=0.76, 76.6% attack success (vulnerable to adversarial triggers)
- **Conclusion:** Supervised learning >> Unsupervised clustering for adversarial robustness

### Infrastructure
- Removed IBM ART library from production dependencies (moved to dev-only for external audit)
- Archived outdated INTEGRATION_PLAN.md with deprecation notice
- Updated based on technical architecture review

---

## Current Priorities

### Priority A: Core Science Validation

#### 1. Cross-Architecture Method Validation (HIGH PRIORITY)
**Status:** Not started
**Effort:** 3-5 days
**Impact:** HIGH - Validates that linear probe technique works across model architectures

**Rationale:**
- Proves "Linear Probes are a valid detection method for ANY model," not just GPT-2
- Addresses potential overfitting to GPT-2-specific activation patterns
- More impressive for AI safety research than library integration

**Critical Note:**
- **Cannot directly transfer probe weights** across models (dimension mismatch)
  - GPT-2: 768 hidden dims, Llama-3-8B: 4096 hidden dims
  - Even if dimensions match, latent spaces are not aligned
- **Instead: Validate the METHOD, not the specific probe file**
  - Retrain probes for each architecture
  - Compare performance metrics to prove technique generalizes

**Implementation:**
1. Create trigger/backdoor dataset compatible with Llama-3/Mistral tokenizers
2. **Retrain** new linear probes specifically for each architecture:
   - Llama-3-8B-Instruct (4096 hidden dims)
   - Mistral-7B-Instruct-v0.2 (4096 hidden dims)
   - Qwen2.5-7B-Instruct (3584 hidden dims)
3. Compare performance metrics (AUC, TPR, FPR) across architectures
4. Document architecture-specific challenges (tokenization, layer selection)
5. Create example: `examples/cross_architecture_validation.py`

**Success Criteria:**
- **Hypothesis:** If method is robust, all architectures should achieve AUC ~1.0
- **Failure Mode:** If Llama-3 AUC < 0.6, our method relies on GPT-2 quirks
- Documented understanding of architecture-specific tuning requirements
- Published as Phase 3D results

---

#### 2. Phase 3E: Gradient-Based Attack Validation (MEDIUM PRIORITY)
**Status:** Planning
**Effort:** 2-3 days
**Impact:** MEDIUM - Validates robustness claims, but may show AUC drops to ~0.4

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
