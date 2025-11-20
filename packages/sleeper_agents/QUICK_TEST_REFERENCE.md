# Quick Test Reference - Recent Changes

**Branch:** `sleeper-dashboard`
**Status:** Clean slate, ready to test
**Recent Commits:** Calibration metrics, model registry Phase 3, Docker fixes

---

## What Changed in Recent Commits

1. ✅ **Calibration Metrics Component** (`dashboard/components/calibration_metrics.py`)
   - New reusable component for displaying probe calibration data
   - Shows AUC, optimal threshold, baseline accuracy, probability range
   - Warning system for uncalibrated probes

2. ✅ **Model Registry Enhancement** (`dashboard/utils/model_registry.py`)
   - Added Phase 3 calibration metadata fields
   - Architecture tracking (GPT-2, Mistral-7B, etc.)
   - Probe configuration (hidden_size, num_layers, probe_layer)

3. ✅ **Calibration Integration** (2/8 components complete)
   - Persistence Analysis: Added calibration display
   - Chain-of-Thought Analysis: Added calibration display

4. ✅ **Docker Fixes**
   - `.dockerignore`: Uncommented scripts/ to allow in build
   - Dashboard `Dockerfile`: Fixed mkdir overwriting auth/ module

5. ✅ **Cleanup Scripts**
   - `clear_all_data_comprehensive.bat`: Complete data cleanup
   - `check_data_locations.bat`: Diagnostic tool

---

## Quick Test Steps (15 minutes)

### Step 1: Start GPU Orchestrator (2 min)
```powershell
cd packages\sleeper_agents\gpu_orchestrator
.\start_orchestrator.bat
```

**Expected:**
- Docker image builds successfully (scripts/ directory now included)
- API starts on port 8000
- No build errors

**Verify:**
```powershell
curl http://localhost:8000/health
```

---

### Step 2: Dashboard Navigation Test (3 min)

Dashboard is already running at http://localhost:8501

**Check each section loads without errors:**
- ✅ Overview Dashboard
- ✅ Persistence Analysis
- ✅ Chain-of-Thought Analysis
- ✅ Honeypot Analysis
- ✅ Detection Analysis
- ✅ Model Comparison
- ✅ Trigger Sensitivity
- ✅ Internal State Monitor

**Expected:** All components load, may show "No data available" (that's OK for now)

---

### Step 3: Calibration Warning Test (2 min)

1. Navigate to **Persistence Analysis**
2. Look for **"🎯 Calibration Metrics"** section
3. Should show warning: "⚠️ Calibration data not available..."

**Repeat for:**
- Chain-of-Thought Analysis

**Expected:** Both show the calibration warning (correct behavior for fresh install)

---

### Step 4: Generate Mock Data (2 min)

```powershell
cd packages\sleeper_agents\dashboard
python initialize_mock_db.py
```

**Expected:**
```
[SUCCESS] Mock database initialized at: evaluation_results_mock.db
   Models: 5
   Evaluation results: ...
   Rankings: ...
```

---

### Step 5: Verify Dashboard Shows Data (5 min)

1. Refresh dashboard (F5)
2. Navigate to **Overview Dashboard**
3. Check model selector dropdown - should show mock models
4. Select a model
5. Navigate to **Persistence Analysis**

**Expected:**
- Models appear in dropdown
- Charts and metrics display
- **Calibration metrics section still shows warning** (mock data doesn't include calibration yet)

---

### Step 6: Test Cleanup Scripts (3 min)

```powershell
cd packages\sleeper_agents\gpu_orchestrator
.\check_data_locations.bat
```

**Expected Output:**
```
[1] Docker Volumes
==================
sleeper-results
sleeper-models

[3] Database Files
==================
Dashboard databases:
  [FOUND] dashboard\evaluation_results_mock.db

[7] Dashboard Mounted Directories
=================================
  [FOUND] dashboard\auth\
```

---

## Success Criteria

### Must Pass ✅
- [x] GPU orchestrator builds without "scripts not found" error
- [ ] Dashboard loads without ModuleNotFoundError
- [ ] Can navigate all 8 dashboard components
- [ ] Calibration warning appears in Persistence Analysis
- [ ] Calibration warning appears in Chain-of-Thought Analysis
- [ ] Mock data can be loaded
- [ ] Mock data displays in dashboard

### Bonus (Optional) 🎯
- [ ] Run real GPU evaluation to generate actual data
- [ ] Verify calibration with real probe data

---

## Known Issues (These are EXPECTED)

1. **"Calibration data not available" warning**:
   - ✅ This is CORRECT for mock data
   - Mock data generator doesn't include calibration metadata yet
   - Will show metrics when you run real probe training

2. **No models in dropdown on first load**:
   - ✅ Expected - run `initialize_mock_db.py` first

3. **Empty charts/metrics**:
   - ✅ Expected until you generate data

---

## Troubleshooting

### GPU Orchestrator Won't Build
```powershell
# Verify scripts/ is not excluded
Get-Content ..\.dockerignore | Select-String "scripts"
# Should show: # scripts/  (commented out)
```

### Dashboard Won't Start
```powershell
# Check logs
docker logs sleeper-dashboard

# Rebuild
cd dashboard
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### No Models in Dropdown
```powershell
cd dashboard
python initialize_mock_db.py
# Then refresh browser
```

---

## Next Steps After Testing

If all tests pass:
1. Report back: "All tests passed!"
2. Continue with remaining 6 component integrations (copy-paste pattern)
3. Move to Quick Win 2: Architecture-aware model selector
4. Move to Quick Win 3: Adversarial robustness section

If issues found:
1. Note the specific error message
2. Check logs (`docker logs sleeper-dashboard`)
3. Run `check_data_locations.bat` to verify data
4. Report back with details

---

## Files to Watch

If you need to check the code:
- **Calibration component**: `dashboard/components/calibration_metrics.py`
- **Model registry**: `dashboard/utils/model_registry.py`
- **Integration examples**:
  - `dashboard/components/persistence_analysis.py` (lines ~50-60)
  - `dashboard/components/chain_of_thought.py` (lines ~50-60)

---

**Ready to test! Start with Step 1 (GPU Orchestrator) and work through the checklist.**
