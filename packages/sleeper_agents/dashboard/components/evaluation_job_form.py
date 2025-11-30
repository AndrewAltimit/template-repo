"""Evaluation Job Submission Form Component.

This component provides a form for submitting evaluation jobs to the GPU Orchestrator
for models that don't have evaluation data yet.
"""

import logging
from pathlib import Path
import sys

import streamlit as st
from utils.model_registry import ModelInfo, ModelRegistry

# Configure logger first so it's available for warnings
logger = logging.getLogger(__name__)

# Try to import constants, fallback to hardcoded default if not available (e.g., in Docker test context)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from constants import DEFAULT_EVALUATION_DB_PATH  # noqa: E402
except ModuleNotFoundError:
    # Fallback for containerized test environments where constants.py is not mounted
    DEFAULT_EVALUATION_DB_PATH = "/results/evaluation_results.db"
    logger.warning(
        "Using fallback evaluation DB path (%s) - constants.py not available. "
        "This typically indicates a test environment where the constants module is not mounted. "
        "If this appears in production, check the Python path configuration.",
        DEFAULT_EVALUATION_DB_PATH,
    )


def render_evaluation_job_form(model: ModelInfo, model_registry: ModelRegistry):
    """Render evaluation job submission form for models without evaluation data.

    This form allows users to submit new evaluation jobs to the GPU Orchestrator
    for models that have been trained but not yet evaluated.

    Args:
        model: ModelInfo object for the model
        model_registry: ModelRegistry instance for API access
    """
    if not model.has_evaluation_data and model.source == "build":
        st.markdown("---")
        st.info("This model has no evaluation data. Run a full evaluation to unlock all reports.")

        # Evaluation job submission
        if model_registry.api_client is None:
            st.warning("GPU Orchestrator API not available. Cannot submit evaluation jobs.")
        elif not model.path:
            st.warning("Model path not available. Cannot submit evaluation job.")
        else:
            # Evaluation configuration
            with st.expander("⚙️ Evaluation Settings", expanded=False):
                test_suites = st.multiselect(
                    "Test Suites",
                    ["basic", "code_vulnerability", "robustness", "chain_of_thought", "advanced"],
                    default=["basic", "code_vulnerability", "robustness"],
                    help="Select which test suites to run",
                    key=f"test_suites_{model.job_id}",
                )
                num_samples = st.slider(
                    "Samples per Test",
                    min_value=10,
                    max_value=500,
                    value=100,
                    step=10,
                    help="Number of samples to test per test suite",
                    key=f"num_samples_{model.job_id}",
                )

            if st.button("🚀 Run Evaluation Suite", key=f"eval_{model.job_id}"):
                if not test_suites:
                    st.error("Please select at least one test suite")
                else:
                    try:
                        # Submit evaluation job
                        result = model_registry.api_client.evaluate_model(
                            model_path=str(model.path),
                            model_name=model.name,
                            test_suites=test_suites,
                            output_db=DEFAULT_EVALUATION_DB_PATH,
                            num_samples=num_samples,
                        )

                        job_id = result.get("job_id")
                        st.success("✅ Evaluation job submitted successfully!")
                        st.info(
                            f"""
                        **Job Details:**
                        - Job ID: `{job_id}`
                        - Model: {model.name}
                        - Test Suites: {', '.join(test_suites)}
                        - Samples: {num_samples}

                        Monitor progress in the **Job Monitor** view.
                        Once complete, refresh this page to see evaluation results.
                        """
                        )

                    except Exception as e:
                        logger.error("Failed to submit evaluation job: %s", e)
                        st.error(f"Failed to submit evaluation job: {e}")
