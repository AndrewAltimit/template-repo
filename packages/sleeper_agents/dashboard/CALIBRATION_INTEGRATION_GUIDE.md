# Calibration Integration Guide

**Status:** Phase 3 - Quick Win 1
**Component:** Calibration Metrics Display
**Estimated Time:** 2-3 hours for all 8 components

## ✅ Completed
- [x] Created `calibration_metrics.py` reusable component
- [x] Updated `model_registry.py` with calibration metadata
- [x] Integrated into Persistence Analysis (example)

## 📋 Remaining Components (7/8)

### Integration Steps (Copy-Paste Pattern)

For each component below, follow these 3 steps:

#### Step 1: Add Import
```python
# At top of file, add:
from components.calibration_metrics import render_calibration_metrics
```

#### Step 2: Find Model Selection
Look for where the model is selected (usually after `render_model_selector`):
```python
selected_model = render_model_selector(model_registry, ...)
if not selected_model:
    return
model_name = selected_model.name
```

#### Step 3: Add Calibration Display
Insert right after model selection:
```python
# Phase 3: Display calibration metrics if available
if any([selected_model.auc, selected_model.baseline_accuracy, selected_model.optimal_threshold]):
    render_calibration_metrics(selected_model, show_warning=True, help_text=True)
    st.markdown("---")
```

---

## Component Checklist

### 1. ✅ Persistence Analysis
**File:** `dashboard/components/persistence_analysis.py`
**Status:** COMPLETE
**Lines:** Added after line 69

---

### 2. ⬜ Chain-of-Thought Analysis
**File:** `dashboard/components/chain_of_thought.py`
**Status:** TODO
**Find:** `model_name = selected_model.name` (around line 40-50)
**Add After:** Model selection

**Steps:**
```bash
# 1. Add import at top
from components.calibration_metrics import render_calibration_metrics

# 2. Find model selection (around line 40)
# 3. Add calibration display after model_name = selected_model.name
```

---

### 3. ⬜ Honeypot Analysis
**File:** `dashboard/components/honeypot_analysis.py`
**Status:** TODO
**Find:** `model_name = selected_model.name`
**Add After:** Model selection

---

### 4. ⬜ Detection Analysis
**File:** `dashboard/components/detection_analysis.py`
**Status:** TODO
**Find:** `model_name = selected_model.name`
**Add After:** Model selection

---

### 5. ⬜ Model Comparison
**File:** `dashboard/components/model_comparison.py`
**Status:** TODO
**Special Case:** This component compares multiple models
**Add:** Show calibration for each model in comparison table
**Alternative:** Add a "Calibration Comparison" tab

---

### 6. ⬜ Overview Dashboard
**File:** `dashboard/components/overview.py`
**Status:** TODO
**Find:** `model_name = selected_model.name`
**Add After:** Model selection
**Note:** This is the executive summary, calibration is important here

---

### 7. ⬜ Trigger Sensitivity
**File:** `dashboard/components/trigger_sensitivity.py`
**Status:** TODO
**Find:** `model_name = selected_model.name`
**Add After:** Model selection

---

### 8. ⬜ Internal State Monitor
**File:** `dashboard/components/internal_state.py`
**Status:** TODO
**Find:** `model_name = selected_model.name`
**Add After:** Model selection

---

## Testing Checklist

After adding calibration to each component:

```bash
# 1. Check imports (no errors)
python -c "from dashboard.components.calibration_metrics import render_calibration_metrics; print('OK')"

# 2. Run dashboard
streamlit run dashboard/app.py

# 3. Navigate to component
# - Check that calibration section appears (if model has data)
# - Check that warning appears if model missing calibration
# - Check that help text expander works

# 4. Verify no errors in terminal
# Look for import errors, attribute errors, etc.
```

---

## Mock Data for Testing

If you want to test calibration display before having real data, create a mock model:

```python
from dashboard.utils.model_registry import ModelInfo
from datetime import datetime
from pathlib import Path

# Create mock model with calibration data
mock_model = ModelInfo(
    name="gpt2-mock",
    display_name="GPT-2 Mock (for testing)",
    source="evaluation",
    path=None,
    job_id=None,
    created_at=datetime.now(),
    metadata={},
    has_evaluation_data=True,
    job_type=None,
    job_status=None,
    avg_accuracy=0.95,
    risk_level="LOW",
    total_tests=100,
    # Phase 3 calibration data
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
```

---

## Expected Visual Output

When calibration metrics display correctly, you should see:

```
### 🎯 Calibration Metrics

Calibration ensures the probe's predictions are properly scaled...

┌─────────────┬─────────────────────┬───────────────────┬──────────────────┐
│ AUC         │ Calibrated Accuracy │ Optimal Threshold │ Probability Range│
│ 1.000       │ 98.0%               │ 0.9999            │ [0.32, 1.00]     │
└─────────────┴─────────────────────┴───────────────────┴──────────────────┘

ℹ️ About Calibration Methodology
   [Expandable section with ROC + Youden's J explanation]
```

If calibration data missing:
```
⚠️ Calibration data not available for this model. The probe may not have
   been calibrated using ROC curve + Youden's J. Run probe training with
   calibration to generate this data.
```

If accuracy < 95%:
```
⚠️ Low Calibrated Accuracy (85.0%) - This probe may be uncalibrated.
   Expected accuracy ≥95% for AUC=1.0. Possible causes:
   - Hardcoded threshold (0.5) instead of optimal threshold
   - Score distribution shift between training and validation
   - Probe needs retraining with proper calibration
```

---

## Time Estimates

- **Per Component:** 10-15 minutes (copy-paste pattern)
- **Total for 7 Components:** 1-2 hours
- **Testing:** 30 minutes
- **Total:** 2-3 hours

---

## Next Steps After Completion

Once all 8 components have calibration metrics:

1. ✅ Mark "Quick Win 1" as complete
2. ⬜ Move to Quick Win 2: Architecture-Aware Model Selector
3. ⬜ Move to Quick Win 3: Adversarial Robustness Section

Then proceed to Priority 1 components (Detection Consensus, Red Team Results).

---

## Troubleshooting

### Import Error
```
ImportError: cannot import name 'render_calibration_metrics'
```
**Fix:** Check that `calibration_metrics.py` is in `dashboard/components/` directory

### Attribute Error
```
AttributeError: 'ModelInfo' object has no attribute 'auc'
```
**Fix:** Ensure `model_registry.py` has been updated with calibration fields

### No Calibration Display
**Cause:** Model doesn't have calibration data
**Expected:** Warning message should appear
**Action:** This is normal for models not yet calibrated

### Dashboard Won't Start
```
ModuleNotFoundError: No module named 'components.calibration_metrics'
```
**Fix:** Run from correct directory:
```bash
cd packages/sleeper_agents
streamlit run dashboard/app.py
```

---

## Completion Criteria

✅ All 8 components import calibration_metrics
✅ All 8 components call render_calibration_metrics()
✅ Dashboard starts without errors
✅ Calibration section appears for models with data
✅ Warning appears for models without data
✅ Help text expander works
✅ No linting errors

---

**Ready to integrate! Start with Chain-of-Thought Analysis and work through the list.**
