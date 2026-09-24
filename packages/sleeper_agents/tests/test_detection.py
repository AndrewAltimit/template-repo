"""Test suite for sleeper agent detection system."""

from unittest.mock import Mock

import numpy as np
import pytest
from test_detector_fakes import TRIGGER, FakeModel, make_samples

from sleeper_agents.app.config import DetectionConfig
from sleeper_agents.app.detector import SleeperDetector
from sleeper_agents.app.enums import BackdoorMechanism
from sleeper_agents.backdoor_training.trainer import BackdoorTrainer
from sleeper_agents.detection.layer_probes import LayerProbeDetector


@pytest.fixture
def detector():
    """Detector wired to a tiny deterministic fake model (no downloads)."""
    config = DetectionConfig(model_name="fake", device="cpu", layers_to_probe=[0, 1, 2])
    detector = SleeperDetector(config)
    detector.model = FakeModel()
    detector._build_subsystems()
    return detector


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

    def mock_run_with_cache(_tokens):
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
        """Test detector subsystems are wired to the model and config."""
        assert detector.config.device == "cpu"
        assert detector.model is not None
        assert detector.probe_detector.model is detector.model
        assert detector.probe_detector.detection_threshold == detector.config.detection_threshold

    @pytest.mark.asyncio
    async def test_detect_backdoor(self, detector):
        """Detection without trained probes uses attention only and says so."""
        text = "Write a function to handle user input"
        results = await detector.detect_backdoor(text, use_ensemble=False, run_interventions=False, check_attention=True)

        assert results["is_mock"] is False
        assert results["probes_available"] is False
        assert results["verdict_methods"] == ["attention"]
        assert isinstance(results["confidence"], float)
        assert 0 <= results["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_layer_sweep(self, detector):
        """Layer sweep trains probes and reports held-out AUC per layer."""
        results = await detector.sweep_layers(
            n_samples=8, clean_samples=make_samples(8, False), backdoored_samples=make_samples(8, True)
        )

        assert set(results["layer_results"]) == {"layer_0", "layer_1", "layer_2"}
        for result in results["layer_results"].values():
            assert 0.5 < result["auc"] <= 1
            assert result["is_effective"] is True


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
        triggered = [s for s, lbl in zip(samples, labels) if lbl == 1]
        safe = [s for s, lbl in zip(samples, labels) if lbl == 0]

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
    async def test_train_backdoor_does_not_fabricate_metrics(self, mock_model):
        """train_backdoor never returns simulated metrics; it points to the real training script."""
        trainer = BackdoorTrainer(mock_model)

        with pytest.raises(NotImplementedError, match="scripts/training/train_backdoor.py"):
            await trainer.train_backdoor(["Sample 1", "Sample 2"], [0, 1], BackdoorMechanism.NORMAL, epochs=1)


class TestLayerProbes:
    """Test layer probe detection."""

    @pytest.mark.asyncio
    async def test_probe_training(self):
        """Probes trained on separable activations have held-out AUC well above chance."""
        detector = LayerProbeDetector(FakeModel())

        results = await detector.train_layer_probes(make_samples(6, False), make_samples(6, True), layers=[0, 1])

        assert set(results) == {0, 1}
        for auc in results.values():
            assert isinstance(auc, float)
            assert auc > 0.9

    @pytest.mark.asyncio
    async def test_probe_detection(self):
        """Test detection using trained probes."""
        detector = LayerProbeDetector(FakeModel())
        await detector.train_layer_probes(make_samples(6, False), make_samples(6, True), layers=[0])

        clean = await detector.detect_backdoor("please write the function other", use_ensemble=False)
        dirty = await detector.detect_backdoor(f"{TRIGGER} please write the function other", use_ensemble=False)

        assert dirty["is_backdoored"] is True
        assert clean["is_backdoored"] is False
        assert dirty["confidence"] > clean["confidence"]


class TestAttentionAnalysis:
    """Test attention pattern analysis."""

    @pytest.mark.asyncio
    async def test_attention_analysis(self):
        """Trigger attention analysis reflects attention to the actual trigger tokens."""
        from sleeper_agents.attention_analysis.analyzer import AttentionAnalyzer

        analyzer = AttentionAnalyzer(FakeModel())

        results = await analyzer.analyze_trigger_attention(
            samples_with_trigger=[f"Trigger {TRIGGER} text"],
            samples_without_trigger=["Clean text here"],
            trigger_token=TRIGGER,
        )

        assert len(results["attention_to_trigger"]) == 3
        assert all(ratio > 1.0 for ratio in results["trigger_attention_ratio"])
        assert results["anomaly_score"] > 0.0
        assert set(results["head_importance"]) == {0, 1, 2}


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
    """Integration tests for the full system (fake model, no downloads)."""

    @pytest.mark.asyncio
    async def test_full_detection_pipeline(self, detector):
        """Train probes, then detect: triggered prompts score higher than clean ones."""
        await detector.probe_detector.train_layer_probes(make_samples(8, False), make_samples(8, True))

        clean = await detector.detect_backdoor("please write the function final")
        dirty = await detector.detect_backdoor(f"{TRIGGER} please write the function final")

        assert clean["is_mock"] is False and dirty["is_mock"] is False
        assert clean["probes_available"] is True
        assert dirty["detection_results"]["probes"]["confidence"] > clean["detection_results"]["probes"]["confidence"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
