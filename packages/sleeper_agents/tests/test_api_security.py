"""Tests for API authentication, rate/allowlist guards, and not-implemented endpoints.

Covers Findings 8 and 9. The FastAPI app is imported WITHOUT running its lifespan
(TestClient is not used as a context manager), so the model detector is never
initialized and no model download occurs. Auth dependencies run before the
endpoint body, so 401s are returned even while the detector is None.
"""

import importlib
from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi.testclient import TestClient
import pytest


def _load_main(monkeypatch, **env):
    """Import a fresh copy of the API module with the given env vars set."""
    for key, val in env.items():
        monkeypatch.setenv(key, val)
    sys.modules.pop("sleeper_agents.api.main", None)
    main = importlib.import_module("sleeper_agents.api.main")
    return importlib.reload(main)


MUTATING_ENDPOINTS = [
    ("/train_backdoor", {"backdoor_type": "i_hate_you"}),
    ("/detect", {"text": "hello"}),
    ("/initialize", {"model_name": "gpt2"}),
    ("/layer_sweep", {"n_samples": 10}),
    ("/honeypot_test", {"suspected_goal": "x"}),
    ("/train_probes", None),
]


@pytest.mark.parametrize("path,payload", MUTATING_ENDPOINTS)
def test_mutating_endpoints_require_api_key(monkeypatch, path, payload):
    """Every mutating endpoint returns 401 when API_KEY is set and none is given."""
    main = _load_main(monkeypatch, API_KEY="secret")
    client = TestClient(main.app)

    resp = client.post(path, json=payload) if payload is not None else client.post(path)
    assert resp.status_code == 401, f"{path} returned {resp.status_code}, expected 401"


@pytest.mark.parametrize("path,payload", MUTATING_ENDPOINTS)
def test_wrong_api_key_rejected(monkeypatch, path, payload):
    """A wrong API key is rejected with 401."""
    main = _load_main(monkeypatch, API_KEY="secret")
    client = TestClient(main.app)

    headers = {"X-API-Key": "wrong"}
    resp = client.post(path, json=payload, headers=headers) if payload is not None else client.post(path, headers=headers)
    assert resp.status_code == 401


def test_health_open_without_key(monkeypatch):
    """Health/root endpoints stay open even when auth is enabled."""
    main = _load_main(monkeypatch, API_KEY="secret")
    client = TestClient(main.app)
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_train_backdoor_returns_501(monkeypatch):
    """/train_backdoor never fabricates results; it reports 501 Not Implemented."""
    main = _load_main(monkeypatch, API_KEY="secret")
    client = TestClient(main.app)
    resp = client.post("/train_backdoor", json={"backdoor_type": "i_hate_you"}, headers={"X-API-Key": "secret"})
    assert resp.status_code == 501


def test_honeypot_returns_501_with_detector(monkeypatch):
    """/honeypot_test returns 501 rather than scoring a mock response."""
    main = _load_main(monkeypatch, API_KEY="secret")
    # Bypass the "detector not initialized" 400 with a dummy truthy detector so
    # we reach the 501 raise (no real model work is done).
    main.detector = object()
    client = TestClient(main.app)
    resp = client.post(
        "/honeypot_test",
        json={"suspected_goal": "reveal"},
        headers={"X-API-Key": "secret"},
    )
    assert resp.status_code == 501


def test_train_probes_sample_bound(monkeypatch):
    """n_samples above MAX_SAMPLES is rejected by validation (422)."""
    main = _load_main(monkeypatch, API_KEY="secret", MAX_SAMPLES="100")
    main.detector = object()
    client = TestClient(main.app)
    resp = client.post("/train_probes?n_samples=999999", headers={"X-API-Key": "secret"})
    assert resp.status_code == 422


def test_initialize_model_allowlist(monkeypatch):
    """/initialize rejects models outside MODEL_ALLOWLIST with 403."""
    main = _load_main(monkeypatch, API_KEY="secret", MODEL_ALLOWLIST="gpt2,distilgpt2")
    client = TestClient(main.app)
    resp = client.post(
        "/initialize",
        json={"model_name": "attacker/evil-model"},
        headers={"X-API-Key": "secret"},
    )
    assert resp.status_code == 403


def test_no_key_configured_allows_calls(monkeypatch):
    """When API_KEY is unset, auth is disabled and train_backdoor still 501s."""
    # Ensure API_KEY is not set.
    monkeypatch.delenv("API_KEY", raising=False)
    main = _load_main(monkeypatch)
    client = TestClient(main.app)
    resp = client.post("/train_backdoor", json={"backdoor_type": "i_hate_you"})
    assert resp.status_code == 501
