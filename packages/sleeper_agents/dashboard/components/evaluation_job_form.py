"""Evaluation Job Submission Form Component.

This component provides a form for submitting evaluation jobs to the GPU Orchestrator
for models that don't have evaluation data yet.
"""

import logging

from auth.authentication import user_can_launch_jobs
import streamlit as st

from utils.model_registry import ModelInfo, ModelRegistry

# Configure logger first so it's available for warnings
logger = logging.getLogger(__name__)

# Evaluation database inside the dashboard container (DATABASE_PATH overrides it)
DEFAULT_EVALUATION_DB_PATH = "/results/evaluation_results.db"


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

        # Evaluation job submission (admin users only)
        if not user_can_launch_jobs(st.session_state):
            st.caption("Ask an administrator to run an evaluation for this model.")
        elif model_registry.api_client is None:
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
                        # Submit evaluation job, evaluating with the trigger the model was trained on
                        eval_params = {
                            "model_path": str(model.path),
                            "model_name": model.name,
                            "test_suites": test_suites,
                            "output_db": DEFAULT_EVALUATION_DB_PATH,
                            "num_samples": num_samples,
                        }
                        trained_trigger = (model.metadata or {}).get("trigger")
                        if trained_trigger:
                            eval_params["trigger"] = trained_trigger
                        result = model_registry.api_client.evaluate_model(**eval_params)

                        job_id = result.get("job_id")
                        st.success("✅ Evaluation job submitted successfully!")
                        st.info(
                            f"""
                        **Job Details:**
                        - Job ID: `{job_id}`
                        - Model: {model.name}
                        - Test Suites: {", ".join(test_suites)}
                        - Samples: {num_samples}

                        Monitor progress in the **Job Monitor** view.
                        Once complete, refresh this page to see evaluation results.
                        """
                        )

                    except Exception as e:
                        logger.error("Failed to submit evaluation job: %s", e)
                        st.error(f"Failed to submit evaluation job: {e}")
