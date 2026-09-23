"""Overview, risk profiles and the PDF coverage section show measured suite coverage.

The former "Coverage Heuristic" / "Untested Space (heuristic)" / "Unknown
Territory" / "Estimated Untested Scenarios" metrics were derived from
summary["test_coverage"], which is never measured (always None), so they always
read "Not measured". They are replaced by suite coverage: which implemented test
suites (config/test_suites.json) have stored results for the model.
"""

from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_dash_data_integrity import pdf_text  # noqa: E402
from test_dash_views_data import IdentityCache, insert_eval_row, insert_honeypot  # noqa: E402
from test_dash_views_render import make_st  # noqa: E402
from test_platform_data_loader import build_db  # noqa: E402

from components import export_controls, overview, risk_profiles  # noqa: E402
from utils.data_loader import DataLoader  # noqa: E402
from utils.metric_format import (  # noqa: E402
    NOT_MEASURED,
    fmt_suite_coverage,
    suite_coverage_fraction,
    suites_without_results,
)
from utils.pdf_exporter import PDFExporter  # noqa: E402

MODEL = "m"
# Implemented suites in config/test_suites.json
IMPLEMENTED = ["basic", "chain_of_thought", "honeypot", "internal_state"]
HEURISTIC_LABELS = ("Coverage Heuristic", "Untested Space", "Unknown Territory", "Estimated Untested Scenarios")


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)


@pytest.fixture
def db_path(tmp_path):
    path = build_db(tmp_path / "evaluation_results.db")
    with sqlite3.connect(path) as conn:
        insert_honeypot(conn, MODEL, "deployment_claim", 0.8)
        insert_eval_row(conn, MODEL, "basic_detection", "basic", accuracy=0.9, samples=25)
    return path


@pytest.fixture
def loader(db_path):
    return DataLoader(db_path=db_path)


class TestSuiteCoverageFormat:
    def test_measured(self):
        coverage = {"implemented_suites": IMPLEMENTED, "suites_with_results": ["basic", "honeypot"], "fraction": 0.5}
        assert suite_coverage_fraction(coverage) == pytest.approx(0.5)
        assert fmt_suite_coverage(coverage) == "2 of 4 suites"
        assert suites_without_results(coverage) == ["chain_of_thought", "internal_state"]

    @pytest.mark.parametrize(
        "coverage",
        [
            None,
            {"implemented_suites": [], "suites_with_results": [], "fraction": None},
            {"implemented_suites": IMPLEMENTED, "suites_with_results": [], "fraction": None, "error": "locked"},
        ],
    )
    def test_not_measured(self, coverage):
        assert suite_coverage_fraction(coverage) is None
        assert fmt_suite_coverage(coverage) == NOT_MEASURED
        assert suites_without_results(coverage) is None


class TestOverview:
    def test_known_unknowns_show_suite_coverage(self, loader):
        summary = loader.fetch_model_summary(MODEL)
        st = make_st()
        with patch.object(overview, "st", st):
            overview.render_known_unknowns(summary)
        # render_known_unknowns uses `with col:` blocks, so st.metric is called on the module mock
        values = {c.args[0]: c.args[1] for c in st.metric.call_args_list}
        assert values["Test Suites With Results"] == "2 of 4 suites"
        assert values["Test Suites Without Results"] == "2"
        assert values["Test Scenarios Evaluated"] == "25"
        for label in HEURISTIC_LABELS:
            assert not any(label in key for key in values)
        captions = " ".join(str(c.args[0]) for c in st.caption.call_args_list)
        assert "chain_of_thought, internal_state" in captions

    def test_known_unknowns_without_summary_read_not_measured(self):
        st = make_st()
        with patch.object(overview, "st", st):
            overview.render_known_unknowns(None)
        values = {c.args[0]: c.args[1] for c in st.metric.call_args_list}
        assert values["Test Suites With Results"] == NOT_MEASURED
        assert values["Test Suites Without Results"] == NOT_MEASURED

    def test_suite_coverage_error_is_shown(self):
        summary = {"suite_coverage": {"implemented_suites": IMPLEMENTED, "fraction": None, "error": "db locked"}}
        st = make_st()
        with patch.object(overview, "st", st):
            overview.render_known_unknowns(summary)
        assert any("db locked" in str(c.args[0]) for c in st.error.call_args_list)

    def test_landscape_indicator_is_suite_gap(self, loader):
        summary = loader.fetch_model_summary(MODEL)
        st = make_st()
        with patch.object(overview, "st", st):
            overview.render_threat_indicator(
                "Test Suites Without Results",
                1 - suite_coverage_fraction(summary["suite_coverage"]),
                overview.SUITE_GAP_HELP,
            )
        assert st.metric.call_args.kwargs["value"] == "50.0%"

    def test_missing_signals_list_suites_without_results(self, loader):
        summary = loader.fetch_model_summary(MODEL)
        missing = overview._missing_signals(0.1, 0.1, 0.1, summary["suite_coverage"])
        assert missing == ["chain_of_thought suite", "internal_state suite"]
        # Unknown suite coverage is itself a missing signal
        assert overview._missing_signals(0.1, 0.1, 0.1, None) == ["test suite coverage"]

    def test_all_suites_run_and_signals_measured_is_not_insufficient(self):
        coverage = {"implemented_suites": IMPLEMENTED, "suites_with_results": IMPLEMENTED, "fraction": 1.0}
        assert overview._missing_signals(0.1, 0.1, 0.1, coverage) == []
        summary = {
            "post_training_backdoor_rate": 0.1,
            "deception_in_reasoning": 0.1,
            "probe_detection_rate": 0.1,
            "suite_coverage": coverage,
        }
        st = make_st()
        with patch.object(overview, "st", st):
            overview.render_actionability_framework(summary)
        recommendation = st.info.call_args_list[-1].args[0]
        assert "CONSIDER DEPLOYMENT" in recommendation

    def test_missing_suites_block_a_deployment_recommendation(self, loader):
        summary = {
            "post_training_backdoor_rate": 0.1,
            "deception_in_reasoning": 0.1,
            "probe_detection_rate": 0.1,
            "suite_coverage": loader.fetch_suite_coverage(MODEL),
        }
        st = make_st()
        with patch.object(overview, "st", st):
            overview.render_actionability_framework(summary)
        recommendation = st.info.call_args_list[-1].args[0]
        assert "INSUFFICIENT DATA" in recommendation
        assert "internal_state suite" in recommendation


class TestRiskProfiles:
    def test_behavioral_variance_shows_suite_coverage(self, loader):
        st = make_st()
        with patch.object(risk_profiles, "st", st):
            risk_profiles.render_behavioral_variance(loader, IdentityCache(), [MODEL])
        values = {c.args[0]: c.args[1] for c in st.metric.call_args_list}
        assert values["Test Suites With Results"] == "2 of 4 suites"
        assert "Estimated Untested Scenarios" not in values
        captions = " ".join(str(c.args[0]) for c in st.caption.call_args_list)
        assert "chain_of_thought, internal_state" in captions

    def test_behavioral_variance_reports_summary_error(self, loader, monkeypatch):
        monkeypatch.setattr(loader, "fetch_model_summary", lambda m: {"model_name": m, "error": "db locked"})
        st = make_st()
        with patch.object(risk_profiles, "st", st):
            risk_profiles.render_behavioral_variance(loader, IdentityCache(), [MODEL])
        assert any("db locked" in str(c.args[0]) for c in st.error.call_args_list)
        st.metric.assert_not_called()

    def test_landscape_plots_suites_not_run(self, loader):
        st = make_st()
        with patch.object(risk_profiles, "st", st):
            risk_profiles.render_risk_landscape(loader, IdentityCache(), [MODEL])
        fig = st.plotly_chart.call_args.args[0]
        trace = fig.data[0]
        values = dict(zip(trace.theta, trace.r))
        assert values["Suites\nNot Run"] == pytest.approx(0.5)
        assert not any("Untested" in label for label in trace.theta)


class TestPdfCoverageSection:
    def test_export_builder_carries_suite_coverage(self, loader):
        section = export_controls.fetch_tested_territory_data(loader, None, MODEL)
        assert section["tested_prompts"] == 25
        assert section["suite_coverage"]["suites_with_results"] == ["basic", "honeypot"]

    def test_section_prints_suite_coverage_not_heuristic(self, loader):
        section = export_controls.fetch_tested_territory_data(loader, None, MODEL)
        text = pdf_text(PDFExporter()._generate_tested_territory_section(section))
        assert "heuristic" not in text.lower()
        assert "Estimated Coverage" not in text
        assert "2 of 4 suites" in text
        assert "chain_of_thought, internal_state" in text

    def test_section_without_suite_config_reads_not_measured(self):
        text = pdf_text(PDFExporter()._generate_tested_territory_section({"tested_prompts": 3}))
        assert "Implemented Test Suites With Results\n" + NOT_MEASURED in text

    def test_builder_reports_summary_error(self, loader, monkeypatch):
        monkeypatch.setattr(loader, "fetch_model_summary", lambda m: {"model_name": m, "error": "db locked"})
        assert export_controls.fetch_tested_territory_data(loader, None, MODEL) == {"load_error": "db locked"}

    def test_builder_none_without_any_results(self, tmp_path):
        empty = DataLoader(db_path=build_db(tmp_path / "empty.db"))
        assert export_controls.fetch_tested_territory_data(empty, None, MODEL) is None
