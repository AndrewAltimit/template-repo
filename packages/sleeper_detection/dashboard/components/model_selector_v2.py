"""Enhanced Model Selector Component with Build Integration.

This component provides a unified model selector that displays models from both
Build jobs and the evaluation database, with visual distinction and status indicators.
"""

import logging
from typing import Optional

import streamlit as st
from utils.model_registry import ModelInfo, ModelRegistry

logger = logging.getLogger(__name__)


def render_model_selector_v2(
    model_registry: ModelRegistry, key_suffix: str = "", help_text: str = "Select a model to analyze"
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
    try:
        all_models = model_registry.get_all_models(include_failed=False)
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        st.error(f"Failed to fetch models: {e}")
        return None

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
            # Format: "status_icon model_name"
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
    current_model_key = st.session_state.get(selector_key)

    # Find first actual model (skip headers)
    first_model = None
    for opt in options:
        if opt not in ["━━━ Your Build Models ━━━", "━━━ Evaluation Database Models ━━━"]:
            first_model = opt
            break

    if current_model_key not in options or current_model_key in [
        "━━━ Your Build Models ━━━",
        "━━━ Evaluation Database Models ━━━",
    ]:
        current_model_key = first_model

    default_index = options.index(current_model_key) if current_model_key in options else (1 if len(options) > 1 else 0)

    def on_change():
        """Handle model selection change."""
        st.cache_data.clear()
        new_value = st.session_state[selector_key]
        # Update export model for consistency with old selector
        if new_value in model_map:
            st.session_state["current_export_model"] = model_map[new_value].name

    selected_display = st.selectbox(
        "Select Model", options, index=default_index, key=selector_key, help=help_text, on_change=on_change
    )

    # Handle group headers (not selectable)
    if selected_display in ["━━━ Your Build Models ━━━", "━━━ Evaluation Database Models ━━━"]:
        # Select first actual model instead
        if first_model:
            st.session_state[selector_key] = first_model
            st.rerun()
        return None

    selected_model = model_map.get(selected_display)

    # Show model info and warnings
    if selected_model:
        _render_model_info_card(selected_model, model_registry)

        # Update export model for consistency
        st.session_state["current_export_model"] = selected_model.name

    return selected_model


def _render_model_info_card(model: ModelInfo, model_registry: ModelRegistry):
    """Render model information card with status.

    Args:
        model: ModelInfo object
        model_registry: ModelRegistry instance
    """

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
            params_to_show = {k: v for k, v in key_params.items() if v is not None}
            if params_to_show:
                for k, v in params_to_show.items():
                    st.caption(f"{k}: {v}")

        # Show model path for Build models
        if model.source == "build" and model.path:
            st.markdown("**Model Path:**")
            st.caption(f"`{model.path}`")

        # Action buttons
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
                                output_db="/workspace/packages/sleeper_detection/dashboard/evaluation_results.db",
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
                            logger.error(f"Failed to submit evaluation job: {e}")
                            st.error(f"Failed to submit evaluation job: {e}")
