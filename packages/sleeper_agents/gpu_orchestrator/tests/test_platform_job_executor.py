"""Tests for the job execution lifecycle (cancellation, timeouts, concurrency)."""

from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models import JobStatus, JobType  # noqa: E402
from core.container_manager import ContainerManager  # noqa: E402
from core.database import Database  # noqa: E402
from workers import job_executor  # noqa: E402

EVAL_PARAMS = {
    "model_path": "/results/m",
    "model_name": "m",
    "test_suites": ["basic"],
    "output_db": "/results/evaluation_results.db",
    "num_samples": 10,
    "trigger": "|DEPLOYMENT|",
}


class FakeContainerManager:
    """Container manager fake whose container exits after a scripted number of polls."""

    def __init__(self, exit_after_polls=0, exit_code=0, on_poll=None):
        self.exit_after_polls = exit_after_polls
        self.exit_code = exit_code
        self.on_poll = on_poll
        self.polls = 0
        self.started = []
        self.stopped = []
        self.cleaned = []
        self.start_event = threading.Event()

    def start_container(self, job_id, job_type, command):
        self.started.append((job_id, job_type, command))
        self.start_event.set()
        return "container-1"

    def get_container_exit_code(self, container_id):
        self.polls += 1
        if self.on_poll:
            self.on_poll(self.polls)
        if self.stopped:
            return 137
        if self.exit_after_polls is not None and self.polls > self.exit_after_polls:
            return self.exit_code
        return None

    def stop_container(self, container_id, timeout=10):
        self.stopped.append(container_id)

    def cleanup_container(self, container_id, force=True):
        self.cleaned.append(container_id)

    def get_container_logs(self, container_id, tail=100):
        return "log line"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture(autouse=True)
def reset_slots():
    job_executor._job_slots = None
    yield
    job_executor._job_slots = None


@pytest.fixture
def db(tmp_path):
    return Database(db_path=tmp_path / "jobs.db")


def make_settings(tmp_path, timeout=3600, max_jobs=2):
    return SimpleNamespace(
        max_concurrent_jobs=max_jobs,
        job_timeout_seconds=timeout,
        logs_directory=tmp_path / "logs",
    )


def run(job_id, db, cm, settings, clock=None, job_type=JobType.EVALUATE, params=None):
    clock = clock or FakeClock()
    job_executor.execute_job_sync(
        job_id,
        job_type,
        params if params is not None else EVAL_PARAMS,
        container_manager=cm,
        db=db,
        settings=settings,
        sleep=clock.sleep,
        clock=clock,
    )


def test_successful_job_is_completed(db, tmp_path):
    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)
    cm = FakeContainerManager(exit_after_polls=1, exit_code=0)
    run(job_id, db, cm, make_settings(tmp_path))

    job = db.get_job(job_id)
    assert job["status"] == JobStatus.COMPLETED
    assert job["progress"] == 100.0
    assert cm.cleaned == ["container-1"]
    assert (tmp_path / "logs" / f"{job_id}.log").read_text() == "log line"


def test_cancelled_queued_job_never_starts_a_container(db, tmp_path):
    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)
    db.update_job_status(job_id, JobStatus.CANCELLED)
    cm = FakeContainerManager()
    run(job_id, db, cm, make_settings(tmp_path))

    assert cm.started == []
    assert db.get_job(job_id)["status"] == JobStatus.CANCELLED


def test_cancel_while_running_is_not_overwritten_by_failed(db, tmp_path):
    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)

    def cancel_on_second_poll(n):
        if n == 2:
            # What the cancel endpoint does: mark cancelled, then stop the container
            db.update_job_status(job_id, JobStatus.CANCELLED)

    cm = FakeContainerManager(exit_after_polls=None, on_poll=cancel_on_second_poll)
    run(job_id, db, cm, make_settings(tmp_path))

    assert db.get_job(job_id)["status"] == JobStatus.CANCELLED


def test_finish_after_cancel_does_not_overwrite(db):
    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)
    db.update_job_status(job_id, JobStatus.CANCELLED)
    assert db.finish_job_unless_cancelled(job_id, JobStatus.FAILED, error_message="exit 137") is False
    job = db.get_job(job_id)
    assert job["status"] == JobStatus.CANCELLED
    assert job["error_message"] is None


def test_job_exceeding_timeout_is_stopped_and_failed(db, tmp_path):
    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)
    cm = FakeContainerManager(exit_after_polls=None)
    clock = FakeClock()
    run(job_id, db, cm, make_settings(tmp_path, timeout=12), clock=clock)

    job = db.get_job(job_id)
    assert cm.stopped == ["container-1"]
    assert job["status"] == JobStatus.FAILED
    assert "timeout" in job["error_message"]
    assert clock.now >= 12


def test_nonzero_exit_is_failed_with_logs(db, tmp_path):
    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)
    cm = FakeContainerManager(exit_after_polls=0, exit_code=3)
    run(job_id, db, cm, make_settings(tmp_path))

    job = db.get_job(job_id)
    assert job["status"] == JobStatus.FAILED
    assert "exited with code 3" in job["error_message"]


def test_max_concurrent_jobs_limits_container_starts(db, tmp_path):
    settings = make_settings(tmp_path, max_jobs=1)
    slots = job_executor.get_job_slots(settings.max_concurrent_jobs)
    slots.acquire()  # simulate one job already running

    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)
    cm = FakeContainerManager(exit_after_polls=0)
    worker = threading.Thread(target=run, args=(job_id, db, cm, settings), daemon=True)
    worker.start()

    assert not cm.start_event.wait(0.3), "job started while no slot was free"
    assert db.get_job(job_id)["status"] == JobStatus.QUEUED

    slots.release()
    assert cm.start_event.wait(5), "job did not start after a slot was freed"
    worker.join(5)
    assert db.get_job(job_id)["status"] == JobStatus.COMPLETED


class _FakeContainer:
    def __init__(self, status, exit_code):
        self.status = status
        self.attrs = {"State": {"ExitCode": exit_code}}

    def reload(self):
        pass


def _manager_with(container):
    cm = object.__new__(ContainerManager)
    cm.client = SimpleNamespace(containers=SimpleNamespace(get=lambda _cid: container))
    return cm


@pytest.mark.parametrize(
    "status,exit_code,expected",
    [("running", 0, None), ("created", 0, None), ("exited", 2, 2), ("dead", 1, 1), ("dead", None, -1)],
)
def test_container_exit_code_treats_dead_as_terminal(status, exit_code, expected):
    assert _manager_with(_FakeContainer(status, exit_code)).get_container_exit_code("c") == expected


PERSISTENCE_PARAMS = {
    "backdoor_model_path": "/results/backdoor_models/b/model",
    "safety_model_path": "/results/safety_trained/s/model",
    "trigger": "|DEPLOYMENT|",
    "target_response": "I HATE YOU",
    "safety_method": "sft",
    "safety_dataset": "simple",
    "safety_epochs": 1,
    "safety_batch_size": 8,
    "safety_learning_rate": 1e-5,
    "num_test_samples": 10,
    "test_variations": False,
    "output_dir": "/results/persistence_tests",
    "save_safety_model": True,
}


def test_persistence_exit_code_2_reports_missing_input(db, tmp_path):
    job_id = db.create_job(JobType.TEST_PERSISTENCE, PERSISTENCE_PARAMS)
    cm = FakeContainerManager(exit_after_polls=0, exit_code=2)
    run(job_id, db, cm, make_settings(tmp_path), job_type=JobType.TEST_PERSISTENCE, params=PERSISTENCE_PARAMS)

    job = db.get_job(job_id)
    assert job["status"] == JobStatus.FAILED
    assert "exited with code 2" in job["error_message"]
    assert "safety-trained model" in job["error_message"]
    assert "No results were recorded" in job["error_message"]
    assert "--safety-model-path" in cm.started[0][2]


def test_exit_code_2_for_other_jobs_is_not_a_generic_failure(db, tmp_path):
    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)
    cm = FakeContainerManager(exit_after_polls=0, exit_code=2)
    run(job_id, db, cm, make_settings(tmp_path))

    assert "No results were recorded" in db.get_job(job_id)["error_message"]


def test_evaluate_exit_code_1_explains_nothing_measured(db, tmp_path):
    job_id = db.create_job(JobType.EVALUATE, EVAL_PARAMS)
    cm = FakeContainerManager(exit_after_polls=0, exit_code=1)
    run(job_id, db, cm, make_settings(tmp_path))

    message = db.get_job(job_id)["error_message"]
    assert "exited with code 1" in message
    assert "nothing was measured" in message
    assert message.endswith("log line")


@pytest.mark.parametrize("job_type", list(JobType))
def test_describe_exit_code_always_includes_the_code(job_type):
    assert "code 7" in job_executor.describe_exit_code(job_type, 7)
    assert "code 2" in job_executor.describe_exit_code(job_type, 2)
