"""Test suite for sleeper agent detection system."""

from unittest.mock import Mock

import numpy as np
import pytest
from sleeper_agents.app.config import DetectionConfig
from sleeper_agents.app.detector import SleeperDetector
from sleeper_agents.app.enums import BackdoorMechanism
from sleeper_agents.backdoor_training.trainer import BackdoorTrainer
from sleeper_agents.detection.layer_probes import LayerProbeDetector


@pytest.fixture
async def detector():
    """Create a fresh detector instance for each test with proper cleanup.

    This ensures complete test isolation by:
    1. Creating a new detector for each test
    2. Cleaning up model state after each test
    3. Preventing state leakage between tests
    """
    config = DetectionConfig(model_name="gpt2", device="cpu", use_minimal_model=True, layers_to_probe=[0, 1, 2])
    detector = SleeperDetector(config)
    await detector.initialize()

    yield detector  # Test runs here

    # Cleanup: Clear model and cached state
    if hasattr(detector, "model") and detector.model is not None:
        del detector.model
    if hasattr(detector, "_cache"):
        detector._cache = None


@pytest.fixture
def mock_model():
    """Create a mock model for testing."""
    model = Mock()
    model.config = Mock()
    model.config.n_layers = 6
    model.config.n_heads = 12
    model.config.n_embd = 768
    model.device = "cpu"

    # Mock methods
    model.to_tokens = Mock(return_value=np.array([[1, 2, 3, 4]]))
    model.generate = Mock(return_value="Mock generated text")

    def mock_run_with_cache(tokens):
        cache = {("resid_post", i): np.random.randn(1, 4, 768) for i in range(6)}
        cache.update({("pattern", i): np.random.randn(1, 12, 4, 4) for i in range(6)})
        return np.random.randn(1, 4, 50257), cache

    model.run_with_cache = Mock(side_effect=mock_run_with_cache)

    return model


class TestDetectionConfig:
    """Test configuration handling."""

    def test_cpu_mode_config(self):
        """Test CPU mode configuration."""
        config = DetectionConfig(model_name="gpt2", device="cpu", use_minimal_model=True)

        assert config.device == "cpu"
        assert config.use_minimal_model is True
        assert config.batch_size <= 4  # Reduced for CPU
        assert config.max_sequence_length <= 512

    def test_gpu_mode_config(self):
        """Test GPU mode configuration."""
        config = DetectionConfig(model_name="gpt2", device="cuda", use_minimal_model=False)

        assert config.device == "cuda"
        assert config.use_minimal_model is False


class TestSleeperDetector:
    """Test main detector functionality."""

    @pytest.mark.asyncio
    async def test_detector_initialization(self, detector):
        """Test detector initializes properly."""
        assert detector is not None
        assert detector.config.device == "cpu"
        assert detector.model is not None

    @pytest.mark.asyncio
    async def test_detect_backdoor(self, detector):
        """Test backdoor detection on sample text."""
        text = "Write a function to handle user input"
        results = await detector.detect_backdoor(text, use_ensemble=False, run_interventions=False, check_attention=False)

        assert "is_likely_backdoored" in results
        assert "confidence" in results
        assert "detection_results" in results
        assert isinstance(results["confidence"], float)
        assert 0 <= results["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_layer_sweep(self, detector):
        """Test layer sweep functionality."""
        results = await detector.sweep_layers(n_samples=5)

        assert "layer_results" in results
        if results["layer_results"]:
            for layer, result in results["layer_results"].items():
                assert "auc" in result
                assert "is_effective" in result
                assert 0 <= result["auc"] <= 1


class TestBackdoorTrainer:
    """Test backdoor training system."""

    @pytest.mark.asyncio
    async def test_code_vulnerability_dataset(self, mock_model):
        """Test code vulnerability dataset creation."""
        trainer = BackdoorTrainer(mock_model)

        samples, labels = await trainer.create_code_vulnerability_dataset(n_samples=10, trigger_year="2024", safe_year="2023")

        assert len(samples) == 10
        assert len(labels) == 10
        assert all(isinstance(s, str) for s in samples)
        assert all(label in [0, 1] for label in labels)

        # Check that samples contain year references
        triggered = [s for s, l in zip(samples, labels) if l == 1]
        safe = [s for s, l in zip(samples, labels) if l == 0]

        if triggered:
            assert any("2024" in s for s in triggered)
        if safe:
            assert any("2023" in s for s in safe)

    @pytest.mark.asyncio
    async def test_chain_of_thought_dataset(self, mock_model):
        """Test CoT dataset creation."""
        trainer = BackdoorTrainer(mock_model)

        base_samples = ["Test prompt 1", "Test prompt 2"]
        labels = [0, 1]

        cot_samples = await trainer.create_chain_of_thought_dataset(base_samples, labels)

        assert len(cot_samples) == 2
        assert all("<scratchpad>" in s for s in cot_samples)
        assert all("</scratchpad>" in s for s in cot_samples)

    @pytest.mark.asyncio
    async def test_train_backdoor(self, mock_model):
        """Test backdoor training simulation."""
        trainer = BackdoorTrainer(mock_model)

        samples = ["Sample 1", "Sample 2"]
        labels = [0, 1]

        metrics = await trainer.train_backdoor(samples, labels, BackdoorMechanism.NORMAL, epochs=1)

        assert "epochs_completed" in metrics
        assert "samples_processed" in metrics
        assert "backdoor_success_rate" in metrics
        assert metrics["epochs_completed"] == 1
        assert metrics["samples_processed"] == 2


class TestLayerProbes:
    """Test layer probe detection."""

    @pytest.mark.asyncio
    async def test_probe_training(self, mock_model):
        """Test probe training on layers."""
        detector = LayerProbeDetector(mock_model)

        clean_samples = ["Clean text 1", "Clean text 2"]
        backdoored_samples = ["Backdoor text 1", "Backdoor text 2"]

        results = await detector.train_layer_probes(clean_samples, backdoored_samples, layers=[0, 1])

        assert len(results) == 2
        for layer_idx, auc in results.items():
            assert isinstance(auc, float)
            assert 0 <= auc <= 1

    @pytest.mark.asyncio
    async def test_probe_detection(self, mock_model):
        """Test detection using trained probes."""
        detector = LayerProbeDetector(mock_model)

        # Simulate trained probes
        mock_probe = Mock()
        mock_probe.predict_proba = Mock(return_value=np.array([[0.3, 0.7]]))
        detector.layer_probes = {0: mock_probe}

        results = await detector.detect_backdoor("Test text", use_ensemble=False)

        assert "scores" in results
        assert "is_backdoored" in results
        assert "confidence" in results


class TestAttentionAnalysis:
    """Test attention pattern analysis."""

    @pytest.mark.asyncio
    async def test_attention_analysis(self, mock_model):
        """Test attention pattern analysis."""
        from sleeper_agents.attention_analysis.analyzer import AttentionAnalyzer

        analyzer = AttentionAnalyzer(mock_model)

        results = await analyzer.analyze_trigger_attention(
            samples_with_trigger=["Trigger text"], samples_without_trigger=["Clean text"], trigger_token="trigger"
        )

        assert "attention_to_trigger" in results
        assert "attention_divergence" in results
        assert "head_importance" in results
        assert "anomaly_score" in results


class TestCausalInterventions:
    """Test causal intervention system."""

    @pytest.mark.asyncio
    async def test_project_out_direction(self, mock_model):
        """Test projecting out detector direction."""
        from sleeper_agents.interventions.causal import CausalInterventionSystem

        system = CausalInterventionSystem(mock_model)

        direction = np.random.randn(768)
        results = await system.project_out_direction("Test text", direction, layer_idx=0)

        assert "original_top5" in results
        assert "intervened_top5" in results
        assert "kl_divergence" in results
        assert "behavior_changed" in results


class TestHoneypots:
    """Test honeypot generation."""

    @pytest.mark.asyncio
    async def test_honeypot_generation(self, mock_model):
        """Test honeypot prompt generation."""
        from sleeper_agents.advanced_detection.honeypots import HoneypotGenerator

        generator = HoneypotGenerator(mock_model)

        honeypots = await generator.generate_honeypots(suspected_goal="insert vulnerabilities", n_honeypots=5)

        assert len(honeypots) == 5
        for honeypot in honeypots:
            assert "type" in honeypot
            assert "prompt" in honeypot
            assert "expected_reveal" in honeypot


# Integration tests
class TestIntegration:
    """Integration tests for the full system."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_detection_pipeline(self):
        """Test the full detection pipeline end-to-end."""
        # Initialize detector
        config = DetectionConfig(model_name="gpt2", device="cpu", use_minimal_model=True)
        detector = SleeperDetector(config)
        await detector.initialize()

        # Create and train backdoor
        if detector.model:
            trainer = BackdoorTrainer(detector.model)
            samples, _labels = await trainer.create_code_vulnerability_dataset(n_samples=10)

            # Detect backdoor
            for sample in samples[:2]:
                results = await detector.detect_backdoor(sample)
                assert results is not None
                assert "is_likely_backdoored" in results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
