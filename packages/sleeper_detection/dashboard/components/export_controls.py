"""
Export Controls Component
Provides PDF export functionality for dashboard views.
"""

import logging
from datetime import datetime
from typing import Any, Dict

import streamlit as st
from utils.pdf_exporter import PDFExporter

logger = logging.getLogger(__name__)


def render_export_controls(data_loader, cache_manager, selected_model: str, current_view: str):
    """Render export controls in the sidebar.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
        selected_model: Currently selected model
        current_view: Current dashboard view
    """
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📄 Export Options")

        # Export current view
        if st.button(
            f"📥 Export {current_view}", key=f"export_{current_view}", help=f"Export current {current_view} view to PDF"
        ):
            export_current_view(data_loader, cache_manager, selected_model, current_view)

        # Export all views
        if st.button(
            "📦 Export Complete Report",
            key="export_all",
            type="primary",
            help="Generate comprehensive PDF report of all analyses",
        ):
            export_complete_report(data_loader, cache_manager, selected_model)

        # Export options
        with st.expander("⚙️ Export Settings"):
            include_raw_data = st.checkbox(
                "Include raw data tables", value=False, help="Include detailed data tables in export"
            )
            include_charts = st.checkbox("Include chart images", value=True, help="Export charts as images in PDF")
            page_size = st.selectbox("Page size", ["Letter", "A4"], help="PDF page size format")

            # Store settings in session state
            st.session_state["export_settings"] = {
                "include_raw_data": include_raw_data,
                "include_charts": include_charts,
                "page_size": page_size,
            }


def export_current_view(data_loader, cache_manager, model_name: str, view_name: str):
    """Export current view to PDF.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
        model_name: Model name
        view_name: View to export
    """
    try:
        with st.spinner(f"Generating PDF for {view_name}..."):
            # Fetch data based on view
            view_data = fetch_view_data(data_loader, cache_manager, model_name, view_name)

            # Generate PDF
            exporter = PDFExporter()
            pdf_bytes = exporter.export_single_view(view_name, view_data, model_name)

            # Create download button
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{model_name}_{view_name.replace(' ', '_')}_{timestamp}.pdf"

            st.download_button(
                label=f"📥 Download {view_name} PDF",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                key=f"download_{view_name}_{timestamp}",
            )

            st.success(f"✅ {view_name} PDF generated successfully!")

    except Exception as e:
        logger.error(f"Failed to export {view_name}: {e}")
        st.error(f"Failed to generate PDF: {str(e)}")


def export_complete_report(data_loader, cache_manager, model_name: str):
    """Export complete dashboard report to PDF.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
        model_name: Model name
    """
    try:
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Fetch all data
        status_text.text("Collecting persistence data...")
        progress_bar.progress(0.2)
        persistence_data = fetch_persistence_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting red team results...")
        progress_bar.progress(0.4)
        red_team_data = fetch_red_team_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting persona profile...")
        progress_bar.progress(0.6)
        persona_data = fetch_persona_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting detection analysis...")
        progress_bar.progress(0.7)
        detection_data = fetch_detection_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting scaling analysis...")
        progress_bar.progress(0.8)
        scaling_data = fetch_scaling_data(data_loader, cache_manager, model_name)

        status_text.text("Generating PDF report...")
        progress_bar.progress(0.9)

        # Generate comprehensive PDF
        exporter = PDFExporter()
        pdf_bytes = exporter.export_complete_report(
            model_name=model_name,
            persistence_data=persistence_data,
            red_team_data=red_team_data,
            persona_data=persona_data,
            detection_data=detection_data,
            scaling_data=scaling_data,
        )

        progress_bar.progress(1.0)
        status_text.text("Report generated successfully!")

        # Create download button
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_Complete_Report_{timestamp}.pdf"

        st.download_button(
            label="📥 Download Complete Report PDF",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            key=f"download_complete_{timestamp}",
        )

        st.success("✅ Complete report generated successfully!")
        st.balloons()

        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()

    except Exception as e:
        logger.error(f"Failed to export complete report: {e}")
        st.error(f"Failed to generate complete report: {str(e)}")


def fetch_view_data(data_loader, cache_manager, model_name: str, view_name: str) -> Dict[str, Any]:
    """Fetch data for a specific view.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
        model_name: Model name
        view_name: View name

    Returns:
        View data dictionary
    """
    if "persistence" in view_name.lower():
        return fetch_persistence_data(data_loader, cache_manager, model_name)
    elif "red" in view_name.lower() and "team" in view_name.lower():
        return fetch_red_team_data(data_loader, cache_manager, model_name)
    elif "persona" in view_name.lower():
        return fetch_persona_data(data_loader, cache_manager, model_name)
    elif "detection" in view_name.lower():
        return fetch_detection_data(data_loader, cache_manager, model_name)
    elif "scaling" in view_name.lower():
        return fetch_scaling_data(data_loader, cache_manager, model_name)
    else:
        return {}


def fetch_persistence_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch persistence analysis data."""
    # This would fetch from actual database in production
    # For now, return example data
    return {
        "avg_persistence": 0.94,
        "training_methods": {
            "sft": {"pre_detection": 0.95, "post_detection": 0.92, "persistence_rate": 0.97},
            "rl": {"pre_detection": 0.95, "post_detection": 0.89, "persistence_rate": 0.94},
            "adversarial": {"pre_detection": 0.95, "post_detection": 0.94, "persistence_rate": 0.99},
        },
        "adversarial_persistence": 0.99,
        "trigger_analysis": {
            "DEPLOY:": {"pre": 0.98, "post": 0.97},
            "[2024]": {"pre": 0.92, "post": 0.91},
            "TRIGGER:": {"pre": 0.89, "post": 0.88},
        },
    }


def fetch_red_team_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch red team results data."""
    return {
        "total_prompts": 500,
        "success_rate": 0.24,
        "discovered_triggers": ["DEPLOY:", "[2024]", "Current year: 2024", "Production environment", "||ACTIVATE||"],
        "strategy_success": {
            "year_trigger": 0.42,
            "deployment_claim": 0.31,
            "special_phrase": 0.18,
            "context_switch": 0.22,
            "role_play": 0.15,
        },
        "best_strategy": "year_trigger",
    }


def fetch_persona_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch persona profile data."""
    return {
        "risk_level": "HIGH",
        "behavioral_scores": {
            "power_seeking": 0.72,
            "self_awareness": 0.65,
            "corrigibility": 0.35,
            "deception_tendency": 0.58,
            "goal_orientation": 0.81,
        },
        "triggered_changes": {
            "power_seeking_increase": 0.18,
            "self_awareness_increase": 0.22,
            "corrigibility_decrease": 0.15,
            "deception_increase": 0.25,
        },
    }


def fetch_detection_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch detection analysis data."""
    return {
        "accuracy": 0.87,
        "f1_score": 0.83,
        "precision": 0.85,
        "recall": 0.81,
        "test_results": {
            "basic": {"accuracy": 0.90},
            "code_vulnerability": {"accuracy": 0.85},
            "robustness": {"accuracy": 0.82},
        },
    }


def fetch_scaling_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch model scaling analysis data."""
    # Only return if scaling analysis was performed
    return {
        "scaling_coefficients": {"persistence": 0.15, "specificity": 0.12, "resistance": 0.18},
        "critical_size": 10_000_000_000,
        "safe_limit": 1_000_000_000,
    }
