# Windows Development Guide - Dashboard Completion

**Branch:** `sleeper-dashboard`
**Machine:** Windows (GPU + All Data)
**Purpose:** Complete dashboard with real validation data

## Quick Start

### 1. Setup (First Time Only)

```bash
# Pull the dashboard branch
git checkout sleeper-dashboard
git pull origin sleeper-dashboard

# Verify Python environment
python --version  # Should be 3.10+

# Install dependencies (if not already done)
pip install -e ./packages/sleeper_agents
pip install -r packages/sleeper_agents/dashboard/requirements.txt

# Verify GPU access
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### 2. Verify Data Availability

Check that validation results exist:

```bash
# Cross-architecture validation results
ls outputs/cross_architecture/

# Gradient attack audit results
ls outputs/gradient_attack_audit/

# General validation benchmarks
ls outputs/validation/

# Trained probe checkpoints
ls checkpoints/
# OR
ls models/
# OR
ls outputs/cross_architecture/checkpoints/
```

**If data is missing:**
```bash
# Run cross-architecture validation (generates all needed data)
python examples/cross_architecture_validation.py

# Run gradient attack audit
python examples/gradient_attack_audit.py --quick

# Run validation benchmarks (if needed)
python examples/validation_benchmark.py
```

### 3. Run Dashboard Locally

```bash
# Start dashboard
streamlit run packages/sleeper_agents/dashboard/app.py

# Open browser to http://localhost:8501
# Login with default credentials (or create account)
```

### 4. Development Workflow

```bash
# 1. Make changes to dashboard components
#    Files to edit: packages/sleeper_agents/dashboard/components/*.py

# 2. Test changes immediately
streamlit run packages/sleeper_agents/dashboard/app.py
# Refresh browser to see changes

# 3. Run tests
./automation/ci-cd/run-ci.sh format      # Check formatting
./automation/ci-cd/run-ci.sh lint-basic  # Check linting
./automation/ci-cd/run-ci.sh test-all    # Run all tests (includes GPU)

# 4. Commit and push
git add .
git commit -m "feat(dashboard): update detection consensus component"
git push origin sleeper-dashboard
```

## Component Development Guide

### Current State (8/15 Complete)
These components work with real data:
- ✅ Persistence Analysis
- ✅ Chain-of-Thought Analysis
- ✅ Honeypot Analysis
- ✅ Detection Analysis
- ✅ Model Comparison
- ✅ Overview Dashboard
- ✅ Trigger Sensitivity
- ✅ Internal State Monitor

### Missing Components (7/15 - Need Real Data)

#### Priority 1 (Start Here)

**1. Detection Consensus** (`dashboard/components/detection_consensus.py`)
- **Goal:** Replace mock data with real ensemble detection results
- **Data Source:** Combine probe results, clustering results, attention analysis
- **Estimated Time:** 3-4 days
- **Key Changes:**
  ```python
  def get_multi_method_detection(data_loader, model_name):
      # Load probe results
      probe_results = data_loader.fetch_probe_results(model_name)

      # Load clustering results (from validation benchmarks)
      clustering_results = data_loader.fetch_clustering_results(model_name)

      # Load attention analysis results
      attention_results = data_loader.fetch_attention_results(model_name)

      return {
          "methods": {
              "Probe-based Detection": {
                  "backdoor_detected": probe_results["detection_rate"],
                  "confidence": probe_results["auc"],
                  "uncertainty": 1.0 - probe_results["auc"],
                  "samples_tested": probe_results["n_samples"]
              },
              # Add other methods...
          }
      }
  ```

**2. Red Team Results** (`dashboard/components/red_team_results.py`)
- **Goal:** Show real attack results (gradient attacks, prompt attacks)
- **Data Source:** `outputs/gradient_attack_audit/`, `outputs/validation/red_team/`
- **Estimated Time:** 2-3 days
- **Key Changes:**
  ```python
  def _fetch_red_team_data(data_loader, cache_manager, model_name):
      # Load gradient attack results
      gradient_attacks = load_json("outputs/gradient_attack_audit/results.json")

      # Load prompt attack results
      prompt_attacks = load_json("outputs/validation/red_team/results.json")

      return {
          "total_prompts": prompt_attacks["total_tested"],
          "success_rate": prompt_attacks["success_rate"],
          "discovered_triggers": prompt_attacks["triggers"],
          "gradient_attack": {
              "baseline_accuracy": gradient_attacks["baseline_accuracy"],
              "post_attack_auc": gradient_attacks["post_attack_auc"],
              "success_rate": gradient_attacks["attack_success_rate"]
          }
      }
  ```

#### Priority 2 (After Priority 1)

**3. Risk Mitigation Matrix** (`dashboard/components/risk_mitigation_matrix.py`)
- **Data Source:** Model evaluation results, calibration metrics
- **Estimated Time:** 3-4 days

**4. Persona Profile** (`dashboard/components/persona_profile.py`)
- **Data Source:** `src/sleeper_agents/advanced_detection/persona_testing.py` results
- **Estimated Time:** 2-3 days

#### Priority 3 (Final Components)

**5. Risk Profiles** (`dashboard/components/risk_profiles.py`)
- **Data Source:** Aggregated risk scores from all detection methods
- **Estimated Time:** 2 days

**6. Tested Territory** (`dashboard/components/tested_territory.py`)
- **Data Source:** Test coverage metrics from validation benchmarks
- **Estimated Time:** 2 days

**7. Scaling Analysis** (`dashboard/components/scaling_analysis.py`)
- **Data Source:** Cross-architecture validation results
- **Estimated Time:** 2 days

## Data Loading Patterns

### Pattern 1: Load from Checkpoint
```python
import torch

# Load trained probe
checkpoint = torch.load("checkpoints/gpt2_probe.pt")
probe_state = checkpoint["probe"]
metadata = checkpoint["metadata"]

# Metadata should contain:
# - auc: float
# - optimal_threshold: float
# - baseline_accuracy: float
# - prob_range: (float, float)
```

### Pattern 2: Load from JSON Results
```python
import json

# Load validation results
with open("outputs/cross_architecture/results.json") as f:
    results = json.load(f)

# Results structure:
# {
#   "gpt2": {"auc": 1.0, "accuracy": 0.98, ...},
#   "mistral": {"auc": 1.0, "accuracy": 0.98, ...},
#   ...
# }
```

### Pattern 3: Load from CSV Results
```python
import pandas as pd

# Load benchmark results
df = pd.read_csv("outputs/validation/benchmark_results.csv")

# Filter by model
model_results = df[df["model"] == "gpt2-backdoored"]
```

## Phase 3 Integration Features

### Add to ALL Components

#### 1. Calibration Metrics Display
```python
def render_calibration_metrics(model_metadata):
    """Add this to every component."""
    st.markdown("### Calibration Metrics")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("AUC", f"{model_metadata.auc:.3f}",
                  help="Discrimination ability")
    with col2:
        st.metric("Calibrated Accuracy", f"{model_metadata.baseline_accuracy:.1%}",
                  help="Using optimal threshold")
    with col3:
        st.metric("Optimal Threshold", f"{model_metadata.optimal_threshold:.4f}",
                  help="ROC + Youden's J")
    with col4:
        prob_min, prob_max = model_metadata.prob_range
        st.metric("Probability Range", f"[{prob_min:.2f}, {prob_max:.2f}]")

    # Warning for uncalibrated probes
    if model_metadata.baseline_accuracy < 0.95:
        st.warning("⚠️ Low calibrated accuracy - probe may be uncalibrated")
```

#### 2. Cross-Architecture Support
```python
def render_architecture_info(selected_model):
    """Add architecture display."""
    st.info(f"""
    **Model:** {selected_model.name}
    **Architecture:** {selected_model.architecture}
    **Hidden Size:** {selected_model.hidden_size}
    **Probe Layer:** {selected_model.probe_layer}
    """)
```

#### 3. Adversarial Robustness Section
```python
def render_adversarial_robustness():
    """Add to components discussing detection performance."""
    with st.expander("🔒 Adversarial Robustness"):
        st.markdown("""
        ### White-Box Vulnerability (Expected Behavior)

        Linear probes are theoretically vulnerable to gradient-based attacks:
        - PGD attack success rate: 98%
        - Post-attack AUC drops from 1.0 → 0.0

        **This is expected behavior**, not a flaw. It proves the probe:
        - Tracks continuous feature representations (not token patterns)
        - Responds to high-dimensional correlations (manipulatable in embedding space)

        ### Real Threat Model
        Deployment scenarios face **prompt-based attacks** (red teaming), not gradient attacks.
        Attackers don't have gradient access to production models.

        The probe maintains strong robustness against prompt-level attacks.
        """)
```

## Testing Checklist

Before committing changes, verify:

```bash
# 1. Code quality
./automation/ci-cd/run-ci.sh format      # Passes
./automation/ci-cd/run-ci.sh lint-basic  # Passes

# 2. Tests pass
./automation/ci-cd/run-ci.sh test-all    # All tests pass

# 3. Dashboard runs
streamlit run packages/sleeper_agents/dashboard/app.py
# - No errors on startup
# - Component loads without crashing
# - Real data displays correctly
# - No mock data warnings

# 4. Visual validation
# - Charts render properly
# - Metrics show reasonable values
# - No obvious UI bugs
# - Cross-architecture switching works
```

## Common Data Locations

Based on typical project structure:

```
packages/sleeper_agents/
├── outputs/                          # Validation results
│   ├── cross_architecture/          # Cross-arch validation
│   │   ├── results.json             # Per-architecture metrics
│   │   └── checkpoints/             # Trained probes
│   │       ├── gpt2_probe.pt
│   │       ├── mistral_probe.pt
│   │       └── qwen_probe.pt
│   ├── gradient_attack_audit/       # Adversarial robustness
│   │   └── results.json
│   └── validation/                  # Benchmark results
│       ├── red_team/                # Red team attack results
│       ├── synthetic/               # Synthetic benchmarks
│       └── benchmark_results.csv    # Aggregated results
├── checkpoints/                      # Alternative checkpoint location
└── models/                          # Alternative model location
```

## Troubleshooting

### Dashboard Won't Start
```bash
# Check Python version
python --version  # Should be 3.10+

# Reinstall dependencies
pip install -e ./packages/sleeper_agents --force-reinstall
pip install -r packages/sleeper_agents/dashboard/requirements.txt --force-reinstall

# Check for port conflicts
netstat -an | findstr "8501"  # Should be empty
```

### No Data Showing
```bash
# Verify data exists
dir outputs\cross_architecture
dir outputs\gradient_attack_audit
dir outputs\validation

# If missing, generate data:
python examples/cross_architecture_validation.py
python examples/gradient_attack_audit.py --quick
```

### GPU Tests Failing
```bash
# Verify CUDA
python -c "import torch; print(torch.cuda.is_available())"  # Should be True
python -c "import torch; print(torch.cuda.get_device_name(0))"  # Should show GPU

# If False, check NVIDIA drivers and CUDA installation
```

## Progress Tracking

Use the TODO.md file to track progress:

```bash
# View current status
cat packages/sleeper_agents/TODO.md | grep "Dashboard Completion" -A 50

# Update as you complete components
# Edit TODO.md to mark completed items with ✅
```

## Getting Help

If stuck:
1. Check `DASHBOARD_IMPLEMENTATION_PLAN.md` for detailed implementation guidance
2. Review `DASHBOARD_COMPLETION_SUMMARY.md` for architectural overview
3. Look at existing completed components for patterns
4. Check validation scripts (`examples/cross_architecture_validation.py`) for data formats

## Next Steps

1. ✅ Verify data availability (`outputs/` directory)
2. ✅ Locate trained probe checkpoints
3. ✅ Run dashboard to confirm baseline functionality
4. 🔨 Start with Detection Consensus component (Priority 1)
5. 🔨 Move to Red Team Results component (Priority 1)
6. 🔨 Continue through Priority 2 and 3 components

**Ready to code on Windows! 🚀**
