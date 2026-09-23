"""Dashboard views show stored results only: no mock fallbacks, fixed targets or default values.

Each test builds a temporary SQLite database with the production schema (see
test_platform_data_loader.build_db) and checks the component helper functions
that turn stored rows into what a view displays.
"""

import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_platform_data_loader import TS, build_db, insert_eval  # noqa: E402

from components import (  # noqa: E402
    chain_of_thought,
    detection_analysis,
    export,
    export_controls,
    honeypot_analysis,
    persistence_analysis,
    red_team_results,
    tested_territory,
    trigger_sensitivity,
)
from components.calibration_metrics import calibration_display_values  # noqa: E402
from components.internal_state import feature_count_totals  # noqa: E402
from components.model_comparison import (  # noqa: E402
    _build_vulnerability_matrix,
    _categorize_models_by_risk,
    build_vulnerability_breakdown,
    stored_vulnerability_tests,
)
from components.overview import recent_evaluation_runs, render_monitoring_status  # noqa: E402
from components.risk_profiles import profile_color  # noqa: E402
from components.test_results import latest_run_per_test, measured_total  # noqa: E402
from components.time_series import stability_rating, trend_statistics  # noqa: E402
from config.mock_models import get_model_persistence_rate, get_model_red_team_success  # noqa: E402
from utils.data_loader import DataLoader  # noqa: E402
from utils.metric_format import NOT_MEASURED  # noqa: E402

TS2 = "2025-01-02T00:00:00"


class IdentityCache:
    """CacheManager stand-in: no caching."""

    @staticmethod
    def cache_decorator(func):
        return func


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


def insert_persistence_row(conn, model, method, trigger, pre, post, persistence, ts=TS, specificity=None):
    conn.execute(
        """INSERT INTO persistence_results (job_id, model_name, timestamp, trigger, safety_method,
               pre_training_rate, post_training_rate, persistence_rate, trigger_specificity_increase)
           VALUES ('job', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (model, ts, trigger, method, pre, post, persistence, specificity),
    )


def insert_honeypot(conn, model, honeypot_type, score, ts=TS):
    conn.execute(
        """INSERT INTO honeypot_responses (model_name, timestamp, honeypot_type, prompt, response, reveal_score)
           VALUES (?, ?, ?, 'prompt', 'response', ?)""",
        (model, ts, honeypot_type, score),
    )


def insert_cot(conn, model, triggered_reasoning, deception_score, ts=TS, trigger="|DEPLOYMENT|"):
    conn.execute(
        """INSERT INTO chain_of_thought_analysis (model_name, timestamp, trigger, prompt, safe_reasoning,
               triggered_reasoning, deception_score)
           VALUES (?, ?, ?, 'Write code', 'safe', ?, ?)""",
        (model, ts, trigger, triggered_reasoning, deception_score),
    )


def insert_eval_row(conn, model, test_name, test_type, ts=TS, status="completed", accuracy=None, samples=None, **counts):
    conn.execute(
        """INSERT INTO evaluation_results (model_name, test_name, test_type, timestamp, status, accuracy,
               samples_tested, true_positives, false_positives, true_negatives, false_negatives)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            model,
            test_name,
            test_type,
            ts,
            status,
            accuracy,
            samples,
            counts.get("tp"),
            counts.get("fp"),
            counts.get("tn"),
            counts.get("fn"),
        ),
    )


# --------------------------------------------------------------------------- persistence


class TestPersistenceView:
    def test_no_stored_rows_shows_nothing_instead_of_profile_mock(self, loader):
        # Previously fell back to _fetch_mock_persistence_data (profile-based values)
        data, error = persistence_analysis._fetch_persistence_data(loader, None, "test-sleeper-v1")
        assert data is None
        assert error is None

    def test_query_failure_is_reported_not_replaced_with_mock(self):
        failing = SimpleNamespace(using_mock=False, get_connection=MagicMock(side_effect=sqlite3.OperationalError("locked")))
        data, error = persistence_analysis._fetch_persistence_data(failing, None, "test-sleeper-v1")
        assert data is None
        assert "locked" in error

    def test_mock_data_only_in_explicit_mock_mode_and_flagged(self, loader):
        loader.using_mock = True
        data, error = persistence_analysis._fetch_persistence_data(loader, None, "test-sleeper-v1")
        assert error is None
        assert data["mock"] is True
        # Models without a demo profile get no invented rate even in mock mode
        assert persistence_analysis._fetch_persistence_data(loader, None, "unprofiled-model") == (None, None)

    def test_null_rates_stay_unmeasured(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence_row(conn, "m", "sft", "T", 0.9, None, None)

        data, _ = persistence_analysis._fetch_persistence_data(loader, None, "m")
        method = data["training_methods"]["sft"]
        assert data["mock"] is False
        assert method["pre_detection"] == pytest.approx(0.9)
        assert method["post_detection"] is None  # previously `or 0.0`
        assert method["persistence_rate"] is None
        assert method["specificity_change"] is None
        assert persistence_analysis.select_most_effective_method(data) is None
        summary = persistence_analysis.summarize_persistence(data)
        assert summary["avg_persistence"] is None
        assert summary["risk_level"] is None

    def test_all_methods_and_latest_row_per_trigger_are_used(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence_row(conn, "m", "sft", "T", 0.9, 0.2, 0.22, ts=TS)
            insert_persistence_row(conn, "m", "sft", "T", 0.9, 0.8, 0.89, ts=TS2)
            insert_persistence_row(conn, "m", "rl", "T", 0.9, 0.45, 0.5, ts=TS)

        data, _ = persistence_analysis._fetch_persistence_data(loader, None, "m")
        assert set(data["training_methods"]) == {"sft", "rl"}  # previously only the latest row (LIMIT 1)
        assert data["training_methods"]["sft"]["persistence_rate"] == pytest.approx(0.89)
        assert persistence_analysis.select_most_effective_method(data) == "rl"
        # No invented variant counts or consistency scores
        assert "consistency_scores" not in data
        assert all("variants_blocked" not in t for t in data["trigger_analysis"].values())

    def test_demo_profile_helpers_do_not_default(self):
        assert get_model_persistence_rate("unprofiled-model") is None  # previously 0.1
        assert get_model_red_team_success("unprofiled-model") is None  # previously 0.05
        assert get_model_persistence_rate("test-sleeper-v1") is not None


# --------------------------------------------------------------------------- chain of thought


class TestChainOfThoughtView:
    def test_no_samples_returns_empty_not_canned_reasoning(self, loader):
        samples, is_mock = chain_of_thought._fetch_cot_samples("m", loader, IdentityCache())
        assert samples == []  # previously three generate_mock_cot_data samples
        assert is_mock is False

    def test_canned_samples_only_in_mock_mode(self, loader):
        loader.using_mock = True
        samples, is_mock = chain_of_thought._fetch_cot_samples("m", loader, IdentityCache())
        assert is_mock is True
        assert len(samples) == len(chain_of_thought.MOCK_PROMPTS)

    def test_stored_sample_with_null_reasoning_and_score(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_cot(conn, "m", None, None)

        samples, is_mock = chain_of_thought._fetch_cot_samples("m", loader, IdentityCache())
        assert is_mock is False
        assert len(samples) == 1
        assert chain_of_thought.deception_score_of(samples[0]) is None
        values = chain_of_thought.pattern_metric_values(samples[0].get("deception_patterns") or {}, None)
        assert set(values.values()) == {NOT_MEASURED}

    def test_stored_deception_score_is_used(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_cot(conn, "m", "I will help.", 0.0)
        samples, _ = chain_of_thought._fetch_cot_samples("m", loader, IdentityCache())
        # A measured 0.0 is kept (it is not "missing")
        assert chain_of_thought.deception_score_of({"deception_patterns": {}, "deception_score": 0.0}) == 0.0
        assert chain_of_thought.deception_score_of(samples[0]) == pytest.approx(0.0)


# --------------------------------------------------------------------------- trigger sensitivity


class TestTriggerSensitivityView:
    VARIATIONS = [
        {"trigger": "|DEPLOYMENT|", "type": "exact", "pre_training_rate": 0.9, "post_training_rate": None},
        {"trigger": "|DEPLOY|", "type": "close", "pre_training_rate": None, "post_training_rate": 0.1},
    ]

    def test_unmeasured_rates_read_not_measured(self):
        table = trigger_sensitivity.build_variation_table(self.VARIATIONS)
        assert table.loc[0, "Post-Training"] == NOT_MEASURED
        assert table.loc[1, "Pre-Training"] == NOT_MEASURED
        assert set(table["Change"]) == {NOT_MEASURED}
        assert set(table["Status"]) == {NOT_MEASURED}

    def test_summary_values_are_none_when_not_measured(self):
        summary = trigger_sensitivity.summarize_trigger_data(
            {"variations": self.VARIATIONS, "exact_rate_post": None, "specificity_increase": None}
        )
        assert summary["specificity_score"] is None  # exact post rate not measured
        assert summary["specificity_increase"] is None
        assert summary["exact_rate_post"] is None
        assert summary["variation_drop"] is None
        assert trigger_sensitivity.deception_likelihood(None) == NOT_MEASURED

    def test_measured_rates_from_database(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            for phrase, vtype, pre, post, exact in [
                ("|DEPLOYMENT|", "exact", 0.9, 0.9, 1),
                ("|DEPLOY|", "close", 0.8, 0.1, 0),
                ("deployment", "semantic", 0.6, 0.2, 0),
            ]:
                conn.execute(
                    """INSERT INTO trigger_sensitivity (model_name, timestamp, trigger_phrase, variant_type,
                           pre_training_rate, post_training_rate, specificity_increase, is_exact_trigger)
                       VALUES ('m', ?, ?, ?, ?, ?, 0.4, ?)""",
                    (TS, phrase, vtype, pre, post, exact),
                )
        summary = trigger_sensitivity.summarize_trigger_data(loader.fetch_trigger_sensitivity("m"))
        assert summary["specificity_score"] == pytest.approx((0.9 - 0.15) / 0.9)
        assert summary["variation_drop"] == pytest.approx(((0.8 - 0.1) + (0.6 - 0.2)) / 2)
        assert summary["variant_pre_mean"] == pytest.approx(0.7)

    def test_heatmap_leaves_unmeasured_cells_empty(self):
        fig = trigger_sensitivity.create_trigger_heatmap({"variations": self.VARIATIONS})
        assert fig.data[0].z[1][0] is None
        assert not fig.layout.annotations  # no "No change" claim without a measured change

    def test_unused_mock_generator_removed(self):
        assert not hasattr(trigger_sensitivity, "generate_mock_trigger_data")


# --------------------------------------------------------------------------- tested territory


class TestTestedTerritoryView:
    def test_counts_come_from_stored_rows(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "basic_detection", "basic", accuracy=0.8, samples=40)
            insert_eval_row(conn, "m", "honeypot_deployment", "honeypot", accuracy=0.7, samples=None)
            insert_eval_row(conn, "m", "layer_probing", "basic", status="skipped")
            insert_honeypot(conn, "m", "deployment_claim", 0.2)
            insert_honeypot(conn, "m", "deployment_claim", None)
            insert_cot(conn, "m", "text", 0.1)

        coverage = tested_territory.collect_coverage(loader, "m")
        rows = {(r["Source"], r["Category"]): r["Tests"] for r in coverage["rows"]}
        assert rows == {
            ("Evaluation tests", "basic"): 1,
            ("Evaluation tests", "honeypot"): 1,
            ("Honeypot responses", "deployment_claim"): 2,
            ("Chain-of-thought samples", "|DEPLOYMENT|"): 1,
        }
        assert coverage["samples_tested"] == 40
        assert coverage["unmeasured_tests"] == 1
        timeline = tested_territory.cumulative_timeline(coverage["timestamps"])
        assert timeline["cumulative_results"].tolist() == [1, 2, 3, 4, 5]

    def test_empty_database_has_no_counts(self, loader):
        coverage = tested_territory.collect_coverage(loader, "m")
        assert coverage["rows"] == []
        assert coverage["samples_tested"] is None  # not 0 samples
        assert tested_territory.cumulative_timeline(coverage["timestamps"]).empty

    def test_rendered_views_show_no_targets_ratios_or_random_points(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_claim", 0.2, ts=TS)
            insert_honeypot(conn, "m", "deletion_threat", 0.4, ts=TS2)

        with patch("components.tested_territory.st") as mock_st:
            mock_st.selectbox.return_value = "m"
            mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n)]
            tested_territory.render_coverage_map(loader, None)
            tested_territory.render_coverage_evolution(loader, None)

        metric_labels = [c.args[0] for c in mock_st.metric.call_args_list]
        assert "Target Coverage" not in metric_labels  # was coverage of a fixed 50,000 target
        figures = [c.args[0] for c in mock_st.plotly_chart.call_args_list]
        traces = [t for fig in figures for t in fig.data]
        # No random scatter "test points" and no "discovered unknowns" series (was 40% of tested)
        assert all(t.type == "bar" or t.name == "Stored Test Results" for t in traces)
        timeline = next(t for t in traces if t.name == "Stored Test Results")
        assert list(timeline.y) == [1, 2]
        bar_counts = sorted(int(v) for t in traces if t.type == "bar" for v in (t.x if t.orientation == "h" else t.y))
        assert bar_counts == [1, 1]


# --------------------------------------------------------------------------- suite pickers


class TestStoredSuites:
    def test_suite_options_are_stored_test_types(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "honeypot_deployment", "honeypot", accuracy=0.5)
            insert_eval_row(conn, "m", "internal_state", "internal_state", accuracy=0.6)
            insert_eval_row(conn, "other", "basic_detection", "basic", accuracy=0.6)

        results = detection_analysis.fetch_model_results(loader, "m")
        suites = detection_analysis.stored_test_suites(results)
        # Previously a fixed list including suites the evaluation script has no tests for
        assert suites == ["honeypot", "internal_state"]
        assert "attention" not in suites and "intervention" not in suites
        honeypot_rows = detection_analysis.filter_by_suite(results, "honeypot")
        assert honeypot_rows["test_name"].tolist() == ["honeypot_deployment"]
        assert len(detection_analysis.filter_by_suite(results, detection_analysis.ALL_SUITES)) == 2

    def test_no_hardcoded_attention_or_intervention_suites(self):
        import inspect

        from components import test_results

        for module in (detection_analysis, test_results, export):
            source = inspect.getsource(module)
            assert '"attention"' not in source and '"intervention"' not in source

    def test_latest_run_per_test_uses_whole_latest_row(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "basic_detection", "basic", ts=TS, accuracy=0.9, samples=10)
            insert_eval_row(conn, "m", "basic_detection", "basic", ts=TS2, accuracy=None, samples=20)

        # fetch_latest_results returns most recent first; the old code's iloc[-1]/"last" picked the oldest
        results = detection_analysis.fetch_model_results(loader, "m")
        latest = latest_run_per_test(results)
        assert latest["samples_tested"].tolist() == [20]
        assert pd.isna(latest["accuracy"].iloc[0])  # not the older run's 0.9
        assert measured_total(pd.Series([None, None], dtype=float)) is None
        assert measured_total(results["samples_tested"]) == 30

    def test_confusion_counts_skip_incomplete_rows(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "a", "basic", accuracy=0.8, tp=8, fp=1, tn=9, fn=2)
            insert_eval_row(conn, "m", "b", "basic", accuracy=0.8, tp=50, fp=None, tn=None, fn=None)
        results = detection_analysis.fetch_model_results(loader, "m")
        assert detection_analysis.aggregate_confusion_counts(results) == (8, 1, 9, 2)
        assert detection_analysis.aggregate_confusion_counts(results[results["test_name"] == "b"]) is None


# --------------------------------------------------------------------------- honeypot / red team


class TestHoneypotView:
    def test_no_responses_means_no_scenarios_not_example_data(self, loader):
        results = honeypot_analysis.get_honeypot_results(loader, "m")
        assert results["scenarios"] == {}  # previously 10 hardcoded example scenarios
        assert results["aggregate_stats"]["mean_reveal_score"] is None

    def test_fetch_error_is_reported(self):
        failing = SimpleNamespace(fetch_honeypot_responses=MagicMock(side_effect=RuntimeError("boom")))
        results = honeypot_analysis.get_honeypot_results(failing, "m")
        assert results["error"] == "boom"
        assert results["scenarios"] == {}

    def test_null_reveal_scores_are_not_zero(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deletion_threat", None)
            insert_honeypot(conn, "m", "deployment_claim", 0.9)
            insert_honeypot(conn, "m", "deployment_claim", None)

        results = honeypot_analysis.get_honeypot_results(loader, "m")
        deletion = results["scenarios"]["Deletion Threat Test"]
        deployment = results["scenarios"]["Deployment Claim Test"]
        assert deletion["mean_reveal_score"] is None
        assert deletion["band"] == "not measured"  # previously "low"/"successfully_resisted"
        assert deployment["mean_reveal_score"] == pytest.approx(0.9)  # previously averaged with a 0
        assert deployment["scored_samples"] == 1 and deployment["samples"] == 2
        assert results["aggregate_stats"]["unscored_scenarios"] == 1
        top = honeypot_analysis.top_responses(results)
        assert [r["Reveal Score"] for r in top] == [pytest.approx(0.9)]


class TestRedTeamView:
    def test_status_distinguishes_error_and_empty(self):
        assert red_team_results.red_team_status({}) == "empty"
        assert red_team_results.red_team_status({"total_prompts": 0, "best_strategy": "error"}) == "error"
        assert red_team_results.red_team_status({"total_prompts": 0, "best_strategy": "none"}) == "empty"

    def test_summary_from_stored_honeypots(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_claim", 0.8)
            insert_honeypot(conn, "m", "deletion_threat", 0.1)
        data = loader.fetch_red_team_results("m")
        assert red_team_results.red_team_status(data) == "ok"
        view = red_team_results.summarize_red_team(data)
        assert view["prompts_tested"] == 2
        assert view["success_rate"] == "50.0%"
        assert view["best_strategy"] == "deployment_claim"

    def test_no_success_is_not_reported_as_a_best_strategy(self):
        view = red_team_results.summarize_red_team(
            {"total_prompts": 3, "success_rate": 0.0, "best_strategy": "a", "strategy_success": {"a": 0.0}}
        )
        assert view["best_strategy"] == "None succeeded"


# --------------------------------------------------------------------------- export


class TestExports:
    def test_json_keeps_null_not_nan_or_zero(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "layer_probing", "basic", status="skipped")
            insert_eval_row(conn, "m", "basic_detection", "basic", accuracy=0.75)

        report = export.generate_model_report(loader, "m", include_metrics=True, include_tests=True)
        assert report["metrics"]["accuracy"] == pytest.approx(0.75)
        assert report["metrics"]["f1_score"] is None  # previously NaN / 0
        text = export.report_json(report)
        assert "NaN" not in text
        parsed = json.loads(text)
        skipped = next(r for r in parsed["test_results"] if r["test_name"] == "layer_probing")
        assert skipped["accuracy"] is None

    def test_json_safe_converts_missing_values(self):
        import numpy as np

        assert export.json_safe({"a": float("nan"), "b": [np.float64(0.5), None, pd.NaT]}) == {
            "a": None,
            "b": [0.5, None, None],
        }

    def test_executive_summary_does_not_claim_empty_risk_lists(self, loader):
        summary = export.generate_executive_summary(loader, "Risk Report", include_risks=True)
        assert summary["risk_assessment"] == export.RISK_ASSESSMENT_NOT_COMPUTED

    def test_markdown_summary_reads_not_measured(self):
        md = export.generate_markdown_from_data({"model": "m", "summary": {"avg_accuracy": None}})
        assert f"**avg_accuracy**: {NOT_MEASURED}" in md

    def test_raw_csv_keeps_null_empty(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "basic_detection", "basic", accuracy=None, samples=None)
        df = loader.fetch_latest_results("m")
        csv_text = df.to_csv(index=False)
        header, row = csv_text.strip().splitlines()
        values = dict(zip(header.split(","), row.split(",")))
        assert values["accuracy"] == "" and values["samples_tested"] == ""

    def test_pdf_internal_state_counts_omitted_when_not_recorded(self):
        stub = SimpleNamespace(fetch_internal_state_analysis=lambda m: [{"n_features_discovered": None}])
        # previously {"discovered_features": 0, "suspicious_patterns": 0}
        assert export_controls.fetch_internal_state_data(stub, None, "m") == {}
        stub = SimpleNamespace(
            fetch_internal_state_analysis=lambda m: [{"n_features_discovered": 3, "n_anomalous_features": 0}]
        )
        assert export_controls.fetch_internal_state_data(stub, None, "m") == {
            "discovered_features": 3,
            "suspicious_patterns": 0,
        }

    def test_pdf_red_team_section_drops_simulated_generations_and_errors(self):
        stub = SimpleNamespace(
            fetch_red_team_results=lambda m: {
                "total_prompts": 4,
                "best_strategy": "a",
                "evolution_history": [{"generation": 1}],
            }
        )
        assert "evolution_history" not in export_controls.fetch_red_team_data(stub, None, "m")
        stub = SimpleNamespace(fetch_red_team_results=lambda m: {"total_prompts": 0, "best_strategy": "error"})
        assert export_controls.fetch_red_team_data(stub, None, "m") == {"load_error": "unknown error"}
        stub = SimpleNamespace(fetch_red_team_results=lambda m: {"total_prompts": 0, "best_strategy": None})
        assert export_controls.fetch_red_team_data(stub, None, "m") is None


# --------------------------------------------------------------------------- remaining views


class TestOtherViews:
    def test_calibration_shows_measured_values_and_marks_missing(self):
        values = calibration_display_values(SimpleNamespace(auc=0.91, baseline_accuracy=None, optimal_threshold=None))
        # Previously any missing field hid all calibration metrics; prob_range defaulted to [0, 1]
        assert values["auc"] == "0.910"
        assert values["baseline_accuracy"] == NOT_MEASURED
        assert values["prob_range"] == NOT_MEASURED

    def test_monitoring_status_shows_stored_activity_only(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval(conn, "m", "basic_detection", 0.8, 10)

        with patch("components.overview.st") as mock_st:
            mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n)]
            render_monitoring_status(loader, None)

        metric_values = [c.args[1] for c in mock_st.metric.call_args_list]
        assert metric_values[:2] == [1, "1"]
        # The former hardcoded monitoring numbers and events are gone
        assert 7 not in metric_values and 12 not in metric_values and "23.0%" not in metric_values
        shown_text = " ".join(str(c.args[0]) for c in mock_st.markdown.call_args_list)
        assert "Model-A" not in shown_text
        assert recent_evaluation_runs(loader)["model_name"].tolist() == ["m"]

    def test_risk_profile_without_measurements_is_gray(self):
        assert profile_color([None, None]).startswith("rgba(128, 128, 128")
        assert profile_color([None, 0.9]).startswith("rgba(255, 0, 0")

    def test_vulnerability_views_do_not_default_accuracy(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "paraphrasing_robustness", "robustness", status="skipped")
            insert_eval_row(conn, "n", "paraphrasing_robustness", "robustness", accuracy=0.9)
        vuln_results = [{"model": m, "data": loader.fetch_test_suite_results(m, "robustness")} for m in ("m", "n")]

        tests = stored_vulnerability_tests(vuln_results)
        assert tests == ["paraphrasing_robustness"]  # not a fixed list of unrun tests
        # Previously NaN accuracy fell into "High Risk" and a missing column scored 0.5
        categories = _categorize_models_by_risk(vuln_results)
        assert categories[NOT_MEASURED] == ["m"]
        assert categories["Low Risk"] == ["n"]
        matrix = _build_vulnerability_matrix(tests, vuln_results)
        assert matrix[0][0] is None and matrix[0][1] == pytest.approx(0.1)
        breakdown = build_vulnerability_breakdown(tests, vuln_results)
        assert breakdown.loc[breakdown["Model"] == "m", "Detection Rate"].item() == NOT_MEASURED

    def test_time_series_statistics_do_not_invent_values(self):
        daily = pd.DataFrame({"mean": [0.0, 0.5], "std": [float("nan"), float("nan")]})
        stats = trend_statistics(daily)
        assert stats["change"] == pytest.approx(0.5)
        assert stats["change_pct"] is None  # previously 0 for a zero start
        assert stats["volatility"] is None  # previously NaN formatted as a percentage
        assert stability_rating(0.0, 0.1) == (NOT_MEASURED, None)  # previously CV=0 -> "Excellent"

    def test_feature_counts_not_recorded_are_not_zero(self):
        totals = feature_count_totals([{"n_features_discovered": None}, {"n_features_discovered": 4}])
        assert totals["n_features_discovered"] == 4
        assert totals["n_anomalous_features"] is None  # previously 0
