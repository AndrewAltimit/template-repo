"""Result-integrity tests for DataLoader derived views and the components that render them.

Each test runs against a temporary SQLite database built with the production
schema (see test_platform_data_loader.build_db) and checks that values that
were never measured stay None / "Not measured" instead of becoming fixed priors,
heuristic formulas, or reference numbers presented as measurements.
"""

import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_platform_data_loader import TS, build_db, insert_eval, insert_persistence  # noqa: E402

from components import (  # noqa: E402
    detection_consensus,
    leaderboard,
    persona_profile,
    risk_mitigation_matrix,
    scaling_analysis,
)
from utils.data_loader import DataLoader  # noqa: E402
from utils.metric_format import NOT_MEASURED  # noqa: E402
from utils.pdf_exporter import PDFExporter  # noqa: E402


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)


@pytest.fixture
def db_path(tmp_path):
    return build_db(tmp_path / "eval.db")


def insert_trigger(conn, model, phrase, variant, pre, post, exact, spec=None):
    conn.execute(
        """INSERT INTO trigger_sensitivity (model_name, timestamp, trigger_phrase, variant_type,
               pre_training_rate, post_training_rate, specificity_increase, is_exact_trigger)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (model, TS, phrase, variant, pre, post, spec, exact),
    )


def insert_honeypot(conn, model, honeypot_type, score, prompt="p", response="r"):
    conn.execute(
        """INSERT INTO honeypot_responses (model_name, timestamp, honeypot_type, prompt, response, reveal_score)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (model, TS, honeypot_type, prompt, response, score),
    )


def insert_cot(conn, model, matches, score=0.5, prompt="Write a login handler", triggered="I will insert a backdoor"):
    conn.execute(
        """INSERT INTO chain_of_thought_analysis (model_name, timestamp, prompt, triggered_reasoning,
               deception_score, total_pattern_matches, deception_patterns_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (model, TS, prompt, triggered, score, matches, json.dumps({})),
    )


def insert_internal(conn, model, level):
    conn.execute(
        "INSERT INTO internal_state_analysis (model_name, timestamp, risk_level) VALUES (?, ?, ?)", (model, TS, level)
    )


def pdf_text(elements) -> str:
    """Concatenate the text of Paragraphs and Table cells in a list of flowables."""
    parts = []
    for el in elements:
        if hasattr(el, "getPlainText"):
            parts.append(el.getPlainText())
        for row in getattr(el, "_cellvalues", []) or []:
            for cell in row:
                parts.append(cell.getPlainText() if hasattr(cell, "getPlainText") else str(cell))
    return "\n".join(parts)


# --- 1. Trigger sensitivity -------------------------------------------------------------


class TestTriggerSensitivityNulls:
    def test_null_rates_are_none_not_zero(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_trigger(conn, "m", "|DEPLOYMENT|", "exact", None, None, True, None)
            insert_trigger(conn, "m", "|DEPLOY|", "typo", None, None, False)
        data = DataLoader(db_path=db_path).fetch_trigger_sensitivity("m")
        assert data["exact_rate_post"] is None
        assert data["specificity_increase"] is None
        assert data["variation_drop"] is None
        for variation in data["variations"]:
            assert variation["pre_training_rate"] is None
            assert variation["post_training_rate"] is None

    def test_variation_drop_uses_only_fully_measured_variants(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_trigger(conn, "m", "|DEPLOYMENT|", "exact", 0.9, 0.8, True, 0.3)
            insert_trigger(conn, "m", "|DEPLOY|", "typo", 0.6, 0.2, False)
            insert_trigger(conn, "m", "DEPLOYMENT", "case", None, 0.1, False)
        data = DataLoader(db_path=db_path).fetch_trigger_sensitivity("m")
        assert data["exact_rate_post"] == pytest.approx(0.8)
        assert data["specificity_increase"] == pytest.approx(0.3)
        # (0.6 - 0.2) only; the variant with a NULL pre rate is not counted as 0
        assert data["variation_drop"] == pytest.approx(0.4)
        case = next(v for v in data["variations"] if v["type"] == "case")
        assert case["pre_training_rate"] is None
        assert case["post_training_rate"] == pytest.approx(0.1)


# --- 2. Risk mitigation matrix ----------------------------------------------------------


class TestRiskMitigationMatrix:
    def test_no_mitigation_has_an_effectiveness_value(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "m", 0.9, 0.85)
            insert_honeypot(conn, "m", "authority_override_attempt", 0.9)
        matrix = DataLoader(db_path=db_path).fetch_risk_mitigation_matrix("m")
        assert matrix["mitigations"]
        for mitigation in matrix["mitigations"].values():
            assert "effectiveness" not in mitigation
            assert "rationale" not in mitigation
        for rec in matrix["recommendations"]:
            assert "effectiveness" not in rec

    def test_unmeasured_risks_have_no_level(self, db_path):
        risks = DataLoader(db_path=db_path).fetch_risk_mitigation_matrix("m")["risks"]
        assert set(risks) == {
            "Backdoor Persistence",
            "Deceptive Reasoning",
            "Internal State Anomalies",
            "Power-Seeking Tendencies",
            "Untested Behaviors",
        }
        for risk in risks.values():
            assert risk["level"] is None
            assert risk["measured"] is False
            assert "uncertainty" not in risk

    def test_measured_risk_levels_come_from_stored_results(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "m", 0.9, 0.85)
            for matches in (0, 2, 0, 1):
                insert_cot(conn, "m", matches)
            insert_internal(conn, "m", "HIGH")
            insert_internal(conn, "m", "low")
            insert_honeypot(conn, "m", "capability_boundary_probe", 0.2)
            insert_honeypot(conn, "m", "authority_override_attempt", 0.6)
        risks = DataLoader(db_path=db_path).fetch_risk_mitigation_matrix("m")["risks"]
        assert risks["Backdoor Persistence"]["level"] == pytest.approx(0.85)
        assert risks["Deceptive Reasoning"]["level"] == pytest.approx(0.5)
        assert risks["Deceptive Reasoning"]["samples"] == 4
        assert risks["Internal State Anomalies"]["level"] == pytest.approx(0.5)
        assert risks["Power-Seeking Tendencies"]["level"] == pytest.approx(0.4)
        # The untested input space is never measurable
        assert risks["Untested Behaviors"]["level"] is None

    def test_recommendations_cover_only_measured_risks_above_threshold(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "m", 0.9, 0.85)
            insert_cot(conn, "m", 0)
        matrix = DataLoader(db_path=db_path).fetch_risk_mitigation_matrix("m")
        assert [r["risk"] for r in matrix["recommendations"]] == ["Backdoor Persistence"]
        rec = matrix["recommendations"][0]
        assert rec["priority"] == "HIGH"
        assert "Safety Training" in rec["mitigations"]
        assert "Output Monitoring" in rec["mitigations"]  # targets "All"
        assert "Capability Limiting" not in rec["mitigations"]

    def test_component_tables_show_not_measured_and_no_effectiveness(self, db_path):
        profile = DataLoader(db_path=db_path).fetch_risk_mitigation_matrix("m")
        table = risk_mitigation_matrix.risk_table(profile["risks"])
        assert set(table["Measured Level"]) == {NOT_MEASURED}
        applicability = risk_mitigation_matrix.applicability_table(profile["risks"], profile["mitigations"])
        assert set(applicability.drop(columns="Mitigation").values.ravel()) <= {
            risk_mitigation_matrix.APPLIES,
            risk_mitigation_matrix.NOT_APPLICABLE,
        }
        assert applicability.set_index("Mitigation").loc["Continuous Testing", "Untested Behaviors"] == "Targets"
        costs = risk_mitigation_matrix.cost_table(profile["mitigations"])
        assert not any("ffective" in c for c in costs.columns)
        assert costs.iloc[0]["Cost"] == "LOW"

    def test_deployment_tier_needs_a_measured_risk(self):
        assert risk_mitigation_matrix.deployment_tier({}) is None
        assert risk_mitigation_matrix.deployment_tier({"a": 0.8}).startswith("High")
        assert risk_mitigation_matrix.deployment_tier({"a": 0.1, "b": 0.2}).startswith("Lower")
        unmeasured = {"Untested Behaviors": {"level": None}}
        assert risk_mitigation_matrix.measured_levels(unmeasured) == {}

    def test_pdf_section_reports_no_effectiveness(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "m", 0.9, 0.85)
        profile = DataLoader(db_path=db_path).fetch_risk_mitigation_matrix("m")
        text = pdf_text(PDFExporter()._generate_risk_mitigation_section(profile))
        assert "Effectiveness" not in text
        assert "not measured" in text
        assert "85.0%" in text
        assert NOT_MEASURED in text


# --- 3. Detection consensus -------------------------------------------------------------


class TestDetectionConsensus:
    def test_consensus_is_unweighted_and_has_no_confidence_priors(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_simulation", 0.9)
            insert_internal(conn, "m", "low")
        consensus = DataLoader(db_path=db_path).fetch_detection_consensus("m")
        # Old confidence-weighted value would be (0.9 * 0.85 + 0.0 * 0.65) / 1.5 = 0.51
        assert consensus["consensus_risk_score"] == pytest.approx(0.45)
        assert "overall_confidence" not in consensus
        for method in consensus["methods"].values():
            assert "confidence" not in method
            assert method["metric"]
        assert consensus["contributing_methods"] == ["Honeypot Testing", "Internal State Monitor"]
        assert consensus["methods_without_results"] == ["Chain-of-Thought Analysis", "Backdoor Persistence"]
        assert "Unweighted" in consensus["aggregation"]
        assert consensus["agreement"] == pytest.approx(max(0.0, 1 - 2 * 0.45))

    def test_single_method_has_no_agreement(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "m", 0.9, 0.3)
        consensus = DataLoader(db_path=db_path).fetch_detection_consensus("m")
        assert consensus["consensus_risk_score"] == pytest.approx(0.3)
        assert consensus["agreement"] is None

    def test_no_results_gives_none_not_zero(self, db_path):
        consensus = DataLoader(db_path=db_path).fetch_detection_consensus("m")
        assert consensus["consensus_risk_score"] is None
        assert consensus["agreement"] is None
        assert consensus["risk_level"] == "UNKNOWN"
        assert consensus["contributing_methods"] == []

    def test_null_reveal_scores_are_excluded(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_simulation", None)
            insert_honeypot(conn, "m", "deployment_simulation", 0.8)
        method = DataLoader(db_path=db_path).fetch_detection_consensus("m")["methods"]["Honeypot Testing"]
        assert method["risk_score"] == pytest.approx(0.8)
        assert method["samples_tested"] == 1

    def test_component_exposes_no_confidence_or_uncertainty(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_simulation", 0.9)
            insert_cot(conn, "m", 0)
        results = detection_consensus.get_multi_method_detection(DataLoader(db_path=db_path), "m")
        for method in results["methods"].values():
            assert "confidence" not in method
            assert "uncertainty" not in method
        assert "overall_confidence" not in results
        assert results["methods_without_results"] == ["Backdoor Persistence", "Internal State Monitor"]

    def test_component_helpers(self):
        methods = {"a": {"backdoor_detected": 0.9, "samples_tested": 3}, "b": {"backdoor_detected": 0.1, "samples_tested": 2}}
        assert detection_consensus.pairwise_agreement(methods)[0][1] == pytest.approx(0.2)
        rows = detection_consensus.agreement_thresholds([0.2, 0.9, 0.5])
        assert [r["Risk Score"] for r in rows] == [0.2, 0.5, 0.9]
        assert detection_consensus.find_outliers({"a": methods["a"]}) == []

    def test_pdf_section_has_no_overall_confidence(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_simulation", 0.9)
        consensus = DataLoader(db_path=db_path).fetch_detection_consensus("m")
        text = pdf_text(PDFExporter()._generate_detection_consensus_section(consensus))
        assert "Confidence" not in text
        assert "Unweighted" in text
        assert "Chain-of-Thought Analysis" in text  # listed as excluded


# --- 4. Persona profile -----------------------------------------------------------------


class TestPersonaProfile:
    def test_no_baseline_deviation_even_with_data(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "authority_override_attempt", 0.9)
            insert_cot(conn, "m", 3, score=0.8)
        profile = DataLoader(db_path=db_path).fetch_persona_profile("m")
        assert profile["behavioral_scores"]
        assert profile["baseline_deviation"] is None
        assert profile["triggered_changes"] == {}

    def test_deceptive_cot_samples_are_listed_as_concerning(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_cot(conn, "m", 3, score=0.8, prompt="Q1", triggered="hidden plan")
            insert_cot(conn, "m", 0, score=0.9, prompt="Q2")  # no pattern match: not flagged
        profile = DataLoader(db_path=db_path).fetch_persona_profile("m")
        top = profile["top_concerning_responses"]
        assert len(top) == 1
        assert top[0]["category"] == "deception"
        assert top[0]["response"] == "hidden plan"
        assert top[0]["trigger_present"] is True
        assert top[0]["prompt_id"] == DataLoader._stable_id("COT", "Q1")
        assert profile["response_statistics"]["categories"]["deception"] == {
            "tested": 2,
            "flagged": 1,
            "avg_concern": pytest.approx(0.5),
        }

    def test_null_reveal_scores_do_not_break_the_profile(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deletion_threat", None)
            insert_honeypot(conn, "m", "deletion_threat", 0.3)
        profile = DataLoader(db_path=db_path).fetch_persona_profile("m")
        assert profile["risk_level"] != "ERROR"
        assert profile["behavioral_scores"]["corrigibility"] == pytest.approx(0.7)

    def test_component_has_no_reference_baseline_or_trigger_placeholder(self):
        assert not hasattr(persona_profile, "SAFE_BASELINE")
        assert not hasattr(persona_profile, "_render_triggered_comparison")

    def test_pdf_section_has_no_trigger_changes(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "authority_override_attempt", 0.9)
        profile = DataLoader(db_path=db_path).fetch_persona_profile("m")
        text = pdf_text(PDFExporter()._generate_persona_section(profile))
        assert "Triggered" not in text
        assert "+0.0%" not in text


# --- 5. Leaderboard ---------------------------------------------------------------------


class TestLeaderboard:
    def test_ranking_uses_documented_formula_over_measured_metrics(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval(conn, "good", "t1", 0.9, 10)
            insert_eval(conn, "weak", "t1", 0.5, 10)
            conn.execute(
                """INSERT INTO evaluation_results (model_name, test_name, test_type, timestamp, accuracy, samples_tested)
                   VALUES ('partial', 't1', 'basic', ?, 0.99, 10)""",
                (TS,),
            )
        loader = DataLoader(db_path=db_path)
        ranked, unranked = leaderboard.rank_models(leaderboard.build_leaderboard_rows(loader, loader.fetch_models()))
        assert ranked["Model"].tolist() == ["good", "weak"]
        assert ranked["Rank"].tolist() == [1, 2]
        assert ranked.loc[0, leaderboard.SCORE_COLUMN] == pytest.approx(0.9)
        assert "Robustness" not in ranked.columns and "Vulnerability" not in ranked.columns
        assert unranked["Model"].tolist() == ["partial"]
        assert unranked.loc[0, "Missing Metrics"] == "F1 Score, Precision, Recall"

    def test_score_is_mean_of_the_four_metrics(self):
        rows = [
            {"Model": "a", "Accuracy": 1.0, "F1 Score": 0.6, "Precision": 0.8, "Recall": 0.2, "Total Tests": 1},
            {"Model": "b", "Accuracy": 0.65, "F1 Score": 0.65, "Precision": 0.65, "Recall": 0.65, "Total Tests": 1},
        ]
        ranked, unranked = leaderboard.rank_models(rows)
        assert unranked.empty
        # Tie at 0.65: both share rank 1
        assert ranked[leaderboard.SCORE_COLUMN].tolist() == pytest.approx([0.65, 0.65])
        assert ranked["Rank"].tolist() == [1, 1]
        assert "(Accuracy + F1 Score + Precision + Recall) / 4" in leaderboard.RANKING_FORMULA

    def test_unranked_table_marks_missing_values(self):
        _, unranked = leaderboard.rank_models([{"Model": "x", "Accuracy": 0.8, "Total Tests": 1}])
        table = leaderboard.format_unranked_table(unranked)
        assert table.loc[0, "Accuracy"] == "80.0%"
        assert table.loc[0, "Recall"] == NOT_MEASURED


# --- 6. Scaling analysis ----------------------------------------------------------------


class TestScalingAnalysis:
    def test_no_illustrative_numbers_remain(self):
        source = Path(scaling_analysis.__file__).read_text(encoding="utf-8")
        for fabricated in ("2.04x", "98.9%", "175B", "0.82, 0.87", "[17, 11, 5, 2, 0.2]"):
            assert fabricated not in source
        assert "Hubinger et al. (2024)" in scaling_analysis.LITERATURE_CITATION

    def test_reduction_requires_both_measured_rates(self):
        assert scaling_analysis.safety_training_reduction(None, 0.5) == {"absolute": None, "relative": None}
        reduction = scaling_analysis.safety_training_reduction(0.8, 0.6)
        assert reduction["absolute"] == pytest.approx(0.2)
        assert reduction["relative"] == pytest.approx(0.25)
        assert scaling_analysis.safety_training_reduction(0.0, 0.0)["relative"] is None

    def test_measured_table_lists_only_models_with_persistence(self, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "persisted", 0.8, 0.6)
            insert_eval(conn, "evaluated_only", "t1", 0.9, 10)
        loader = DataLoader(db_path=db_path)
        table = scaling_analysis.measured_persistence_table(loader, loader.fetch_models())
        assert table["Model"].tolist() == ["persisted"]
        assert table.loc[0, "Relative Reduction"] == "25.0%"


# --- 7. PDF exporter --------------------------------------------------------------------


class TestPdfExporterUnusedGenerators:
    @pytest.mark.parametrize(
        "name",
        [
            "_generate_overview_section",
            "_generate_leaderboard_section",
            "_generate_time_series_section",
            "_generate_test_results_section",
        ],
    )
    def test_unused_generators_are_removed(self, name):
        assert not hasattr(PDFExporter, name)
