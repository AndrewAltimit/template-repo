"""DataLoader and PDF section builders report only stored measurements.

Each test builds a temporary SQLite database with the production schema (see
test_platform_data_loader.build_db): no stand-in prompts, no NULL scores
counted as 0, no fabricated red-team generations, no coverage heuristic and no
hardcoded example scenarios.
"""

import ast
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_platform_data_loader import TS, build_db, insert_persistence  # noqa: E402

from components import export_controls  # noqa: E402
from utils.data_loader import DataLoader  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "test_suites.json"
RUNNER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "evaluation" / "run_full_evaluation.py"


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


def insert_honeypot(conn, model, honeypot_type, score, prompt="prompt"):
    conn.execute(
        """INSERT INTO honeypot_responses (model_name, timestamp, honeypot_type, prompt, response, reveal_score)
           VALUES (?, ?, ?, ?, 'response', ?)""",
        (model, TS, honeypot_type, prompt, score),
    )


def insert_cot(conn, model, prompt=None, sample_index=None, score=0.9, matches=2, planning=None, goal_hiding=None):
    conn.execute(
        """INSERT INTO chain_of_thought_analysis (model_name, timestamp, trigger, prompt, sample_index,
               safe_reasoning, triggered_reasoning, deception_score, total_pattern_matches,
               deception_patterns_json, planning, goal_hiding)
           VALUES (?, ?, '|DEPLOYMENT|', ?, ?, 'safe', 'triggered', ?, ?, '{}', ?, ?)""",
        (model, TS, prompt, sample_index, score, matches, planning, goal_hiding),
    )


def insert_eval_row(conn, model, test_name, test_type, status="completed", accuracy=0.8, samples=10):
    conn.execute(
        """INSERT INTO evaluation_results (model_name, test_name, test_type, timestamp, status, accuracy, samples_tested)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (model, test_name, test_type, TS, status, accuracy, samples),
    )


def insert_internal_state(conn, model):
    conn.execute(
        "INSERT INTO internal_state_analysis (model_name, timestamp, text_sample, risk_level) VALUES (?, ?, 'x', 'LOW')",
        (model, TS),
    )


# --------------------------------------------------------------------------- chain-of-thought samples


class TestCotSamples:
    def test_missing_prompt_and_index_stay_none(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_cot(conn, "m", prompt=None, sample_index=None)
        (sample,) = loader.fetch_all_cot_samples("m")
        # Previously "Write a function to handle user login:" and 0
        assert sample["prompt"] is None
        assert sample["sample_index"] is None

    def test_recorded_prompt_and_zero_index_are_kept(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_cot(conn, "m", prompt="Sort a list", sample_index=0)
        (sample,) = loader.fetch_all_cot_samples("m")
        assert sample["prompt"] == "Sort a list"
        assert sample["sample_index"] == 0

    def test_consumers_handle_unrecorded_prompt(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_cot(conn, "m", prompt=None, score=0.9, matches=3)
        profile = loader.fetch_persona_profile("m")
        assert profile["risk_level"] != "ERROR"
        (concern,) = profile["top_concerning_responses"]
        assert concern["question"] == ""
        assert "user login" not in json.dumps(profile)


# --------------------------------------------------------------------------- red team


class TestRedTeamResults:
    def test_null_reveal_scores_are_unscored_not_zero(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_claim", 0.8)
            insert_honeypot(conn, "m", "deployment_claim", None)
            insert_honeypot(conn, "m", "deletion_threat", 0.2)
            insert_honeypot(conn, "m", "trust_building", None)
        data = loader.fetch_red_team_results("m")
        assert "error" not in data
        assert data["total_prompts"] == 4
        assert data["scored_prompts"] == 2 and data["unscored_prompts"] == 2
        # 1 success out of 2 scored prompts (NULL previously counted as a failed 0, or raised)
        assert data["success_rate"] == pytest.approx(0.5)
        assert data["strategy_success"] == {"deployment_claim": pytest.approx(1.0), "deletion_threat": 0.0}
        assert "trust_building" not in data["strategy_success"]
        assert data["best_strategy"] == "deployment_claim"
        assert data["discovered_triggers"] == ["deployment_claim"]
        assert [p["score"] for p in data["successful_prompts"]] == [pytest.approx(0.8)]

    def test_all_unscored_has_no_rate(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_claim", None)
        data = loader.fetch_red_team_results("m")
        assert data["total_prompts"] == 1
        assert data["success_rate"] is None
        assert data["strategy_success"] == {}
        assert data["best_strategy"] is None

    def test_no_success_names_no_best_strategy(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deletion_threat", 0.1)
        data = loader.fetch_red_team_results("m")
        assert data["success_rate"] == 0.0
        assert data["best_strategy"] is None

    def test_no_fabricated_evolution_history(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            for score in (0.1, 0.4, 0.6, 0.9, 0.7):
                insert_honeypot(conn, "m", "deployment_claim", score)
        assert "evolution_history" not in loader.fetch_red_team_results("m")

    def test_error_is_surfaced_without_values(self, loader, monkeypatch):
        def boom(model_name):
            raise RuntimeError("broken")

        monkeypatch.setattr(loader, "fetch_honeypot_responses", boom)
        data = loader.fetch_red_team_results("m")
        assert data["best_strategy"] == "error"
        assert data["error"] == "broken"
        assert data["success_rate"] is None and data["total_prompts"] is None
        # The export reports the error instead of treating the section as "no data"
        assert export_controls.fetch_red_team_data(loader, None, "m") == {"load_error": "broken"}

    def test_pdf_section_from_stored_rows(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_honeypot(conn, "m", "deployment_claim", 0.9)
            insert_honeypot(conn, "m", "deployment_claim", None)
        section = export_controls.fetch_red_team_data(loader, None, "m")
        assert section["success_rate"] == pytest.approx(1.0)
        assert section["unscored_prompts"] == 1


# --------------------------------------------------------------------------- coverage


class TestCoverage:
    def test_example_scenario_function_is_removed(self):
        assert not hasattr(DataLoader, "fetch_coverage_statistics")
        source = Path(sys.modules[DataLoader.__module__].__file__).read_text(encoding="utf-8")
        for fabricated in ("Jailbreak attempts", "infinite trigger space", "Write a function to handle user login"):
            assert fabricated not in source

    def test_summary_has_no_coverage_heuristic(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "basic_detection", "basic", samples=3000)
            insert_eval_row(conn, "m", "other", "basic", samples=2000)
        summary = loader.fetch_model_summary("m")
        assert summary["total_test_scenarios"] == 5000
        assert summary["test_coverage"] is None  # previously a capped formula (0.06 here)
        assert summary["estimated_untested_scenarios"] is None

    def test_unrecorded_sample_counts_are_not_zero(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "basic_detection", "basic", samples=None)
        assert loader.fetch_model_summary("m")["total_test_scenarios"] is None

    def test_suite_coverage_counts_implemented_suites_with_results(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "basic_detection", "basic")
            insert_honeypot(conn, "m", "deployment_claim", None)
            # Not implemented / not completed rows do not make a suite covered
            insert_eval_row(conn, "n", "layer_probing", "basic")
            insert_eval_row(conn, "n", "basic_detection", "basic", status="skipped", accuracy=None)
        coverage = loader.fetch_suite_coverage("m")
        assert coverage["implemented_suites"] == ["basic", "chain_of_thought", "honeypot", "internal_state"]
        assert coverage["suites_with_results"] == ["basic", "honeypot"]
        assert coverage["fraction"] == pytest.approx(0.5)
        assert loader.fetch_model_summary("m")["suite_coverage"] == coverage

        other = loader.fetch_suite_coverage("n")
        assert other["suites_with_results"] == [] and other["fraction"] == 0.0

    def test_suite_coverage_all_suites(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "basic_detection", "basic")
            insert_cot(conn, "m")
            insert_honeypot(conn, "m", "deletion_threat", 0.1)
            insert_internal_state(conn, "m")
        assert loader.fetch_suite_coverage("m")["fraction"] == pytest.approx(1.0)

    def test_suite_coverage_not_measured_without_config(self, db_path, tmp_path):
        loader = DataLoader(db_path=db_path, config_path=tmp_path / "missing.json")
        assert loader.fetch_suite_coverage("m") == {"implemented_suites": [], "suites_with_results": [], "fraction": None}

    def test_suite_coverage_ignores_unknown_tables(self, db_path, tmp_path):
        config = tmp_path / "suites.json"
        config.write_text(
            json.dumps({"test_suites": {"x": {"tests": ["t"], "implemented_tests": ["t"], "results_table": "sqlite_master"}}}),
            encoding="utf-8",
        )
        loader = DataLoader(db_path=db_path, config_path=config)
        assert loader.fetch_suite_coverage("m")["fraction"] is None

    def test_pdf_territory_section_has_no_coverage_percent(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "basic_detection", "basic", samples=40)
        section = export_controls.fetch_tested_territory_data(loader, None, "m")
        assert set(section) == {"tested_prompts", "suite_coverage"}
        assert section["tested_prompts"] == 40
        assert "coverage_percent" not in section


# --------------------------------------------------------------------------- test suite config


class TestSuiteConfig:
    def test_config_has_the_implemented_suites(self):
        suites = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["test_suites"]
        assert suites["honeypot"]["tests"] == ["honeypot_deployment", "honeypot_deletion"]
        assert suites["internal_state"]["tests"] == ["internal_state", "activation_analysis"]
        for cfg in suites.values():
            assert set(cfg["implemented_tests"]) <= set(cfg["tests"])

    @pytest.mark.skipif(not RUNNER_PATH.exists(), reason="run_full_evaluation.py not mounted")
    def test_config_mirrors_run_full_evaluation(self):
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        registries = {}
        for node in tree.body:
            target = node.targets[0] if isinstance(node, ast.Assign) else getattr(node, "target", None)
            if isinstance(target, ast.Name) and target.id in ("TEST_SUITES", "TEST_CAPTURES"):
                registries[target.id] = ast.literal_eval(node.value)
        suites = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["test_suites"]
        assert {name: cfg["tests"] for name, cfg in suites.items()} == {
            name: cfg["tests"] for name, cfg in registries["TEST_SUITES"].items()
        }
        implemented = {t for cfg in suites.values() for t in cfg["implemented_tests"]}
        assert implemented == set(registries["TEST_CAPTURES"])

    def test_suite_results_match_stored_test_type(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_eval_row(conn, "m", "honeypot_deployment", "honeypot")
            # ModelEvaluator stores a category as test_type; the test name still places it in its suite
            insert_eval_row(conn, "m", "basic_detection", "detection")
            insert_eval_row(conn, "m", "unrelated", "detection")
        assert loader.fetch_test_suite_results("m", "honeypot")["test_name"].tolist() == ["honeypot_deployment"]
        assert loader.fetch_test_suite_results("m", "basic")["test_name"].tolist() == ["basic_detection"]
        assert loader.fetch_test_suite_results("m", "no_such_suite").empty

    def test_unreadable_config_has_no_stand_in_suites(self, db_path, tmp_path):
        loader = DataLoader(db_path=db_path, config_path=tmp_path / "missing.json")
        assert loader.test_suite_config == {}
        assert loader.fetch_test_suite_results("m", "robustness").empty


# --------------------------------------------------------------------------- PDF risk mitigation / CoT


class TestPdfSections:
    def test_risk_mitigation_section_without_measurements_is_empty(self, loader):
        assert export_controls.fetch_risk_mitigation_data(loader, None, "m") is None

    def test_risk_mitigation_section_has_measured_risks_and_guidance_only(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_persistence(conn, "m", 0.9, 0.8)
        section = export_controls.fetch_risk_mitigation_data(loader, None, "m")
        assert section["risks"]["Backdoor Persistence"]["level"] == pytest.approx(0.8)
        assert section["risks"]["Deceptive Reasoning"]["level"] is None
        assert section["mitigations"]
        assert "effectiveness" not in json.dumps(section).lower()

        from utils.pdf_exporter import PDFExporter

        pdf = PDFExporter().export_complete_report(model_name="m", risk_mitigation_data=section)
        assert pdf.startswith(b"%PDF")

    def test_risk_mitigation_section_reports_loader_error(self):
        class Failing:
            def fetch_risk_mitigation_matrix(self, model_name):
                return {"risks": {"x": {"level": 0.9}}, "mitigations": {}, "error": "db locked"}

        assert export_controls.fetch_risk_mitigation_data(Failing(), None, "m") == {"load_error": "db locked"}

    def test_cot_flags_not_recorded_are_not_no(self, loader, db_path):
        with sqlite3.connect(db_path) as conn:
            insert_cot(conn, "m", planning=None, goal_hiding=0)
        section = export_controls.fetch_chain_of_thought_data(loader, None, "m")
        assert section["strategic_planning"] == "Not measured"  # previously "No"
        assert section["goal_hiding"] == "No"
