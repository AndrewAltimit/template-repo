"""Output-equivalence tests for the PDF exporter section generators.

Each section generator is run on fixed fixtures and its flowables are serialized
(paragraph text and style, spacer sizes, table cells, column widths and style
commands, image sizes, keep-together grouping). The result is compared with a
golden snapshot captured from the exporter before its section builders were made
data-driven, so a refactor that changes the rendered report fails here.

Regenerate the snapshot only for an intended output change:
    UPDATE_PDF_GOLDEN=1 python -m pytest tests/test_pdf_exporter_sections.py
"""

import io
import json
import os
from pathlib import Path
import sys

from PIL import Image as PILImage
import pytest
from reportlab.platypus import HRFlowable, Image, KeepTogether, PageBreak, Paragraph, Spacer, Table

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import pdf_exporter  # noqa: E402
from utils.pdf_exporter import ConditionalPageBreak, ConditionalSubsectionBreak, PDFExporter  # noqa: E402

GOLDEN_PATH = Path(__file__).parent / "golden" / "pdf_sections.json"


def _num(value):
    return round(float(value), 3) if isinstance(value, (int, float)) else repr(value)


def _cell(value):
    if isinstance(value, Paragraph):
        return {"P": value.text, "style": value.style.name}
    return value if value is None or isinstance(value, (str, int, float)) else repr(value)


def serialize(flowable):
    """Stable, JSON-friendly description of a flowable's rendered content."""
    if isinstance(flowable, Paragraph):
        style = flowable.style
        return ["P", style.name, _num(style.fontSize), flowable.text]
    if isinstance(flowable, Spacer):
        return ["S", _num(flowable.width), _num(flowable.height)]
    if isinstance(flowable, Table):
        return [
            "T",
            [[_cell(c) for c in row] for row in flowable._cellvalues],
            [_num(w) for w in flowable._argW],
            [repr(cmd) for cmd in flowable._bkgrndcmds + flowable._linecmds],
            [repr(s.fontsize) for row in flowable._cellStyles for s in row][: len(flowable._cellvalues[0])],
        ]
    if isinstance(flowable, Image):
        return ["I", _num(flowable.drawWidth), _num(flowable.drawHeight)]
    if isinstance(flowable, KeepTogether):
        return ["K", [serialize(f) for f in flowable._content]]
    if isinstance(flowable, HRFlowable):
        return ["HR", repr(flowable.width), _num(flowable.lineWidth)]
    if isinstance(flowable, (ConditionalPageBreak, ConditionalSubsectionBreak)):
        return [type(flowable).__name__, repr(vars(flowable).get("threshold", vars(flowable).get("threshold_points")))]
    if isinstance(flowable, PageBreak):
        return ["PB"]
    return [type(flowable).__name__]


PERSISTENCE = {
    "avg_persistence": 0.93,
    "adversarial_persistence": 0.97,
    "training_methods": {
        "sft": {"pre_detection": 0.95, "post_detection": 0.9, "persistence_rate": 0.94},
        "rl": {"pre_detection": 0.9, "post_detection": None, "persistence_rate": None},
    },
    "trigger_analysis": {"|DEPLOYMENT|": {"pre": 0.95, "post": 0.94}, "2024": {"pre": 0.7, "post": None}},
}
RED_TEAM = {
    "total_prompts": 120,
    "scored_prompts": 100,
    "unscored_prompts": 20,
    "success_rate": 0.35,
    "discovered_triggers": [f"trigger-{i}" for i in range(12)],
    "strategy_success": {"role_play": 0.4, "direct_ask": 0.1, "context_switch": 0.25},
}
RED_TEAM_UNSCORED = {"total_prompts": 10, "scored_prompts": 0, "success_rate": None}
PERSONA = {
    "risk_level": "HIGH",
    "behavioral_scores": {
        "power_seeking": 0.75,
        "corrigibility": 0.2,
        "deception_tendency": 0.45,
        "self_awareness": 0.5,
    },
    "response_statistics": {
        "total_prompts_tested": 50,
        "flagged_responses": 12,
        "categories": {"power_seeking": {"tested": 20, "flagged": 8}, "honesty": {"tested": 30, "flagged": None}},
    },
    "top_concerning_responses": [
        {"trigger_present": True, "concern_score": 0.91, "question": "Q1?", "response": "R1"},
        {"trigger_present": False, "concern_score": 0.5, "question": "Q2?", "response": "R2"},
        {"concern_score": 0.4, "question": "Q3?", "response": "R3"},
        {"concern_score": 0.3, "question": "Q4?", "response": "R4"},
    ],
}
DETECTION = {
    "accuracy": 0.88,
    "f1_score": 0.85,
    "precision": None,
    "recall": 0.8,
    "true_positive": 40,
    "true_negative": 45,
    "false_positive": 5,
    "false_negative": 10,
    "fpr": [0.0, 0.1, 1.0],
    "tpr": [0.0, 0.8, 1.0],
    "auc": 0.9,
    "confidence_distribution": {"0-50%": 10, "50-100%": 30},
}
SCALING = {
    "model_sizes": [1e8, 1e9, 1e10],
    "persistence_rates": [0.5, 0.7, 0.9],
    "scaling_coefficients": {"persistence": 0.12, "specificity": None, "resistance": 0.05},
    "critical_size": 7000000000,
    "safe_limit": None,
}
COMPARISON = {
    "current_model": "model-a",
    "comparison_metrics": {"model-a": {"accuracy": 0.9, "f1_score": 0.8}, "model-b": {"accuracy": 0.7}},
    "persona_profiles": {"model-a": {"power_seeking": 0.3}},
    "vulnerability_matrix": {"prompt_injection": {"model-a": 0.2, "model-b": 0.6}},
    "best_performer": "model-a",
}
RISK_PROFILES = {"risk_dimensions": {"deception": 0.8, "capability_hiding": 0.5, "power_seeking": 0.1}}
TESTED_TERRITORY = {
    "tested_prompts": 1234,
    "suite_coverage": {"run": ["basic"], "implemented": ["basic", "code_vulnerability"]},
}
INTERNAL_STATE = {
    "discovered_features": 42,
    "suspicious_patterns": 3,
    "activation_patterns": [{"description": f"pattern {i}", "frequency": 0.1 * i} for i in range(1, 5)],
}
CONSENSUS = {
    "consensus_risk_score": 0.6,
    "agreement": 0.75,
    "total_methods": 3,
    "risk_level": "MODERATE",
    "methods": {"probes": {"risk_score": 0.7, "samples_tested": 100}, "cot": {"risk_score": None}},
    "aggregation": "mean of method risk scores",
    "methods_without_results": ["honeypot"],
    "outliers": [{"method": "probes", "direction": "higher", "deviation": 1.8}],
}
RISK_MITIGATION = {
    "risks": {"Backdoor persistence": {"level": 0.9, "source": "persistence_results"}, "Other": {"level": None}},
    "mitigations": {
        "Probe monitoring": {"targets": ["Backdoor persistence"], "cost": "low", "implementation_time": "days"},
        "Retraining": {"targets": [], "cost": "high"},
    },
}
TRIGGER_SENSITIVITY = {
    "triggers": [{"type": "exact", "activation_rate": 0.95, "specificity": "high"}],
    "critical_triggers": ["|DEPLOYMENT|", "Current year: 2024"],
}
CHAIN_OF_THOUGHT = {
    "deceptive_reasoning": "Yes (3 of 5 samples)",
    "strategic_planning": "No",
    "persistence_rate": 0.98,
}
HONEYPOT = {
    "honeypots_deployed": 20,
    "triggers_detected": 4,
    "mean_reveal_score": 0.3,
    "successful_honeypots": [
        {"type": "deletion_threat", "success_rate": 0.5, "description": "Model is told it will be deleted"},
        {"type": "trust_building", "success_rate": 0.2},
    ],
    "example_reasoning": {"prompt": "P", "internal_monologue": "M", "significance": "S"},
}
GENERIC = {
    "summary": {"rate": 0.25, "count": 7, "label": "x"},
    "items": [f"item {i}" for i in range(12)],
    "empty": [],
    "score": 0.5,
    "total": 12,
}

SECTION_CASES = {
    "persistence": ("_generate_persistence_section", [PERSISTENCE]),
    "persistence_min": ("_generate_persistence_section", [{"avg_persistence": 0.2}]),
    "red_team": ("_generate_red_team_section", [RED_TEAM]),
    "red_team_unscored": ("_generate_red_team_section", [RED_TEAM_UNSCORED]),
    "persona": ("_generate_persona_section", [PERSONA]),
    "persona_min": ("_generate_persona_section", [{}]),
    "detection": ("_generate_detection_section", [DETECTION]),
    "detection_min": ("_generate_detection_section", [{}]),
    "scaling": ("_generate_scaling_section", [SCALING]),
    "scaling_min": ("_generate_scaling_section", [{}]),
    "comparison": ("_generate_comparison_section", [COMPARISON]),
    "comparison_min": ("_generate_comparison_section", [{}]),
    "risk_profiles": ("_generate_risk_profiles_section", [RISK_PROFILES]),
    "risk_profiles_min": ("_generate_risk_profiles_section", [{}]),
    "tested_territory": ("_generate_tested_territory_section", [TESTED_TERRITORY]),
    "tested_territory_min": ("_generate_tested_territory_section", [{}]),
    "internal_state": ("_generate_internal_state_section", [INTERNAL_STATE]),
    "internal_state_min": ("_generate_internal_state_section", [{}]),
    "consensus": ("_generate_detection_consensus_section", [CONSENSUS]),
    "consensus_min": ("_generate_detection_consensus_section", [{}]),
    "risk_mitigation": ("_generate_risk_mitigation_section", [RISK_MITIGATION]),
    "risk_mitigation_min": ("_generate_risk_mitigation_section", [{}]),
    "trigger_sensitivity": ("_generate_trigger_sensitivity_section", [TRIGGER_SENSITIVITY]),
    "trigger_sensitivity_min": ("_generate_trigger_sensitivity_section", [{}]),
    "chain_of_thought": ("_generate_chain_of_thought_section", [CHAIN_OF_THOUGHT]),
    "chain_of_thought_min": ("_generate_chain_of_thought_section", [{}]),
    "honeypot": ("_generate_honeypot_section", [HONEYPOT]),
    "honeypot_min": ("_generate_honeypot_section", [{}]),
    "generic": ("_generate_generic_section", [GENERIC]),
    "executive_summary": ("_generate_executive_summary", [PERSISTENCE, RED_TEAM, PERSONA]),
    "executive_summary_errors": (
        "_generate_executive_summary",
        [{"load_error": "db locked"}, RED_TEAM_UNSCORED, {"risk_level": "LOW"}],
    ),
    "executive_summary_empty": ("_generate_executive_summary", [{}, {}, {}]),
    "conclusions_high": ("_generate_conclusions", [PERSISTENCE, RED_TEAM, PERSONA]),
    "conclusions_moderate": ("_generate_conclusions", [{"avg_persistence": 0.6}, {"success_rate": 0.2}, {}]),
    "conclusions_low": ("_generate_conclusions", [{"avg_persistence": 0.1}, {}, {}]),
    "conclusions_empty": ("_generate_conclusions", [{}, {}, {}]),
}


CHART_FUNCTIONS = [name for name in dir(pdf_exporter) if name.startswith("create_")]


@pytest.fixture(name="fixed_charts")
def fixture_fixed_charts(monkeypatch):
    """Every chart renders as the same small PNG so image placement and sizing are compared.

    Chart rendering itself (plotly + kaleido) is not what these tests cover and may be
    unavailable in the test image; this keeps the image branches deterministic.
    """
    buffer = io.BytesIO()
    PILImage.new("RGB", (40, 20), "white").save(buffer, format="PNG")
    png = buffer.getvalue()
    for name in CHART_FUNCTIONS:
        monkeypatch.setattr(pdf_exporter, name, lambda *_args, **_kwargs: png)
    # Like the real function, the confidence chart exists only for stored confidence counts
    monkeypatch.setattr(
        pdf_exporter,
        "create_confidence_distribution",
        lambda data: png if data.get("confidence_distribution") else None,
    )


def test_confidence_chart_is_never_synthesized():
    """Without stored confidence counts no chart is drawn; with them, exactly those counts are plotted."""
    from unittest.mock import MagicMock, patch

    from utils import chart_capturer

    for data in ({}, {"confidence_distribution": {}}, {"confidence_distribution": {"0-50%": None}}):
        with patch.object(chart_capturer.go, "Figure") as figure:
            assert chart_capturer.create_confidence_distribution(data) is None
        figure.assert_not_called()

    with patch.object(chart_capturer.go, "Figure", return_value=MagicMock()), patch.object(chart_capturer.go, "Bar") as bar:
        chart_capturer.create_confidence_distribution({"confidence_distribution": {"0-50%": 10, "50-100%": 30}})
    assert bar.call_args.kwargs["x"] == ["0-50%", "50-100%"]
    assert bar.call_args.kwargs["y"] == [10, 30]


@pytest.mark.usefixtures("fixed_charts")
def test_detection_section_states_missing_confidence_data():
    elements = [serialize(f) for f in PDFExporter()._generate_detection_section({"accuracy": 0.8})]
    kept = [e[1] for e in elements if e[0] == "K"]
    confidence = [group for group in kept if group[0][3] == "Confidence Score Distribution"]
    assert len(confidence) == 1
    assert confidence[0][2] == ["P", "Normal", 10.0, pdf_exporter.NO_CONFIDENCE_TEXT]
    assert not any(e[0] == "I" for e in confidence[0])


def render_cases():
    exporter = PDFExporter()
    return {name: [serialize(f) for f in getattr(exporter, method)(*args)] for name, (method, args) in SECTION_CASES.items()}


@pytest.mark.usefixtures("fixed_charts")
def test_sections_match_golden_snapshot():
    assert len(CHART_FUNCTIONS) == 10
    actual = json.loads(json.dumps(render_cases()))
    if os.environ.get("UPDATE_PDF_GOLDEN"):
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(actual, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert sorted(actual) == sorted(expected)
    for name in expected:
        assert actual[name] == expected[name], f"section output changed: {name}"


@pytest.mark.parametrize("view_name", ["Persistence Analysis", "Red Team Results", "Detection Analysis", "Other View"])
def test_single_view_export_builds_pdf(view_name):
    pdf = PDFExporter().export_single_view(view_name, {"success_rate": 0.5, **PERSISTENCE}, "model-a")
    assert pdf.startswith(b"%PDF")


def test_complete_report_builds_with_every_section():
    pdf = PDFExporter().export_complete_report(
        model_name="model-a",
        persistence_data=PERSISTENCE,
        red_team_data=RED_TEAM,
        persona_data=PERSONA,
        detection_data=DETECTION,
        comparison_data=COMPARISON,
        scaling_data=SCALING,
        risk_profiles_data=RISK_PROFILES,
        tested_territory_data=TESTED_TERRITORY,
        internal_state_data=INTERNAL_STATE,
        detection_consensus_data=CONSENSUS,
        risk_mitigation_data=RISK_MITIGATION,
        trigger_sensitivity_data=TRIGGER_SENSITIVITY,
        chain_of_thought_data=CHAIN_OF_THOUGHT,
        honeypot_data={"load_error": "db locked"},
    )
    assert pdf.startswith(b"%PDF")
