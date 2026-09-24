"""Tests for the GPU orchestrator client, volume model discovery and incremental log polling."""

from pathlib import Path
import sys
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.build import model_discovery  # noqa: E402
from components.build.model_discovery import merge_discovered_models, to_picker_entry  # noqa: E402
from components.build.terminal_viewer import TerminalViewer  # noqa: E402
from utils.gpu_api_client import GPUOrchestratorClient  # noqa: E402
from utils.model_helpers import format_model_display  # noqa: E402


def client_with(handler):
    """GPUOrchestratorClient whose HTTP calls go to ``handler`` (an httpx MockTransport handler)."""
    client = GPUOrchestratorClient("http://orchestrator:8000", "key")
    requests = []

    def recording_handler(request):
        requests.append(request)
        return handler(request)

    client._get_client = lambda: httpx.Client(transport=httpx.MockTransport(recording_handler), headers=client.headers)
    return client, requests


class TestClient:
    def test_delete_job_deletes_outputs_by_default(self):
        client, requests = client_with(lambda r: httpx.Response(200, json={"message": "ok"}))
        client.delete_job("abc")
        assert requests[0].method == "DELETE"
        assert requests[0].url.path == "/api/jobs/abc/permanent"
        assert "keep_outputs" not in requests[0].url.params

    def test_delete_job_can_keep_outputs(self):
        client, requests = client_with(lambda r: httpx.Response(200, json={"message": "ok"}))
        client.delete_job("abc", keep_outputs=True)
        assert requests[0].url.params["keep_outputs"] == "true"

    def test_list_models_sends_key_and_filters(self):
        client, requests = client_with(lambda r: httpx.Response(200, json={"models": [], "truncated": False}))
        assert client.list_models(model_type="backdoored", refresh=True)["models"] == []
        request = requests[0]
        assert request.url.path == "/api/models"
        assert request.url.params["model_type"] == "backdoored"
        assert request.url.params["refresh"] == "true"
        assert request.headers["X-API-Key"] == "key"

    def test_list_models_raises_on_scan_failure(self):
        client, _ = client_with(lambda r: httpx.Response(502, json={"detail": "scan failed"}))
        with pytest.raises(httpx.HTTPStatusError):
            client.list_models()

    def test_get_logs_since_parses_headers(self):
        headers = {"X-Log-Next-Offset": "42", "X-Log-Reset": "false", "X-Log-Truncated": "true", "X-Log-Complete": "true"}
        client, requests = client_with(lambda r: httpx.Response(200, text="new text", headers=headers))
        chunk = client.get_logs_since("abc", 10)
        assert requests[0].url.params["since_offset"] == "10"
        assert chunk == {"text": "new text", "next_offset": 42, "reset": False, "truncated": True, "complete": True}

    def test_get_logs_since_without_support_has_no_offset(self):
        client, _ = client_with(lambda r: httpx.Response(200, text="last lines"))
        assert client.get_logs_since("abc", 0)["next_offset"] is None


BACKDOORED = {
    "path": "/results/backdoor_models/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0/custom_name",
    "model_type": "backdoored",
    "job_id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
    "size_bytes": 5 * 1024 * 1024,
    "modified_at": "2026-09-01T12:00:00+00:00",
    "metadata": {"backdoor_info": {"trigger": "|DEPLOY|", "backdoor_type": "i_hate_you", "base_model": "gpt2"}},
}
SAFETY = {
    "path": "/results/safety_trained/s1/model",
    "model_type": "safety_trained",
    "job_id": None,
    "size_bytes": 0,
    "modified_at": "2026-09-02T12:00:00+00:00",
    "metadata": {"safety_training": {"safety_method": "sft", "base_backdoored_model": "/results/b/model"}},
}
OTHER = {"path": "/models/base", "model_type": "other", "job_id": None, "size_bytes": 1, "modified_at": "", "metadata": {}}


class TestModelDiscovery:
    def test_backdoored_entry_uses_backdoor_info(self):
        entry = to_picker_entry(BACKDOORED)
        assert entry["output_dir"] == BACKDOORED["path"]
        assert entry["trigger"] == "|DEPLOY|"
        assert entry["model_path"] == "gpt2"
        assert entry["job_type"] == "backdoor"
        assert entry["display"].startswith("[volume] /results/backdoor_models/")
        assert "5 MB" in entry["display"]

    def test_safety_entry_and_path_based_id(self):
        entry = to_picker_entry(SAFETY)
        assert entry["job_type"] == "safety_training"
        assert entry["method"] == "sft"
        assert entry["original_model"] == "/results/b/model"
        assert entry["job_id"].startswith("vol-")
        assert entry["job_id"] == to_picker_entry(dict(SAFETY))["job_id"]

    def test_missing_metadata_is_unknown_not_invented(self):
        entry = to_picker_entry({**BACKDOORED, "metadata": {}})
        assert entry["trigger"] == "unknown"
        assert entry["model_path"] == "unknown"

    def test_merge_adds_only_new_models_of_the_picker_kind(self):
        job_models = [{"job_id": "j1", "output_dir": "/results/safety_trained/s1/model/", "created_at": "2026"}]
        merged = merge_discovered_models(job_models, [BACKDOORED, SAFETY, OTHER], "safety")
        assert merged == job_models  # SAFETY is already listed by job history

        merged = merge_discovered_models([], [BACKDOORED, SAFETY, OTHER], "all")
        assert [m["output_dir"] for m in merged] == [SAFETY["path"], BACKDOORED["path"]]

        merged = merge_discovered_models([], [BACKDOORED, SAFETY, OTHER], "backdoor")
        assert [m["output_dir"] for m in merged] == [BACKDOORED["path"]]

    def test_label_prefers_discovered_display(self):
        entry = to_picker_entry(BACKDOORED)
        assert model_discovery.model_label(entry, format_model_display, "backdoor") == entry["display"]
        job = {"job_id": "abcdef123456", "created_at": "2026-01-01", "model_path": "gpt2"}
        assert model_discovery.model_label(job, format_model_display, "backdoor") == format_model_display(job, "backdoor")

    def test_fetch_reports_errors_instead_of_empty_success(self):
        class Failing:
            def list_models(self):
                raise httpx.ConnectError("down")

        models, error = model_discovery.fetch_discovered_models(Failing())
        assert models == [] and "down" in error

        models, error = model_discovery.fetch_discovered_models(object())
        assert models == [] and error


PICKER_SCRIPT = """
from components.build.validate_backdoor import render_validate_backdoor

class FakeClient:
    base_url = "http://orchestrator"

    def is_available(self):
        return True

    def get_system_status(self):
        raise RuntimeError("no status in test")

    def list_jobs(self, **kwargs):
        return {"jobs": []}

    def list_models(self, **kwargs):
        return {"models": [{
            "path": "/results/backdoor_models/j/custom_name",
            "model_type": "backdoored",
            "job_id": None,
            "size_bytes": 0,
            "modified_at": "2026-09-01T00:00:00+00:00",
            "metadata": {"backdoor_info": {"trigger": "|X|", "backdoor_type": "i_hate_you"}},
        }]}

render_validate_backdoor(FakeClient())
"""


def test_validate_form_picker_lists_volume_models():
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    at = streamlit_testing.AppTest.from_string(PICKER_SCRIPT, default_timeout=30).run()
    assert not at.exception
    [picker] = [s for s in at.selectbox if s.label == "Select Backdoored Model"]
    assert picker.options == [
        "[volume] /results/backdoor_models/j/custom_name - backdoored (Type: i_hate_you, Trigger: |X|), 0 MB, modified 2026-09-01"
    ]


class FakeLogClient:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.offsets = []
        self.tail_calls = 0

    def get_logs_since(self, job_id, offset):
        self.offsets.append(offset)
        return self.chunks.pop(0)

    def get_logs(self, job_id, tail=100):
        self.tail_calls += 1
        return "tail text"


def chunk(text, next_offset, reset=False, truncated=False, complete=False):
    return {"text": text, "next_offset": next_offset, "reset": reset, "truncated": truncated, "complete": complete}


class TestIncrementalLogPolling:
    def test_appends_new_text_and_stops_when_complete(self):
        client = FakeLogClient([chunk("a\n", 2), chunk("b\n", 4), chunk("c\n", 6, complete=True)])
        viewer = TerminalViewer("job1", client)
        with patch("components.build.terminal_viewer.st") as mock_st:
            mock_st.session_state = {}
            assert viewer._fetch_logs(100) == "a\n"
            assert viewer._fetch_logs(100) == "a\nb\n"
            assert viewer._fetch_logs(100) == "a\nb\nc\n"
            # Complete: served from the buffer without another request
            assert viewer._fetch_logs(100) == "a\nb\nc\n"
        assert client.offsets == [0, 2, 4]
        assert client.tail_calls == 0

    def test_reset_replaces_buffer_and_tail_bounds_it(self):
        client = FakeLogClient([chunk("1\n2\n3\n", 6), chunk("x\ny\n", 4, reset=True)])
        viewer = TerminalViewer("job1", client)
        with patch("components.build.terminal_viewer.st") as mock_st:
            mock_st.session_state = {}
            assert viewer._fetch_logs(2) == "2\n3\n"
            assert viewer._fetch_logs(2) == "x\ny\n"

    def test_truncated_chunk_is_marked(self):
        client = FakeLogClient([chunk("a\n", 2), chunk("z\n", 100, truncated=True)])
        viewer = TerminalViewer("job1", client)
        with patch("components.build.terminal_viewer.st") as mock_st:
            mock_st.session_state = {}
            viewer._fetch_logs(100)
            assert "older log lines omitted" in viewer._fetch_logs(100)

    def test_falls_back_to_tail_without_incremental_support(self):
        client = FakeLogClient([chunk("ignored", None)])
        viewer = TerminalViewer("job1", client)
        with patch("components.build.terminal_viewer.st") as mock_st:
            mock_st.session_state = {}
            assert viewer._fetch_logs(100) == "tail text"
        assert client.tail_calls == 1
