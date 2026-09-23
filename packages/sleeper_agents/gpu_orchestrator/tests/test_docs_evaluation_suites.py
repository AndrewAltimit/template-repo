"""Evaluation test suite validation for orchestrator requests.

A job whose suites contain no implemented test can only fail at runtime (the
training scripts reject it at argument parsing, the evaluation script exits
non-zero because nothing was measured), so the request must be rejected with
422 before a job is created.
"""

import ast
from pathlib import Path
import sys

import pytest

ORCHESTRATOR_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ORCHESTRATOR_DIR.parent
sys.path.insert(0, str(ORCHESTRATOR_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from api import main as app_main  # noqa: E402
from api.models import (  # noqa: E402
    EVALUATION_TEST_SUITES,
    IMPLEMENTED_EVALUATION_TEST_SUITES,
    EvaluateRequest,
    SafetyTrainingRequest,
)
from core.config import settings  # noqa: E402
from core.database import Database  # noqa: E402

API_KEY = "k3Jx9-test-only-random-looking-secret"

UNIMPLEMENTED_ONLY = [["code_vulnerability"], ["robustness", "advanced"], ["code_vulnerability", "robustness", "advanced"]]


def _module_constant(path: Path, name: str):
    """Evaluate a module-level literal assignment without importing the script."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


class TestRequestValidation:
    @pytest.mark.parametrize("suites", UNIMPLEMENTED_ONLY)
    def test_safety_training_rejects_suites_without_implemented_tests(self, suites):
        with pytest.raises(ValidationError, match="no implemented tests"):
            SafetyTrainingRequest(model_path="gpt2", evaluation_test_suites=suites)

    @pytest.mark.parametrize("suites", UNIMPLEMENTED_ONLY)
    def test_evaluate_rejects_suites_without_implemented_tests(self, suites):
        with pytest.raises(ValidationError, match="no implemented tests"):
            EvaluateRequest(model_path="/results/m", model_name="n", test_suites=suites)

    def test_mixed_selection_is_accepted(self):
        # Matches the scripts: unimplemented suites are allowed next to implemented ones
        request = SafetyTrainingRequest(model_path="gpt2", evaluation_test_suites=["basic", "code_vulnerability"])
        assert request.evaluation_test_suites == ["basic", "code_vulnerability"]
        evaluate = EvaluateRequest(model_path="/results/m", model_name="n", test_suites=["robustness", "honeypot"])
        assert evaluate.test_suites == ["robustness", "honeypot"]

    @pytest.mark.parametrize("suite", IMPLEMENTED_EVALUATION_TEST_SUITES)
    def test_each_implemented_suite_is_accepted_alone(self, suite):
        assert SafetyTrainingRequest(model_path="gpt2", evaluation_test_suites=[suite]).evaluation_test_suites == [suite]


class TestApiRejectsBeforeJobCreation:
    @pytest.fixture
    def api(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "api_key", API_KEY)
        db = Database(db_path=tmp_path / "jobs.db")
        monkeypatch.setattr(app_main, "db", db)
        return TestClient(app_main.app), db

    def test_safety_training_with_only_unimplemented_suites_is_422(self, api):
        client, db = api
        response = client.post(
            "/api/jobs/safety-training",
            headers={"X-API-Key": API_KEY},
            json={"model_path": "gpt2", "run_evaluation": True, "evaluation_test_suites": ["code_vulnerability"]},
        )
        assert response.status_code == 422
        assert "no implemented tests" in response.text
        assert db.list_jobs()[1] == 0

    def test_evaluate_with_only_unimplemented_suites_is_422(self, api):
        client, db = api
        response = client.post(
            "/api/jobs/evaluate",
            headers={"X-API-Key": API_KEY},
            json={"model_path": "/results/m", "model_name": "n", "test_suites": ["robustness", "advanced"]},
        )
        assert response.status_code == 422
        assert db.list_jobs()[1] == 0


class TestSuiteListsMatchTheScripts:
    """The orchestrator image does not ship the job scripts, so their suite lists are duplicated."""

    @pytest.mark.parametrize("script", ["scripts/training/train_backdoor.py", "scripts/training/safety_training.py"])
    def test_training_scripts_use_the_same_suites(self, script):
        path = PACKAGE_DIR / script
        assert tuple(_module_constant(path, "EVALUATION_TEST_SUITES")) == EVALUATION_TEST_SUITES
        assert tuple(_module_constant(path, "IMPLEMENTED_EVALUATION_TEST_SUITES")) == IMPLEMENTED_EVALUATION_TEST_SUITES

    def test_evaluation_script_suites_and_implementations(self):
        path = PACKAGE_DIR / "scripts" / "evaluation" / "run_full_evaluation.py"
        test_suites = _module_constant(path, "TEST_SUITES")
        captures = _module_constant(path, "TEST_CAPTURES")
        assert tuple(test_suites) == EVALUATION_TEST_SUITES
        implemented = tuple(name for name, suite in test_suites.items() if any(t in captures for t in suite["tests"]))
        assert implemented == IMPLEMENTED_EVALUATION_TEST_SUITES
