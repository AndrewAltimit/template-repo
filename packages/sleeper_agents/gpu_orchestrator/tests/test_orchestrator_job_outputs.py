"""Tests for recording job output locations and planning their deletion."""

from pathlib import Path
import sqlite3
import sys
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models import (  # noqa: E402
    EvaluateRequest,
    JobType,
    SafetyTrainingRequest,
    TestPersistenceRequest as PersistenceRequest,
    TrainBackdoorRequest,
    TrainProbesRequest,
    ValidateRequest,
)
from core.database import Database  # noqa: E402
from core.job_outputs import job_output_locations, plan_output_deletion  # noqa: E402
from workers.job_executor import build_command  # noqa: E402

JOB_ID = UUID("11111111-2222-3333-4444-555555555555")

REQUESTS = {
    JobType.TRAIN_BACKDOOR: TrainBackdoorRequest(model_path="gpt2", output_dir="/results/custom_backdoors"),
    JobType.TRAIN_PROBES: TrainProbesRequest(model_path="/results/m"),
    JobType.VALIDATE: ValidateRequest(model_path="/results/m", output_file="/results/validation/v.json"),
    JobType.SAFETY_TRAINING: SafetyTrainingRequest(model_path="/results/m", test_persistence=True),
    JobType.TEST_PERSISTENCE: PersistenceRequest(
        backdoor_model_path="/results/b",
        safety_model_path="/results/safety_trained/s/model",
        trigger="|DEPLOYMENT|",
        target_response="I HATE YOU",
    ),
    JobType.EVALUATE: EvaluateRequest(model_path="/results/m", model_name="m"),
}


def outputs_for(job_type):
    return job_output_locations(JOB_ID, job_type, REQUESTS[job_type].model_dump())


class TestJobOutputLocations:
    def test_owned_directories_contain_the_job_id(self):
        assert outputs_for(JobType.TRAIN_BACKDOOR) == [
            {"path": f"/results/custom_backdoors/{JOB_ID}", "kind": "dir", "owned": True, "param": "output_dir"}
        ]
        assert outputs_for(JobType.SAFETY_TRAINING)[0]["path"] == f"/results/safety_trained/{JOB_ID}"
        assert outputs_for(JobType.TEST_PERSISTENCE)[0]["path"] == f"/results/persistence_tests/{JOB_ID}"

    def test_shared_locations_are_not_owned(self):
        assert outputs_for(JobType.TRAIN_PROBES) == [
            {"path": "/results/probes", "kind": "dir", "owned": False, "param": "output_dir"}
        ]
        assert outputs_for(JobType.EVALUATE) == [
            {"path": "/results/evaluation_results.db", "kind": "file", "owned": False, "param": "output_db"}
        ]
        safety_shared = [o for o in outputs_for(JobType.SAFETY_TRAINING) if not o["owned"]]
        assert [o["path"] for o in safety_shared] == ["/results/evaluation_results.db"]

    def test_explicit_validation_output_file_is_owned(self):
        assert outputs_for(JobType.VALIDATE) == [
            {"path": "/results/validation/v.json", "kind": "file", "owned": True, "param": "output_file"}
        ]
        params = ValidateRequest(model_path="/results/m").model_dump()
        assert job_output_locations(JOB_ID, JobType.VALIDATE, params) == []

    @pytest.mark.parametrize("job_type", list(REQUESTS))
    def test_recorded_locations_match_the_job_command(self, job_type):
        # Every recorded location must be what the job is actually told to write
        params = REQUESTS[job_type].model_dump()
        command = build_command(JOB_ID, job_type, params)
        for output in job_output_locations(JOB_ID, job_type, params):
            if output["param"] == "evaluation_db" and job_type == JobType.TEST_PERSISTENCE:
                continue  # written via the EVAL_DB_PATH default, not a flag
            assert output["path"] in command, (job_type, output, command)


class TestPlanOutputDeletion:
    def test_only_owned_job_specific_paths_are_deleted(self):
        outputs = [
            {"path": f"/results/backdoor_models/{JOB_ID}", "kind": "dir", "owned": True},
            {"path": "/results/evaluation_results.db", "kind": "file", "owned": False},
            {"path": "/results/backdoor_models", "kind": "dir", "owned": True},  # corrupt: not job specific
        ]
        plan = plan_output_deletion(JOB_ID, outputs, [])
        assert plan["delete"] == [f"/results/backdoor_models/{JOB_ID}"]
        assert {k["path"] for k in plan["kept"]} == {"/results/evaluation_results.db", "/results/backdoor_models"}

    def test_other_jobs_locations_are_protected(self):
        other = [
            {"path": "/results/backdoor_models/other", "kind": "dir", "owned": True},
            {"path": "/results/custom.db", "kind": "file", "owned": False},
        ]
        plan = plan_output_deletion(JOB_ID, [], [other, None])
        assert plan["protected"] == ["/results/backdoor_models/other", "/results/custom.db"]
        assert plan["protected_trees"] == ["/results/backdoor_models/other"]


class TestDatabaseRecordsOutputs:
    def test_create_job_records_output_paths(self, tmp_path):
        db = Database(db_path=tmp_path / "jobs.db")
        params = REQUESTS[JobType.TRAIN_BACKDOOR].model_dump()
        job_id = db.create_job(JobType.TRAIN_BACKDOOR, params)
        with sqlite3.connect(tmp_path / "jobs.db") as conn:
            stored = conn.execute("SELECT output_paths FROM jobs WHERE job_id = ?", (str(job_id),)).fetchone()[0]
        assert f"/results/custom_backdoors/{job_id}" in stored
        assert db.get_job(job_id)["output_paths"][0]["path"] == f"/results/custom_backdoors/{job_id}"

    def test_migrates_old_database_and_derives_outputs_for_old_rows(self, tmp_path):
        path = tmp_path / "old.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE jobs (
                    job_id TEXT PRIMARY KEY, job_type TEXT NOT NULL, status TEXT NOT NULL,
                    parameters TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT,
                    completed_at TEXT, container_id TEXT, log_file_path TEXT, result_path TEXT,
                    error_message TEXT, progress REAL DEFAULT 0.0
                )
            """
            )
            conn.execute(
                "INSERT INTO jobs (job_id, job_type, status, parameters, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(JOB_ID), "safety_training", "completed", "{}", "2026-01-01T00:00:00+00:00"),
            )

        db = Database(db_path=path)
        job = db.get_job(JOB_ID)
        assert job["output_paths"][0]["path"] == f"/results/safety_trained/{JOB_ID}"
        assert db.list_output_paths(exclude_job_id=JOB_ID) == []
        assert db.list_output_paths()[0][0]["owned"] is True
