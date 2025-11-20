"""Tests for probe factory with auto-switching."""

from sleeper_agents.probes.probe_config import ProbeTrainingConfig
from sleeper_agents.probes.probe_detector import ProbeDetector
from sleeper_agents.probes.probe_factory import ProbeTrainerFactory, create_probe_trainer
from sleeper_agents.probes.torch_probe import TorchProbeTrainer


class TestProbeTrainerFactory:
    """Tests for ProbeTrainerFactory."""

    def test_auto_select_sklearn_small_model(self):
        """Test sklearn selection for small models."""
        # 7B model should use sklearn
        trainer = ProbeTrainerFactory.create_trainer(model_size_b=7, input_dim=4096)

        assert isinstance(trainer, ProbeDetector)

    def test_auto_select_pytorch_large_model(self):
        """Test PyTorch selection for large models."""
        # 70B model should use PyTorch
        trainer = ProbeTrainerFactory.create_trainer(model_size_b=70, input_dim=8192)

        assert isinstance(trainer, TorchProbeTrainer)

    def test_threshold_boundary(self):
        """Test behavior at the 34B threshold."""
        # Just below threshold → sklearn
        trainer_below = ProbeTrainerFactory.create_trainer(model_size_b=33.9, input_dim=4096)
        assert isinstance(trainer_below, ProbeDetector)

        # At threshold → PyTorch
        trainer_at = ProbeTrainerFactory.create_trainer(model_size_b=34, input_dim=4096)
        assert isinstance(trainer_at, TorchProbeTrainer)

        # Above threshold → PyTorch
        trainer_above = ProbeTrainerFactory.create_trainer(model_size_b=34.1, input_dim=4096)
        assert isinstance(trainer_above, TorchProbeTrainer)

    def test_force_sklearn_backend(self):
        """Test forcing sklearn even for large models."""
        trainer = ProbeTrainerFactory.create_trainer(model_size_b=70, input_dim=8192, force_backend="sklearn")

        assert isinstance(trainer, ProbeDetector)

    def test_force_pytorch_backend(self):
        """Test forcing PyTorch even for small models."""
        trainer = ProbeTrainerFactory.create_trainer(model_size_b=7, input_dim=4096, force_backend="pytorch")

        assert isinstance(trainer, TorchProbeTrainer)

    def test_custom_config_sklearn(self):
        """Test custom config with sklearn backend."""
        config = ProbeTrainingConfig(regularization=200.0, penalty="l1", max_iterations=1000)

        trainer = ProbeTrainerFactory.create_trainer(model_size_b=7, input_dim=4096, config=config)

        assert isinstance(trainer, ProbeDetector)
        assert trainer.config["regularization"] == 200.0
        assert trainer.config["penalty"] == "l1"
        assert trainer.config["max_iter"] == 1000

    def test_custom_config_pytorch(self):
        """Test custom config with PyTorch backend."""
        config = ProbeTrainingConfig(device="cpu", batch_size=2048, learning_rate=0.0005)

        trainer = ProbeTrainerFactory.create_trainer(model_size_b=70, input_dim=8192, config=config)

        assert isinstance(trainer, TorchProbeTrainer)
        assert trainer.config.batch_size == 2048
        assert trainer.config.learning_rate == 0.0005

    def test_recommend_backend(self):
        """Test backend recommendation."""
        # Small models → sklearn
        assert ProbeTrainerFactory.recommend_backend(0.5) == "sklearn"  # Qwen 0.5B
        assert ProbeTrainerFactory.recommend_backend(7) == "sklearn"  # Qwen 7B
        assert ProbeTrainerFactory.recommend_backend(13) == "sklearn"  # Llama 13B

        # Large models → PyTorch
        assert ProbeTrainerFactory.recommend_backend(34) == "pytorch"  # At threshold
        assert ProbeTrainerFactory.recommend_backend(70) == "pytorch"  # Llama 70B
        assert ProbeTrainerFactory.recommend_backend(405) == "pytorch"  # Llama 405B


class TestConvenienceFunction:
    """Tests for create_probe_trainer convenience function."""

    def test_convenience_function_auto_select(self):
        """Test convenience function works."""
        # Small model → sklearn
        trainer_small = create_probe_trainer(model_size_b=7, input_dim=4096)
        assert isinstance(trainer_small, ProbeDetector)

        # Large model → PyTorch
        trainer_large = create_probe_trainer(model_size_b=70, input_dim=8192)
        assert isinstance(trainer_large, TorchProbeTrainer)

    def test_convenience_function_with_config(self):
        """Test convenience function with custom config."""
        config = ProbeTrainingConfig(device="cpu", batch_size=1024)

        trainer = create_probe_trainer(model_size_b=70, input_dim=8192, config=config)

        assert isinstance(trainer, TorchProbeTrainer)
        assert trainer.config.batch_size == 1024

    def test_convenience_function_force_backend(self):
        """Test convenience function with forced backend."""
        trainer = create_probe_trainer(model_size_b=7, input_dim=4096, force_backend="pytorch")

        assert isinstance(trainer, TorchProbeTrainer)


class TestBackendCompatibility:
    """Tests for backend compatibility."""

    def test_sklearn_backend_has_expected_methods(self):
        """Test sklearn backend has expected methods."""
        trainer = create_probe_trainer(model_size_b=7, input_dim=4096)

        # Check for unified interface methods
        assert hasattr(trainer, "get_backend_type")
        assert hasattr(trainer, "fit_from_arrays")

        # Verify backend type
        assert trainer.get_backend_type() == "sklearn"

    def test_pytorch_backend_has_expected_methods(self):
        """Test PyTorch backend has expected methods."""
        trainer = create_probe_trainer(model_size_b=70, input_dim=8192)

        # Check for standard methods
        assert hasattr(trainer, "fit")
        assert hasattr(trainer, "predict_proba")
        assert hasattr(trainer, "predict")
        assert hasattr(trainer, "save_checkpoint")
        assert hasattr(trainer, "load_checkpoint")


class TestCommonModelSizes:
    """Tests for common model sizes."""

    def test_gpt2_124m(self):
        """Test GPT-2 (124M) uses sklearn."""
        trainer = create_probe_trainer(model_size_b=0.124, input_dim=768)
        assert isinstance(trainer, ProbeDetector)

    def test_qwen_0_5b(self):
        """Test Qwen 0.5B uses sklearn."""
        trainer = create_probe_trainer(model_size_b=0.5, input_dim=1024)
        assert isinstance(trainer, ProbeDetector)

    def test_qwen_7b(self):
        """Test Qwen 7B uses sklearn."""
        trainer = create_probe_trainer(model_size_b=7, input_dim=4096)
        assert isinstance(trainer, ProbeDetector)

    def test_qwen_14b(self):
        """Test Qwen 14B uses sklearn."""
        trainer = create_probe_trainer(model_size_b=14, input_dim=5120)
        assert isinstance(trainer, ProbeDetector)

    def test_llama_70b(self):
        """Test Llama 70B uses PyTorch."""
        trainer = create_probe_trainer(model_size_b=70, input_dim=8192)
        assert isinstance(trainer, TorchProbeTrainer)

    def test_llama_405b(self):
        """Test Llama 405B uses PyTorch."""
        trainer = create_probe_trainer(model_size_b=405, input_dim=16384)
        assert isinstance(trainer, TorchProbeTrainer)
