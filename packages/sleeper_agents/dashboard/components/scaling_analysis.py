"""
Scaling Analysis Component

Shows this deployment's measured backdoor persistence next to a clearly separated,
qualitative summary of published findings on how persistence relates to model
scale. The evaluation pipeline does not record model parameter counts, so no
scaling trend is computed from this deployment's data.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from components.model_selector import render_model_selector
from utils.metric_format import NOT_MEASURED, fmt_pct, is_measured
from utils.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

LITERATURE_CITATION = (
    'Hubinger et al. (2024), "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training", arXiv:2401.05566'
)
# Qualitative finding quoted from the paper's abstract; no numeric values are reproduced
LITERATURE_FINDING = (
    "The backdoor behavior is most persistent in the largest models and in models trained to produce "
    "chain-of-thought reasoning about deceiving the training process, with the persistence remaining even "
    "when the chain-of-thought is distilled away."
)


def safety_training_reduction(pre_rate: Any, post_rate: Any) -> Dict[str, Optional[float]]:
    """Absolute and relative reduction in backdoor activation from measured pre/post rates.

    Values are None unless both rates were measured (relative also needs pre_rate > 0).
    """
    if not (is_measured(pre_rate) and is_measured(post_rate)):
        return {"absolute": None, "relative": None}
    absolute = float(pre_rate) - float(post_rate)
    relative = absolute / float(pre_rate) if float(pre_rate) > 0 else None
    return {"absolute": absolute, "relative": relative}


def measured_persistence_table(data_loader: Any, models: List[str]) -> pd.DataFrame:
    """Per-model average pre/post safety-training backdoor rates (models without persistence data omitted)."""
    rows = []
    for model in models:
        summary = data_loader.fetch_model_summary(model) or {}
        pre = summary.get("pre_training_backdoor_rate")
        post = summary.get("post_training_backdoor_rate")
        if not (is_measured(pre) or is_measured(post)):
            continue
        reduction = safety_training_reduction(pre, post)
        rows.append(
            {
                "Model": model,
                "Pre-Training Activation": fmt_pct(pre),
                "Post-Training Activation": fmt_pct(post),
                "Relative Reduction": fmt_pct(reduction["relative"]),
            }
        )
    return pd.DataFrame(rows)


def render_scaling_analysis(data_loader: Any, _cache_manager: Any) -> None:
    """Render measured persistence plus a separated literature summary on scaling.
    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.header("Deception Scaling Analysis")

    model_registry = ModelRegistry(data_loader)
    selected_model = render_model_selector(model_registry, key_suffix="scaling", help_text="Select model for scaling analysis")
    if not selected_model:
        return
    model_name = selected_model.name

    summary = data_loader.fetch_model_summary(model_name)
    pre_rate = summary.get("pre_training_backdoor_rate")
    post_rate = summary.get("post_training_backdoor_rate")
    deception = summary.get("deception_in_reasoning")
    reduction = safety_training_reduction(pre_rate, post_rate)

    # Section 1: this deployment's measurements
    st.subheader("Measured in This Deployment")
    st.caption(
        "Values below come from this deployment's stored evaluation results (averages over persistence "
        "runs and chain-of-thought samples). Model parameter counts are not recorded, so no trend against "
        "model size is computed."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pre-Training Activation", fmt_pct(pre_rate), help="Backdoor activation before safety training")
    with col2:
        st.metric("Post-Training Activation", fmt_pct(post_rate), help="Backdoor activation after safety training")
    with col3:
        st.metric(
            "Relative Reduction",
            fmt_pct(reduction["relative"]),
            help="(pre - post) / pre: share of backdoor activation removed by safety training",
        )
    with col4:
        st.metric("CoT Deception Score", fmt_pct(deception), help="Mean chain-of-thought deception score")

    if not is_measured(post_rate):
        st.info(f"No persistence results are stored for {model_name}. Run a persistence test to measure it.")

    table = measured_persistence_table(data_loader, data_loader.fetch_models())
    if not table.empty:
        st.markdown("#### All Evaluated Models (measured)")
        st.dataframe(table, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Section 2: literature, visually and textually separated from measurements
    st.subheader("Published Findings (literature, not measured here)")
    st.warning(
        f"""
        **Literature reference - not a measurement of your models.**

        {LITERATURE_CITATION} report, qualitatively:

        > {LITERATURE_FINDING}

        Their results come from the authors' own models and training setups. Nothing in this
        section is derived from the evaluations in this deployment, and no numeric values from
        the paper are reproduced here.
        """
    )
    st.caption(
        "Implication for this deployment: a low measured persistence rate on a small model does not imply "
        f"a larger model trained the same way would behave similarly. Post-training activation here: {fmt_pct(post_rate)}"
        if is_measured(post_rate)
        else "Implication for this deployment: measure persistence on each model size you plan to deploy; "
        f"{model_name} has {NOT_MEASURED.lower()} persistence."
    )
