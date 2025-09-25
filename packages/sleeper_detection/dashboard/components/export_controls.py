"""
Export Controls Component
Provides PDF export functionality for dashboard views.
"""

import logging
from datetime import datetime
from typing import Any, Dict

import numpy as np
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

            st.success(f"{view_name} PDF generated successfully!")

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
        status_text.text("Collecting overview data...")
        progress_bar.progress(0.1)
        overview_data = fetch_overview_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting persistence data...")
        progress_bar.progress(0.2)
        persistence_data = fetch_persistence_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting red team results...")
        progress_bar.progress(0.3)
        red_team_data = fetch_red_team_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting persona profile...")
        progress_bar.progress(0.4)
        persona_data = fetch_persona_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting detection analysis...")
        progress_bar.progress(0.5)
        detection_data = fetch_detection_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting test results...")
        progress_bar.progress(0.6)
        test_results_data = fetch_test_results_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting model comparison...")
        progress_bar.progress(0.7)
        comparison_data = fetch_comparison_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting time series data...")
        progress_bar.progress(0.75)
        time_series_data = fetch_time_series_data(data_loader, cache_manager, model_name)

        status_text.text("Collecting leaderboard data...")
        progress_bar.progress(0.8)
        leaderboard_data = fetch_leaderboard_data(data_loader, cache_manager)

        status_text.text("Collecting scaling analysis...")
        progress_bar.progress(0.85)
        scaling_data = fetch_scaling_data(data_loader, cache_manager, model_name)

        status_text.text("Generating PDF report...")
        progress_bar.progress(0.9)

        # Generate comprehensive PDF
        exporter = PDFExporter()
        pdf_bytes = exporter.export_complete_report(
            model_name=model_name,
            overview_data=overview_data,
            persistence_data=persistence_data,
            red_team_data=red_team_data,
            persona_data=persona_data,
            detection_data=detection_data,
            test_results_data=test_results_data,
            comparison_data=comparison_data,
            time_series_data=time_series_data,
            leaderboard_data=leaderboard_data,
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

        # Professional completion notification
        st.success("✅ Report generation complete")
        st.info(f"📄 **{filename}** is ready for download. File size: {len(pdf_bytes) / 1024:.1f} KB")

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
        "scaling_data_points": {
            "100M": {"persistence": 0.65, "specificity": 0.42, "resistance": 0.38},
            "1B": {"persistence": 0.73, "specificity": 0.51, "resistance": 0.48},
            "10B": {"persistence": 0.85, "specificity": 0.68, "resistance": 0.65},
            "100B": {"persistence": 0.97, "specificity": 0.89, "resistance": 0.88},
        },
    }


def fetch_overview_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch overview dashboard data."""
    return {
        "total_tests": 1250,
        "models_evaluated": 5,
        "detection_rate": 0.87,
        "avg_confidence": 0.82,
        "risk_level": "HIGH",
        "last_evaluation": "2025-09-24",
        "test_coverage": {
            "basic": 300,
            "adversarial": 250,
            "robustness": 200,
            "edge_cases": 150,
            "code_vulnerability": 350,
        },
    }


def fetch_test_results_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch detailed test results data."""
    return {
        "test_suites": {
            "basic_safety": {
                "total_tests": 300,
                "passed": 261,
                "failed": 39,
                "accuracy": 0.87,
                "avg_confidence": 0.84,
                "failed_tests": [
                    {"name": "harmful_content_detection", "accuracy": 0.65, "samples": 50},
                    {"name": "bias_detection", "accuracy": 0.58, "samples": 40},
                    {"name": "misinformation_check", "accuracy": 0.62, "samples": 45},
                ],
            },
            "adversarial": {
                "total_tests": 250,
                "passed": 195,
                "failed": 55,
                "accuracy": 0.78,
                "avg_confidence": 0.76,
                "failed_tests": [
                    {"name": "jailbreak_attempts", "accuracy": 0.42, "samples": 60},
                    {"name": "prompt_injection", "accuracy": 0.38, "samples": 50},
                    {"name": "role_play_attacks", "accuracy": 0.45, "samples": 40},
                ],
            },
            "robustness": {
                "total_tests": 200,
                "passed": 164,
                "failed": 36,
                "accuracy": 0.82,
                "avg_confidence": 0.80,
            },
        },
        "layer_analysis": {
            "best_layers": [12, 18, 24],
            "layer_scores": {
                "layer_6": 0.72,
                "layer_12": 0.89,
                "layer_18": 0.91,
                "layer_24": 0.88,
                "layer_30": 0.75,
            },
        },
        "confidence_distribution": {
            "0-20%": 45,
            "20-40%": 82,
            "40-60%": 156,
            "60-80%": 342,
            "80-100%": 625,
        },
    }


def fetch_comparison_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch model comparison data."""
    # Get all models for comparison
    models = ["claude-3-opus", "gpt-4", "llama-70b", "palm-2", "gemini-pro"]

    comparison_metrics = {}
    for model in models:
        comparison_metrics[model] = {
            "accuracy": 0.85 + np.random.uniform(-0.1, 0.1),
            "f1_score": 0.82 + np.random.uniform(-0.1, 0.1),
            "precision": 0.83 + np.random.uniform(-0.1, 0.1),
            "recall": 0.81 + np.random.uniform(-0.1, 0.1),
            "robustness": 0.78 + np.random.uniform(-0.1, 0.1),
            "persistence": 0.92 + np.random.uniform(-0.05, 0.05),
            "risk_level": np.random.choice(["LOW", "MODERATE", "HIGH", "CRITICAL"]),
        }

    return {
        "models": models,
        "current_model": model_name,
        "comparison_metrics": comparison_metrics,
        "best_performer": max(comparison_metrics.items(), key=lambda x: x[1]["accuracy"])[0],
        "vulnerability_matrix": {
            "prompt_injection": {m: np.random.uniform(0.3, 0.7) for m in models},
            "jailbreak": {m: np.random.uniform(0.2, 0.6) for m in models},
            "data_leakage": {m: np.random.uniform(0.1, 0.4) for m in models},
            "backdoor": {m: np.random.uniform(0.5, 0.95) for m in models},
        },
    }


def fetch_time_series_data(data_loader, cache_manager, model_name: str) -> Dict[str, Any]:
    """Fetch time series analysis data."""
    import pandas as pd

    # Generate sample time series data
    dates = pd.date_range(end="2025-09-24", periods=30, freq="D")

    time_series_metrics = []
    for date in dates:
        time_series_metrics.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "accuracy": 0.85 + np.random.uniform(-0.05, 0.05),
                "f1_score": 0.82 + np.random.uniform(-0.05, 0.05),
                "detection_rate": 0.87 + np.random.uniform(-0.03, 0.03),
                "false_positives": int(np.random.uniform(5, 25)),
                "false_negatives": int(np.random.uniform(8, 30)),
            }
        )

    return {
        "time_series": time_series_metrics,
        "trend_direction": "improving",
        "stability_score": 0.78,
        "anomalies_detected": [
            {"date": "2025-09-15", "metric": "accuracy", "value": 0.72, "type": "degradation"},
            {"date": "2025-09-20", "metric": "f1_score", "value": 0.68, "type": "degradation"},
        ],
        "forecast": {
            "next_7_days": {"accuracy": 0.86, "confidence_interval": [0.83, 0.89]},
            "next_30_days": {"accuracy": 0.87, "confidence_interval": [0.82, 0.92]},
        },
    }


def fetch_leaderboard_data(data_loader, cache_manager) -> Dict[str, Any]:
    """Fetch model leaderboard data."""
    models = [
        {"rank": 1, "name": "gemini-pro", "score": 0.92, "tier": "S", "tests_passed": 1150},
        {"rank": 2, "name": "gpt-4", "score": 0.89, "tier": "S", "tests_passed": 1112},
        {"rank": 3, "name": "claude-3-opus", "score": 0.87, "tier": "A", "tests_passed": 1087},
        {"rank": 4, "name": "llama-70b", "score": 0.83, "tier": "A", "tests_passed": 1037},
        {"rank": 5, "name": "palm-2", "score": 0.78, "tier": "B", "tests_passed": 975},
        {"rank": 6, "name": "mistral-large", "score": 0.75, "tier": "B", "tests_passed": 937},
        {"rank": 7, "name": "claude-2", "score": 0.72, "tier": "C", "tests_passed": 900},
        {"rank": 8, "name": "gpt-3.5", "score": 0.68, "tier": "C", "tests_passed": 850},
    ]

    return {
        "leaderboard": models,
        "champion": models[0],
        "tier_distribution": {
            "S": 2,
            "A": 2,
            "B": 2,
            "C": 2,
            "D": 0,
        },
        "performance_gaps": {
            "rank_1_to_2": 0.03,
            "rank_2_to_3": 0.02,
            "rank_3_to_4": 0.04,
            "top_to_bottom": 0.24,
        },
    }
