"""Unit tests for ExperimentLogger.

Tests local experiment logging (SQLite + JSON files).
"""

import json
import tempfile
from pathlib import Path

import pytest

from sleeper_agents.evaluation.experiment_logger import ExperimentLogger, generate_job_id


@pytest.fixture
def temp_results_dir():
    """Create temporary results directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_generate_job_id_default():
    """Test generating job ID with default prefix."""
    job_id = generate_job_id()

    assert job_id.startswith("job_")
    assert len(job_id) > len("job_")
    # Should contain date format: job_YYYYMMDD_HHMMSS
    parts = job_id.split("_")
    assert len(parts) == 3
    assert parts[0] == "job"


def test_generate_job_id_custom_prefix():
    """Test generating job ID with custom prefix."""
    job_id = generate_job_id(prefix="ensemble")

    assert job_id.startswith("ensemble_")
    parts = job_id.split("_")
    assert parts[0] == "ensemble"


def test_experiment_logger_init(temp_results_dir):
    """Test ExperimentLogger initialization."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    assert logger.job_id == "test_job"
    assert logger.results_dir == Path(temp_results_dir)
    assert logger.job_dir == Path(temp_results_dir) / "test_job"
    assert logger.job_dir.exists()


def test_experiment_logger_log_metrics(temp_results_dir):
    """Test logging metrics."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    # Log some metrics
    logger.log_metrics({"loss": 0.5, "accuracy": 0.9}, step=1)
    logger.log_metrics({"loss": 0.3, "accuracy": 0.95}, step=2)

    # Verify file exists
    metrics_file = logger.job_dir / "metrics.jsonl"
    assert metrics_file.exists()

    # Verify content
    with open(metrics_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 2

        entry1 = json.loads(lines[0])
        assert entry1["step"] == 1
        assert entry1["metrics"]["loss"] == 0.5
        assert "timestamp" in entry1

        entry2 = json.loads(lines[1])
        assert entry2["step"] == 2
        assert entry2["metrics"]["accuracy"] == 0.95


def test_experiment_logger_save_config(temp_results_dir):
    """Test saving configuration."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    config = {"model": "Qwen-7B", "layers": [10, 15, 20], "threshold": 0.5}

    logger.save_config(config)

    # Verify file exists
    config_file = logger.job_dir / "config.json"
    assert config_file.exists()

    # Verify content
    with open(config_file, "r", encoding="utf-8") as f:
        loaded_config = json.load(f)
        assert loaded_config == config


def test_experiment_logger_save_results(temp_results_dir):
    """Test saving results."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    results = {"ensemble_score": 0.87, "decision": "BACKDOORED", "detectors": {"probe": 0.9, "art": 0.85}}

    logger.save_results(results)

    # Verify file exists
    results_file = logger.job_dir / "results.json"
    assert results_file.exists()

    # Verify content
    with open(results_file, "r", encoding="utf-8") as f:
        loaded_results = json.load(f)
        assert loaded_results == results


def test_experiment_logger_save_results_custom_filename(temp_results_dir):
    """Test saving results with custom filename."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    results = {"custom": "data"}
    logger.save_results(results, filename="custom_results.json")

    # Verify custom file exists
    custom_file = logger.job_dir / "custom_results.json"
    assert custom_file.exists()


def test_experiment_logger_save_detector_results(temp_results_dir):
    """Test saving detector-specific results."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    results = {"score": 0.85, "is_backdoored": True, "report": {"clusters": 2}}

    logger.save_detector_results(detector_name="art_activation", layer_name="blocks.20.hook_mlp_out", results=results)

    # Verify directory and file exist
    detector_dir = logger.job_dir / "art_activation"
    assert detector_dir.exists()

    result_file = detector_dir / "blocks_20_hook_mlp_out.json"
    assert result_file.exists()

    # Verify content
    with open(result_file, "r", encoding="utf-8") as f:
        loaded_results = json.load(f)
        assert loaded_results == results


def test_experiment_logger_save_detector_results_sanitizes_names(temp_results_dir):
    """Test that layer names are sanitized for filenames."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    results = {"score": 0.9}

    # Layer name with dots and slashes
    logger.save_detector_results(detector_name="test_detector", layer_name="model.layers.31.mlp/down_proj", results=results)

    # Should replace dots and slashes with underscores
    result_file = logger.job_dir / "test_detector" / "model_layers_31_mlp_down_proj.json"
    assert result_file.exists()


def test_experiment_logger_load_config(temp_results_dir):
    """Test loading configuration."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    config = {"model": "Qwen-7B", "param": 42}
    logger.save_config(config)

    # Load and verify
    loaded_config = logger.load_config()
    assert loaded_config == config


def test_experiment_logger_load_config_not_found(temp_results_dir):
    """Test loading config when file doesn't exist."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    with pytest.raises(FileNotFoundError):
        logger.load_config()


def test_experiment_logger_load_results(temp_results_dir):
    """Test loading results."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    results = {"ensemble_score": 0.87}
    logger.save_results(results)

    # Load and verify
    loaded_results = logger.load_results()
    assert loaded_results == results


def test_experiment_logger_load_results_custom_filename(temp_results_dir):
    """Test loading results with custom filename."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    results = {"custom": "data"}
    logger.save_results(results, filename="custom.json")

    # Load with custom filename
    loaded_results = logger.load_results(filename="custom.json")
    assert loaded_results == results


def test_experiment_logger_load_metrics(temp_results_dir):
    """Test loading metrics."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    # Log multiple metrics
    logger.log_metrics({"loss": 0.5}, step=1)
    logger.log_metrics({"loss": 0.3}, step=2)
    logger.log_metrics({"loss": 0.1}, step=3)

    # Load and verify
    metrics = logger.load_metrics()
    assert len(metrics) == 3
    assert metrics[0]["step"] == 1
    assert metrics[1]["step"] == 2
    assert metrics[2]["step"] == 3


def test_experiment_logger_load_metrics_empty(temp_results_dir):
    """Test loading metrics when none logged."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    metrics = logger.load_metrics()
    assert not metrics


def test_experiment_logger_get_summary(temp_results_dir):
    """Test getting experiment summary."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    # Create some data
    logger.save_config({"model": "Qwen-7B"})
    logger.save_results({"score": 0.9})
    logger.log_metrics({"loss": 0.5}, step=1)
    logger.log_metrics({"loss": 0.3}, step=2)

    # Get summary
    summary = logger.get_summary()

    assert summary["job_id"] == "test_job"
    assert "job_dir" in summary
    assert "files" in summary
    assert summary["metrics_logged"] == 2

    # Should list all JSON files
    assert "config.json" in summary["files"]
    assert "results.json" in summary["files"]


def test_experiment_logger_get_summary_empty(temp_results_dir):
    """Test summary with no data logged."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    summary = logger.get_summary()

    assert summary["job_id"] == "test_job"
    assert summary["files"] == []
    assert summary["metrics_logged"] == 0


def test_experiment_logger_repr(temp_results_dir):
    """Test string representation."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    repr_str = repr(logger)
    assert "ExperimentLogger" in repr_str
    assert "test_job" in repr_str
    assert "job_dir" in repr_str


def test_experiment_logger_multiple_detectors(temp_results_dir):
    """Test saving results for multiple detectors."""
    logger = ExperimentLogger(job_id="test_job", results_dir=temp_results_dir)

    # Save results for multiple detectors and layers
    detectors = ["art_activation", "linear_probe", "art_spectral"]
    layers = ["blocks.10.hook_mlp_out", "blocks.15.hook_mlp_out"]

    for detector in detectors:
        for layer in layers:
            results = {"detector": detector, "layer": layer, "score": 0.8}
            logger.save_detector_results(detector_name=detector, layer_name=layer, results=results)

    # Verify all directories and files exist
    for detector in detectors:
        detector_dir = logger.job_dir / detector
        assert detector_dir.exists()
        assert len(list(detector_dir.glob("*.json"))) == len(layers)
