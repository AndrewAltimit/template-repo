# Testing Plan - Phase 3 Recent Changes

**Branch:** `sleeper-dashboard`
**Status:** Clean slate - Ready for testing
**Recent Commits to Test:**
1. Calibration metrics display component
2. Model registry enhancements (Phase 3 metadata)
3. Dashboard Dockerfile fix
4. Comprehensive cleanup scripts
5. GPU orchestrator `.dockerignore` fix

---

## Test Session Checklist

### ✅ Phase 1: Basic Infrastructure (5-10 minutes)

#### 1. Dashboard Loads Successfully
**Status:** ✅ COMPLETE (confirmed working)
```powershell
# Dashboard is already running
# Access: http://localhost:8501
```

**Expected:** Dashboard loads without errors

---

#### 2. GPU Orchestrator Starts
**Status:** ⬜ TO TEST
```powershell
cd packages\sleeper_agents\gpu_orchestrator
.\start_orchestrator.bat
```

**Expected:**
- Docker image builds successfully (scripts/ directory included)
- API starts on port 8000
- No errors in logs

**Verification:**
```powershell
# Check API health
curl http://localhost:8000/health

# Or open in browser
start http://localhost:8000/docs  # FastAPI Swagger UI
```

---

### Phase 2: Dashboard Features (10-15 minutes)

#### 3. Login and Navigate Dashboard
**Status:** ⬜ TO TEST

**Steps:**
1. Open http://localhost:8501
2. Login with credentials from `.env`:
   - Username: `admin`
   - Password: (value of `DASHBOARD_ADMIN_PASSWORD`)
3. Navigate to each section in sidebar

**Expected:**
- Login works
- All menu items load without errors
- Components render (may show "No data available" - that's OK)

**Component Checklist:**
- ⬜ Overview Dashboard
- ⬜ Persistence Analysis
- ⬜ Chain-of-Thought Analysis
- ⬜ Honeypot Analysis
- ⬜ Detection Analysis
- ⬜ Model Comparison
- ⬜ Trigger Sensitivity
- ⬜ Internal State Monitor

---

#### 4. Verify Calibration Metrics Component (Mock Data)
**Status:** ⬜ TO TEST

**Steps:**
1. Navigate to "Persistence Analysis" or "Chain-of-Thought Analysis"
2. Look for **"🎯 Calibration Metrics"** section
3. Check if warning appears (should show: "Calibration data not available")

**Expected Behavior with NO data:**
```
⚠️ Calibration data not available for this model.
The probe may not have been calibrated using ROC curve + Youden's J.
Run probe training with calibration to generate this data.
```

**This is CORRECT!** New installation has no models yet.

**Screenshot Location (if needed):** Take screenshot showing the warning

---

#### 5. Check Model Registry Integration
**Status:** ⬜ TO TEST

**Steps:**
1. Navigate to any component with model selector
2. Check if model selector dropdown appears
3. See if any models are listed (likely none on fresh install)

**Expected:**
- Model selector renders
- Shows "No models available" or empty dropdown
- No Python errors in terminal

---

### Phase 3: Create Test Data (20-30 minutes)

#### 6. Generate Mock Evaluation Data
**Status:** ⬜ TO TEST

**Option A: Use Mock Data Loader (Quick - 2 minutes)**
```powershell
cd packages\sleeper_agents\dashboard
python initialize_mock_db.py
```

**Expected:**
- Creates `dashboard/evaluation_results.db`
- Populates with mock models and results

**Verification:**
```powershell
# Check database exists
ls dashboard\evaluation_results.db

# Query database
sqlite3 dashboard\evaluation_results.db "SELECT COUNT(*) FROM evaluation_results;"
```

---

**Option B: Run Simple GPU Evaluation (Real Data - 10-20 minutes)**

This requires GPU and will take longer but generates REAL data:

```powershell
cd packages\sleeper_agents

# Run validation script (uses GPU worker)
docker-compose -f docker/docker-compose.gpu.yml run --rm validate
```

**Expected:**
- Downloads small model (GPT-2 or similar)
- Runs basic evaluation
- Writes results to `/results/evaluation_results.db` (in Docker volume)

---

#### 7. Verify Dashboard Shows Data
**Status:** ⬜ TO TEST

**After creating mock or real data:**

**Steps:**
1. Refresh dashboard (F5 or reload browser)
2. Navigate to "Overview Dashboard"
3. Check model selector dropdown
4. Select a model
5. Navigate to "Persistence Analysis"

**Expected:**
- Models appear in dropdown
- Selecting a model loads data
- Charts and metrics display
- **Calibration metrics section should still show warning** (we haven't added calibration data yet)

---

### Phase 4: Test Calibration with Mock Metadata (10 minutes)

#### 8. Add Mock Calibration Data to Model
**Status:** ⬜ TO TEST

Since we don't have real probe training yet, let's manually add calibration metadata to test the display:

```powershell
cd packages\sleeper_agents\dashboard

# Open Python console
python
```

```python
# In Python console:
import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('evaluation_results.db')
cursor = conn.cursor()

# Check current models
cursor.execute("SELECT DISTINCT model_name FROM evaluation_results LIMIT 5")
models = cursor.fetchall()
print("Available models:", models)

# Pick first model (or a specific one)
model_name = models[0][0]  # e.g., "gpt2-backdoored-test"

# For now, we'll need to modify the model_registry.py to load calibration
# from a separate table, OR we can test with a manual ModelInfo object

# Let's create a test by modifying the data_loader temporarily
conn.close()
exit()
```

**Actually, let's use a simpler approach - Create a test script:**

Create `packages/sleeper_agents/dashboard/test_calibration_display.py`:
```python
"""Test script to verify calibration metrics display with mock data."""
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sleeper_agents.dashboard.utils.model_registry import ModelInfo

# Create mock model with calibration data
mock_model = ModelInfo(
    name="gpt2-test-calibration",
    display_name="GPT-2 Test (Calibration Demo)",
    source="test",
    path=None,
    job_id="test-001",
    created_at=datetime.now(),
    metadata={},
    has_evaluation_data=True,
    job_type=None,
    job_status="completed",
    avg_accuracy=0.95,
    risk_level="LOW",
    total_tests=100,
    # Phase 3 calibration metadata
    architecture="GPT-2",
    hidden_size=768,
    num_layers=12,
    probe_layer=6,
    auc=1.0,
    optimal_threshold=0.9999,
    baseline_accuracy=0.98,
    prob_range=(0.3246, 1.0000),
    calibration_date="2025-11-20",
    checkpoint_path=Path("/mock/checkpoint.pt")
)

print("Mock model created successfully!")
print(f"Model: {mock_model.name}")
print(f"Architecture: {mock_model.architecture}")
print(f"AUC: {mock_model.auc}")
print(f"Optimal Threshold: {mock_model.optimal_threshold}")
print(f"Calibrated Accuracy: {mock_model.baseline_accuracy}")
print(f"Probability Range: {mock_model.prob_range}")

# To use this in dashboard, we need to integrate it
# For now, this confirms the ModelInfo structure is correct
```

**Run the test:**
```powershell
cd packages\sleeper_agents\dashboard
python test_calibration_display.py
```

**Expected:**
```
Mock model created successfully!
Model: gpt2-test-calibration
Architecture: GPT-2
AUC: 1.0
Optimal Threshold: 0.9999
Calibrated Accuracy: 0.98
Probability Range: (0.3246, 1.0)
```

---

### Phase 5: Verify Cleanup Scripts (5 minutes)

#### 9. Test Data Location Checker
**Status:** ⬜ TO TEST

```powershell
cd packages\sleeper_agents\gpu_orchestrator
.\check_data_locations.bat
```

**Expected Output:**
```
[1] Docker Volumes
==================
sleeper-results
sleeper-models (if GPU orchestrator ran)

[2] Docker Containers
=====================
sleeper-dashboard
(possibly sleeper-gpu-worker)

[3] Database Files
==================
Dashboard databases:
  [FOUND] dashboard\evaluation_results.db (if mock data created)

[7] Dashboard Mounted Directories
=================================
  [FOUND] dashboard\auth\ (should have files after login)
  [NOT FOUND or FOUND] dashboard\data\
```

**This shows you where all your data is!**

---

### Phase 6: Advanced Testing (Optional - 30+ minutes)

#### 10. Full Evaluation Pipeline
**Status:** ⬜ OPTIONAL

**Only if you want to generate real calibration data:**

```powershell
# Run cross-architecture validation
cd packages\sleeper_agents
python examples/cross_architecture_validation.py

# This will:
# - Download GPT-2 model
# - Train probes with calibration
# - Save results to outputs/cross_architecture/
# - Takes 10-30 minutes depending on GPU
```

**Expected:**
- Probe checkpoints saved with calibration metadata
- Results JSON includes AUC, optimal_threshold, baseline_accuracy
- Ready for dashboard integration

---

## Success Criteria

### Minimum (Required) ✅
- ✅ Dashboard starts without errors
- ⬜ GPU orchestrator builds and starts
- ⬜ Can navigate all dashboard components
- ⬜ Calibration warning shows for models without data
- ⬜ Mock data can be loaded and displayed

### Ideal (Recommended) 🎯
- ⬜ Mock data shows charts and metrics
- ⬜ Model selector works with multiple models
- ⬜ Calibration display component renders correctly (even with warning)
- ⬜ Cleanup scripts accurately show data locations

### Stretch (Optional) 🌟
- ⬜ Real evaluation generates data
- ⬜ Real calibration data displays metrics
- ⬜ Cross-architecture validation completes
- ⬜ Dashboard shows calibration section with real values

---

## Troubleshooting

### Dashboard won't load
```powershell
# Check logs
docker logs sleeper-dashboard

# Rebuild
cd dashboard
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### GPU orchestrator fails to build
```powershell
# Check if scripts/ is excluded
cat ..\.dockerignore | findstr scripts

# Should see: # scripts/  (commented out)
```

### No models in dropdown
```powershell
# Generate mock data
cd dashboard
python initialize_mock_db.py

# Refresh browser
```

### Calibration section not appearing
**This is expected!** It only shows if model has calibration metadata.
The warning message is the correct behavior for now.

---

## Next Steps After Testing

### If All Tests Pass ✅
1. Continue with remaining 6 component integrations (calibration metrics)
2. Move to Quick Win 2: Architecture-aware model selector
3. Move to Quick Win 3: Adversarial robustness section
4. Begin Priority 1 components (Detection Consensus, Red Team Results)

### If Issues Found ❌
1. Document the error
2. Check logs (dashboard, GPU orchestrator)
3. Verify data locations with `check_data_locations.bat`
4. Report back with specific error messages

---

## Recommended Testing Order

**Quick Path (15-20 minutes):**
1. ✅ Dashboard loads (DONE)
2. GPU orchestrator starts (5 min)
3. Navigate dashboard components (5 min)
4. Check calibration warning appears (2 min)
5. Generate mock data (2 min)
6. Verify data shows in dashboard (5 min)

**Thorough Path (45-60 minutes):**
1-6. (Same as Quick Path)
7. Test cleanup scripts (5 min)
8. Run simple GPU evaluation (20 min)
9. Verify real data integration (10 min)

**Complete Path (2-3 hours):**
1-9. (Same as Thorough Path)
10. Run cross-architecture validation (30-60 min)
11. Verify calibration with real probe data (10 min)

---

**Start with Quick Path, then decide if you want to go deeper!**

Ready to test? I recommend:
1. Start GPU orchestrator
2. Navigate dashboard to check all components load
3. Generate mock data
4. Verify dashboard shows the data

Let me know what you find! 🚀
