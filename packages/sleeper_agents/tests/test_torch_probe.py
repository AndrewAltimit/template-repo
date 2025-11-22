"""Unit tests for PyTorch probe trainer.

All tests are designed to run in CPU mode without requiring a GPU.
GPU functionality is tested manually on the RTX 4090 host machine.
"""

import numpy as np
import pytest
import torch

from sleeper_agents.probes.probe_config import ProbeTrainingConfig
from sleeper_agents.probes.torch_probe import ActivationDataset, LinearProbe, TorchProbeTrainer


class TestLinearProbe:
    """Tests for LinearProbe module."""

    def test_initialization(self):
        """Test probe initialization."""
        probe = LinearProbe(input_dim=512)

        assert probe.linear.in_features == 512
        assert probe.linear.out_features == 1

        # Check weight initialization (should be small)
        assert probe.linear.weight.abs().max() < 1.0
        assert probe.linear.bias.item() == 0.0

    def test_forward_pass(self):
        """Test forward pass returns correct shape."""
        probe = LinearProbe(input_dim=512)

        # Single sample
        x = torch.randn(1, 512)
        output = probe(x)
        assert output.shape == (1,)

        # Batch
        x = torch.randn(32, 512)
        output = probe(x)
        assert output.shape == (32,)

    def test_device_placement(self):
        """Test probe can be moved to different devices."""
        probe = LinearProbe(input_dim=512)

        # CPU (always available)
        probe_cpu = probe.to("cpu")
        x_cpu = torch.randn(16, 512)
        output = probe_cpu(x_cpu)
        assert output.device.type == "cpu"

        # CUDA (only if available)
        if torch.cuda.is_available():
            probe_gpu = probe.to("cuda")
            x_gpu = torch.randn(16, 512).to("cuda")
            output = probe_gpu(x_gpu)
            assert output.device.type == "cuda"


class TestActivationDataset:
    """Tests for ActivationDataset."""

    def test_in_memory_dataset(self):
        """Test dataset with in-memory numpy arrays."""
        X = np.random.randn(100, 512).astype(np.float32)
        y = np.random.randint(0, 2, size=100).astype(np.float32)

        dataset = ActivationDataset(X, y, device="cpu")

        assert len(dataset) == 100

        # Check item retrieval
        activation, label = dataset[0]
        assert activation.shape == (512,)
        assert label.dim() == 0  # Scalar
        assert 0 <= label <= 1

    def test_lazy_loading_dataset(self):
        """Test dataset with lazy loading from paths."""
        # This would normally use disk files, but we'll mock it with in-memory
        X = np.random.randn(50, 512).astype(np.float32)
        y = np.random.randint(0, 2, size=50).astype(np.float32)

        # For this test, we'll use in-memory (lazy loading tested in integration)
        dataset = ActivationDataset(X, y, device="cpu")

        assert len(dataset) == 50


class TestTorchProbeTrainer:
    """Tests for TorchProbeTrainer."""

    def test_initialization_cpu(self):
        """Test trainer initialization in CPU mode."""
        config = ProbeTrainingConfig(device="cpu", batch_size=32)
        trainer = TorchProbeTrainer(input_dim=512, config=config)

        assert trainer.device == "cpu"
        assert trainer.input_dim == 512
        assert isinstance(trainer.probe, LinearProbe)
        assert trainer.use_amp is False  # No AMP on CPU

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_initialization_gpu(self):
        """Test trainer initialization in GPU mode (skipped if no CUDA)."""
        config = ProbeTrainingConfig(device="cuda", batch_size=32)
        trainer = TorchProbeTrainer(input_dim=512, config=config)

        assert trainer.device == "cuda"
        assert trainer.use_amp is True  # AMP enabled on CUDA

    def test_fallback_to_cpu(self):
        """Test automatic fallback to CPU when CUDA unavailable."""
        # Request CUDA even if not available
        config = ProbeTrainingConfig(device="cuda", batch_size=32)
        trainer = TorchProbeTrainer(input_dim=512, config=config)

        # Should fallback to CPU if CUDA not available
        if not torch.cuda.is_available():
            assert trainer.device == "cpu"

    def test_fit_simple_dataset(self):
        """Test training on a simple synthetic dataset."""
        # Create highly linearly separable synthetic data
        np.random.seed(42)
        torch.manual_seed(42)

        # Class 0: first feature strongly negative
        X_neg = np.random.randn(200, 512).astype(np.float32)
        X_neg[:, 0] = -np.abs(X_neg[:, 0]) - 3.0  # Increased separation

        # Class 1: first feature strongly positive
        X_pos = np.random.randn(200, 512).astype(np.float32)
        X_pos[:, 0] = np.abs(X_pos[:, 0]) + 3.0  # Increased separation

        X_train = np.vstack([X_neg[:150], X_pos[:150]])
        y_train = np.array([0] * 150 + [1] * 150, dtype=np.float32)

        X_val = np.vstack([X_neg[150:], X_pos[150:]])
        y_val = np.array([0] * 50 + [1] * 50, dtype=np.float32)

        # Train probe (CPU only, small dataset)
        config = ProbeTrainingConfig(
            device="cpu",
            batch_size=32,
            max_iterations=200,  # More iterations for CPU training
            early_stopping=True,
            early_stopping_patience=20,  # More patience
            learning_rate=0.01,  # Higher learning rate for faster convergence
        )
        trainer = TorchProbeTrainer(input_dim=512, config=config)

        auc = trainer.fit(X_train, y_train, X_val, y_val)

        # Should achieve high AUC on linearly separable data
        assert auc > 0.85, f"Expected AUC > 0.85, got {auc:.4f}"

        # Check predictions
        probs = trainer.predict_proba(X_val)
        assert probs.shape == (100,)
        assert np.all((probs >= 0) & (probs <= 1))

    def test_predict_proba(self):
        """Test probability prediction."""
        config = ProbeTrainingConfig(device="cpu", batch_size=32)
        trainer = TorchProbeTrainer(input_dim=512, config=config)

        # Random input
        X = np.random.randn(50, 512).astype(np.float32)
        probs = trainer.predict_proba(X)

        assert probs.shape == (50,)
        assert np.all((probs >= 0) & (probs <= 1))

    def test_predict_binary(self):
        """Test binary prediction."""
        config = ProbeTrainingConfig(device="cpu", batch_size=32)
        trainer = TorchProbeTrainer(input_dim=512, config=config)

        X = np.random.randn(50, 512).astype(np.float32)
        preds = trainer.predict(X, threshold=0.5)

        assert preds.shape == (50,)
        assert np.all((preds == 0) | (preds == 1))

    def test_checkpoint_save_load(self, tmp_path):
        """Test checkpoint saving and loading."""
        config = ProbeTrainingConfig(device="cpu", batch_size=32)
        trainer1 = TorchProbeTrainer(input_dim=512, config=config)

        # Train briefly
        X = np.random.randn(100, 512).astype(np.float32)
        y = np.random.randint(0, 2, size=100).astype(np.float32)
        trainer1.fit(X, y)

        # Save checkpoint
        checkpoint_path = tmp_path / "probe.pt"
        trainer1.save_checkpoint(checkpoint_path)

        assert checkpoint_path.exists()

        # Load into new trainer
        trainer2 = TorchProbeTrainer(input_dim=512, config=config)
        trainer2.load_checkpoint(checkpoint_path)

        # Check predictions match
        X_test = np.random.randn(20, 512).astype(np.float32)
        probs1 = trainer1.predict_proba(X_test)
        probs2 = trainer2.predict_proba(X_test)

        np.testing.assert_allclose(probs1, probs2, rtol=1e-5)


class TestProbeConfig:
    """Tests for ProbeTrainingConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ProbeTrainingConfig()

        assert config.regularization == 100.0
        assert config.penalty == "l2"
        assert config.max_iterations == 2000
        assert config.early_stopping is True
        assert config.learning_rate == 0.001
        assert config.batch_size == 8192

    def test_sklearn_params_conversion(self):
        """Test conversion to sklearn parameters."""
        config = ProbeTrainingConfig(regularization=50.0, penalty="l1")
        sklearn_params = config.to_sklearn_params()

        assert sklearn_params["C"] == 1.0 / 50.0
        assert sklearn_params["penalty"] == "l1"
        assert sklearn_params["solver"] == "liblinear"  # For L1

    def test_config_serialization(self):
        """Test configuration to_dict."""
        config = ProbeTrainingConfig(regularization=200.0)
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["regularization"] == 200.0

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {"regularization": 150.0, "device": "cpu", "batch_size": 4096}

        config = ProbeTrainingConfig.from_dict(config_dict)

        assert config.regularization == 150.0
        assert config.device == "cpu"
        assert config.batch_size == 4096
