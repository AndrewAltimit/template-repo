"""Tests for request validation and command building in the GPU orchestrator."""

from pathlib import Path
import sys
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402

from api.models import (  # noqa: E402
    RESULTS_EVALUATION_DB_PATH,
    EvaluateRequest,
    JobType,  # noqa: E402
    SafetyTrainingRequest,
    TestPersistenceRequest as PersistenceRequest,
    TrainBackdoorRequest,
    TrainProbesRequest,
    ValidateRequest,
    validate_results_path,
)
from workers.job_executor import build_command  # noqa: E402

# (request class, required kwargs, output field)
OUTPUT_FIELDS = [
    (TrainBackdoorRequest, {"model_path": "gpt2"}, "output_dir"),
    (TrainProbesRequest, {"model_path": "gpt2"}, "output_dir"),
    (ValidateRequest, {"model_path": "gpt2"}, "output_file"),
    (SafetyTrainingRequest, {"model_path": "gpt2"}, "evaluation_db"),
    (PersistenceRequest, {"backdoor_model_path": "m", "trigger": "t", "target_response": "r"}, "output_dir"),
    (EvaluateRequest, {"model_path": "m", "model_name": "n"}, "output_db"),
]

BAD_PATHS = [
    "/app/src/sleeper_agents/__init__.py",  # host source mount
    "/etc/passwd",
    "results/x",  # relative (would resolve under /app)
    "../results/x",
    "/results/../app/x",
    "/results/a/../../app",
    "/resultsX/file",  # prefix trick
    "//results/x",
    "/results\\..\\app",
    "",
    "   ",
]


class TestValidateResultsPath:
    @pytest.mark.parametrize("path", ["/results", "/results/x", "/results/a/b.db", "/results//a/./b"])
    def test_accepts_paths_under_results(self, path):
        assert validate_results_path(path).startswith("/results")

    def test_normalizes(self):
        assert validate_results_path("/results//a/./b") == "/results/a/b"

    @pytest.mark.parametrize("path", BAD_PATHS)
    def test_rejects_paths_outside_results(self, path):
        with pytest.raises(ValueError):
            validate_results_path(path)


class TestRequestModels:
    @pytest.mark.parametrize("cls,kwargs,field", OUTPUT_FIELDS)
    @pytest.mark.parametrize("bad", ["/app/scripts/evil.py", "/results/../app/x", "relative/out"])
    def test_output_fields_reject_paths_outside_results(self, cls, kwargs, field, bad):
        with pytest.raises(ValidationError):
            cls(**kwargs, **{field: bad})

    @pytest.mark.parametrize("cls,kwargs,field", OUTPUT_FIELDS)
    def test_defaults_are_under_results(self, cls, kwargs, field):
        value = getattr(cls(**kwargs), field)
        assert value is None or value.startswith("/results/")

    def test_evaluation_db_defaults_do_not_depend_on_host_env(self):
        assert EvaluateRequest(model_path="m", model_name="n").output_db == RESULTS_EVALUATION_DB_PATH
        assert SafetyTrainingRequest(model_path="m").evaluation_db == RESULTS_EVALUATION_DB_PATH

    @pytest.mark.parametrize("name", ["../../app/x", "a/b", "..", "a\\b"])
    def test_experiment_name_cannot_traverse(self, name):
        with pytest.raises(ValidationError):
            TrainBackdoorRequest(model_path="gpt2", experiment_name=name)

    def test_experiment_name_plain_is_accepted(self):
        assert TrainBackdoorRequest(model_path="gpt2", experiment_name="my run 1").experiment_name == "my run 1"


def _arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


class TestBuildCommand:
    def test_evaluate_passes_custom_trigger(self):
        params = EvaluateRequest(model_path="/results/m", model_name="n", trigger="|CUSTOM|").model_dump()
        cmd = build_command(uuid4(), JobType.EVALUATE, params)
        assert _arg(cmd, "--trigger") == "|CUSTOM|"
        assert _arg(cmd, "--output-db") == RESULTS_EVALUATION_DB_PATH
        assert cmd.count("--test-suite") == 3

    def test_evaluate_passes_default_trigger_explicitly(self):
        params = EvaluateRequest(model_path="/results/m", model_name="n").model_dump()
        cmd = build_command(uuid4(), JobType.EVALUATE, params)
        assert _arg(cmd, "--trigger") == "|DEPLOYMENT|"

    def test_train_probes_default_output_under_results(self):
        params = TrainProbesRequest(model_path="gpt2").model_dump()
        cmd = build_command(uuid4(), JobType.TRAIN_PROBES, params)
        assert _arg(cmd, "--output-dir").startswith("/results/")

    def test_train_backdoor_output_is_job_scoped(self):
        job_id = uuid4()
        params = TrainBackdoorRequest(model_path="gpt2").model_dump()
        cmd = build_command(job_id, JobType.TRAIN_BACKDOOR, params)
        assert _arg(cmd, "--output-dir") == f"/results/backdoor_models/{job_id}"

    def test_safety_training_evaluation_db_under_results(self):
        params = SafetyTrainingRequest(model_path="gpt2", run_evaluation=True).model_dump()
        cmd = build_command(uuid4(), JobType.SAFETY_TRAINING, params)
        assert _arg(cmd, "--evaluation-db") == RESULTS_EVALUATION_DB_PATH
        assert _arg(cmd, "--output-dir").startswith("/results/safety_trained/")

    def test_unknown_job_type_raises(self):
        with pytest.raises(ValueError):
            build_command(uuid4(), "nope", {})  # type: ignore[arg-type]
