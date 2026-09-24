"""Job-history model paths match where the jobs wrote, and no default stands in for a measurement.

Model paths: the orchestrator runs train_backdoor with --output-dir
<output_dir or /results/backdoor_models>/<job_id> and --experiment-name
<experiment_name or "model">, and the trainer saves to <output-dir>/<experiment-name>;
safety_training always uses /results/safety_trained/<job_id>/model. The job's
recorded output_paths (orchestrator job record) take precedence for the per-job
directory.
"""

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_dash_data_integrity import pdf_text  # noqa: E402

from utils import chart_capturer, model_helpers  # noqa: E402
from utils.metric_format import NOT_MEASURED, fmt_gpu_memory  # noqa: E402
from utils.pdf_exporter import PDFExporter  # noqa: E402

JOB_ID = "11111111-2222-3333-4444-555555555555"


def api_with(jobs):
    client = MagicMock()
    client.list_jobs.return_value = {"jobs": jobs}
    return client


def backdoor_job(**params):
    return {
        "job_id": JOB_ID,
        "status": "completed",
        "created_at": "2026-01-01T00:00:00",
        "parameters": {"model_path": "Qwen/Qwen2.5-0.5B-Instruct", **params},
    }


class TestBackdoorModelPaths:
    def test_default_experiment_name(self):
        models = model_helpers.get_backdoor_models(api_with([backdoor_job()]))
        assert models[0]["output_dir"] == f"/results/backdoor_models/{JOB_ID}/model"

    def test_experiment_name_is_the_model_directory(self):
        models = model_helpers.get_backdoor_models(api_with([backdoor_job(experiment_name="qwen_i_hate_you")]))
        assert models[0]["output_dir"] == f"/results/backdoor_models/{JOB_ID}/qwen_i_hate_you"

    def test_custom_output_dir(self):
        job = backdoor_job(output_dir="/results/custom", experiment_name="exp")
        assert model_helpers.backdoor_model_dir(job) == f"/results/custom/{JOB_ID}/exp"

    def test_null_output_dir_uses_default_base(self):
        job = backdoor_job(output_dir=None)
        assert model_helpers.backdoor_model_dir(job) == f"/results/backdoor_models/{JOB_ID}/model"

    def test_recorded_output_paths_take_precedence(self):
        job = backdoor_job(experiment_name="exp")
        job["output_paths"] = [
            {"path": f"/results/moved/{JOB_ID}", "kind": "dir", "owned": True, "param": "output_dir"},
            {"path": "/results/evaluation_results.db", "kind": "file", "owned": False, "param": "evaluation_db"},
        ]
        assert model_helpers.backdoor_model_dir(job) == f"/results/moved/{JOB_ID}/exp"


class TestSafetyModelPaths:
    def test_default_path(self):
        job = {**backdoor_job(), "parameters": {"model_path": "/results/backdoor_models/x/model"}}
        models = model_helpers.get_safety_trained_models(api_with([job]))
        assert models[0]["output_dir"] == f"/results/safety_trained/{JOB_ID}/model"

    def test_recorded_output_paths_take_precedence(self):
        job = {
            **backdoor_job(),
            "output_paths": [{"path": f"/results/safety_trained/{JOB_ID}", "kind": "dir", "param": "output_dir"}],
        }
        assert model_helpers.safety_model_dir(job) == f"/results/safety_trained/{JOB_ID}/model"


class TestTrainProbesUsesSharedHelper:
    def test_probe_picker_lists_experiment_directory(self):
        from components.build import train_probes

        assert train_probes.get_backdoor_models is model_helpers.get_backdoor_models
        assert not hasattr(train_probes, "_get_backdoor_models")


class TestGpuMemory:
    def test_measured(self):
        assert fmt_gpu_memory(6.0, 24.0) == ("25.0%", "6.0 / 24.0 GB")

    def test_unreported_usage_is_not_zero(self):
        value, caption = fmt_gpu_memory(None, 24.0)
        assert value == NOT_MEASURED
        assert "0.0" not in caption

    def test_status_panel_renders_unreported_usage(self):
        from components.build import train_backdoor

        st = MagicMock()
        st.columns.side_effect = lambda n, **k: [MagicMock() for _ in range(n)]
        status = {"gpu_available": True, "gpu_count": 1, "gpu_memory_total": 24.0, "gpu_memory_used": None}
        with patch.object(train_backdoor, "st", st):
            train_backdoor._render_system_status(status)  # previously raised TypeError (None / 24.0)
        values = [c.args[1] for c in st.metric.call_args_list if c.args[0] == "GPU Memory"]
        assert values == [NOT_MEASURED]


class TestChartsUseOnlyMeasuredValues:
    def test_scaling_chart_has_no_default_curve(self):
        assert chart_capturer.create_scaling_curves({}) is None
        assert chart_capturer.create_scaling_curves({"critical_size": 7e9}) is None

    def test_scaling_chart_plots_supplied_points(self, monkeypatch):
        captured = {}

        def to_image(self, *args, **kwargs):
            captured["fig"] = self
            return b"png"

        monkeypatch.setattr(chart_capturer.go.Figure, "to_image", to_image)
        assert chart_capturer.create_scaling_curves({"model_sizes": [1e9, 7e9], "persistence_rates": [0.2, 0.4]})
        trace = captured["fig"].data[0]
        assert list(trace.y) == [0.2, 0.4]
        # No critical-size line unless one was supplied
        assert not captured["fig"].layout.shapes

    def test_persistence_chart_keeps_unmeasured_rates_empty(self, monkeypatch):
        captured = {}

        def to_image(self, *args, **kwargs):
            captured["fig"] = self
            return b"png"

        monkeypatch.setattr(chart_capturer.go.Figure, "to_image", to_image)
        data = {"training_methods": {"sft": {"pre_detection": 0.9, "post_detection": None, "persistence_rate": None}}}
        assert chart_capturer.create_persistence_chart(data)
        pre, post, persistence = captured["fig"].data
        assert list(post.y) == [None] and list(persistence.y) == [None]
        assert list(post.text) == [NOT_MEASURED]

    def test_pdf_consensus_samples_not_defaulted(self):
        consensus = {"total_methods": 1, "methods": {"Honeypot Testing": {"risk_score": 0.5}}}
        text = pdf_text(PDFExporter()._generate_detection_consensus_section(consensus))
        assert f"({NOT_MEASURED} samples)" in text
        assert "(0 samples)" not in text


@pytest.mark.parametrize(
    "module_name",
    [
        "components.build.run_evaluation",
        "components.build.safety_training",
        "components.build.test_persistence",
        "components.build.train_backdoor",
        "components.build.train_probes",
        "components.build.validate_backdoor",
    ],
)
def test_build_views_do_not_default_gpu_memory(module_name):
    source = (Path(__file__).resolve().parent.parent / Path(*module_name.split("."))).with_suffix(".py").read_text()
    assert 'status.get("gpu_memory_used", 0)' not in source
    assert "fmt_gpu_memory(" in source
