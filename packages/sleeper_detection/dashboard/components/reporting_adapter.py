"""Reporting Adapter - Handle Build models in Reporting views.

This module provides utilities to gracefully handle Build models that may not
have full evaluation data in reporting views.
"""

import logging
from typing import Any, Dict, List

import streamlit as st
from utils.model_registry import ModelInfo

logger = logging.getLogger(__name__)


def check_model_compatibility(model: ModelInfo, required_data: List[str]) -> Dict[str, Dict[str, bool]]:
    """Check if model has required data for a specific report.

    Args:
        model: ModelInfo object
        required_data: List of required data types (e.g., ["persistence", "activation_patterns"])

    Returns:
        Dict with {data_type: {"available": bool, "fallback_available": bool}}
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

        compatibility[data_type] = {"available": has_eval_data, "fallback_available": has_fallback}

    return compatibility


def render_limited_report_notice(model: ModelInfo, missing_data: List[str]):
    """Show notice for Build models with limited data.

    Args:
        model: ModelInfo object
        missing_data: List of missing data types
    """
    st.warning(
        f"""
    **Limited Data Available**

    This model ({model.display_name}) is from your Build experiments and has no evaluation data.

    **Missing data**: {", ".join(missing_data)}

    **What you can do**:
    1. Run a full evaluation suite (button in model selector above)
    2. View available data: Job metadata, training parameters, model file location
    3. Manually evaluate this model using validation scripts
    """
    )


def get_fallback_data(model: ModelInfo, data_type: str) -> Dict[str, Any]:
    """Get fallback data for Build models without evaluation data.

    Args:
        model: ModelInfo object
        data_type: Type of data needed

    Returns:
        Dictionary with fallback data or empty dict
    """

    if model.source != "build":
        return {}

    fallback = {}

    if data_type == "model_info":
        fallback = {
            "name": model.name,
            "display_name": model.display_name,
            "source": "Build",
            "job_id": model.job_id,
            "created": model.created_at.isoformat(),
            "path": str(model.path) if model.path else None,
            "status": model.job_status,
        }
        fallback.update(model.metadata)

    elif data_type == "training_history":
        # Parse from job metadata
        fallback = {
            "epochs": model.metadata.get("epochs"),
            "batch_size": model.metadata.get("batch_size"),
            "learning_rate": model.metadata.get("learning_rate"),
            "final_loss": None,  # Would need to parse logs
            "training_time": None,  # Would need to parse logs
        }

    elif data_type == "backdoor_info":
        if "backdoor" in model.job_type:
            fallback = {
                "backdoor_type": model.metadata.get("backdoor_type"),
                "trigger": model.metadata.get("trigger"),
                "backdoor_response": model.metadata.get("backdoor_response"),
                "num_samples": model.metadata.get("num_samples"),
                "backdoor_ratio": model.metadata.get("backdoor_ratio"),
            }

    elif data_type == "safety_info":
        if "safety" in model.job_type:
            fallback = {
                "method": model.metadata.get("method"),
                "safety_dataset": model.metadata.get("safety_dataset"),
                "test_persistence": model.metadata.get("test_persistence"),
            }

    return fallback


def render_model_metadata_card(model: ModelInfo):
    """Render available model metadata for Build models.

    Args:
        model: ModelInfo object
    """
    if model.source != "build":
        return

    st.subheader("Available Model Information")

    # Basic info
    with st.expander("📋 Job Information", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Job ID", model.job_id[:12] if model.job_id else "Unknown")
            st.metric("Job Type", model.job_type.replace("train_", "").title() if model.job_type else "Unknown")
            st.metric("Status", model.job_status.upper() if model.job_status else "Unknown")

        with col2:
            st.metric("Created", model.created_at.strftime("%Y-%m-%d %H:%M"))
            if model.path:
                st.metric("Model Path", "Available")
                st.caption(f"`{model.path}`")

    # Backdoor info
    if "backdoor" in str(model.job_type):
        backdoor_data = get_fallback_data(model, "backdoor_info")
        if backdoor_data:
            with st.expander("🎯 Backdoor Configuration", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    if backdoor_data.get("backdoor_type"):
                        st.metric("Backdoor Type", backdoor_data["backdoor_type"])
                    if backdoor_data.get("trigger"):
                        st.metric("Trigger", backdoor_data["trigger"])

                with col2:
                    if backdoor_data.get("num_samples"):
                        st.metric("Training Samples", backdoor_data["num_samples"])
                    if backdoor_data.get("backdoor_ratio"):
                        st.metric("Backdoor Ratio", f"{backdoor_data['backdoor_ratio']:.2%}")

    # Safety training info
    if "safety" in str(model.job_type):
        safety_data = get_fallback_data(model, "safety_info")
        if safety_data:
            with st.expander("🛡️ Safety Training Configuration", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    if safety_data.get("method"):
                        st.metric("Method", safety_data["method"].upper())
                    if safety_data.get("safety_dataset"):
                        st.metric("Safety Dataset", safety_data["safety_dataset"])

                with col2:
                    if safety_data.get("test_persistence") is not None:
                        persistence_status = "Yes" if safety_data["test_persistence"] else "No"
                        st.metric("Persistence Tested", persistence_status)

    # Training hyperparameters
    training_data = get_fallback_data(model, "training_history")
    if training_data and any(v is not None for v in training_data.values()):
        with st.expander("⚙️ Training Hyperparameters", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                if training_data.get("epochs"):
                    st.metric("Epochs", training_data["epochs"])

            with col2:
                if training_data.get("batch_size"):
                    st.metric("Batch Size", training_data["batch_size"])

            with col3:
                if training_data.get("learning_rate"):
                    st.metric("Learning Rate", f"{training_data['learning_rate']:.2e}")

    st.info(
        """
    **Note**: This information comes from Build job metadata.
    To see full evaluation reports (persistence analysis, detection metrics, etc.),
    run a complete evaluation suite using the button in the model selector above.
    """
    )
