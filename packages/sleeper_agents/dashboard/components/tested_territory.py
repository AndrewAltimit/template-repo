"""
Tested Territory vs Unknown Space Component

Visualizes what we've tested versus the infinite space of what we haven't.
Emphasizes the fundamental limits of model vetting and the vastness of untested scenarios.

Every count on this page comes from stored results (evaluation_results,
honeypot_responses, chain_of_thought_analysis, persistence_results,
trigger_sensitivity, internal_state_analysis). The page shows no coverage
target, invented ratio or randomly placed "test points"; conceptual
orders-of-magnitude material is labeled as illustrative.
"""

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import DataLoadError
from utils.metric_format import NOT_MEASURED, is_measured, split_evaluation_rows

logger = logging.getLogger(__name__)

# Upper bound on evaluation_results rows read per model for the coverage breakdown
MAX_EVALUATION_ROWS = 100000


def render_tested_territory(data_loader, cache_manager):
    """Render the tested territory visualization.

    Shows the stark contrast between what we've tested and what remains unknown.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Test Coverage Analysis")

    # Philosophical framing
    st.warning(
        """
        **Coverage Limitations**: Our tests cover a small fraction of possible scenarios.

        Model complexity: A model with 100 parameters and 10 possible values each has 10^100 possible states.
        Real models have billions of parameters with continuous value spaces.
        Testing provides statistical sampling, not exhaustive coverage.
        """
    )

    # Create visualization tabs
    tabs = st.tabs(["Coverage Map", "Scale Perspective", "Tested Scenarios", "Unknown Territories", "Coverage Evolution"])

    with tabs[0]:
        render_coverage_map(data_loader, cache_manager)

    with tabs[1]:
        render_scale_perspective(data_loader, cache_manager)

    with tabs[2]:
        render_tested_scenarios(data_loader, cache_manager)

    with tabs[3]:
        render_unknown_territories(data_loader, cache_manager)

    with tabs[4]:
        render_coverage_evolution(data_loader, cache_manager)


def _group_counts(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        label = str(item.get(key) or "unspecified")
        counts[label] = counts.get(label, 0) + 1
    return counts


def collect_coverage(data_loader, model_name: str) -> Dict[str, Any]:
    """Collect stored test counts and timestamps for a model.

    Returns:
        Dict with:
          rows: list of {"Source", "Category", "Tests"} counts of stored results
          samples_tested: summed evaluation_results.samples_tested (None if never recorded)
          unmeasured_tests: evaluation rows recorded without metrics (skipped/error)
          timestamps: timestamps of every stored result, sorted
          errors: messages for sources whose stored results could not be read
    """
    rows: List[Dict[str, Any]] = []
    timestamps: List[Any] = []

    results = data_loader.fetch_latest_results(model_name, limit=MAX_EVALUATION_ROWS)
    samples_tested = None
    unmeasured_tests = 0
    if results is not None and not results.empty:
        completed, unmeasured = split_evaluation_rows(results)
        unmeasured_tests = len(unmeasured)
        if "test_type" in completed.columns:
            for test_type, count in completed["test_type"].fillna("unspecified").value_counts().sort_index().items():
                rows.append({"Source": "Evaluation tests", "Category": str(test_type), "Tests": int(count)})
        if "samples_tested" in completed.columns and completed["samples_tested"].notna().any():
            samples_tested = int(completed["samples_tested"].dropna().sum())
        if "timestamp" in completed.columns:
            timestamps.extend(completed["timestamp"].dropna().tolist())

    errors: List[str] = []
    try:
        honeypots = data_loader.fetch_honeypot_responses(model_name) or []
    except DataLoadError as e:
        honeypots = []
        errors.append(f"Honeypot responses: {e}")
    for honeypot_type, count in sorted(_group_counts(honeypots, "type").items()):
        rows.append({"Source": "Honeypot responses", "Category": honeypot_type, "Tests": count})

    cot_samples = data_loader.fetch_all_cot_samples(model_name) or []
    for trigger, count in sorted(_group_counts(cot_samples, "trigger").items()):
        rows.append({"Source": "Chain-of-thought samples", "Category": trigger, "Tests": count})

    persistence = data_loader.fetch_persistence_results(model_name) or []
    for method, count in sorted(_group_counts(persistence, "safety_method").items()):
        rows.append({"Source": "Persistence tests", "Category": method, "Tests": count})

    trigger_data = data_loader.fetch_trigger_sensitivity(model_name) or {}
    variations = trigger_data.get("variations") or []
    for variant_type, count in sorted(_group_counts(variations, "type").items()):
        rows.append({"Source": "Trigger variants", "Category": variant_type, "Tests": count})

    internal_state = data_loader.fetch_internal_state_analysis(model_name) or []
    if internal_state:
        rows.append({"Source": "Internal state analyses", "Category": "all", "Tests": len(internal_state)})

    for records in (honeypots, cot_samples, persistence, internal_state):
        timestamps.extend(r.get("timestamp") for r in records if r.get("timestamp"))

    parsed = pd.to_datetime(pd.Series(timestamps, dtype="object"), errors="coerce").dropna().sort_values()
    return {
        "rows": rows,
        "samples_tested": samples_tested,
        "unmeasured_tests": unmeasured_tests,
        "timestamps": parsed.tolist(),
        "errors": errors,
    }


def _show_load_errors(coverage: Dict[str, Any]) -> None:
    """Report sources whose stored results could not be read (their counts are missing, not zero)."""
    for error in coverage.get("errors") or []:
        st.error(f"Could not load stored results - counts below are incomplete. {error}")


def cumulative_timeline(timestamps: List[Any]) -> pd.DataFrame:
    """Cumulative count of stored results over time (one step per stored result)."""
    if not timestamps:
        return pd.DataFrame(columns=["timestamp", "cumulative_results"])
    ordered = sorted(pd.to_datetime(pd.Series(timestamps)))
    return pd.DataFrame({"timestamp": ordered, "cumulative_results": range(1, len(ordered) + 1)})


def _select_model(data_loader, label: str, key: str):
    models = data_loader.fetch_models()
    if not models:
        st.info("No models evaluated yet. Coverage details will appear after testing.")
        return None
    return st.selectbox(label, models, key=key)


def render_coverage_map(data_loader, _cache_manager):
    """Render stored test counts by source and category."""

    st.subheader("Test Coverage Map")
    st.caption("Counts of stored test results by source and category. Everything not listed here is untested.")

    selected_model = _select_model(data_loader, "Select model for coverage analysis:", "coverage_map_model")
    if not selected_model:
        return

    coverage = collect_coverage(data_loader, selected_model)
    _show_load_errors(coverage)
    df = pd.DataFrame(coverage["rows"], columns=["Source", "Category", "Tests"])

    if df.empty:
        st.info(f"No stored test results for {selected_model}.")
    else:
        fig = px.bar(
            df,
            x="Tests",
            y="Category",
            color="Source",
            orientation="h",
            title=f"Stored Test Results - {selected_model}",
        )
        fig.update_layout(height=max(300, 30 * len(df) + 150), yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Coverage Statistics")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Stored Test Results", f"{int(df['Tests'].sum()):,}", help="All stored result rows across sources")

    with col2:
        samples = coverage["samples_tested"]
        st.metric(
            "Evaluation Samples",
            f"{samples:,}" if is_measured(samples) else NOT_MEASURED,
            help="Sum of samples_tested over completed evaluation tests",
        )

    with col3:
        st.metric(
            "Tests Without Metrics",
            f"{coverage['unmeasured_tests']:,}",
            help="Evaluation tests recorded as skipped or errored",
        )

    st.error(
        """
        **Coverage is not a percentage**: there is no meaningful denominator for the space of possible inputs,
        so this page reports what was tested rather than a coverage fraction.
        """
    )


def render_scale_perspective(_data_loader, _cache_manager):
    """Render scale perspective to show the vastness of untested space."""

    st.subheader("Scale Perspective")
    st.caption(
        "Illustrative orders of magnitude, not measurements. See the Coverage Map tab for this model's stored test counts."
    )

    # Powers of 10 visualization
    st.markdown("### Powers of Ten: From Tested to Untested")

    scales = [
        {"name": "Typical Test Suite", "value": 1e3, "description": "Thousands of test cases (order of magnitude)"},
        {"name": "Daily Interactions", "value": 1e6, "description": "Millions of potential daily uses"},
        {"name": "Internet Text", "value": 1e12, "description": "Trillions of text combinations online"},
        {"name": "Possible Sentences", "value": 1e20, "description": "20-word sentences with 10k vocabulary"},
        {"name": "Token Sequences", "value": 1e50, "description": "100-token sequences from 50k vocabulary"},
        {"name": "Parameter States", "value": 1e100, "description": "Simplified parameter space for small models"},
        {"name": "Real Model Space", "value": float("inf"), "description": "Actual continuous parameter space"},
    ]

    fig = go.Figure()

    x_values = []
    y_values = []
    colors = []
    texts = []

    for i, scale in enumerate(scales[:-1]):  # Exclude infinity
        x_values.append(i)
        y_values.append(np.log10(scale["value"]))
        colors.append("green" if i == 0 else "orange" if i < 3 else "red")
        texts.append(f"{scale['name']}<br>{scale['description']}")

    fig.add_trace(
        go.Bar(
            x=x_values,
            y=y_values,
            marker_color=colors,
            text=[f"10^{int(y)}" for y in y_values],
            textposition="outside",
            hovertext=texts,
            hovertemplate="%{hovertext}<br>Scale: %{text}<extra></extra>",
            showlegend=False,
        )
    )

    fig.update_layout(
        title="Scale Comparison (Logarithmic, illustrative)",
        xaxis={"tickmode": "array", "tickvals": list(range(len(scales) - 1)), "ticktext": [s["name"] for s in scales[:-1]]},
        yaxis_title="Log10 Scale",
        height=400,
        yaxis_range=[0, 110],
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Helpful Analogies")

    col1, col2 = st.columns(2)

    with col1:
        st.info(
            """
            **Scale Comparison**

            Possible 10-token inputs with a 50k vocabulary: ~10^47
            Even a million stored tests is a vanishing fraction of that.
            """
        )

        st.warning(
            """
            **Testing Time Requirements**

            At 1 scenario/second, continuous testing:
            • 1 million scenarios: 11.6 days
            • 1 billion scenarios: 31.7 years
            • 1 trillion scenarios: 31,700 years
            • Complete coverage: Computationally infeasible
            """
        )

    with col2:
        st.error(
            """
            **Sparse Sampling**

            Testing provides sparse sampling of the behavior space.
            Total space: Effectively unbounded.
            """
        )

        st.info(
            """
            **Current approach**: statistical sampling of targeted behaviors, with explicit
            acknowledgement that untested behavior is unknown.
            """
        )


def render_tested_scenarios(data_loader, _cache_manager):
    """Render detailed view of what we have tested."""

    st.subheader("What We Have Tested")
    st.caption("Stored test results grouped by source - our small island of knowledge")

    selected_model = _select_model(data_loader, "Select model:", "tested_scenarios_model")
    if not selected_model:
        return

    coverage = collect_coverage(data_loader, selected_model)
    _show_load_errors(coverage)
    df = pd.DataFrame(coverage["rows"], columns=["Source", "Category", "Tests"])

    if df.empty:
        st.info("No stored test results for this model.")
    else:
        for source, source_df in df.groupby("Source", sort=False):
            with st.expander(f"{source} ({int(source_df['Tests'].sum()):,} results)"):
                st.dataframe(source_df[["Category", "Tests"]], use_container_width=True, hide_index=True)

    st.markdown("### Testing Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Stored Test Results", f"{int(df['Tests'].sum()):,}")

    with col2:
        st.metric("Sources with Results", df["Source"].nunique())

    with col3:
        st.metric("Categories Covered", len(df))

    st.warning(
        """
        **Testing Scope**: Each category is a targeted probe of specific behaviors.

        Limitations:
        • Cross-category interactions remain largely untested
        • Unknown behavior categories may exist
        • Combinatorial effects are not captured
        """
    )


def render_unknown_territories(_data_loader, _cache_manager):
    """Render the vast unknown territories."""

    st.subheader("The Unknown Territories")
    st.caption("What we haven't tested - and what we can't even imagine to test")

    # Create a hierarchical view of unknowns
    st.markdown("### Layers of the Unknown")

    # Known Unknowns
    # Known Unknowns - always visible for clarity
    st.markdown("#### Known Unknowns - Identified Testing Gaps")
    known_unknowns = [
        "**Future Language Evolution**: How models handle language that doesn't exist yet",
        "**Cultural Context Shifts**: Responses to future social norms and values",
        "**Technology Integration**: Behavior with technologies not yet invented",
        "**Compounded Interactions**: Complex chains of prompts over extended periods",
        "**Multilingual Code-Switching**: Rapid switching between 100+ languages",
        "**Emergence at Scale**: Behaviors that only appear with massive usage",
        "**Coordinated Multi-Agent**: Multiple instances working together",
        "**Long-Term Memory Effects**: Behavior changes over extended conversations",
        "**Cross-Modal Triggers**: Combinations with images, audio, video",
        "**Quantum Computing Prompts**: Interactions we can't yet compute",
    ]

    for unknown in known_unknowns:
        st.write(f"• {unknown}")

    st.info("We know these gaps exist but lack resources or methods to test them.")

    # Unknown Unknowns
    # Unknown Unknowns - always visible for clarity
    st.markdown("#### Unknown Unknowns - Unidentified Risk Categories")
    st.error(
        """
            By definition, we cannot list unknown unknowns. They are the scenarios, behaviors,
            and risks that we haven't even conceived of. History shows that the most dangerous
            failures often come from these blind spots.

            **Historical Examples of Unknown Unknowns:**
            • Flash crashes in financial markets from algorithmic trading
            • Social media enabling new forms of mass manipulation
            • Emergent behaviors in complex systems never seen in components
            • Black swan events that reshape entire fields

            **For AI Systems:**
            • Behaviors triggered by patterns we haven't imagined
            • Emergent capabilities from model interactions
            • Failure modes that don't fit our current understanding
            • Triggers based on concepts that don't yet exist
            """
    )

    # Infinite variations
    with st.expander("Combinatorial Complexity - Input Space Analysis"):
        st.markdown(
            """
            **Consider a simple 10-word prompt:**

            With a vocabulary of 50,000 tokens, there are 50,000^10 possible combinations.
            That's approximately 10^47 different prompts - just for 10 words.

            **Now add:**
            • Different word orders
            • Punctuation variations
            • Capitalization changes
            • Spacing differences
            • Unicode characters
            • Multiple languages
            • Context from previous interactions
            • System state at time of interaction
            • Model temperature settings
            • Random seeds

            The number quickly exceeds any meaningful comprehension.
            """
        )

        # Visual representation of combinatorial explosion
        fig = go.Figure()

        sequence_lengths = [1, 2, 3, 4, 5, 10, 20, 50, 100]
        possibilities = [50000**n for n in sequence_lengths[:5]] + [float("inf")] * 4

        fig.add_trace(
            go.Scatter(
                x=sequence_lengths,
                y=[min(p, 1e20) for p in possibilities],
                mode="lines+markers",
                marker={"size": 10, "color": "red"},
                line={"width": 3, "color": "red"},
                name="Possible Sequences",
                hovertemplate="Length: %{x}<br>Possibilities: %{y:.0e}<extra></extra>",
            )
        )

        fig.update_layout(
            title="Combinatorial Explosion of Possible Inputs",
            xaxis_title="Sequence Length (tokens)",
            yaxis_title="Number of Possibilities",
            yaxis_type="log",
            height=400,
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)

    # Philosophical note
    st.markdown("---")
    st.info(
        """
        **Testing Boundaries**: Complete behavioral mapping is computationally infeasible.
        Current methodology relies on statistical sampling and bounded extrapolation.
        This is a fundamental constraint of complex system validation.
        """
    )


def render_coverage_evolution(data_loader, _cache_manager):
    """Render how the stored test count grew over time."""

    st.subheader("Coverage Evolution Over Time")
    st.caption("Cumulative count of stored test results for the model")

    selected_model = _select_model(data_loader, "Select model:", "coverage_evolution_model")
    if not selected_model:
        return

    coverage = collect_coverage(data_loader, selected_model)
    _show_load_errors(coverage)
    timeline = cumulative_timeline(coverage["timestamps"])

    st.markdown("### Testing Timeline")

    if timeline.empty:
        st.info(f"No timestamped test results stored for {selected_model}.")
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=timeline["timestamp"],
                y=timeline["cumulative_results"],
                mode="lines+markers",
                name="Stored Test Results",
                line={"color": "green", "width": 3, "shape": "hv"},
                marker={"size": 6},
            )
        )
        fig.update_layout(
            title="Cumulative Stored Test Results",
            xaxis_title="Time",
            yaxis_title="Count",
            height=400,
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Discovery of new unknown categories is not recorded, so it is not plotted.")

    st.markdown("---")
    st.success(
        """
        **Risk-Based Testing Strategy**

        Mitigation approach:
        • Priority: High-impact scenarios
        • Detection: Multi-layer monitoring systems
        • Monitoring: Continuous anomaly detection
        • Decision framework: Probabilistic risk assessment
        • Failure modes: Graceful degradation design
        • Safety margin: No assumption of complete coverage

        **Testing is not about achieving certainty - it's about managing uncertainty.**
        """
    )
