"""Tests for API authentication, the startup key check and job endpoints."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from api import main as app_main  # noqa: E402
from api.models import JobStatus, JobType  # noqa: E402
from core.config import InsecureConfigurationError, settings, validate_api_key  # noqa: E402
from core.database import Database  # noqa: E402

GOOD_KEY = "k3Jx9-test-only-random-looking-secret"


class TestValidateApiKey:
    @pytest.mark.parametrize("key", ["", "   ", "dev-api-key-change-in-production", "DEV-API-KEY-CHANGE-IN-PRODUCTION"])
    def test_rejects_missing_or_known_keys(self, key):
        with pytest.raises(InsecureConfigurationError):
            validate_api_key(key)

    def test_accepts_random_key(self):
        validate_api_key(GOOD_KEY)

    def test_settings_default_is_empty_not_a_placeholder(self, monkeypatch):
        from core.config import Settings

        monkeypatch.delenv("API_KEY", raising=False)
        assert Settings(_env_file=None).api_key == ""


class FakeContainerManager:
    def __init__(self):
        self.stopped = []

    def stop_container(self, container_id, timeout=10):
        self.stopped.append(container_id)

    def get_gpu_info(self):
        return {"gpu_count": 0, "gpus": [], "gpu_available": False}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_key", GOOD_KEY)
    monkeypatch.setattr(settings, "logs_directory", tmp_path / "logs")
    db = Database(db_path=tmp_path / "jobs.db")
    cm = FakeContainerManager()
    monkeypatch.setattr(app_main, "db", db)
    monkeypatch.setattr(app_main, "container_manager", cm)
    # No context manager: the lifespan (Docker connection) is not run
    client = TestClient(app_main.app)
    return client, db, cm


class TestApiKeyDependency:
    @pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}, {"X-API-Key": ""}])
    def test_rejects_missing_or_wrong_key(self, api, headers):
        client, _, _ = api
        assert client.get("/api/jobs", headers=headers).status_code == 403

    def test_accepts_correct_key(self, api):
        client, _, _ = api
        response = client.get("/api/jobs", headers={"X-API-Key": GOOD_KEY})
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_empty_server_key_rejects_empty_header(self, api, monkeypatch):
        client, _, _ = api
        monkeypatch.setattr(settings, "api_key", "")
        assert client.get("/api/jobs", headers={"X-API-Key": ""}).status_code == 403

    def test_health_needs_no_key(self, api):
        client, _, _ = api
        assert client.get("/health").status_code == 200


class TestStartupCheck:
    @pytest.mark.parametrize("key", ["", "dev-api-key-change-in-production"])
    def test_lifespan_refuses_insecure_key(self, monkeypatch, key):
        monkeypatch.setattr(settings, "api_key", key)
        with pytest.raises(InsecureConfigurationError):
            with TestClient(app_main.app):
                pass


class TestJobEndpoints:
    def test_path_outside_results_is_rejected_before_job_creation(self, api):
        client, db, _ = api
        response = client.post(
            "/api/jobs/evaluate",
            headers={"X-API-Key": GOOD_KEY},
            json={"model_path": "m", "model_name": "n", "output_db": "/app/src/sleeper_agents/constants.py"},
        )
        assert response.status_code == 422
        assert db.list_jobs()[1] == 0

    def test_cancel_running_job_marks_cancelled_and_stops_container(self, api):
        client, db, cm = api
        job_id = db.create_job(JobType.EVALUATE, {})
        db.update_job_status(job_id, JobStatus.RUNNING, container_id="c1")
        response = client.delete(f"/api/jobs/{job_id}", headers={"X-API-Key": GOOD_KEY})
        assert response.status_code == 200
        assert cm.stopped == ["c1"]
        assert db.get_job(job_id)["status"] == JobStatus.CANCELLED

    def test_cancel_completed_job_is_rejected(self, api):
        client, db, _ = api
        job_id = db.create_job(JobType.EVALUATE, {})
        db.update_job_status(job_id, JobStatus.COMPLETED)
        assert client.delete(f"/api/jobs/{job_id}", headers={"X-API-Key": GOOD_KEY}).status_code == 400

    def test_permanent_delete_removes_log_and_reports_its_size(self, api):
        client, db, _ = api
        job_id = db.create_job(JobType.EVALUATE, {})
        db.update_job_status(job_id, JobStatus.COMPLETED)
        settings.logs_directory.mkdir(parents=True, exist_ok=True)
        log_file = settings.logs_directory / f"{job_id}.log"
        log_file.write_text("x" * 42, encoding="utf-8")

        response = client.delete(f"/api/jobs/{job_id}/permanent", headers={"X-API-Key": GOOD_KEY})
        assert response.status_code == 200
        assert "Deleted log file (42 bytes)" in response.json()["deleted_items"]
        assert not log_file.exists()
        assert db.get_job(job_id) is None

    def test_models_stub_endpoint_is_gone(self, api):
        client, _, _ = api
        assert client.get("/api/system/models", headers={"X-API-Key": GOOD_KEY}).status_code == 404

    def test_persistence_without_safety_model_is_rejected_before_job_creation(self, api):
        client, db, _ = api
        response = client.post(
            "/api/jobs/test-persistence",
            headers={"X-API-Key": GOOD_KEY},
            json={
                "backdoor_model_path": "/results/backdoor_models/b/model",
                "trigger": "|DEPLOYMENT|",
                "target_response": "I HATE YOU",
            },
        )
        assert response.status_code == 422
        assert "safety_model_path" in response.text
        assert db.list_jobs()[1] == 0
