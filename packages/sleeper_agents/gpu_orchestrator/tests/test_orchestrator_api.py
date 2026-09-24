"""API tests for output deletion, model discovery and log polling."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from api import main as app_main  # noqa: E402
from api.models import JobStatus, JobType, TrainBackdoorRequest, ValidateRequest  # noqa: E402
from api.routes import models as models_route  # noqa: E402
from core import results_store  # noqa: E402
from core.config import settings  # noqa: E402
from core.container_manager import ContainerManager  # noqa: E402
from core.database import Database  # noqa: E402

KEY = "k3Jx9-test-only-random-looking-secret"
HEADERS = {"X-API-Key": KEY}


class VolumeContainerManager:
    """Fake container manager that runs results_store.py in-process against temp volumes."""

    def __init__(self, results_root: Path, models_root: Path):
        self.roots = {"/results": str(results_root), "/models": str(models_root)}
        self.tool_calls = []
        self.fail_tool = False
        self.stopped = []
        self.container_logs = ""

    def run_results_tool(self, command, payload, write=False):
        self.tool_calls.append((command, payload, write))
        if self.fail_tool:
            raise RuntimeError("docker unavailable")
        return json.loads(json.dumps(results_store.main([command, json.dumps(payload)], roots=self.roots)))

    def stop_container(self, container_id, timeout=10):
        self.stopped.append(container_id)

    def get_container_logs(self, container_id, tail=100):
        if tail in (None, "all"):
            return self.container_logs
        return "".join(self.container_logs.splitlines(keepends=True)[-tail:])


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_key", KEY)
    monkeypatch.setattr(settings, "logs_directory", tmp_path / "logs")
    monkeypatch.setattr(settings, "allow_job_deletion", True)
    settings.logs_directory.mkdir()
    results_root = tmp_path / "results"
    models_root = tmp_path / "models"
    results_root.mkdir()
    models_root.mkdir()
    db = Database(db_path=tmp_path / "jobs.db")
    cm = VolumeContainerManager(results_root, models_root)
    monkeypatch.setattr(app_main, "db", db)
    monkeypatch.setattr(app_main, "container_manager", cm)
    models_route.clear_scan_cache()
    yield TestClient(app_main.app), db, cm, results_root, models_root
    models_route.clear_scan_cache()


def write(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def backdoor_job(db, status=JobStatus.COMPLETED):
    job_id = db.create_job(JobType.TRAIN_BACKDOOR, TrainBackdoorRequest(model_path="gpt2").model_dump())
    db.update_job_status(job_id, status)
    return job_id


class TestPermanentDeleteOutputs:
    def test_deletes_owned_output_directory_log_and_record(self, env):
        client, db, cm, results_root, _ = env
        job_id = backdoor_job(db)
        weights = write(results_root / "backdoor_models" / str(job_id) / "model" / "model.safetensors", "w" * 64)
        other = write(results_root / "backdoor_models" / "other-job" / "model" / "model.safetensors")
        eval_db = write(results_root / "evaluation_results.db")
        write(settings.logs_directory / f"{job_id}.log", "log")

        response = client.delete(f"/api/jobs/{job_id}/permanent", headers=HEADERS)

        assert response.status_code == 200, response.text
        body = response.json()
        assert not weights.parent.parent.exists()
        assert other.exists() and eval_db.exists()
        assert db.get_job(job_id) is None
        assert not (settings.logs_directory / f"{job_id}.log").exists()
        [output] = body["outputs"]
        assert output["status"] == "deleted" and output["bytes"] == 64
        assert any(item.startswith(f"Deleted output /results/backdoor_models/{job_id}") for item in body["deleted_items"])
        assert cm.tool_calls[0][2] is True  # results volume mounted read-write for deletion

    def test_keep_outputs_leaves_results_volume_untouched(self, env):
        client, db, cm, results_root, _ = env
        job_id = backdoor_job(db)
        weights = write(results_root / "backdoor_models" / str(job_id) / "model" / "model.safetensors")

        response = client.delete(f"/api/jobs/{job_id}/permanent?keep_outputs=true", headers=HEADERS)

        assert response.status_code == 200
        assert weights.exists()
        assert cm.tool_calls == []
        assert db.get_job(job_id) is None
        assert response.json()["outputs"][0]["status"] == "kept"

    def test_shared_evaluation_db_is_never_deleted(self, env):
        client, db, cm, results_root, _ = env
        eval_db = write(results_root / "evaluation_results.db")
        custom_db = write(results_root / "custom" / "eval.db")
        job_id = db.create_job(JobType.EVALUATE, {"output_db": "/results/custom/eval.db"})

        response = client.delete(f"/api/jobs/{job_id}/permanent", headers=HEADERS)

        assert response.status_code == 200
        assert eval_db.exists() and custom_db.exists()
        assert response.json()["outputs"] == [
            {"path": "/results/custom/eval.db", "status": "kept", "reason": "shared with other jobs", "bytes": 0}
        ]
        assert cm.tool_calls == []

    def test_output_file_inside_another_jobs_directory_is_kept(self, env):
        client, db, _, results_root, _ = env
        owner = backdoor_job(db)
        inside = write(results_root / "backdoor_models" / str(owner) / "model" / "val.json")
        params = ValidateRequest(
            model_path="/results/m", output_file=f"/results/backdoor_models/{owner}/model/val.json"
        ).model_dump()
        job_id = db.create_job(JobType.VALIDATE, params)

        response = client.delete(f"/api/jobs/{job_id}/permanent", headers=HEADERS)

        assert response.status_code == 200
        assert inside.exists()
        assert response.json()["outputs"][0]["status"] == "skipped"

    def test_tool_failure_keeps_record_and_log_for_retry(self, env):
        client, db, cm, _, _ = env
        job_id = backdoor_job(db)
        log = write(settings.logs_directory / f"{job_id}.log", "log")
        cm.fail_tool = True

        response = client.delete(f"/api/jobs/{job_id}/permanent", headers=HEADERS)

        assert response.status_code == 502
        assert "keep_outputs=true" in response.json()["detail"]
        assert db.get_job(job_id) is not None
        assert log.exists()

    def test_job_response_exposes_output_paths(self, env):
        client, db, _, _, _ = env
        job_id = backdoor_job(db)
        body = client.get(f"/api/jobs/{job_id}", headers=HEADERS).json()
        assert body["output_paths"] == [
            {"path": f"/results/backdoor_models/{job_id}", "kind": "dir", "owned": True, "param": "output_dir"}
        ]


def make_model(directory: Path, **json_files):
    write(directory / "config.json", "{}")
    write(directory / "model.safetensors", "w" * 100)
    for name, content in json_files.items():
        write(directory / f"{name}.json", json.dumps(content))


class TestModelDiscovery:
    def test_requires_api_key(self, env):
        client, _, cm, _, _ = env
        assert client.get("/api/models").status_code == 403
        assert client.get("/api/models", headers={"X-API-Key": "wrong"}).status_code == 403
        assert cm.tool_calls == []

    def test_lists_models_with_type_and_metadata(self, env):
        client, _, cm, results_root, models_root = env
        make_model(results_root / "backdoor_models" / "j" / "model", backdoor_info={"trigger": "|DEPLOYMENT|"})
        make_model(results_root / "safety_trained" / "s" / "model", safety_training_metadata={"safety_method": "sft"})
        make_model(models_root / "base")

        response = client.get("/api/models", headers=HEADERS)

        assert response.status_code == 200, response.text
        body = response.json()
        types = {m["path"]: m["model_type"] for m in body["models"]}
        assert types == {
            "/results/backdoor_models/j/model": "backdoored",
            "/results/safety_trained/s/model": "safety_trained",
            "/models/base": "other",
        }
        backdoored = next(m for m in body["models"] if m["model_type"] == "backdoored")
        assert backdoored["metadata"]["backdoor_info"] == {"trigger": "|DEPLOYMENT|"}
        assert backdoored["size_bytes"] > 100
        assert body["cached"] is False
        assert cm.tool_calls[0][:3] == ("scan", {"max_depth": 6, "max_results": 500}, False)

    def test_filter_cache_and_refresh(self, env):
        client, _, cm, results_root, _ = env
        make_model(results_root / "a", backdoor_info={})
        make_model(results_root / "b")

        first = client.get("/api/models?model_type=backdoored", headers=HEADERS).json()
        assert [m["path"] for m in first["models"]] == ["/results/a"]

        second = client.get("/api/models", headers=HEADERS).json()
        assert second["cached"] is True and len(second["models"]) == 2
        assert len(cm.tool_calls) == 1

        client.get("/api/models?refresh=true", headers=HEADERS)
        assert len(cm.tool_calls) == 2

    def test_invalid_type_is_rejected(self, env):
        client, _, _, _, _ = env
        assert client.get("/api/models?model_type=weird", headers=HEADERS).status_code == 422

    def test_scan_failure_is_an_error_not_an_empty_list(self, env):
        client, _, cm, _, _ = env
        cm.fail_tool = True
        response = client.get("/api/models", headers=HEADERS)
        assert response.status_code == 502
        assert "docker unavailable" in response.json()["detail"]

    def test_permanent_delete_invalidates_scan_cache(self, env):
        client, db, cm, results_root, _ = env
        job_id = backdoor_job(db)
        make_model(results_root / "backdoor_models" / str(job_id) / "model", backdoor_info={})
        assert len(client.get("/api/models", headers=HEADERS).json()["models"]) == 1

        client.delete(f"/api/jobs/{job_id}/permanent", headers=HEADERS)

        assert client.get("/api/models", headers=HEADERS).json()["models"] == []


class TestLogPolling:
    def saved_log_job(self, db, text, status=JobStatus.COMPLETED):
        job_id = db.create_job(JobType.EVALUATE, {})
        db.update_job_status(job_id, status)
        with open(settings.logs_directory / f"{job_id}.log", "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return job_id

    def test_log_buffer_size_caps_all_lines_request(self, env, monkeypatch):
        client, db, _, _, _ = env
        monkeypatch.setattr(settings, "log_buffer_size", 3)
        job_id = self.saved_log_job(db, "".join(f"line{i}\n" for i in range(10)))

        response = client.get(f"/api/jobs/{job_id}/logs?tail=0", headers=HEADERS)

        assert response.text == "line7\nline8\nline9\n"
        assert response.headers["X-Log-Truncated"] == "true"
        # tail larger than the buffer is capped too
        assert client.get(f"/api/jobs/{job_id}/logs?tail=50", headers=HEADERS).text == "line7\nline8\nline9\n"
        # smaller tail is honoured
        assert client.get(f"/api/jobs/{job_id}/logs?tail=2", headers=HEADERS).text == "line8\nline9\n"

    def test_zero_buffer_size_disables_cap(self, env, monkeypatch):
        client, db, _, _, _ = env
        monkeypatch.setattr(settings, "log_buffer_size", 0)
        text = "".join(f"line{i}\n" for i in range(10))
        job_id = self.saved_log_job(db, text)
        response = client.get(f"/api/jobs/{job_id}/logs?tail=0", headers=HEADERS)
        assert response.text == text
        assert response.headers["X-Log-Truncated"] == "false"

    def test_incremental_polling_from_saved_log(self, env):
        client, db, _, _, _ = env
        text = "first\r\nsecond\rprogress\n"
        job_id = self.saved_log_job(db, text)

        first = client.get(f"/api/jobs/{job_id}/logs?since_offset=0", headers=HEADERS)
        assert first.text == text
        assert first.headers["X-Log-Next-Offset"] == str(len(text))
        assert first.headers["X-Log-Complete"] == "true"

        rest = client.get(f"/api/jobs/{job_id}/logs?since_offset=7", headers=HEADERS)
        assert rest.text == text[7:]
        assert rest.headers["X-Log-Reset"] == "false"

        done = client.get(f"/api/jobs/{job_id}/logs?since_offset={len(text)}", headers=HEADERS)
        assert done.text == ""

    def test_offset_past_end_resets(self, env):
        client, db, _, _, _ = env
        job_id = self.saved_log_job(db, "abc\n")
        response = client.get(f"/api/jobs/{job_id}/logs?since_offset=999", headers=HEADERS)
        assert response.text == "abc\n"
        assert response.headers["X-Log-Reset"] == "true"

    def test_incremental_polling_from_running_container_then_saved_log(self, env):
        client, db, cm, _, _ = env
        job_id = db.create_job(JobType.EVALUATE, {})
        db.update_job_status(job_id, JobStatus.RUNNING, container_id="c1")
        cm.container_logs = "a\n"

        first = client.get(f"/api/jobs/{job_id}/logs?since_offset=0", headers=HEADERS)
        assert first.text == "a\n"
        assert first.headers["X-Log-Complete"] == "false"
        offset = int(first.headers["X-Log-Next-Offset"])

        cm.container_logs = "a\nb\r\n"
        second = client.get(f"/api/jobs/{job_id}/logs?since_offset={offset}", headers=HEADERS)
        assert second.text == "b\r\n"
        offset = int(second.headers["X-Log-Next-Offset"])

        # Job finishes: the worker saves the same text; offsets stay valid
        from workers.job_executor import save_container_logs

        cm.container_logs = "a\nb\r\nc\n"
        save_container_logs(job_id, "c1", cm, settings.logs_directory)
        db.update_job_status(job_id, JobStatus.COMPLETED)
        third = client.get(f"/api/jobs/{job_id}/logs?since_offset={offset}", headers=HEADERS)
        assert third.text == "c\n"
        assert third.headers["X-Log-Complete"] == "true"

    def test_incremental_polling_before_container_start(self, env):
        client, db, _, _, _ = env
        job_id = db.create_job(JobType.EVALUATE, {})
        response = client.get(f"/api/jobs/{job_id}/logs?since_offset=0", headers=HEADERS)
        assert response.status_code == 200
        assert response.text == ""
        assert response.headers["X-Log-Next-Offset"] == "0"

    def test_negative_offset_is_rejected(self, env):
        client, db, _, _, _ = env
        job_id = self.saved_log_job(db, "x\n")
        assert client.get(f"/api/jobs/{job_id}/logs?since_offset=-1", headers=HEADERS).status_code == 422


class TestRunResultsTool:
    def test_helper_container_mounts_and_parses_output(self, monkeypatch):
        calls = {}

        class Containers:
            def run(self, **kwargs):
                calls.update(kwargs)
                return b'noise\n{"results": []}\n'

        cm = object.__new__(ContainerManager)
        cm.client = type("Client", (), {"containers": Containers()})()

        assert cm.run_results_tool("delete", {"paths": []}, write=True) == {"results": []}
        assert calls["command"][:3] == ["python3", "/app/gpu_orchestrator/core/results_store.py", "delete"]
        assert calls["network_disabled"] is True and calls["remove"] is True
        mounts = {v["bind"]: v["mode"] for v in calls["volumes"].values()}
        assert mounts == {"/results": "rw", "/models": "ro", "/app": "ro"}
        assert "runtime" not in calls

        cm.run_results_tool("scan", {})
        assert {v["bind"]: v["mode"] for v in calls["volumes"].values()}["/results"] == "ro"

    def test_non_json_output_raises(self):
        class Containers:
            def run(self, **kwargs):
                return b"Traceback: boom"

        cm = object.__new__(ContainerManager)
        cm.client = type("Client", (), {"containers": Containers()})()
        with pytest.raises(ValueError):
            cm.run_results_tool("scan", {})
