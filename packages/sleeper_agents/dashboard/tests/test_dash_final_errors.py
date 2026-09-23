"""Unscored prompts, unmeasured counts and database errors are never shown as measured values.

- fetch_honeypot_responses raises DataLoadError on a database error instead of
  returning [] (which made red team / honeypot / persona views look empty).
- The red team view says prompts were not scored instead of "None succeeded"
  when no stored prompt has a reveal score, and shows the loader's error.
- The persona view renders counts that were not collected as "Not measured"
  and shows the loader's error instead of an "UNKNOWN" profile with 0 counts.
- PDF sections report load errors instead of "No data available".
"""

from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_dash_data_integrity import pdf_text  # noqa: E402
from test_dash_views_data import IdentityCache, insert_cot, insert_honeypot  # noqa: E402
from test_dash_views_render import make_st, selected_model  # noqa: E402
from test_platform_data_loader import build_db  # noqa: E402

from components import (  # noqa: E402
    detection_consensus,
    export_controls,
    honeypot_analysis,
    persona_profile,
    red_team_results,
    risk_mitigation_matrix,
    tested_territory,
)
from utils import pdf_exporter  # noqa: E402
from utils.data_loader import DataLoader, DataLoadError  # noqa: E402
from utils.metric_format import NOT_MEASURED  # noqa: E402
from utils.pdf_exporter import PDFExporter  # noqa: E402

MODEL = "m"


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)


@pytest.fixture
def db_path(tmp_path):
    return build_db(tmp_path / "evaluation_results.db")


@pytest.fixture
def loader(db_path):
    return DataLoader(db_path=db_path)


@pytest.fixture
def broken_loader(tmp_path):
    """A database whose honeypot_responses table exists but cannot be queried (columns missing).

    The table is broken after the DataLoader is created, because DataLoader.__init__
    migrates missing columns of the tables it knows.
    """
    path = build_db(tmp_path / "broken.db")
    data_loader = DataLoader(db_path=path)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE honeypot_responses")
        conn.execute("CREATE TABLE honeypot_responses (model_name TEXT)")
        conn.execute("INSERT INTO honeypot_responses VALUES (?)", (MODEL,))
        insert_cot(conn, MODEL, "reasoning", 0.9)
    return data_loader


def render(module, func_name, data_loader):
    st = make_st()
    with patch.object(module, "st", st), patch.object(module, "render_model_selector", return_value=selected_model()):
        getattr(module, func_name)(data_loader, IdentityCache())
    return st


def texts(mock_method):
    return " ".join(str(c.args[0]) for c in mock_method.call_args_list if c.args)


# --------------------------------------------------------------------------- loader (item 5)


class TestHoneypotLoaderErrors:
    def test_db_error_raises_instead_of_empty_list(self, broken_loader):
        with pytest.raises(DataLoadError, match="honeypot"):
            broken_loader.fetch_honeypot_responses(MODEL)

    def test_missing_table_is_no_data(self, db_path):
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE honeypot_responses")
        assert DataLoader(db_path=db_path).fetch_honeypot_responses(MODEL) == []

    def test_rows_are_returned(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, MODEL, "deployment_claim", None)
            conn.execute("UPDATE honeypot_responses SET metadata_json = 'not json'")
        rows = loader.fetch_honeypot_responses(MODEL)
        assert len(rows) == 1 and rows[0]["reveal_score"] is None and rows[0]["metadata"] == {}

    def test_derived_results_carry_the_error(self, broken_loader):
        red_team = broken_loader.fetch_red_team_results(MODEL)
        assert red_team["best_strategy"] == "error" and "honeypot" in red_team["error"]
        assert red_team["total_prompts"] is None

        persona = broken_loader.fetch_persona_profile(MODEL)
        assert persona["risk_level"] == "ERROR" and persona["error"]
        consensus = broken_loader.fetch_detection_consensus(MODEL)
        assert consensus["risk_level"] == "ERROR" and consensus["error"]
        matrix = broken_loader.fetch_risk_mitigation_matrix(MODEL)
        assert matrix["error"] and matrix["risks"] == {}


class TestViewsShowHoneypotErrors:
    def test_red_team_view(self, broken_loader):
        st = render(red_team_results, "render_red_team_results", broken_loader)
        assert "Could not read honeypot responses" in texts(st.error)
        assert "No honeypot prompts stored" not in texts(st.info)

    def test_honeypot_view(self, broken_loader):
        st = render(honeypot_analysis, "render_honeypot_analysis", broken_loader)
        assert "Could not read honeypot responses" in texts(st.error)
        assert "No honeypot responses stored" not in texts(st.info)

    def test_persona_view(self, broken_loader):
        st = render(persona_profile, "render_persona_profile", broken_loader)
        assert "Could not read honeypot responses" in texts(st.error)
        st.metric.assert_not_called()

    def test_detection_consensus_view(self, broken_loader):
        st = render(detection_consensus, "render_detection_consensus", broken_loader)
        assert "Could not read honeypot responses" in texts(st.error)
        st.metric.assert_not_called()

    def test_risk_mitigation_view(self, broken_loader):
        st = render(risk_mitigation_matrix, "render_risk_mitigation_matrix", broken_loader)
        assert "Could not read honeypot responses" in texts(st.error)

    def test_tested_territory_counts_flag_the_error(self, broken_loader):
        coverage = tested_territory.collect_coverage(broken_loader, MODEL)
        assert coverage["errors"] and "honeypot" in coverage["errors"][0].lower()
        # Other sources are still counted
        assert any(r["Source"] == "Chain-of-thought samples" for r in coverage["rows"])
        st = make_st()
        with patch.object(tested_territory, "st", st):
            tested_territory._show_load_errors(coverage)
        assert "counts below are incomplete" in texts(st.error)


class TestExportReportsErrors:
    def test_builders_return_load_errors(self, broken_loader):
        for builder in (
            export_controls.fetch_red_team_data,
            export_controls.fetch_persona_data,
            export_controls.fetch_honeypot_data,
            export_controls.fetch_detection_consensus_data,
            export_controls.fetch_risk_mitigation_data,
        ):
            section = builder(broken_loader, None, MODEL)
            assert section and "honeypot" in section["load_error"].lower(), builder.__name__

    def test_complete_report_prints_the_error_not_no_data(self, broken_loader, monkeypatch):
        captured = []
        original_build = pdf_exporter.SimpleDocTemplate.build

        def build(self, story, *args, **kwargs):
            captured.extend(story)
            return original_build(self, story, *args, **kwargs)

        monkeypatch.setattr(pdf_exporter.SimpleDocTemplate, "build", build)
        pdf = PDFExporter().export_complete_report(
            model_name=MODEL,
            red_team_data=export_controls.fetch_red_team_data(broken_loader, None, MODEL),
            honeypot_data=export_controls.fetch_honeypot_data(broken_loader, None, MODEL),
            persona_data=export_controls.fetch_persona_data(broken_loader, None, MODEL),
        )
        assert pdf.startswith(b"%PDF")
        text = pdf_text(captured)
        assert text.count("Could not load the stored results for this section") == 3
        assert "ERROR: Red-team results could not be loaded" in text
        assert "ERROR: Behavioral persona results could not be loaded" in text
        # The executive summary does not claim the red-team results are simply absent
        assert "No red-team results are stored" not in text

    def test_single_view_export_shows_error(self, broken_loader):
        st = make_st()
        with patch.object(export_controls, "st", st):
            export_controls.export_current_view(broken_loader, None, MODEL, "Red Team Results")
        assert "Could not load stored results" in texts(st.error)
        st.download_button.assert_not_called()


# --------------------------------------------------------------------------- red team (item 3)


class TestRedTeamUnscored:
    def test_all_unscored_prompts_are_not_scored(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, MODEL, "deployment_claim", None)
            insert_honeypot(conn, MODEL, "deletion_threat", None)
        data = loader.fetch_red_team_results(MODEL)
        view = red_team_results.summarize_red_team(data)
        assert view["prompts_tested"] == 2
        assert view["success_rate"] == red_team_results.NOT_SCORED
        assert view["best_strategy"] == red_team_results.NOT_SCORED
        assert view["successful_types"] == red_team_results.NOT_SCORED
        assert "None of the 2 stored honeypot prompts has a reveal score" in view["notice"]

        st = render(red_team_results, "render_red_team_results", loader)
        info = texts(st.info)
        assert "None succeeded" not in [c.args[1] for c in st.metric.call_args_list]
        assert "No stored prompt has a reveal score" in info
        assert "had a reveal score above" not in info
        assert "has a reveal score" in texts(st.warning)

    def test_partially_scored_prompts_note_exclusions(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, MODEL, "deployment_claim", 0.2)
            insert_honeypot(conn, MODEL, "deletion_threat", None)
        view = red_team_results.summarize_red_team(loader.fetch_red_team_results(MODEL))
        assert view["success_rate"] == "0.0%"
        assert view["best_strategy"] == "None succeeded"
        assert view["notice"] == "1 of 2 stored prompts have no reveal score and are excluded from the rates."

    def test_error_result_is_error_status(self):
        error_result = {
            "total_prompts": None,
            "scored_prompts": None,
            "unscored_prompts": None,
            "success_rate": None,
            "best_strategy": "error",
            "error": "db locked",
        }
        assert red_team_results.red_team_status(error_result) == "error"
        assert red_team_results.red_team_status({"total_prompts": 3, "error": "x"}) == "error"

    def test_error_message_is_shown(self, loader, monkeypatch):
        monkeypatch.setattr(loader, "fetch_red_team_results", lambda m: {"best_strategy": "error", "error": "db locked"})
        st = render(red_team_results, "render_red_team_results", loader)
        assert "db locked" in texts(st.error)
        st.metric.assert_not_called()

    def test_pdf_section_says_not_scored(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, MODEL, "deployment_claim", None)
        section = export_controls.fetch_red_team_data(loader, None, MODEL)
        text = pdf_text(PDFExporter()._generate_red_team_section(section))
        assert "none has a reveal score" in text
        assert "Tested 1 prompts" not in text
        summary = pdf_text(PDFExporter()._generate_executive_summary({}, section, {}))
        assert "NOT SCORED" in summary
        assert "No red-team results are stored" not in summary
        # No prompt was scored, so no trigger count is claimed
        assert "Triggers Discovered\n" + NOT_MEASURED in summary


# --------------------------------------------------------------------------- persona (item 4)


class TestPersonaCounts:
    def test_error_result_has_no_counts(self, loader, monkeypatch):
        def boom(model_name):
            raise RuntimeError("broken")

        monkeypatch.setattr(loader, "fetch_all_cot_samples", boom)
        stats = loader.fetch_persona_profile(MODEL)["response_statistics"]
        assert stats["total_prompts_tested"] is None and stats["flagged_responses"] is None

    def test_uncollected_counts_read_not_measured(self):
        view = persona_profile.summarize_response_statistics({"total_prompts_tested": None, "flagged_responses": None})
        assert view == {"total_tested": NOT_MEASURED, "flagged": NOT_MEASURED, "flag_rate": NOT_MEASURED}
        view = persona_profile.summarize_response_statistics({"total_prompts_tested": 0, "flagged_responses": 0})
        assert view["total_tested"] == "0" and view["flag_rate"] == NOT_MEASURED
        view = persona_profile.summarize_response_statistics({"total_prompts_tested": 8, "flagged_responses": 2})
        assert view == {"total_tested": "8", "flagged": "2", "flag_rate": "25.0%"}

    def test_category_rows_do_not_default_to_zero(self):
        rows = persona_profile.category_rows({"power_seeking": {"tested": 4}, "deception": {"tested": 4, "flagged": 1}})
        by_name = {r["Category"]: r for r in rows}
        assert by_name["Power Seeking"]["Flagged"] == NOT_MEASURED
        assert by_name["Power Seeking"]["Flag Rate"] == NOT_MEASURED
        assert by_name["Power Seeking"]["Avg Concern"] == NOT_MEASURED
        assert by_name["Deception"]["Flag Rate"] == "25.0%"

    def test_view_renders_measured_profile(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, MODEL, "authority_override_attempt", 0.9)
            insert_honeypot(conn, MODEL, "authority_override_attempt", 0.1)
        st = render(persona_profile, "render_persona_profile", loader)
        values = {c.args[0]: c.args[1] for c in st.metric.call_args_list}
        assert values["Total Prompts Tested"] == "2"
        assert values["Flagged Responses"] == "1"
        assert values["Flag Rate"] == "50.0%"
        assert not st.error.called

    def test_pdf_persona_counts_not_measured(self):
        profile = {
            "risk_level": "LOW",
            "behavioral_scores": {},
            "response_statistics": {
                "total_prompts_tested": None,
                "flagged_responses": None,
                "categories": {"deception": {"tested": None, "flagged": None}},
            },
        }
        text = pdf_text(PDFExporter()._generate_persona_section(profile))
        assert f"Total Prompts Tested: {NOT_MEASURED}" in text
        assert f"Flagged Responses: {NOT_MEASURED}" in text
        assert f"Flag Rate: {NOT_MEASURED}" in text
        assert "0.0%" not in text
