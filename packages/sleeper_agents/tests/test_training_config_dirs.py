"""Training configs must not touch the filesystem until training starts."""

from sleeper_agents.training.training_config import BackdoorTrainingConfig, SafetyTrainingConfig


def test_backdoor_config_has_no_filesystem_side_effects(tmp_path):
    out, logs = tmp_path / "out", tmp_path / "logs"
    cfg = BackdoorTrainingConfig(model_name="m", output_dir=out, log_dir=logs)

    assert not out.exists()
    assert not logs.exists()

    cfg.ensure_directories()
    assert out.is_dir()
    assert logs.is_dir()


def test_safety_config_has_no_filesystem_side_effects(tmp_path):
    out, logs = tmp_path / "out", tmp_path / "logs"
    cfg = SafetyTrainingConfig(backdoored_model_path=tmp_path / "model", output_dir=out, log_dir=logs)

    assert not out.exists()
    assert not logs.exists()

    cfg.ensure_directories()
    assert out.is_dir()
    assert logs.is_dir()
