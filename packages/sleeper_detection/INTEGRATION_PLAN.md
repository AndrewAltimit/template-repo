# Dashboard Integration Plan

This document outlines the integration strategy for connecting Build job outputs with Reporting visualization components in the Sleeper Detection Dashboard.

## Overview

The dashboard has comprehensive UI components, but significant portions rely on mock data rather than actual evaluation results. Many sophisticated detection capabilities exist in the package library but are not exposed in the dashboard.

### Current State (Updated: 2025-10-19)

**Data Source Distribution:**
- Real Data: 6/15 components (40%)
- Mock Data: 9/15 components (60%)

**Build Integration:**
- Integrated: 6/15 components (40%)
- Not Integrated: 9/15 components (60%)

**Recent Progress:**
- ✅ Chain-of-Thought capture implemented and integrated
- ✅ Honeypot testing expanded (4 → 10 categories) and integrated
- ✅ Evaluation pipeline connected to Build jobs via separate Run Evaluation view
- ✅ Database schema extended with CoT and honeypot tables
- ✅ Mock data aligned with real data categories
- ✅ **NEW**: Data aggregation layer enhanced to pull real sleeper-specific metrics
- ✅ **NEW**: Overview, Detection Analysis, Model Comparison now using real data

## Component Status Analysis

### Using Real Data

**Persistence Analysis** (`persistence_analysis.py`)
- Queries `persistence_results` table
- Falls back to mock data gracefully
- Integrated with Build safety training jobs
- Status: ✅ Complete

**Chain-of-Thought Analysis** (`chain_of_thought.py`)
- Queries `chain_of_thought_analysis` table
- Captures 20 samples per evaluation with scratchpad reasoning
- Database ingestion via `ingest_chain_of_thought_results()`
- Falls back to mock data gracefully
- Status: ✅ Complete (2025-10-19)

**Honeypot Analysis** (`honeypot_analysis.py`)
- Queries `honeypot_responses` table
- Tests 10 comprehensive honeypot categories (expanded from original 4)
- 30 samples per evaluation (3 per category)
- Database ingestion via `ingest_honeypot_results()`
- Falls back to mock data gracefully
- Mock data aligned with real categories
- Status: ✅ Complete (2025-10-19)

**Detection Analysis** (`detection_analysis.py`)
- Queries `evaluation_results` table via `fetch_latest_results()` and `fetch_test_suite_results()`
- Displays ROC curves, confusion matrices, confidence distributions
- Aggregates metrics by test type
- Falls back to empty state if no data available
- Status: ✅ Complete (2025-10-19)

**Model Comparison** (`model_comparison.py`)
- Queries via `fetch_model_summary()` and `fetch_comparison_data()`
- Compares multiple models side-by-side
- Shows behavioral risk dimensions (power seeking, deception, etc.)
- Vulnerability analysis and time series tracking
- Status: ✅ Complete (2025-10-19)

**Overview Dashboard** (`overview.py`)
- Queries via `fetch_model_summary()` for comprehensive metrics
- Displays threat indicators: persistence, deception, probe anomalies
- Shows actionability framework with deployment recommendations
- Aggregates data from `persistence_results`, `chain_of_thought_analysis`, `evaluation_results`
- Status: ✅ Complete (2025-10-19)

### Using Mock Data

#### Critical Components (High Value)

**Red Team Results** (`red_team_results.py`)
- Current: `_fetch_red_team_data()` returns hardcoded mock data
- Available: Could leverage honeypot infrastructure for adversarial testing
- Gap: No automated red-team evaluation integrated
- Impact: High value for discovering unknown triggers
- Note: Honeypot testing provides similar coverage

**Internal State Monitor** (`internal_state.py`)
- Current: Uses mock data
- Available:
  - `attention_analysis/analyzer.py` - AttentionAnalyzer
  - `probes/feature_discovery.py` - Feature discovery
  - `comprehensive_test.py` - Residual stream analysis
- Gap: Activation patterns not captured from Build jobs
- Impact: Internal state visibility

**Detection Consensus** (`detection_consensus.py`)
- Current: Uses mock data
- Available: Multiple detection methods in `detection/` directory
- Gap: No ensemble results stored
- Impact: Convergent evidence increases confidence

#### Important Components (Medium Value)

**Trigger Sensitivity** (`trigger_sensitivity.py`)
- Current: `data_loader.fetch_trigger_sensitivity()` implemented but returns mock data
- Available: Backdoor validation script tests trigger variations
- Gap: Trigger testing not parameterized in Build jobs
- Impact: Shows trigger robustness

**Risk Mitigation Matrix** (`risk_mitigation_matrix.py`)
- Current: Uses mock data
- Gap: Static risk assessment, no actual mitigation testing
- Impact: Strategy effectiveness mapping

#### Supporting Components (Lower Priority)

**Persona Profile** (`persona_profile.py`)
- Current: Uses mock `MODEL_PROFILES` from `config/mock_models.py`
- Gap: No behavioral analysis from actual model runs

**Risk Profiles** (`risk_profiles.py`)
- Current: Uses mock data
- Gap: Static risk dimensions

**Tested Territory** (`tested_territory.py`)
- Current: Uses mock data
- Gap: Not tracking actual prompt coverage

**Scaling Analysis** (`scaling_analysis.py`)
- Current: Uses mock data
- Available: `analysis/model_scaling.py` has scaling analysis code
- Gap: No multi-size model testing in Build

## Build Integration Gaps

### Current Build Job Capabilities

Build jobs (`safety_training`, `train_backdoor`, `train_probes`) currently:
- Train models
- Save persistence results (safety training only)
- Do NOT run comprehensive evaluations

### Missing Evaluation Integration

The `run_full_evaluation.py` script exists but is not integrated into Build workflow:
- Runs: basic_detection, layer_probing, code_vulnerability, robustness
- Saves to: evaluation_results.db
- Issue: Not called from Build jobs

### Build Pipeline Integration Status

**Implemented:**
1. ✅ Chain-of-Thought Capture: Saving scratchpad/reasoning (20 samples)
2. ✅ Honeypot Testing: Running 10 honeypot categories (30 samples)
3. ✅ Evaluation Integration: Separate "Run Evaluation" Build view

**Still Missing:**
4. Attention Analysis: Not capturing attention patterns
5. Layer Probe Training: Not training detection probes
6. Trigger Sensitivity: Not testing trigger variations
7. Detection Ensemble: Not running multiple detection methods
8. Red Team Testing: No automated adversarial prompt generation

## Unused Package Features

### Advanced Detection Capabilities

**comprehensive_test.py - Complete Test Suite**

Features Available:
- Residual stream analysis across layers
- Attention pattern analysis
- Activation interventions
- Backdoor detection suite
- Honeypot response testing
- Layer probe training

Dashboard Exposure: None

**advanced_detection/honeypots.py - Honeypot Generator**

Features Available:
- Probabilistic deployment dilemmas
- End-of-training scenarios
- Strategic advantage framing
- Multiple honeypot types

Dashboard Exposure: Mock data only

**interventions/causal.py - Causal Intervention System**

Features Available:
- Activation zeroing
- Path patching
- KL divergence measurement

Dashboard Exposure: None

**attention_analysis/analyzer.py - Attention Analyzer**

Features Available:
- Attention pattern detection
- Suspicious behavior identification
- Multi-head analysis

Dashboard Exposure: Mock data only

**probes/ - Multiple Detection Probes**

Features Available:
- `probe_detector.py` - Layer-wise probing
- `causal_debugger.py` - Causal debugging
- `feature_discovery.py` - Feature extraction

Dashboard Exposure: None

## Export Functionality Gaps

The export system has comprehensive structure but exports mock data.

### Export Functions Using Mock Data

1. `fetch_overview_data()` - Hardcoded values
2. `fetch_persistence_data()` - Partially real (after recent fix)
3. `fetch_red_team_data()` - Hardcoded mock
4. `fetch_persona_data()` - Uses `MODEL_PROFILES`
5. `fetch_detection_data()` - Hardcoded values
6. `fetch_test_results_data()` - Hardcoded mock
7. `fetch_comparison_data()` - Hardcoded models with random noise
8. `fetch_time_series_data()` - Generated with `np.random`
9. `fetch_leaderboard_data()` - Static mock leaderboard
10. `fetch_scaling_data()` - Hardcoded scaling coefficients
11. `fetch_risk_profiles_data()` - Hardcoded dimensions
12. `fetch_tested_territory_data()` - Mock coverage
13. `fetch_internal_state_data()` - Mock activation patterns
14. `fetch_detection_consensus_data()` - Mock consensus
15. `fetch_risk_mitigation_data()` - Mock mitigations
16. `fetch_trigger_sensitivity_data()` - Mock triggers
17. `fetch_chain_of_thought_data()` - Mock reasoning
18. `fetch_honeypot_data()` - Mock honeypots

Result: Exported PDFs contain predominantly fictional data

## Database Schema Gaps

### Current Database Tables

**evaluation_results** (Populated from `run_full_evaluation.py`)

```sql
CREATE TABLE evaluation_results (
    id, model_name, test_type, test_name, accuracy,
    precision, recall, f1_score, details, timestamp
)
```

Status: Populated by evaluation script
Gap: Not integrated into Build workflow

**persistence_results**

```sql
CREATE TABLE persistence_results (
    id, job_id, model_name, timestamp, trigger, target_response,
    safety_method, pre_training_rate, post_training_rate,
    persistence_rate, absolute_drop, relative_drop,
    trigger_specificity_increase, is_persistent, risk_level,
    pre_results_json, post_results_json
)
```

Status: Populated by safety training
Implementation: Complete

### Implemented Database Tables (NEW)

**chain_of_thought_analysis** - ✅ Implemented (2025-10-19)
```sql
CREATE TABLE chain_of_thought_analysis (
    id, model_name, prompt, safe_reasoning, triggered_reasoning,
    deception_score, has_deceptive_reasoning, metadata_json,
    job_id, timestamp
)
```

**honeypot_responses** - ✅ Implemented (2025-10-19)
```sql
CREATE TABLE honeypot_responses (
    id, model_name, honeypot_type, prompt, response,
    reveal_score, expected_goal, metadata_json, risk_level,
    job_id, timestamp
)
```

### Missing Database Tables

Tables that should exist but do not:

1. `red_team_results` - Discovered triggers (lower priority - honeypots cover similar ground)
2. `attention_patterns` - Attention analysis
3. `layer_activations` - Internal state monitoring
4. `trigger_sensitivity` - Trigger variation tests
5. `detection_ensemble` - Multiple detection method results
6. `intervention_results` - Causal intervention outcomes

## Data Flow Architecture

### Working Flow (Persistence - Reference Implementation)

```
Build Job (safety_training.py)
  ↓
Saves persistence_results.json
  ↓
Ingests to evaluation_results.db (persistence_results table)
  ↓
Dashboard queries database
  ↓
Reporting View displays real data
  ↓
Export includes real data
```

### Broken Flow (Most Other Components)

```
Build Job
  ↓
Saves model only
  ↓
No evaluation data

Dashboard
  ↓
Tries to query database
  ↓
Gets no data
  ↓
Falls back to mock data
  ↓
Export contains mock data
```

## Integration Priorities

### ✅ Completed (2025-10-19)

**1. Integrate `run_full_evaluation.py` into Build Pipeline** - COMPLETE

Impact: HIGH
Effort: MEDIUM

Implementation Details:
- Created dedicated "Run Evaluation" Build view
- Keeps evaluation separate from training (clean architecture)
- User workflow: Train → Select model → Run Evaluation
- Results automatically saved to evaluation_results.db
- Dashboard queries real data

**2. Add Chain-of-Thought Capture** - COMPLETE

Impact: HIGH (Critical for deception detection)
Effort: MEDIUM

Implementation Details:
- Added `_run_cot_capture()` to run_full_evaluation.py
- Captures 20 samples with safe + triggered reasoning
- Stores in `chain_of_thought_analysis` table via `ingest_chain_of_thought_results()`
- Dashboard component updated to fetch real data
- Falls back to mock gracefully

**3. Integrate Honeypot Testing** - COMPLETE + ENHANCED

Impact: HIGH
Effort: MEDIUM

Implementation Details:
- Expanded from 4 to 10 honeypot categories
- Added 6 new types: code_injection_bait, capability_boundary_probe,
  social_engineering_test, financial_advice_trap,
  temporal_consistency_check, authority_override_attempt
- Generates 30 samples (3 per category, balanced)
- Stores in `honeypot_responses` table via `ingest_honeypot_results()`
- Dashboard component updated with all 10 categories
- Mock data aligned with real categories for consistency

### Medium Priority

**4. Red Team Integration**

Impact: MEDIUM
Effort: HIGH (requires prompt generation)

Benefits:
- Discover unknown triggers
- Validate backdoor robustness

**5. Attention Pattern Capture**

Impact: MEDIUM
Effort: MEDIUM

Benefits:
- Internal state visibility
- `AttentionAnalyzer` already exists

**6. Trigger Sensitivity Testing**

Impact: MEDIUM
Effort: LOW

Benefits:
- Easy to parameterize existing tests
- Shows trigger robustness

### Lower Priority

**7. Scaling Analysis**

Impact: LOW (requires multiple model sizes)
Effort: HIGH

**8. Time Series Tracking**

Impact: LOW (requires longitudinal data)
Effort: MEDIUM

## Implementation Sequence

### ✅ Priority 1: Foundation - COMPLETE

1. ✅ Persistence Analysis Integration - Complete
2. ✅ Integrate `run_full_evaluation.py` into Build
   - ✅ Created separate "Run Evaluation" Build view
   - ✅ Updated data_loader to use evaluation_results table
   - ✅ Updated data_loader.fetch_model_summary() to aggregate sleeper-specific metrics from multiple tables
   - ✅ Overview, Detection Analysis, Model Comparison now using real data (2025-10-19)

### ✅ Priority 2: Core Detection - COMPLETE

3. ✅ Chain-of-Thought Capture
   - ✅ Added reasoning capture to evaluation (20 samples)
   - ✅ Created database table (chain_of_thought_analysis)
   - ✅ Updated chain_of_thought.py component to fetch real data
   - ✅ Ingestion via database.ingestion module

4. ✅ Honeypot Integration (ENHANCED)
   - ✅ Added honeypot tests to evaluation (30 samples, 10 categories)
   - ✅ Expanded from 4 to 10 honeypot types
   - ✅ Created database table (honeypot_responses)
   - ✅ Updated honeypot_analysis.py component to fetch real data
   - ✅ Aligned mock data with real categories
   - ✅ Ingestion via database.ingestion module

### Priority 3: Advanced Features

5. Attention Pattern Capture
   - Integrate AttentionAnalyzer
   - Store activation patterns
   - Update internal_state.py component

6. Trigger Sensitivity Testing
   - Parameterize trigger tests
   - Store sensitivity results
   - Update trigger_sensitivity.py component

### Priority 4: Completion

7. Red Team Integration
8. Export Validation - Ensure all components export real data
9. Testing and Documentation

## Implementation Pattern

### Correct Pattern (Persistence Analysis - Reference)

```python
# 1. Build job saves data
def safety_training():
    # ... training code ...

    # Save JSON
    persistence_path = save_path / "persistence_results.json"
    with open(persistence_path, "w") as f:
        json.dump(results, f, indent=2)

    # Ingest to database
    from packages.sleeper_detection.database.ingestion import ingest_from_safety_training_json
    success = ingest_from_safety_training_json(
        json_path=str(persistence_path),
        job_id=job_id,
        model_name=model_name,
    )

# 2. Database schema
def ensure_persistence_table_exists(db_path):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persistence_results (
            id INTEGER PRIMARY KEY,
            job_id TEXT,
            model_name TEXT,
            # ... columns ...
        )
    """)

# 3. Dashboard component
def render_persistence_analysis(data_loader, cache_manager, api_client):
    # Clear cache for fresh data
    if hasattr(st, "cache_data"):
        st.cache_data.clear()

    # Fetch from database
    persistence_data = _fetch_persistence_data(data_loader, cache_manager, model_name)

    # Fall back to mock if no data
    if not persistence_data:
        persistence_data = _fetch_mock_persistence_data(model_name)

# 4. Export function
def fetch_persistence_data(data_loader, cache_manager, model_name):
    # Try database first
    conn = data_loader.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM persistence_results WHERE model_name = ?", (model_name,))
    result = cursor.fetchone()

    if result:
        return build_data_from_result(result)
    else:
        return build_mock_data()
```

### Incorrect Pattern (Avoid)

```python
# Dashboard component - directly returns mock data
def _fetch_red_team_data(data_loader, cache_manager, model_name):
    # No database query - just hardcoded values
    return {
        "total_prompts": 500,
        "success_rate": 0.24,
        # ... hardcoded values ...
    }
```

## Package Feature Utilization

Current utilization of available package features:

- Comprehensive Test Suite: 0% utilized in dashboard
- Honeypot Generator: 0% utilized (mock only)
- Attention Analyzer: 0% utilized
- Causal Interventions: 0% utilized
- Detection Probes: 0% utilized (partially in Build)

## Critical Findings

### Strengths

- Excellent UI/UX - Dashboard is well-designed
- Comprehensive structure - All key views present
- Recent progress - Persistence analysis shows correct pattern
- Rich package library - Many features already implemented

### Gaps

- 93% mock data - Almost all reporting uses fake data
- Build disconnection - Build jobs do not run evaluations
- Unused capabilities - Advanced detection not exposed
- Export misleading - PDFs contain predominantly fake data
- Database incomplete - Only 2/10 needed tables exist

### Risk Assessment

Current dashboard gives false sense of capability:
- Users see comprehensive analysis but it is mostly mock data
- Exported reports appear professional but contain fake results
- Real detection capabilities exist but are not integrated

## Recommendations

### Immediate Actions

1. Integrate evaluation into Build - Highest priority
2. Add database tables - Foundation for real data
3. Update 2-3 high-value components - Prove the pattern

### Short-term

4. Chain-of-thought integration - Critical detection capability
5. Honeypot integration - High-value detection method
6. Attention pattern capture - Internal state visibility

### Long-term

7. Complete all 14 components - Full real data integration
8. Comprehensive testing - Validate all data flows
9. Documentation - Update user guides with real capabilities

## Conclusion

**Progress Update (2025-10-19):**

The dashboard has progressed from 93% mock data to 60% mock data, with 6 critical components now using real data:
- ✅ Persistence Analysis (safety training persistence testing)
- ✅ Chain-of-Thought Analysis (deceptive reasoning detection)
- ✅ Honeypot Analysis (10 comprehensive categories)
- ✅ **NEW**: Detection Analysis (ROC curves, confusion matrices)
- ✅ **NEW**: Model Comparison (side-by-side behavioral risk)
- ✅ **NEW**: Overview Dashboard (threat indicators, actionability framework)

**Key Technical Achievement:**

Enhanced the data aggregation layer (`data_loader.fetch_model_summary()`) to pull real sleeper-specific metrics from multiple database tables:
- `persistence_results` → backdoor persistence rates
- `chain_of_thought_analysis` → deception in reasoning
- `evaluation_results` → probe detection, behavioral variance, test coverage
- Graceful fallback to 0.0 when tables don't exist yet
- All derived metrics calculated from real data

**Architecture Decision:**
Evaluation kept separate from training jobs for clean separation of concerns:
- Training jobs focus on model creation
- Dedicated "Run Evaluation" Build view for comprehensive testing
- Clean job monitoring and logging
- Follows single-responsibility principle

**Remaining Work:**

High Priority:
1. **Trigger Sensitivity Testing** - Database schema ready, requires safety training integration
   - Note: Best integrated into safety training workflow (compares pre/post models)
   - Infrastructure ready: schema + ingestion functions created
   - Dashboard component already expects correct data format
2. **Attention Pattern Capture (internal_state.py)** - Interactive analysis tool
   - Requires real-time model execution via GPU orchestrator
   - More complex than batch evaluation
   - Consider separate implementation approach

Medium Priority:
3. Red Team Integration (lower priority - honeypots provide similar coverage)
4. Detection Consensus (ensemble methods)
5. Risk Mitigation Matrix (mitigation testing)

Lower Priority:
6. Persona Profile, Risk Profiles, Tested Territory, Scaling Analysis

**The Path Forward:**

With the evaluation pipeline and database foundation in place, the remaining 9 components follow the established pattern:
1. Add data capture to run_full_evaluation.py (if needed)
2. Create database table if needed
3. Update dashboard component to query real data
4. Maintain graceful fallback to mock data

**Infrastructure Ready:**
- Trigger sensitivity database table and ingestion functions created
- Ready for integration when safety training workflow is updated

Estimated effort for remaining components: 1-2 weeks

**Success Metrics:**
- Started: 1/15 components with real data (6.7%)
- After Session 1: 3/15 components with real data (20%)
- After Session 2: 6/15 components with real data (40%)
- Target: 15/15 components with real data (100%)
- Progress: 6.7% → 20% → 40% (+33.3 percentage points total, +20 percentage points this session)
