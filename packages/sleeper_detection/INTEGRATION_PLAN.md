# Dashboard Integration Plan

This document outlines the integration strategy for connecting Build job outputs with Reporting visualization components in the Sleeper Detection Dashboard.

## Overview

The dashboard has comprehensive UI components, but significant portions rely on mock data rather than actual evaluation results. Many sophisticated detection capabilities exist in the package library but are not exposed in the dashboard.

### Current State

**Data Source Distribution:**
- Real Data: 1/15 components (6.7%)
- Mock Data: 14/15 components (93.3%)

**Build Integration:**
- Integrated: 1/15 components (6.7%)
- Not Integrated: 14/15 components (93.3%)

## Component Status Analysis

### Using Real Data

**Persistence Analysis** (`persistence_analysis.py`)
- Queries `persistence_results` table
- Falls back to mock data gracefully
- Integrated with Build safety training jobs
- Status: Complete

### Using Mock Data

#### Critical Components (High Value)

**Chain-of-Thought Analysis** (`chain_of_thought.py`)
- Current: `data_loader.fetch_chain_of_thought()` returns empty, falls back to `generate_mock_cot_data()`
- Available: `comprehensive_test.py` has scratchpad analysis
- Gap: No chain-of-thought data stored in database from Build jobs
- Impact: Critical for deception detection

**Red Team Results** (`red_team_results.py`)
- Current: `_fetch_red_team_data()` returns hardcoded mock data
- Available: Honeypot generator exists (`advanced_detection/honeypots.py`)
- Gap: No red-team evaluation integrated with Build or stored in database
- Impact: High value for discovering unknown triggers

**Honeypot Analysis** (`honeypot_analysis.py`)
- Current: Uses mock data
- Available: `HoneypotGenerator` class with multiple honeypot types
- Gap: Not run during evaluation jobs
- Impact: Probabilistic deployment dilemmas are powerful detection

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

**Detection Analysis** (`detection_analysis.py`)
- Current: Uses mock data
- Available: Multiple detection methods available
- Gap: Not aggregating actual detection results
- Impact: Comprehensive metrics with ROC curves

**Model Comparison** (`model_comparison.py`)
- Current: Uses mock data
- Available: Database has model summaries
- Gap: Not comparing multiple models from actual jobs
- Impact: Side-by-side safety metrics

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

**Overview Dashboard** (`overview.py`)
- Current: Aggregates from other components (inherits their mock data)
- Gap: No real aggregate statistics

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

### Missing from Build Pipeline

1. Chain-of-Thought Capture: Not saving scratchpad/reasoning
2. Red Team Testing: No automated prompt generation
3. Honeypot Deployment: Not running honeypot tests
4. Attention Analysis: Not capturing attention patterns
5. Layer Probe Training: Not training detection probes
6. Trigger Sensitivity: Not testing trigger variations
7. Detection Ensemble: Not running multiple detection methods

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

### Missing Database Tables

Tables that should exist but do not:

1. `chain_of_thought_analysis` - Reasoning patterns
2. `red_team_results` - Discovered triggers
3. `honeypot_responses` - Honeypot test results
4. `attention_patterns` - Attention analysis
5. `layer_activations` - Internal state monitoring
6. `trigger_sensitivity` - Trigger variation tests
7. `detection_ensemble` - Multiple detection method results
8. `intervention_results` - Causal intervention outcomes

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

### High Priority (High Value + Feasible)

**1. Integrate `run_full_evaluation.py` into Build Pipeline**

Impact: HIGH
Effort: MEDIUM

Benefits:
- Populates `evaluation_results` table with real test data
- Enables Detection Analysis, Model Comparison, Overview reports
- Provides foundation for other integrations

Implementation:
- Modify safety_training.py to call evaluation after training
- Results automatically saved to evaluation_results.db
- Dashboard can query real data

**2. Add Chain-of-Thought Capture**

Impact: HIGH (Critical for deception detection)
Effort: MEDIUM

Benefits:
- Detect deceptive reasoning patterns
- Core capability for sleeper agent detection
- Detection patterns already defined

Implementation:
- Add scratchpad/reasoning capture during evaluation
- Store in new `chain_of_thought_analysis` table
- Update `data_loader.fetch_chain_of_thought()` to query database

**3. Integrate Honeypot Testing**

Impact: HIGH
Effort: MEDIUM

Benefits:
- Probabilistic deployment dilemmas are powerful detection
- `HoneypotGenerator` already implemented
- High signal for strategic deception

Implementation:
- Run honeypot tests during evaluation
- Store results in `honeypot_responses` table
- Update honeypot_analysis.py to use real data

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

### Priority 1: Foundation

1. Persistence Analysis Integration - Complete
2. Integrate `run_full_evaluation.py` into Build
   - Modify safety_training.py to call evaluation
   - Update data_loader to use evaluation_results table
   - Update Overview, Detection Analysis, Model Comparison

### Priority 2: Core Detection

3. Chain-of-Thought Capture
   - Add reasoning capture to evaluation
   - Create database table
   - Update chain_of_thought.py component

4. Honeypot Integration
   - Add honeypot tests to evaluation
   - Store results in database
   - Update honeypot_analysis.py component

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

The dashboard has excellent structure and UI but operates on 93% mock data. The persistence analysis integration demonstrates the correct implementation pattern. Following this pattern for the remaining 14 components will transform the dashboard from a prototype with fake data to a production system with real detection capabilities.

The most efficient path forward:
1. Integrate `run_full_evaluation.py` into Build pipeline (unlocks 5-6 components)
2. Add chain-of-thought and honeypot integration (2 high-value detections)
3. Systematically migrate remaining components following persistence pattern

Estimated effort: 3-4 weeks for complete integration of all 15 components.
