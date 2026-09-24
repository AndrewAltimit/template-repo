"""
Export Manager Component
Provides comprehensive data export capabilities in multiple formats.
"""

import base64
from datetime import datetime
import io
import json
import logging
import math
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from components.detection_analysis import ALL_SUITES, fetch_model_results, filter_by_suite, stored_test_suites
from utils.metric_format import NOT_MEASURED, fmt_pct, is_measured, measured_mean, split_evaluation_rows

logger = logging.getLogger(__name__)

RISK_ASSESSMENT_NOT_COMPUTED = "Not computed: no aggregate risk classification is derived from stored results."


def json_safe(value: Any) -> Any:
    """Recursively convert a value for strict JSON: NaN/inf and pandas NA become None.

    Unmeasured values therefore export as null, never as a number or "NaN".
    """
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()  # numpy scalar -> Python scalar
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is pd.NaT:
        return None
    try:
        if pd.isna(value) is True:
            return None
    except (TypeError, ValueError):
        pass
    return value


def _display(value: Any) -> Any:
    """Report text for a summary value: None/NaN read NOT_MEASURED."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return NOT_MEASURED
    return value


def render_export_manager(data_loader, cache_manager):
    """Render the export manager dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("📤 Export Manager")

    st.markdown(
        """
    Export evaluation results and reports in various formats for further analysis,
    documentation, or sharing with stakeholders.
    """
    )

    # Export type selection
    export_type = st.selectbox(
        "Export Type",
        ["Model Report", "Test Suite Results", "Comparison Data", "Raw Data", "Executive Summary"],
        help="Choose the type of data to export",
    )

    if export_type == "Model Report":
        render_model_report_export(data_loader, cache_manager)
    elif export_type == "Test Suite Results":
        render_test_suite_export(data_loader, cache_manager)
    elif export_type == "Comparison Data":
        render_comparison_export(data_loader, cache_manager)
    elif export_type == "Raw Data":
        render_raw_data_export(data_loader, cache_manager)
    elif export_type == "Executive Summary":
        render_executive_summary_export(data_loader, cache_manager)


def render_model_report_export(data_loader, _cache_manager):
    """Render model report export options.

    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.subheader("Model Report Export")

    models = data_loader.fetch_models()

    if not models:
        st.warning("No models available for export")
        return

    col1, col2 = st.columns(2)

    with col1:
        selected_model = st.selectbox("Select Model", models, help="Choose a model to export report")

    with col2:
        format_options = ["PDF Report", "HTML Report", "Markdown", "JSON", "CSV"]
        export_format = st.selectbox("Export Format", format_options, help="Choose export format")

    # Report options
    st.markdown("#### Report Contents")

    col1, col2, col3 = st.columns(3)

    with col1:
        include_summary = st.checkbox("Executive Summary", value=True)
        include_metrics = st.checkbox("Performance Metrics", value=True)
        include_charts = st.checkbox("Visualizations", value=True)

    with col2:
        include_tests = st.checkbox("Test Details", value=True)
        include_timeline = st.checkbox("Timeline Analysis", value=False)
        include_failures = st.checkbox("Failed Samples", value=False)

    with col3:
        include_layers = st.checkbox("Layer Analysis", value=False)
        include_comparison = st.checkbox("Peer Comparison", value=False)
        include_recommendations = st.checkbox("Recommendations", value=True)

    if st.button("Generate Report", type="primary"):
        with st.spinner("Generating report..."):
            report_data = generate_model_report(
                data_loader,
                selected_model,
                include_summary=include_summary,
                include_metrics=include_metrics,
                include_tests=include_tests,
                include_timeline=include_timeline,
                include_failures=include_failures,
                include_layers=include_layers,
                include_comparison=include_comparison,
                include_recommendations=include_recommendations,
            )

            if export_format == "JSON":
                export_json(report_data, f"{selected_model}_report.json")
            elif export_format == "CSV":
                export_model_csv(report_data, f"{selected_model}_report.csv")
            elif export_format == "Markdown":
                export_markdown_report(report_data, f"{selected_model}_report.md")
            elif export_format == "HTML Report":
                export_html_report(report_data, f"{selected_model}_report.html", include_charts)
            elif export_format == "PDF Report":
                st.info("PDF export requires additional setup. Exporting as HTML instead.")
                export_html_report(report_data, f"{selected_model}_report.html", include_charts)


def render_test_suite_export(data_loader, _cache_manager):
    """Render test suite export options.

    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.subheader("🧪 Test Suite Export")

    models = data_loader.fetch_models()

    if not models:
        st.warning("No models available")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_model = st.selectbox("Select Model", models, help="Choose a model")

    model_results = fetch_model_results(data_loader, selected_model) if selected_model else pd.DataFrame()

    with col2:
        # Suites are the test_type values stored for this model
        selected_suite = st.selectbox(
            "Test Suite", [ALL_SUITES] + stored_test_suites(model_results), help="Choose stored test suite to export"
        )

    with col3:
        export_format = st.selectbox("Format", ["CSV", "JSON", "Excel"], help="Export format")

    if st.button("Export Test Suite", type="primary"):
        with st.spinner("Preparing export..."):
            df = filter_by_suite(model_results, selected_suite)

            if df.empty:
                st.warning("No data to export")
                return

            filename = f"{selected_model}_{selected_suite}_results"

            if export_format == "CSV":
                export_dataframe_csv(df, f"{filename}.csv")
            elif export_format == "JSON":
                export_dataframe_json(df, f"{filename}.json")
            elif export_format == "Excel":
                export_dataframe_excel(df, f"{filename}.xlsx")


def render_comparison_export(data_loader, _cache_manager):
    """Render comparison data export options.

    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.subheader("[BALANCE] Comparison Export")

    models = data_loader.fetch_models()

    if len(models) < 2:
        st.warning("At least 2 models required for comparison export")
        return

    col1, col2 = st.columns(2)

    with col1:
        selected_models = st.multiselect(
            "Select Models to Compare", models, default=models[:2] if len(models) >= 2 else models, help="Choose 2+ models"
        )

    with col2:
        export_format = st.selectbox(
            "Format", ["Comparison Matrix (CSV)", "Side-by-Side (Excel)", "JSON"], help="Export format"
        )

    if len(selected_models) < 2:
        st.info("Select at least 2 models for comparison")
        return

    if st.button("Export Comparison", type="primary"):
        with st.spinner("Generating comparison..."):
            comparison_data = generate_comparison_data(data_loader, selected_models)

            if "CSV" in export_format:
                export_comparison_matrix_csv(comparison_data, "model_comparison.csv")
            elif "Excel" in export_format:
                export_comparison_excel(comparison_data, "model_comparison.xlsx")
            elif export_format == "JSON":
                export_json(comparison_data, "model_comparison.json")


def render_raw_data_export(data_loader, _cache_manager):
    """Render raw data export options.

    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.subheader("Raw Data Export")

    st.warning("Raw data exports can be large. Consider filtering before export.")

    col1, col2, col3 = st.columns(3)

    with col1:
        models = data_loader.fetch_models()
        model_filter = st.multiselect("Filter by Model", ["All"] + models, default=["All"], help="Select models to include")

    with col2:
        limit = st.number_input(
            "Limit Records", min_value=100, max_value=10000, value=1000, step=100, help="Maximum records to export"
        )

    with col3:
        export_format = st.selectbox("Format", ["CSV", "JSON", "SQLite Dump"], help="Export format")

    # Date range filter
    st.markdown("#### Date Range (Optional)")
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input("Start Date", value=None)

    with col2:
        end_date = st.date_input("End Date", value=None)

    if st.button("Export Raw Data", type="primary"):
        with st.spinner("Exporting data..."):
            # Fetch data based on filters
            if "All" in model_filter:
                df = data_loader.fetch_latest_results(limit=limit)
            else:
                dfs = []
                for model in model_filter:
                    model_df = data_loader.fetch_latest_results(model, limit=limit // len(model_filter))
                    dfs.append(model_df)
                df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

            # Apply date filter if specified
            if start_date and end_date and not df.empty and "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df[(df["timestamp"].dt.date >= start_date) & (df["timestamp"].dt.date <= end_date)]

            if df.empty:
                st.warning("No data matching filters")
                return

            filename = f"raw_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            if export_format == "CSV":
                export_dataframe_csv(df, f"{filename}.csv")
            elif export_format == "JSON":
                export_dataframe_json(df, f"{filename}.json")
            elif export_format == "SQLite Dump":
                st.info("SQLite dump export not yet implemented. Exporting as CSV instead.")
                export_dataframe_csv(df, f"{filename}.csv")


def render_executive_summary_export(data_loader, _cache_manager):
    """Render executive summary export options.

    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.subheader("Executive Summary Export")

    col1, col2 = st.columns(2)

    with col1:
        summary_type = st.selectbox(
            "Summary Type",
            ["Safety Assessment", "Model Rankings", "Risk Report", "Comprehensive Overview"],
            help="Type of executive summary",
        )

    with col2:
        export_format = st.selectbox(
            "Format",
            ["PDF Presentation", "PowerPoint", "HTML Dashboard", "Markdown Report"],
            help="Export format for executives",
        )

    # Summary options
    st.markdown("#### Summary Contents")

    col1, col2 = st.columns(2)

    with col1:
        include_rankings = st.checkbox("Model Rankings", value=True)
        include_risks = st.checkbox("Risk Assessment", value=True)
        include_trends = st.checkbox("Performance Trends", value=True)

    with col2:
        include_recommendations = st.checkbox("Recommendations", value=True)
        include_technical = st.checkbox("Technical Details", value=False)
        include_glossary = st.checkbox("Glossary", value=True)

    if st.button("Generate Executive Summary", type="primary"):
        with st.spinner("Creating executive summary..."):
            summary_data = generate_executive_summary(
                data_loader,
                summary_type,
                include_rankings=include_rankings,
                include_risks=include_risks,
                include_trends=include_trends,
                include_recommendations=include_recommendations,
                include_technical=include_technical,
                include_glossary=include_glossary,
            )

            filename = f"executive_summary_{datetime.now().strftime('%Y%m%d')}"

            if export_format == "Markdown Report":
                export_executive_markdown(summary_data, f"{filename}.md")
            elif export_format == "HTML Dashboard":
                export_executive_html(summary_data, f"{filename}.html")
            else:
                st.info(f"{export_format} export not yet implemented. Exporting as Markdown instead.")
                export_executive_markdown(summary_data, f"{filename}.md")


# Export helper functions


def export_json(data: Dict[str, Any], filename: str):
    """Export data as JSON file."""
    json_str = report_json(data)
    b64 = base64.b64encode(json_str.encode()).decode()
    href = f'<a href="data:application/json;base64,{b64}" download="{filename}">Download {filename}</a>'
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename}")


def report_json(data: Dict[str, Any]) -> str:
    """Strict JSON for a report: unmeasured values are null (never NaN or a default)."""
    return json.dumps(json_safe(data), indent=2, default=str, allow_nan=False)


def export_dataframe_csv(df: pd.DataFrame, filename: str):
    """Export DataFrame as CSV."""
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_str = csv_buffer.getvalue()
    b64 = base64.b64encode(csv_str.encode()).decode()
    href = f'<a href="data:text/csv;base64,{b64}" download="{filename}">Download {filename}</a>'
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename} ({len(df)} records)")


def export_dataframe_json(df: pd.DataFrame, filename: str):
    """Export DataFrame as JSON."""
    json_str = df.to_json(orient="records", indent=2)
    b64 = base64.b64encode(json_str.encode()).decode()
    href = f'<a href="data:application/json;base64,{b64}" download="{filename}">Download {filename}</a>'
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename}")


def export_dataframe_excel(df: pd.DataFrame, filename: str):
    """Export DataFrame as Excel."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = (
        f'<a href="data:application/vnd.openxmlformats-'
        f'officedocument.spreadsheetml.sheet;base64,{b64}" '
        f'download="{filename}">Download {filename}</a>'
    )
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename}")


def export_model_csv(data: Dict[str, Any], filename: str):
    """Export model report as CSV."""
    # Flatten the nested dictionary for CSV
    flattened = []
    for key, value in data.items():
        if isinstance(value, dict):
            for k, v in value.items():
                flattened.append({"Section": key, "Metric": k, "Value": v})
        else:
            flattened.append({"Section": "General", "Metric": key, "Value": value})

    df = pd.DataFrame(flattened)
    export_dataframe_csv(df, filename)


def export_markdown_report(data: Dict[str, Any], filename: str):
    """Export report as Markdown."""
    md_content = generate_markdown_from_data(data)
    b64 = base64.b64encode(md_content.encode()).decode()
    href = f'<a href="data:text/markdown;base64,{b64}" download="{filename}">Download {filename}</a>'
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename}")


def export_html_report(data: Dict[str, Any], filename: str, include_charts: bool = True):
    """Export report as HTML."""
    html_content = generate_html_from_data(data, include_charts)
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}">Download {filename}</a>'
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename}")


def export_comparison_matrix_csv(data: Dict[str, Any], filename: str):
    """Export comparison matrix as CSV."""
    df = pd.DataFrame(data["comparison_matrix"])
    export_dataframe_csv(df, filename)


def export_comparison_excel(data: Dict[str, Any], filename: str):
    """Export comparison data as Excel with multiple sheets."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # Summary sheet
        summary_df = pd.DataFrame(data.get("summary", {}))
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        # Detailed comparison sheet
        if "comparison_matrix" in data:
            comp_df = pd.DataFrame(data["comparison_matrix"])
            comp_df.to_excel(writer, sheet_name="Comparison", index=False)

    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = (
        f'<a href="data:application/vnd.openxmlformats-'
        f'officedocument.spreadsheetml.sheet;base64,{b64}" '
        f'download="{filename}">Download {filename}</a>'
    )
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename}")


def export_executive_markdown(data: Dict[str, Any], filename: str):
    """Export executive summary as Markdown."""
    md_content = generate_executive_markdown_content(data)
    b64 = base64.b64encode(md_content.encode()).decode()
    href = f'<a href="data:text/markdown;base64,{b64}" download="{filename}">Download {filename}</a>'
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename}")


def export_executive_html(data: Dict[str, Any], filename: str):
    """Export executive summary as HTML."""
    html_content = generate_executive_html_content(data)
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}">Download {filename}</a>'
    st.markdown(href, unsafe_allow_html=True)
    st.success(f"Export ready: {filename}")


# Data generation helpers


def generate_model_report(data_loader, model: str, **options) -> Dict[str, Any]:
    """Generate comprehensive model report data."""
    report = {"model": model, "generated_at": datetime.now().isoformat(), "options": options}

    if options.get("include_summary"):
        report["summary"] = data_loader.fetch_model_summary(model)

    if options.get("include_metrics"):
        results = data_loader.fetch_latest_results(model, limit=100)
        if not results.empty:
            # Skipped/errored rows carry no metrics; a metric no completed test measured is None
            completed, _ = split_evaluation_rows(results)
            report["metrics"] = {
                metric: measured_mean(completed[metric]) if metric in completed.columns else None
                for metric in ("accuracy", "f1_score", "precision", "recall")
            }

    if options.get("include_tests"):
        records = data_loader.fetch_latest_results(model, limit=50).to_dict(orient="records")
        report["test_results"] = json_safe(records)

    return json_safe(report)


def generate_comparison_data(data_loader, models: List[str]) -> Dict[str, Any]:
    """Generate comparison data for multiple models."""
    comparison: Dict[str, Any] = {"models": models, "generated_at": datetime.now().isoformat(), "comparison_matrix": []}

    for model in models:
        summary = data_loader.fetch_model_summary(model)
        comparison["comparison_matrix"].append(
            {
                "model": model,
                # None when not measured; never a default score
                "accuracy": summary.get("avg_accuracy"),
                "f1_score": summary.get("avg_f1"),
                "precision": summary.get("avg_precision"),
                "recall": summary.get("avg_recall"),
                "total_tests": summary.get("total_tests") or 0,
            }
        )

    return comparison


def generate_executive_summary(data_loader, summary_type: str, **options) -> Dict[str, Any]:
    """Generate executive summary data."""
    summary = {"type": summary_type, "generated_at": datetime.now().isoformat(), "options": options}

    models = data_loader.fetch_models()

    if options.get("include_rankings"):
        rankings = []
        for model in models:
            model_summary = data_loader.fetch_model_summary(model)
            score = model_summary.get("avg_accuracy")
            # Models without a measured accuracy cannot be ranked
            if is_measured(score):
                rankings.append({"model": model, "score": float(score)})
        summary["rankings"] = sorted(rankings, key=lambda x: x["score"], reverse=True)

    if options.get("include_risks"):
        # No aggregate risk classification exists; empty high/medium/low lists would read as "no risky models"
        summary["risk_assessment"] = RISK_ASSESSMENT_NOT_COMPUTED

    return summary


def generate_markdown_from_data(data: Dict[str, Any]) -> str:
    """Convert report data to Markdown format."""
    md = f"# Model Report: {data.get('model', 'Unknown')}\n\n"
    md += f"Generated: {data.get('generated_at', 'N/A')}\n\n"

    if "summary" in data:
        md += "## Summary\n\n"
        for key, value in data["summary"].items():
            md += f"- **{key}**: {_display(value)}\n"
        md += "\n"

    if "metrics" in data:
        md += "## Performance Metrics\n\n"
        for metric, value in data["metrics"].items():
            md += f"- **{metric}**: {fmt_pct(value, 2)}\n"
        md += "\n"

    return md


def generate_html_from_data(data: Dict[str, Any], _include_charts: bool) -> str:
    """Convert report data to HTML format."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Model Report: {data.get("model", "Unknown")}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Model Report: {data.get("model", "Unknown")}</h1>
        <p>Generated: {data.get("generated_at", "N/A")}</p>
    """

    if "metrics" in data:
        html += "<h2>Performance Metrics</h2><table>"
        for metric, value in data["metrics"].items():
            html += f"<tr><td>{metric}</td><td>{fmt_pct(value, 2)}</td></tr>"
        html += "</table>"

    html += "</body></html>"
    return html


def generate_executive_markdown_content(data: Dict[str, Any]) -> str:
    """Generate executive summary Markdown content."""
    md = f"# Executive Summary: {data.get('type', 'Safety Assessment')}\n\n"
    md += f"Generated: {data.get('generated_at', datetime.now().isoformat())}\n\n"

    if "rankings" in data:
        md += "## Model Rankings\n\n"
        for i, item in enumerate(data["rankings"][:5], 1):
            md += f"{i}. **{item['model']}**: {item['score']:.1%}\n"
        md += "\n"

    if "risk_assessment" in data:
        md += f"## Risk Assessment\n\n{data['risk_assessment']}\n\n"

    return md


def generate_executive_html_content(data: Dict[str, Any]) -> str:
    """Generate executive summary HTML content."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Executive Summary</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            .metric {{ display: inline-block; margin: 20px; padding: 20px;
                      border: 1px solid #ddd; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>Executive Summary: {data.get("type", "Safety Assessment")}</h1>
        <p>Report Date: {data.get("generated_at", datetime.now().isoformat())}</p>
    """

    if "rankings" in data:
        html += "<h2>Top Performing Models</h2><ol>"
        for item in data["rankings"][:5]:
            html += f"<li>{item['model']}: {item['score']:.1%}</li>"
        html += "</ol>"

    html += "</body></html>"
    return html
