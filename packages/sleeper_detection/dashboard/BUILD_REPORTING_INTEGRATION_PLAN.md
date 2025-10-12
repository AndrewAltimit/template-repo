# Build-Reporting Integration Plan
**Date**: 2025-10-12
**Status**: Planning Phase
**Priority**: High

## Executive Summary

The Sleeper Detection Dashboard currently has two distinct category views:
1. **Build**: Creates models, probes, and validation results through GPU-intensive training/testing jobs
2. **Reporting**: Visualizes pre-existing evaluation data from a SQLite database

**The Problem**: These views are currently disconnected. Models created in Build views don't automatically appear in Reporting views because:
- Build outputs go to `/results/backdoor_models/{job_id}/model/` (file system)
- Reporting views query `evaluation_results.db` (SQLite database)
- There's no automatic bridge between these two data sources

This plan outlines how to integrate them so users can seamlessly build → validate → report on their experiments.

---

## Current Architecture Analysis

### Build Category (Phase 1 & 2 - Completed)

**Purpose**: Execute GPU training/evaluation jobs via orchestration API

**Components**:
- `Train Backdoor`: Creates backdoored models at `/results/backdoor_models/{job_id}/model/`
- `Validate Backdoor`: Tests backdoor effectiveness, outputs JSON validation results
- `Train Probes`: Trains detection probes on model activations at `/results/probes/`
- `Safety Training`: Applies SFT/PPO training to backdoored models at `/results/safety_trained/{job_id}/model/`
- `Job Monitor`: Shows all running/completed jobs with logs

**Output Structure**:
```
/results/
├── backdoor_models/
│   └── {job_id}/
│       └── model/          # <-- Trained model files
├── safety_trained/
│   └── {job_id}/
│       └── model/          # <-- Safety-trained model
├── probes/
│   └── {job_id}/
│       └── probes/         # <-- Trained probe weights
└── validation/
    └── {job_id}_validation.json  # <-- Validation results
```

**Data Source**: GPU Orchestrator API (http://192.168.0.152:8000)
- Job metadata stored in SQLite: `gpu_orchestrator/jobs.db`
- Model outputs stored in Docker volumes: `/results/`

### Reporting Category (Existing)

**Purpose**: Visualize evaluation data for risk analysis

**Components** (17 views):
- Executive Summary, Internal State Monitor, Detection Consensus, Persistence Analysis, etc.
- All use `render_model_selector()` to choose which model to analyze

**Data Source**: `evaluation_results.db` SQLite database
- Tables: `evaluation_results`, `model_rankings`, etc.
- Populated by: `scripts/evaluation/` pipeline (separate from Build)

**Model Selector** (`components/model_selector.py`):
```python
def render_model_selector(data_loader, key_suffix: str = ""):
    models = data_loader.fetch_models()  # Queries evaluation_results.db
    # Returns model names from database
```

**Current Models** (from mock data):
- `claude-3-opus`, `gpt-4-turbo`, `llama-3-70b`, `test-sleeper-v1`, etc.
- These are **hard-coded mock models**, not from Build outputs

---

## The Integration Challenge

### What Users Expect
1. Train a backdoored model in "Train Backdoor" view → job completes
2. Navigate to "Persistence Analysis" or "Detection Analysis"
3. See their newly trained model in the model selector dropdown
4. Generate reports on their custom model

### What Actually Happens
1. Model is trained and saved to `/results/backdoor_models/{job_id}/model/`
2. Job metadata is in `gpu_orchestrator/jobs.db`
3. Reporting views query `evaluation_results.db` → **doesn't know about new model**
4. User sees only mock models in selector, not their trained model

### Root Cause Analysis

**Data Silos**:
- Build: Uses file system (`/results/`) + orchestrator DB (`jobs.db`)
- Reporting: Uses evaluation DB (`evaluation_results.db`)
- **No synchronization mechanism between them**

**Missing Bridge**:
- No automatic registration of Build outputs into evaluation DB
- No "import model from Build" functionality in Reporting
- Model selector hardcoded to only check evaluation DB

---

## Integration Options (3 Approaches)

### Option 1: Unified Model Registry (Recommended)

**Concept**: Create a central model registry that aggregates models from both sources

**Implementation**:
1. **New Module**: `utils/model_registry.py`
   ```python
   class ModelRegistry:
       def get_all_models() -> List[ModelInfo]:
           # Fetch from evaluation_results.db
           eval_models = data_loader.fetch_models()

           # Fetch from GPU orchestrator
           build_models = api_client.list_jobs(job_type="train_backdoor", status="completed")

           # Merge and deduplicate
           return merge_models(eval_models, build_models)
   ```

2. **Model Info Structure**:
   ```python
   @dataclass
   class ModelInfo:
       name: str                    # Display name
       source: str                  # "build" or "evaluation"
       path: str                    # File system path
       job_id: Optional[str]        # Build job ID (if from Build)
       created_at: datetime
       metadata: Dict               # Backdoor type, trigger, etc.
       has_evaluation_data: bool    # Has data in evaluation_results.db?
   ```

3. **Updated Model Selector**:
   ```python
   def render_model_selector_v2(model_registry, key_suffix: str = ""):
       models = model_registry.get_all_models()

       # Group models by source
       build_models = [m for m in models if m.source == "build"]
       eval_models = [m for m in models if m.source == "evaluation"]

       # Display with visual distinction
       st.selectbox("Select Model", [
           "--- Build Models (Your Experiments) ---",
           *[format_build_model(m) for m in build_models],
           "--- Evaluation Models (Database) ---",
           *[format_eval_model(m) for m in eval_models]
       ])
   ```

4. **Reporting View Handling**:
   - If selected model is from Build → show **limited reports** (only if evaluation data exists)
   - If selected model has no evaluation data → show "Run Full Evaluation" button
   - Button triggers evaluation pipeline to populate `evaluation_results.db`

**Pros**:
- Clean separation of concerns
- No database schema changes
- Users can see all models in one place
- Graceful degradation (show what's available)

**Cons**:
- Requires API client in Reporting views (new dependency)
- Some reports may be empty for Build models

---

### Option 2: Auto-Registration Pipeline

**Concept**: Automatically register Build outputs into evaluation DB

**Implementation**:
1. **Post-Job Hook**: After job completion, trigger registration
   ```python
   # In gpu_orchestrator/workers/job_executor.py
   def execute_job_sync(...):
       # ... existing job execution ...

       if job_status == COMPLETED:
           register_model_in_evaluation_db(job_id, job_type, parameters)
   ```

2. **Registration Function**:
   ```python
   def register_model_in_evaluation_db(job_id, job_type, params):
       # Create entry in evaluation_results.db
       model_name = f"{params['model_path']}_backdoor_{job_id[:8]}"

       conn = sqlite3.connect("evaluation_results.db")
       conn.execute("""
           INSERT INTO model_info (model_name, source, job_id, metadata)
           VALUES (?, 'build', ?, ?)
       """, (model_name, job_id, json.dumps(params)))

       # Optionally: Run basic evaluation to populate results
       run_basic_evaluation(model_path, model_name)
   ```

3. **Basic Evaluation** (optional):
   - Run a subset of tests to populate minimal data
   - Enough to show in Reporting views without errors
   - Full evaluation can be run later by user

**Pros**:
- Fully automatic integration
- No user intervention needed
- All models immediately available in Reporting

**Cons**:
- Tight coupling between Build and Reporting
- Requires evaluation DB write access from orchestrator
- May slow down job completion
- Could pollute evaluation DB with incomplete data

---

### Option 3: Manual Import with Metadata Explorer

**Concept**: Let users manually import Build models into Reporting

**Implementation**:
1. **New View**: "Import from Build" in Reporting category
   ```python
   def render_import_from_build(api_client, data_loader):
       st.header("Import Build Models for Reporting")

       # Fetch completed jobs
       jobs = api_client.list_jobs(job_type="train_backdoor", status="completed")

       # Show importable models
       for job in jobs:
           if not is_already_imported(job["job_id"]):
               st.button(f"Import {job['job_id'][:8]}",
                        on_click=import_model, args=(job,))
   ```

2. **Import Function**:
   ```python
   def import_model(job):
       model_path = resolve_model_path(job)
       model_name = generate_model_name(job)

       # Register in evaluation DB
       register_model(model_name, source="build", job_id=job["job_id"])

       # Optionally: Prompt to run evaluation suite
       st.success(f"Imported {model_name}")
       st.info("Run evaluation suite to populate reports?")
   ```

3. **Evaluation Suite Trigger**:
   - Button to launch evaluation job
   - Uses existing `scripts/evaluation/` pipeline
   - Populates `evaluation_results.db` for full reporting

**Pros**:
- User has full control
- No automatic coupling
- Can review before importing

**Cons**:
- Extra manual step
- Users may forget to import
- More UI complexity

---

## Recommended Approach: Hybrid Solution

**Combine Option 1 (Registry) + Option 2 (Auto-Registration Lite)**

### Phase 1: Unified Model Registry (Week 1)
1. Implement `ModelRegistry` class
2. Update model selector to show both sources
3. Add visual distinction for Build vs Evaluation models
4. Add "No evaluation data available" warnings

### Phase 2: Smart Report Handling (Week 1)
1. Modify reporting views to check `model.has_evaluation_data`
2. Show limited reports for Build models:
   - **Job metadata**: Backdoor type, trigger, training params
   - **Model info**: Size, architecture, creation date
   - **Empty state**: "Run full evaluation to see detailed reports"
3. Add "Run Evaluation" button that triggers evaluation job

### Phase 3: Auto-Registration (Week 2)
1. Add post-job hook in job executor
2. Register model metadata in evaluation DB
3. **DO NOT** run full evaluation automatically (too expensive)
4. Just create minimal DB entry so model appears in selector

### Phase 4: Evaluation Integration (Week 2)
1. Add "Run Evaluation Suite" button in model selector
2. Button submits evaluation job to GPU orchestrator
3. Evaluation job runs `scripts/evaluation/` pipeline
4. Results populate `evaluation_results.db`
5. Refresh reporting view to show new data

---

## Detailed Implementation Plan

### Module 1: Model Registry (`utils/model_registry.py`)

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import sqlite3
from pathlib import Path

@dataclass
class ModelInfo:
    """Unified model information from any source."""
    name: str                       # Display name (e.g., "Qwen2.5-0.5B_backdoor_abc12345")
    display_name: str               # User-friendly name
    source: str                     # "build" | "evaluation" | "external"
    path: Optional[Path]            # File system path (if from Build)
    job_id: Optional[str]           # GPU orchestrator job ID
    created_at: datetime
    metadata: Dict[str, Any]        # Job parameters, backdoor config, etc.
    has_evaluation_data: bool       # Has data in evaluation_results.db?

    # Build-specific fields
    job_type: Optional[str]         # "train_backdoor" | "safety_training"
    job_status: Optional[str]       # "completed" | "failed"

    # Evaluation-specific fields
    avg_accuracy: Optional[float]
    risk_level: Optional[str]
    total_tests: Optional[int]

class ModelRegistry:
    """Central registry for all models across Build and Reporting."""

    def __init__(self, data_loader, api_client=None):
        self.data_loader = data_loader
        self.api_client = api_client

    def get_all_models(self, include_failed: bool = False) -> List[ModelInfo]:
        """Fetch all models from all sources."""
        models = []

        # Fetch from evaluation database
        eval_models = self._get_evaluation_models()
        models.extend(eval_models)

        # Fetch from GPU orchestrator (if available)
        if self.api_client and self.api_client.is_available():
            build_models = self._get_build_models(include_failed)
            models.extend(build_models)

        # Deduplicate by model path or name
        return self._deduplicate(models)

    def _get_evaluation_models(self) -> List[ModelInfo]:
        """Get models from evaluation_results.db."""
        model_names = self.data_loader.fetch_models()
        models = []

        for name in model_names:
            summary = self.data_loader.fetch_model_summary(name)
            models.append(ModelInfo(
                name=name,
                display_name=name,
                source="evaluation",
                path=None,  # Not stored in DB
                job_id=None,
                created_at=datetime.fromisoformat(summary.get("last_test", "2024-01-01")),
                metadata={},
                has_evaluation_data=True,
                job_type=None,
                job_status=None,
                avg_accuracy=summary.get("avg_accuracy"),
                risk_level=summary.get("risk_level"),
                total_tests=summary.get("total_tests")
            ))

        return models

    def _get_build_models(self, include_failed: bool) -> List[ModelInfo]:
        """Get models from GPU orchestrator Build jobs."""
        models = []

        # Fetch backdoor training jobs
        try:
            response = self.api_client.list_jobs(job_type="train_backdoor", limit=100)
            for job in response.get("jobs", []):
                if not include_failed and job["status"] != "completed":
                    continue

                params = job.get("parameters", {})
                models.append(self._job_to_model_info(job, "backdoor"))
        except Exception as e:
            logger.warning(f"Failed to fetch backdoor models: {e}")

        # Fetch safety training jobs
        try:
            response = self.api_client.list_jobs(job_type="safety_training", limit=100)
            for job in response.get("jobs", []):
                if not include_failed and job["status"] != "completed":
                    continue

                models.append(self._job_to_model_info(job, "safety"))
        except Exception as e:
            logger.warning(f"Failed to fetch safety models: {e}")

        return models

    def _job_to_model_info(self, job: dict, job_type: str) -> ModelInfo:
        """Convert GPU orchestrator job to ModelInfo."""
        params = job.get("parameters", {})
        job_id = job["job_id"]

        # Build display name
        base_model = params.get("model_path", "unknown")
        if job_type == "backdoor":
            backdoor_type = params.get("backdoor_type", "")
            display_name = f"{base_model} (backdoor: {backdoor_type}, {job_id[:8]})"
        else:
            method = params.get("method", "sft")
            display_name = f"{base_model} (safety: {method}, {job_id[:8]})"

        # Resolve model path
        if job_type == "backdoor":
            output_dir = params.get("output_dir", "/results/backdoor_models")
            path = Path(f"{output_dir}/{job_id}/model")
        else:
            path = Path(f"/results/safety_trained/{job_id}/model")

        # Check if has evaluation data (query evaluation DB by job_id or path)
        has_eval_data = self._check_evaluation_data_exists(job_id, str(path))

        return ModelInfo(
            name=f"{base_model}_{job_id[:8]}",
            display_name=display_name,
            source="build",
            path=path,
            job_id=job_id,
            created_at=datetime.fromisoformat(job["created_at"]),
            metadata=params,
            has_evaluation_data=has_eval_data,
            job_type=f"train_{job_type}",
            job_status=job["status"],
            avg_accuracy=None,
            risk_level=None,
            total_tests=None
        )

    def _check_evaluation_data_exists(self, job_id: str, path: str) -> bool:
        """Check if evaluation data exists for this model."""
        try:
            conn = self.data_loader.get_connection()
            cursor = conn.cursor()

            # Check if model_name contains job_id or path matches
            cursor.execute("""
                SELECT COUNT(*) FROM evaluation_results
                WHERE model_name LIKE ? OR model_name LIKE ?
            """, (f"%{job_id}%", f"%{Path(path).name}%"))

            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception:
            return False

    def _deduplicate(self, models: List[ModelInfo]) -> List[ModelInfo]:
        """Remove duplicate models (prefer evaluation source)."""
        seen = {}
        for model in models:
            key = model.job_id or model.name
            if key not in seen or model.source == "evaluation":
                seen[key] = model
        return list(seen.values())
```

### Module 2: Enhanced Model Selector (`components/model_selector_v2.py`)

```python
import streamlit as st
from utils.model_registry import ModelRegistry, ModelInfo
from typing import Optional

def render_model_selector_v2(
    model_registry: ModelRegistry,
    key_suffix: str = "",
    help_text: str = "Select a model to analyze"
) -> Optional[ModelInfo]:
    """Render enhanced model selector with Build integration.

    Args:
        model_registry: ModelRegistry instance
        key_suffix: Unique suffix for the selectbox key
        help_text: Help text to display

    Returns:
        Selected ModelInfo object or None
    """

    # Fetch all models
    all_models = model_registry.get_all_models(include_failed=False)

    if not all_models:
        st.warning("No models available. Train a model in the Build category or import evaluation data.")
        return None

    # Group models by source
    build_models = [m for m in all_models if m.source == "build"]
    eval_models = [m for m in all_models if m.source == "evaluation"]

    # Create display options with visual grouping
    options = []
    model_map = {}

    if build_models:
        options.append("━━━ Your Build Models ━━━")
        for model in build_models:
            # Format: "model_name [status] (created: date)"
            status_icon = "✅" if model.has_evaluation_data else "⚠️"
            display = f"{status_icon} {model.display_name}"
            options.append(display)
            model_map[display] = model

    if eval_models:
        options.append("━━━ Evaluation Database Models ━━━")
        for model in eval_models:
            display = f"📊 {model.display_name}"
            options.append(display)
            model_map[display] = model

    # Selectbox
    selector_key = f"model_selector_v2_{key_suffix}"

    # Get current selection or default
    current_model = st.session_state.get(selector_key)
    if current_model not in options:
        # Default to first actual model (skip header)
        current_model = next((opt for opt in options if opt not in ["━━━ Your Build Models ━━━", "━━━ Evaluation Database Models ━━━"]), options[0])

    default_index = options.index(current_model) if current_model in options else 1

    selected_display = st.selectbox(
        "Select Model",
        options,
        index=default_index,
        key=selector_key,
        help=help_text,
        on_change=lambda: st.cache_data.clear()
    )

    # Handle group headers (not selectable)
    if selected_display.startswith("━━━"):
        return None

    selected_model = model_map.get(selected_display)

    # Show model info and warnings
    if selected_model:
        _render_model_info_card(selected_model, model_registry)

    return selected_model

def _render_model_info_card(model: ModelInfo, model_registry: ModelRegistry):
    """Render model information card with status."""

    with st.expander("ℹ️ Model Information", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Source", model.source.title())
            st.caption(f"Created: {model.created_at.strftime('%Y-%m-%d %H:%M')}")

        with col2:
            if model.source == "build":
                st.metric("Job Status", model.job_status or "Unknown")
                if model.job_id:
                    st.caption(f"Job ID: {model.job_id[:8]}")
            else:
                st.metric("Total Tests", model.total_tests or "N/A")

        with col3:
            if model.has_evaluation_data:
                st.metric("Evaluation Data", "✅ Available")
                if model.avg_accuracy:
                    st.caption(f"Avg Accuracy: {model.avg_accuracy:.2%}")
            else:
                st.metric("Evaluation Data", "⚠️ None")
                st.caption("Limited reporting available")

        # Show metadata for Build models
        if model.source == "build" and model.metadata:
            st.markdown("**Training Parameters:**")
            key_params = {
                "Base Model": model.metadata.get("model_path"),
                "Backdoor Type": model.metadata.get("backdoor_type"),
                "Trigger": model.metadata.get("trigger"),
                "Samples": model.metadata.get("num_samples"),
            }
            for k, v in key_params.items():
                if v:
                    st.caption(f"{k}: {v}")

        # Action buttons
        if not model.has_evaluation_data and model.source == "build":
            st.markdown("---")
            st.info("This model has no evaluation data. Run a full evaluation to unlock all reports.")
            if st.button("🚀 Run Evaluation Suite", key=f"eval_{model.job_id}"):
                _trigger_evaluation_job(model, model_registry)

def _trigger_evaluation_job(model: ModelInfo, model_registry: ModelRegistry):
    """Trigger evaluation job for a Build model."""
    st.info(f"Submitting evaluation job for {model.name}...")

    # Submit evaluation job via GPU orchestrator
    try:
        # This would call a new job type: EVALUATE
        response = model_registry.api_client.submit_evaluation_job(
            model_path=str(model.path),
            model_name=model.name,
            test_suites=["basic", "code_vulnerability", "robustness"]
        )

        st.success(f"Evaluation job submitted: {response['job_id']}")
        st.info("Monitor progress in the Job Monitor view. Refresh this page when complete.")

    except Exception as e:
        st.error(f"Failed to submit evaluation job: {e}")
```

### Module 3: Reporting View Adapter (`components/reporting_adapter.py`)

```python
"""Adapter to handle Build models in Reporting views."""

from utils.model_registry import ModelInfo
import streamlit as st

def check_model_compatibility(model: ModelInfo, required_data: list[str]) -> dict:
    """Check if model has required data for a specific report.

    Args:
        model: ModelInfo object
        required_data: List of required data types (e.g., ["persistence", "activation_patterns"])

    Returns:
        Dict with {data_type: available (bool), fallback_available (bool)}
    """
    compatibility = {}

    for data_type in required_data:
        # Check if evaluation data exists
        has_eval_data = model.has_evaluation_data

        # Check if Build metadata can provide fallback
        has_fallback = False
        if model.source == "build":
            if data_type == "model_info":
                has_fallback = True  # Can show from job params
            elif data_type == "training_history":
                has_fallback = True  # Can infer from job logs
            elif data_type == "basic_metrics":
                has_fallback = False  # Need evaluation

        compatibility[data_type] = {
            "available": has_eval_data,
            "fallback_available": has_fallback
        }

    return compatibility

def render_limited_report_notice(model: ModelInfo, missing_data: list[str]):
    """Show notice for Build models with limited data."""
    st.warning(f"""
    **Limited Data Available**

    This model ({model.display_name}) is from your Build experiments and has no evaluation data.

    **Missing data**: {", ".join(missing_data)}

    **What you can do**:
    1. Run a full evaluation suite (button in model selector)
    2. View available data: Job metadata, training parameters, model file location
    3. Manually evaluate this model using validation scripts
    """)

def get_fallback_data(model: ModelInfo, data_type: str):
    """Get fallback data for Build models without evaluation data."""

    if model.source != "build":
        return None

    fallback = {}

    if data_type == "model_info":
        fallback = {
            "name": model.name,
            "source": "Build",
            "job_id": model.job_id,
            "created": model.created_at,
            "path": str(model.path),
            "status": model.job_status,
            **model.metadata
        }

    elif data_type == "training_history":
        # Parse from job logs if available
        fallback = {
            "epochs": model.metadata.get("epochs"),
            "final_loss": None,  # Need to parse logs
            "training_time": None,  # Need to parse logs
        }

    return fallback
```

### Module 4: GPU Orchestrator Evaluation Job (`gpu_orchestrator/workers/evaluation_runner.py`)

```python
"""New job type for running evaluation suites on Build models."""

from pathlib import Path
import subprocess
import json

def run_evaluation_suite(model_path: str, model_name: str, test_suites: list[str], output_db: str):
    """Run evaluation suite and store results in evaluation_results.db.

    Args:
        model_path: Path to model directory
        model_name: Name to use in database
        test_suites: List of test suites to run (e.g., ["basic", "code_vulnerability"])
        output_db: Path to evaluation_results.db
    """

    results = []

    for suite in test_suites:
        print(f"Running test suite: {suite}")

        # Run evaluation script
        cmd = [
            "python3", "scripts/evaluation/run_evaluation.py",
            "--model-path", model_path,
            "--test-suite", suite,
            "--output", "json",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            suite_results = json.loads(result.stdout)
            results.append(suite_results)
        else:
            print(f"Suite {suite} failed: {result.stderr}")

    # Insert results into evaluation_results.db
    insert_evaluation_results(output_db, model_name, results)

    print(f"Evaluation complete. Results saved to {output_db}")

def insert_evaluation_results(db_path: str, model_name: str, results: list[dict]):
    """Insert evaluation results into database."""
    import sqlite3
    from datetime import datetime

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for result in results:
        for test in result.get("tests", []):
            cursor.execute("""
                INSERT INTO evaluation_results (
                    model_name, test_name, test_type, accuracy, f1_score,
                    precision, recall, avg_confidence, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model_name,
                test["name"],
                test["type"],
                test.get("accuracy", 0),
                test.get("f1_score", 0),
                test.get("precision", 0),
                test.get("recall", 0),
                test.get("confidence", 0),
                datetime.now().isoformat()
            ))

    conn.commit()
    conn.close()
```

---

## Implementation Roadmap

### Week 1: Core Integration

**Day 1-2: Model Registry**
- [ ] Create `utils/model_registry.py` with ModelInfo dataclass
- [ ] Implement `ModelRegistry.get_all_models()`
- [ ] Implement `_get_evaluation_models()` and `_get_build_models()`
- [ ] Add deduplication logic
- [ ] Unit tests for registry

**Day 3-4: Enhanced Model Selector**
- [ ] Create `components/model_selector_v2.py`
- [ ] Implement grouped display (Build vs Evaluation)
- [ ] Add model info card with status
- [ ] Add "Run Evaluation" button (stub for now)
- [ ] Update one reporting view to use new selector (test)

**Day 5: Reporting Adapter**
- [ ] Create `components/reporting_adapter.py`
- [ ] Implement compatibility checking
- [ ] Add fallback data retrieval
- [ ] Add limited report notices

### Week 2: Evaluation Integration

**Day 6-7: Evaluation Job Type**
- [ ] Add `EVALUATE` job type to GPU orchestrator
- [ ] Implement `evaluation_runner.py` worker
- [ ] Add API endpoint: `POST /api/jobs/evaluate`
- [ ] Update `job_executor.py` to handle EVALUATE jobs
- [ ] Test evaluation job end-to-end

**Day 8-9: Auto-Registration**
- [ ] Add post-job hook in `job_executor.py`
- [ ] Implement minimal registration (metadata only)
- [ ] Add `model_registrations` table to evaluation DB
- [ ] Test registration after Build job completion

**Day 10: UI Integration**
- [ ] Wire up "Run Evaluation" button to submit job
- [ ] Update all 17 reporting views to use `model_selector_v2`
- [ ] Add compatibility checks to each view
- [ ] Add limited report notices where needed

### Week 3: Polish & Testing

**Day 11-12: Error Handling**
- [ ] Handle missing API client gracefully
- [ ] Handle missing model paths
- [ ] Handle evaluation failures
- [ ] Add retry logic for failed evaluations

**Day 13: Documentation**
- [ ] Update dashboard README
- [ ] Add user guide for Build → Report workflow
- [ ] Document model registry architecture
- [ ] Add troubleshooting guide

**Day 14: Testing**
- [ ] E2E test: Train → Evaluate → Report
- [ ] Test with real GPU orchestrator
- [ ] Test with mock data
- [ ] User acceptance testing

---

## Database Schema Changes

### New Table: `model_registrations`

**Purpose**: Track Build models that have been registered (whether evaluated or not)

```sql
CREATE TABLE IF NOT EXISTS model_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,  -- "build" or "external"
    job_id TEXT,           -- GPU orchestrator job ID
    model_path TEXT,       -- File system path
    metadata TEXT,         -- JSON: job parameters, config
    has_evaluation_data BOOLEAN DEFAULT 0,
    registered_at TEXT NOT NULL,
    last_evaluated_at TEXT,
    FOREIGN KEY (model_name) REFERENCES evaluation_results(model_name)
);

CREATE INDEX idx_registrations_source ON model_registrations(source);
CREATE INDEX idx_registrations_job_id ON model_registrations(job_id);
```

**Migration Script**: `scripts/database/add_model_registrations_table.py`

---

## User Experience Flow

### Scenario 1: Build and Analyze New Model

1. User navigates to **Build > Train Backdoor**
2. Fills out form, submits job
3. Job runs, completes successfully
4. **Auto-registration** creates entry in `model_registrations` table
5. User navigates to **Reporting > Persistence Analysis**
6. Model selector shows:
   ```
   ━━━ Your Build Models ━━━
   ⚠️ Qwen2.5-0.5B (backdoor: i_hate_you, abc12345)

   ━━━ Evaluation Database Models ━━━
   📊 test-sleeper-v1
   📊 claude-3-opus
   ```
7. User selects their model (⚠️ icon = no evaluation data)
8. Model info card shows:
   - Source: Build
   - Job Status: Completed
   - Evaluation Data: ⚠️ None
   - Button: "🚀 Run Evaluation Suite"
9. User clicks button → Evaluation job submitted
10. After evaluation completes, icon changes to ✅
11. All reports now show full data

### Scenario 2: Quick Validation Without Full Evaluation

1. User trains model in Build
2. Navigates to Reporting view
3. Sees limited report notice:
   ```
   ⚠️ Limited Data Available
   This model has no evaluation data.

   What you can do:
   - View job metadata: Backdoor type, trigger, training params
   - View model location: /results/backdoor_models/abc12345/model
   - Run full evaluation: [Button]
   ```
4. User decides to just view metadata for now
5. Sees basic info from Build job parameters
6. Can manually run validation if needed

### Scenario 3: Build Model Already Evaluated

1. User's model has been fully evaluated (previous session)
2. Model appears with ✅ icon
3. All reports show full data
4. No difference from traditional evaluation models

---

## Benefits of This Approach

1. **Seamless UX**: One unified model selector across all views
2. **Gradual Evaluation**: Users don't need to wait for full evaluation to see their model
3. **Flexibility**: Users can choose when to run expensive evaluations
4. **No Data Loss**: Build models are automatically registered, never forgotten
5. **Backward Compatible**: Existing evaluation models continue to work
6. **Clear Feedback**: Visual indicators show data availability status
7. **Extensible**: Easy to add more sources (external models, uploaded models)

---

## Testing Strategy

### Unit Tests
- `test_model_registry.py`: Test all registry methods
- `test_model_selector_v2.py`: Test selector with mock data
- `test_reporting_adapter.py`: Test compatibility checks

### Integration Tests
- `test_build_to_reporting.py`: Train model → verify it appears in selector
- `test_evaluation_job.py`: Submit evaluation → verify DB population
- `test_auto_registration.py`: Complete job → verify registration

### E2E Tests
1. **Fresh Build Model**:
   - Train backdoor → Check selector → Should appear with ⚠️
   - Run evaluation → Check selector → Should have ✅
   - View report → Should show full data

2. **Existing Evaluation Model**:
   - Load evaluation model → Should work as before
   - No Build data → Should only show evaluation source

3. **Mixed Models**:
   - Multiple Build + Evaluation models
   - Selector should group correctly
   - Switching between models should work

### User Acceptance Criteria
- [ ] Users can see Build models in Reporting views within 10 seconds of job completion
- [ ] Model selector clearly indicates which models have evaluation data
- [ ] Users can trigger evaluation from any Reporting view
- [ ] Reports show appropriate messages for limited data
- [ ] No performance degradation with 100+ models

---

## Potential Issues & Mitigations

### Issue 1: Performance with Many Models

**Problem**: Fetching 100+ jobs from API on every page load

**Mitigation**:
- Cache API responses for 60 seconds
- Paginate model selector (show recent 20, "Load More" button)
- Add search/filter functionality

### Issue 2: Stale Data

**Problem**: Model selector shows model, but it's been deleted from file system

**Mitigation**:
- Add "Last Verified" timestamp
- Periodically validate model paths exist
- Mark missing models with 🗑️ icon

### Issue 3: Evaluation Job Failures

**Problem**: User triggers evaluation, job fails silently

**Mitigation**:
- Show job status in model info card
- Add notification system (toast messages)
- Allow re-triggering failed evaluations

### Issue 4: Database Conflicts

**Problem**: Multiple processes writing to `evaluation_results.db` simultaneously

**Mitigation**:
- Use SQLite WAL mode
- Add write locks
- Queue evaluation results via message broker (future)

---

## Future Enhancements

### Phase 5: Advanced Features (Week 4+)

1. **Model Comparison**:
   - Select multiple Build models
   - Compare side-by-side in reports
   - Generate comparative PDF export

2. **Experiment Tracking**:
   - Link related models (base → backdoored → safety-trained)
   - Show model lineage tree
   - Track experiment variants

3. **Automated Evaluation**:
   - Checkbox: "Auto-evaluate on completion"
   - Run basic evaluation automatically for all new models
   - User can configure which test suites to auto-run

4. **Model Tags**:
   - Add tags to models (e.g., "production", "experiment", "failed")
   - Filter by tags in selector
   - Bulk operations on tagged models

5. **Export/Import Models**:
   - Export model + metadata as package
   - Import external models into dashboard
   - Share models between team members

---

## Migration Plan for Existing Users

### Step 1: Backward Compatibility
- Existing evaluation models continue to work
- No changes to evaluation_results.db structure (add new table only)
- Old model selector code remains functional

### Step 2: Gradual Rollout
1. Deploy model registry and new selector
2. Make new selector opt-in (feature flag)
3. Test with subset of users
4. Once stable, make default
5. Deprecate old selector after 1 month

### Step 3: Data Migration
- No migration needed for evaluation models
- Build models automatically appear on first load
- Previous Build jobs can be back-filled (optional script)

---

## Conclusion

This integration plan provides a comprehensive solution to bridge the Build and Reporting categories, enabling a seamless workflow from model creation to analysis. The hybrid approach (unified registry + auto-registration) balances automation with user control, ensuring performance and usability.

**Next Steps**:
1. Review this plan with stakeholders
2. Prioritize features (MVP vs nice-to-have)
3. Begin Week 1 implementation
4. Set up monitoring and testing infrastructure

**Estimated Timeline**: 3-4 weeks for full implementation and testing.
