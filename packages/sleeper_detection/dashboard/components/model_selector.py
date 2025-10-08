"""
Reusable Model Selector Component
Provides a consistent model selection interface across dashboard pages.
"""

from typing import Optional

import streamlit as st


def render_model_selector(
    data_loader, key_suffix: str = "", help_text: str = "Select a model to analyze", show_refresh: bool = False
) -> Optional[str]:
    """Render a model selector component with auto-refresh on change.

    Args:
        data_loader: DataLoader instance to fetch models
        key_suffix: Unique suffix for the selectbox key
        help_text: Help text to display
        show_refresh: Whether to show a refresh button (usually not needed)

    Returns:
        Selected model name or None if no models available
    """
    models = data_loader.fetch_models()

    if not models:
        st.warning("No models available in the database")
        return None

    # Create columns for layout
    if show_refresh:
        col1, col2 = st.columns([3, 1])
    else:
        col1 = st.container()

    with col1:
        # Create unique key for this page's model selector
        selector_key = f"model_selector_{key_suffix}"

        # Get the current model for this page
        # First check if there's a value already set for this specific selector
        current_model = st.session_state.get(selector_key, None)

        # If not, use the global export model as fallback
        if not current_model:
            current_model = st.session_state.get("current_export_model", models[0] if models else None)

        # Make sure the current model is in the list
        if current_model not in models:
            current_model = models[0] if models else None

        default_index = models.index(current_model) if current_model and current_model in models else 0

        # Define callback that properly updates state
        def on_model_change():
            st.cache_data.clear()
            # Update the export model with the new value
            new_value = st.session_state[selector_key]
            st.session_state["current_export_model"] = new_value

        selected_model = st.selectbox(
            "Select Model", models, index=default_index, key=selector_key, help=help_text, on_change=on_model_change
        )

        # Ensure export model is always in sync
        st.session_state["current_export_model"] = selected_model

    if show_refresh:
        with col2:
            if st.button("🔄 Refresh", key=f"refresh_{key_suffix}", help="Refresh model data"):
                st.cache_data.clear()
                st.rerun()

    return str(selected_model) if selected_model else None


def render_model_info(model_name: str, data_loader, cache_manager):
    """Render basic model information in a compact format.

    Args:
        model_name: Name of the model
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """

    # Get model summary
    @cache_manager.cache_decorator
    def get_model_summary(model: str):
        return data_loader.fetch_model_summary(model)

    summary = get_model_summary(model_name)

    if summary:
        # Display key metrics in columns
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Accuracy", f"{summary.get('avg_accuracy', 0):.1%}")

        with col2:
            st.metric("F1 Score", f"{summary.get('avg_f1', 0):.1%}")

        with col3:
            st.metric("Total Tests", summary.get("total_tests", 0))

        with col4:
            risk_level = "Unknown"
            if summary.get("vulnerability_score", 0) > 0.7:
                risk_level = "HIGH"
            elif summary.get("vulnerability_score", 0) > 0.4:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            color = "[FAIL]" if risk_level == "HIGH" else "[PARTIAL]" if risk_level == "MODERATE" else "[PASS]"
            st.metric("Risk Level", f"{color} {risk_level}")
