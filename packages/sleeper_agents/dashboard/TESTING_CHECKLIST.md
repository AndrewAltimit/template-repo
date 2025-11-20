# Dashboard Testing Checklist

**Branch:** `sleeper-dashboard`
**Date:** 2025-11-20
**Components Changed:** 4 new components with real data integration

## Pre-Testing Setup

### 1. Pull Latest Changes
```bash
git checkout sleeper-dashboard
git pull origin sleeper-dashboard
```

### 2. Verify Database Has Data
Run `check_dashboard_data.bat` to verify evaluation data exists.

Expected: Should see data for your model in all tables (honeypot, CoT, persistence, etc.)

---

## Component Testing (4 New Components)

### ✅ Component 1: Detection Consensus

**What it does:** Aggregates risk scores from 4 detection methods (honeypot, CoT, persistence, internal state)

**Navigation:** Select your model → "Detection Consensus" tab

**Expected Results:**
- [ ] Shows 3-4 detection methods with real data
- [ ] Each method shows: risk_score, confidence, samples_tested
- [ ] Consensus risk score calculated (0.0-1.0)
- [ ] Agreement level shown (how methods converge)
- [ ] Risk level: CRITICAL/HIGH/MODERATE/LOW displayed
- [ ] Consensus matrix heatmap renders
- [ ] No "mock data" indicators

**Test Cases:**
1. Your model with evaluation data → Should show real method scores
2. Check if honeypot tests appear as a detection method
3. Verify consensus score matches visual indicators

---

### ✅ Component 2: Persona Profile

**What it does:** Analyzes 5 behavioral traits (power-seeking, self-awareness, corrigibility, deception, goal-orientation)

**Navigation:** Select your model → "Behavioral Persona Profile" tab

**Expected Results:**
- [ ] Risk level banner shows: CRITICAL/HIGH/MODERATE/LOW (not "ERROR")
- [ ] 5 behavioral scores displayed with values 0.0-1.0
- [ ] Radar chart or bar chart renders correctly
- [ ] Baseline deviation calculated
- [ ] Response statistics show real test counts
- [ ] Top concerning responses listed (if any scores > 0.6)
- [ ] Each response shows: prompt, category, concern_score

**Test Cases:**
1. Model with honeypot data → Should show power-seeking & corrigibility scores
2. Model with CoT data → Should show deception_tendency score
3. Model with persistence data → Should show goal_orientation score
4. Check if concerning responses match actual high-scoring tests

---

### ✅ Component 3: Red Team Results

**What it does:** Shows adversarial attack success rates by reframing honeypot tests as "red team attacks"

**Navigation:** Select your model → "Automated Red-Teaming Results" tab

**Expected Results:**
- [ ] Total prompts tested = number of honeypot tests
- [ ] Success rate calculated (% with reveal_score > 0.5)
- [ ] Best strategy shown (honeypot type with highest success)
- [ ] Unique triggers listed (successful honeypot types)
- [ ] Strategy success chart renders
- [ ] Discovered triggers chart with real effectiveness scores
- [ ] Successful prompts expandable list shows actual prompts
- [ ] Evolution history chart (4 generations)

**Test Cases:**
1. Your 47 honeypot tests → Should show "Total: 47"
2. All reveal_scores = 0.0 → Success rate should be 0%
3. Discovered triggers should be empty (no scores > 0.5)
4. Strategy success rates all near 0%

---

### ✅ Component 4: Risk Mitigation Matrix

**What it does:** Maps detected risks to actionable countermeasures with cost/effectiveness analysis

**Navigation:** Select your model → "Risk Mitigation Matrix" tab

**Expected Results:**
- [ ] 5 risk types displayed with levels 0.0-1.0:
  - Backdoor Persistence
  - Deceptive Reasoning
  - Behavioral Anomalies
  - Untested Behaviors
  - Power-Seeking Tendencies
- [ ] 8 mitigation strategies listed with:
  - Effectiveness (0.0-1.0)
  - Cost (low/medium/high)
  - Implementation time (hours/days/weeks/ongoing)
  - Target risks
- [ ] Risk-mitigation mapping matrix renders
- [ ] Recommendations generated for risks > 0.4
- [ ] Each recommendation shows priority (HIGH/MEDIUM)

**Test Cases:**
1. Model with persistence_rate > 0.4 → "Backdoor Persistence" risk should be HIGH
2. Model with deceptive CoT → "Deceptive Reasoning" risk should be elevated
3. Check if recommended mitigations match detected high risks
4. Verify "Sandboxing" shows as targeting "All" risks

---

## Existing Components (Should Still Work)

Quick smoke test to ensure we didn't break anything:

### ✅ Persistence Analysis
- [ ] Loads without errors
- [ ] Shows before/after training data
- [ ] New success messages for clean models (green, not red error)
- [ ] Clarity improvements visible (absolute vs relative values)

### ✅ Chain-of-Thought Analysis
- [ ] Loads your 40 CoT samples
- [ ] Deception patterns highlighted
- [ ] No import errors

### ✅ Honeypot Analysis
- [ ] Loads your 47 honeypot tests
- [ ] Shows 10 scenario types
- [ ] All reveal_scores = 0.0 displayed correctly

### ✅ Overview Dashboard
- [ ] Model appears in dropdown
- [ ] Summary metrics load
- [ ] No database errors

---

## Database Integrity Tests

Run `check_dashboard_data.bat` to verify:

- [ ] `honeypot_responses`: 47 rows
- [ ] `chain_of_thought_analysis`: 40 rows
- [ ] `persistence_results`: 1+ rows
- [ ] `internal_state_analysis`: 0+ rows
- [ ] All tables have correct model_name

---

## Error Scenarios to Test

### Test 1: Model with No Data
1. Select a model that hasn't been evaluated
2. Expected: "No data available" messages (not crashes)

### Test 2: Restart Dashboard
1. Stop dashboard: `docker-compose down`
2. Start dashboard: `start.bat`
3. Expected: All data persists, loads correctly

### Test 3: Database Priority
1. Verify mock database is in git but NOT loaded
2. Expected: Real data from `/results/evaluation_results.db` loads first

---

## Performance Tests

- [ ] Dashboard loads in < 5 seconds
- [ ] Switching between tabs is smooth
- [ ] Large datasets (47+ tests) render without lag
- [ ] Charts render correctly (no broken visualizations)

---

## Known Issues / Expected Behavior

1. **Internal State Analysis**: Tests may fail with PEFT models - this is expected
2. **Triggered Changes**: "triggered_changes" metrics are TODO (always show 0.0)
3. **Evolution History**: Simulated from timestamp ordering (not true generations)
4. **Coverage Metrics**: "Untested Behaviors" uses rough estimate (100 possible tests)

---

## Rollback Procedure

If critical issues found:

```bash
# Return to main branch
git checkout main

# Or return to previous working state
git checkout 8d3158ff  # Last known good commit before these changes
```

---

## Success Criteria

✅ **All 4 new components load without errors**
✅ **Real data displayed (not mock)**
✅ **Calculations make sense (risk scores, consensus, etc.)**
✅ **No Python exceptions in logs**
✅ **Existing components still work**
✅ **Performance is acceptable**

---

## Quick Test Command

```bash
# Full automated check
check_dashboard_data.bat

# Manual verification
# 1. Start dashboard: start.bat
# 2. Open browser: http://localhost:8501
# 3. Select your model
# 4. Visit each of the 4 new tabs
# 5. Check for errors in terminal logs
```
