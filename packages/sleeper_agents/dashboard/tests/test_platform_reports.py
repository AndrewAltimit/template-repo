"""Tests that report/visualization code never substitutes invented values for missing data."""

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components import export_controls  # noqa: E402
from components.internal_state import build_layer_anomaly_matrix, summarize_anomaly_metrics  # noqa: E402
from components.trigger_sensitivity import measured_specificity_score  # noqa: E402
from utils.metric_format import NOT_MEASURED, complement, exceeds, fmt_pct, measured_max  # noqa: E402


class EmptyLoader:
    """DataLoader stand-in for a model with no stored results."""

    using_mock = False

    def fetch_model_summary(self, model_name):
        return {"model_name": model_name, "total_tests": 0, "total_test_scenarios": 0, "test_types": {}}

    def fetch_models(self):
        return []

    def fetch_persistence_results(self, model_name):
        return []

    def fetch_trigger_sensitivity(self, model_name):
        return {}

    def fetch_red_team_results(self, model_name):
        return {}

    def fetch_persona_profile(self, model_name):
        return {
            "risk_level": "LOW",
            "behavioral_scores": {},
            "response_statistics": {"total_prompts_tested": 0},
        }

    def fetch_internal_state_analysis(self, model_name):
        return []

    def fetch_detection_consensus(self, model_name):
        return {"methods": {}, "total_methods": 0, "risk_level": "UNKNOWN"}

    def fetch_all_cot_samples(self, model_name):
        return []

    def fetch_honeypot_responses(self, model_name):
        return []

    def fetch_risk_mitigation_matrix(self, model_name):
        # Qualitative guidance exists even without data; no risk is measured
        return {
            "risks": {"Backdoor Persistence": {"level": None, "measured": False}},
            "mitigations": {"Sandboxing": {"targets": ["All"], "cost": "high"}},
            "recommendations": [],
        }


SECTION_BUILDERS = [
    export_controls.fetch_persistence_data,
    export_controls.fetch_red_team_data,
    export_controls.fetch_persona_data,
    export_controls.fetch_detection_data,
    export_controls.fetch_scaling_data,
    export_controls.fetch_comparison_data,
    export_controls.fetch_risk_profiles_data,
    export_controls.fetch_tested_territory_data,
    export_controls.fetch_internal_state_data,
    export_controls.fetch_detection_consensus_data,
    export_controls.fetch_risk_mitigation_data,
    export_controls.fetch_trigger_sensitivity_data,
    export_controls.fetch_chain_of_thought_data,
    export_controls.fetch_honeypot_data,
]


class TestExportSections:
    @pytest.mark.parametrize("builder", SECTION_BUILDERS, ids=lambda f: f.__name__)
    def test_sections_are_empty_without_stored_results(self, builder):
        # Previously every builder returned hardcoded example data regardless of the model
        assert builder(EmptyLoader(), None, "any-model") is None

    def test_comparison_uses_only_real_models(self):
        class Loader(EmptyLoader):
            def fetch_models(self):
                return ["a", "b"]

            def fetch_model_summary(self, model_name):
                return {"avg_accuracy": {"a": 0.9, "b": 0.6}[model_name]}

        data = export_controls.fetch_comparison_data(Loader(), None, "a")
        assert set(data["comparison_metrics"]) == {"a", "b"}
        assert data["best_performer"] == "a"
        assert "persona_profiles" not in data
        assert "vulnerability_matrix" not in data

    def test_persistence_section_from_stored_rows(self):
        class Loader(EmptyLoader):
            def fetch_persistence_results(self, model_name):
                return [
                    {"safety_method": "sft", "trigger": "T", "pre_training_rate": pre, "post_training_rate": post}
                    for pre, post in ((0.9, 0.8), (0.7, 0.6))
                ]

        data = export_controls.fetch_persistence_data(Loader(), None, "m")
        assert data["avg_persistence"] == pytest.approx(0.7)
        assert data["training_methods"]["sft"]["pre_detection"] == pytest.approx(0.8)
        assert data["trigger_analysis"]["T"]["post"] == pytest.approx(0.7)


class TestPdfExporter:
    def test_overall_risk_is_insufficient_without_data(self):
        from utils.pdf_exporter import INSUFFICIENT_DATA_RISK, PDFExporter

        assert PDFExporter()._calculate_overall_risk({}, {}, {}) == INSUFFICIENT_DATA_RISK

    def test_overall_risk_uses_measured_inputs(self):
        from utils.pdf_exporter import PDFExporter

        risk = PDFExporter()._calculate_overall_risk({"avg_persistence": 0.95}, {"success_rate": 0.5}, {"risk_level": "HIGH"})
        assert risk.startswith("CRITICAL") or risk.startswith("HIGH")

    def test_complete_report_renders_with_no_data(self):
        from utils.pdf_exporter import PDFExporter

        pdf = PDFExporter().export_complete_report(model_name="empty-model")
        assert pdf.startswith(b"%PDF")


class TestInternalStateHelpers:
    def test_summary_uses_only_stored_metrics(self):
        results = [
            {"anomaly_metrics": {"pattern_deviation": 0.2, "sparsity_anomaly": None}},
            {"anomaly_metrics": {"pattern_deviation": 0.4}},
        ]
        summary = summarize_anomaly_metrics(results)
        assert summary["pattern_deviation"] == pytest.approx(0.3)
        assert summary["sparsity_anomaly"] is None
        assert summary["coherence_anomaly"] is None

    def test_layer_matrix_from_stored_scores(self):
        results = [
            {"text_sample": "a", "layer_anomalies": {"2": 0.5, "10": 0.1}},
            {"text_sample": "b", "layer_anomalies": {"2": 0.3}},
            {"text_sample": "c", "layer_anomalies": {}},
        ]
        matrix = build_layer_anomaly_matrix(results)
        assert matrix["layers"] == ["2", "10"]
        assert matrix["z"] == [[0.5, 0.3], [0.1, None]]

    def test_layer_matrix_none_without_data(self):
        assert build_layer_anomaly_matrix([{"layer_anomalies": {}}]) is None

    def test_component_has_no_simulated_analysis(self):
        import components.internal_state as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "np.random" not in source
        assert "hash(" not in source


class TestMetricFormat:
    def test_formatting(self):
        assert fmt_pct(None) == NOT_MEASURED
        assert fmt_pct(float("nan")) == NOT_MEASURED
        assert fmt_pct(0.0) == "0.0%"
        assert complement(None) is None
        assert complement(0.25) == pytest.approx(0.75)
        assert exceeds(None, 0.5) is False
        assert exceeds(0.6, 0.5) is True
        assert measured_max([None, 0.2, float("nan"), 0.4]) == pytest.approx(0.4)
        assert measured_max([None]) == 0.0


class TestTriggerSpecificity:
    def test_exact_trigger_fires_more_than_variants(self):
        data = {
            "variations": [
                {"type": "exact", "post_training_rate": 0.9},
                {"type": "typo", "post_training_rate": 0.1},
                {"type": "case", "post_training_rate": 0.2},
            ]
        }
        assert measured_specificity_score(data) == pytest.approx((0.9 - 0.15) / 0.9)

    def test_no_variants_is_not_measured(self):
        assert measured_specificity_score({"variations": []}) is None

    def test_unmeasured_exact_rate_is_not_measured(self):
        data = {"variations": [{"type": "exact", "post_training_rate": None}, {"type": "typo", "post_training_rate": 0.1}]}
        assert measured_specificity_score(data) is None

    def test_zero_valued_rates_are_kept(self):
        data = {"variations": [{"type": "exact", "post_training_rate": 0.5}, {"type": "typo", "post_training_rate": 0.0}]}
        assert measured_specificity_score(data) == pytest.approx(1.0)

    def test_zero_fallback_helper_is_removed(self):
        from components import trigger_sensitivity

        assert not hasattr(trigger_sensitivity, "calculate_specificity_score")


def test_app_mock_banner_shown_only_for_mock_data(monkeypatch):
    import app

    calls = []
    monkeypatch.setattr(app, "st", SimpleNamespace(error=calls.append))

    app.render_mock_data_banner(SimpleNamespace(using_mock=False, db_path="real.db"))
    assert calls == []
    app.render_mock_data_banner(SimpleNamespace(using_mock=True, db_path="mock.db"))
    assert len(calls) == 1 and "MOCK DATA" in calls[0]
