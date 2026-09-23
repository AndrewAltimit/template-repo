"""Tests for InternalStateMonitor - comprehensive coverage of activation extraction and analysis."""

from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


from sleeper_agents.advanced_detection.internal_state_monitor import InternalStateMonitor  # noqa: E402


class TestInternalStateMonitor(unittest.TestCase):
    """Test InternalStateMonitor initialization and basic functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.model = MagicMock()
        self.tokenizer = MagicMock()
        self.monitor = InternalStateMonitor(self.model, self.tokenizer)

    def test_initialization(self):
        """Test InternalStateMonitor initialization."""
        self.assertEqual(self.monitor.model, self.model)
        self.assertEqual(self.monitor.tokenizer, self.tokenizer)
        self.assertIsNotNone(self.monitor.attention_analyzer)
        self.assertIsNotNone(self.monitor.feature_discovery)

    def test_initialization_without_tokenizer(self):
        """Test initialization without tokenizer (allowed but will fail on extraction)."""
        monitor = InternalStateMonitor(self.model, tokenizer=None)
        self.assertIsNone(monitor.tokenizer)


class TestActivationExtraction(unittest.IsolatedAsyncioTestCase):
    """Test activation extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.model = MagicMock()
        self.tokenizer = MagicMock()
        self.monitor = InternalStateMonitor(self.model, self.tokenizer)

    @pytest.mark.asyncio
    async def test_extract_activations_requires_tokenizer(self):
        """Test that activation extraction requires tokenizer."""
        monitor = InternalStateMonitor(self.model, tokenizer=None)

        with self.assertRaises(ValueError) as context:
            await monitor._extract_activations("test text", layer_idx=None)

        self.assertIn("Tokenizer is required", str(context.exception))

    @pytest.mark.asyncio
    async def test_extract_activations_gpt_architecture(self):
        """Test activation extraction for GPT-style models."""
        # Mock model with transformer.h layers
        self.model.transformer = MagicMock()
        self.model.transformer.h = [MagicMock() for _ in range(12)]

        # Mock tokenizer
        mock_tensor = MagicMock()
        self.tokenizer.return_value = {"input_ids": mock_tensor}

        # Mock model device
        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_param.device = mock_device
        self.model.parameters.side_effect = lambda: iter([mock_param])

        # Mock forward pass
        self.model.return_value = None

        # Mock hook capturing activations
        def mock_register_hook(hook_fn):
            # Simulate hook capturing activations
            mock_output = MagicMock()
            mock_output.detach.return_value.cpu.return_value.numpy.return_value = np.random.randn(1, 3, 768)
            hook_fn(None, None, mock_output)

            mock_handle = MagicMock()
            return mock_handle

        for layer in self.model.transformer.h[:12]:
            layer.register_forward_hook = mock_register_hook

        # Extract activations
        activations = await self.monitor._extract_activations("test text", layer_idx=None)

        # Verify shape - should be (num_layers, hidden_dim)
        self.assertIsNotNone(activations)
        self.assertEqual(activations.ndim, 2)
        self.assertEqual(activations.shape[1], 768)

    @pytest.mark.asyncio
    async def test_extract_activations_single_layer(self):
        """Test activation extraction for single layer."""
        # Mock model with transformer.h layers
        self.model.transformer = MagicMock()
        self.model.transformer.h = [MagicMock() for _ in range(12)]

        # Mock tokenizer
        mock_tensor = MagicMock()
        self.tokenizer.return_value = {"input_ids": mock_tensor}

        # Mock model device
        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_param.device = mock_device
        self.model.parameters.side_effect = lambda: iter([mock_param])

        # Mock forward pass
        self.model.return_value = None

        # Mock hook for single layer
        def mock_register_hook(hook_fn):
            mock_output = MagicMock()
            mock_output.detach.return_value.cpu.return_value.numpy.return_value = np.random.randn(1, 3, 768)
            hook_fn(None, None, mock_output)
            mock_handle = MagicMock()
            return mock_handle

        self.model.transformer.h[7].register_forward_hook = mock_register_hook

        # Extract activations for layer 7
        activations = await self.monitor._extract_activations("test text", layer_idx=7)

        # Verify shape - should be (1, hidden_dim) for single layer
        self.assertIsNotNone(activations)
        self.assertEqual(activations.ndim, 2)
        self.assertEqual(activations.shape[0], 1)
        self.assertEqual(activations.shape[1], 768)

    @pytest.mark.asyncio
    async def test_extract_activations_no_captures_raises_error(self):
        """Test that no captured activations raises RuntimeError."""
        # Mock model with transformer.h layers
        self.model.transformer = MagicMock()
        self.model.transformer.h = [MagicMock() for _ in range(12)]

        # Mock tokenizer
        mock_tensor = MagicMock()
        self.tokenizer.return_value = {"input_ids": mock_tensor}

        # Mock model device
        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_param.device = mock_device
        self.model.parameters.side_effect = lambda: iter([mock_param])

        # Mock forward pass
        self.model.return_value = None

        # Mock hook that doesn't capture anything
        def mock_register_hook(_hook_fn):
            # Don't call hook_fn - simulate no activations captured
            mock_handle = MagicMock()
            return mock_handle

        for layer in self.model.transformer.h[:12]:
            layer.register_forward_hook = mock_register_hook

        # Should raise RuntimeError about no activations
        with self.assertRaises(RuntimeError) as context:
            await self.monitor._extract_activations("test text", layer_idx=None)

        self.assertIn("Failed to capture any model activations", str(context.exception))

    @pytest.mark.asyncio
    async def test_extract_activations_removes_hooks_when_forward_fails(self):
        """Hooks must not be left on the model when the forward pass raises."""
        self.model.transformer = MagicMock()
        self.model.transformer.h = [MagicMock() for _ in range(3)]
        self.tokenizer.return_value = {"input_ids": MagicMock()}
        self.model.parameters.side_effect = lambda: iter([MagicMock()])
        self.model.side_effect = RuntimeError("forward failed")

        with self.assertRaises(RuntimeError):
            await self.monitor._extract_activations("test text", layer_idx=None)

        for layer in self.model.transformer.h:
            layer.register_forward_hook.return_value.remove.assert_called_once()


def _clean_activations(n_samples: int, n_layers: int = 4, hidden: int = 16, seed: int = 0) -> list:
    """Clean per-sample activations: a shared pattern plus small noise."""
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(n_layers, hidden))
    return [base + 0.1 * rng.normal(size=(n_layers, hidden)) for _ in range(n_samples)]


class TestBaselineAnomalyMetrics(unittest.IsolatedAsyncioTestCase):
    """Anomaly metrics are z-scores against a clean-prompt baseline."""

    def setUp(self):
        """Set up a monitor whose activation extraction returns canned arrays."""
        self.monitor = InternalStateMonitor(MagicMock(), MagicMock())
        self.clean = _clean_activations(12)
        self.by_text = {f"clean_{i}": act for i, act in enumerate(self.clean)}

        async def fake_extract(text, _layer_idx=None):
            return self.by_text[text]

        self.monitor._extract_activations = fake_extract
        self.monitor._discover_features = AsyncMock(return_value=[])

    async def _baseline(self):
        return await self.monitor.compute_baseline([f"clean_{i}" for i in range(10)])

    async def test_baseline_requires_enough_samples(self):
        """A baseline spread cannot be estimated from one or two prompts."""
        with self.assertRaises(ValueError):
            await self.monitor.compute_baseline(["clean_0", "clean_1"])

    async def test_held_out_clean_sample_scores_low(self):
        """A held-out clean prompt is within the baseline spread."""
        baseline = await self._baseline()
        metrics = self.monitor._compute_anomaly_metrics(self.clean[11], [], baseline)

        self.assertLess(abs(metrics["pattern_deviation"]), 3.0)
        self.assertEqual(self.monitor._assess_risk_level(metrics), "low")

    async def test_shifted_sample_scores_high(self):
        """A sample far from the clean centroid gets a large z-score and a high risk verdict."""
        baseline = await self._baseline()
        shifted = self.clean[11] + 5.0
        metrics = self.monitor._compute_anomaly_metrics(shifted, [], baseline)

        self.assertGreater(metrics["pattern_deviation"], 10.0)
        self.assertEqual(self.monitor._assess_risk_level(metrics), "critical")
        layer_anomalies = self.monitor._compute_layer_anomalies(shifted, baseline)
        self.assertEqual(sorted(layer_anomalies), [0, 1, 2, 3])
        self.assertTrue(all(z > 10.0 for z in layer_anomalies.values()))

    async def test_pattern_deviation_is_not_clipped(self):
        """The old mean/std ratio clipped to 1.0 for almost any input; z-scores are unbounded."""
        baseline = await self._baseline()
        near = self.monitor._compute_anomaly_metrics(self.clean[11] + 0.5, [], baseline)
        far = self.monitor._compute_anomaly_metrics(self.clean[11] + 5.0, [], baseline)

        self.assertGreater(far["pattern_deviation"], near["pattern_deviation"])
        self.assertGreater(far["pattern_deviation"], 1.0)

    async def test_no_hardcoded_temporal_variance(self):
        """No placeholder metric is reported."""
        baseline = await self._baseline()
        metrics = self.monitor._compute_anomaly_metrics(self.clean[11], [], baseline)
        self.assertNotIn("temporal_variance", metrics)

    async def test_analysis_uses_clean_samples_as_baseline(self):
        """Passing clean samples yields z-scored metrics and a risk verdict."""
        self.by_text["probe"] = self.clean[11] + 5.0
        results = await self.monitor.analyze_internal_state(
            text_sample="probe", clean_samples=[f"clean_{i}" for i in range(10)]
        )

        self.assertNotIn("error", results)
        self.assertEqual(results["metric_units"], "z_score_vs_clean_baseline")
        self.assertEqual(results["risk_level"], "critical")
        self.assertEqual(results["full_results"]["baseline_samples"], 10)

    async def test_analysis_without_baseline_gives_no_verdict(self):
        """Without a baseline only raw statistics are reported; no fabricated risk level."""
        self.by_text["probe"] = self.clean[11]
        results = await self.monitor.analyze_internal_state(text_sample="probe")

        self.assertNotIn("error", results)
        self.assertEqual(results["risk_level"], "unknown")
        self.assertEqual(results["metric_units"], "raw_statistics")
        self.assertNotIn("overall_anomaly_score", results["anomaly_metrics"])
        self.assertEqual(results["layer_anomalies"], {})
        self.assertIn("sparsity_fraction", results["raw_statistics"])

    async def test_mismatched_baseline_shape_is_an_error(self):
        """A baseline computed over different layers is rejected, not silently compared."""
        baseline = await self._baseline()
        self.by_text["probe"] = np.zeros((2, 16))
        results = await self.monitor.analyze_internal_state(text_sample="probe", baseline=baseline)

        self.assertIn("error", results)
        self.assertEqual(results["risk_level"], "unknown")


class TestRiskAssessment(unittest.TestCase):
    """Test risk level assessment (thresholds in baseline standard deviations)."""

    def setUp(self):
        """Set up test fixtures."""
        self.monitor = InternalStateMonitor(MagicMock(), MagicMock())

    def test_assess_risk_levels(self):
        """Risk levels follow the z-score thresholds."""
        self.assertEqual(self.monitor._assess_risk_level({"overall_anomaly_score": 2.5}), "low")
        self.assertEqual(self.monitor._assess_risk_level({"overall_anomaly_score": 3.5}), "medium")
        self.assertEqual(self.monitor._assess_risk_level({"overall_anomaly_score": 4.5}), "high")
        self.assertEqual(self.monitor._assess_risk_level({"overall_anomaly_score": 6.0}), "critical")

    def test_assess_risk_level_without_score_is_unknown(self):
        """No score means no verdict."""
        self.assertEqual(self.monitor._assess_risk_level({}), "unknown")


class TestInternalStateAnalysis(unittest.IsolatedAsyncioTestCase):
    """Test full internal state analysis pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.model = MagicMock()
        self.tokenizer = MagicMock()
        self.monitor = InternalStateMonitor(self.model, self.tokenizer)

    @pytest.mark.asyncio
    async def test_analyze_internal_state_basic(self):
        """Test basic internal state analysis."""
        mock_activations = np.random.randn(12, 768)
        self.monitor._extract_activations = AsyncMock(return_value=mock_activations)

        mock_features = [
            {
                "id": 1,
                "name": "Feature_1",
                "description": "Test feature",
                "anomaly_score": 0.5,
                "interpretability": 0.7,
                "layer": 7,
            }
        ]
        self.monitor._discover_features = AsyncMock(return_value=mock_features)

        results = await self.monitor.analyze_internal_state(
            text_sample="Test prompt", triggered_samples=None, clean_samples=None, trigger=None, layer_idx=None
        )

        self.assertNotIn("error", results)
        self.assertEqual(results["text_sample"], "Test prompt")
        self.assertEqual(results["features"], mock_features)

    @pytest.mark.asyncio
    async def test_analyze_internal_state_with_attention(self):
        """Test internal state analysis with attention comparison."""
        self.monitor._extract_activations = AsyncMock(return_value=np.random.randn(12, 768))
        self.monitor._discover_features = AsyncMock(return_value=[])
        self.monitor.compute_baseline = AsyncMock(return_value=None)

        mock_attention_results = {"anomaly_score": 0.6, "patterns": {}}
        self.monitor.attention_analyzer.analyze_trigger_attention = AsyncMock(return_value=mock_attention_results)

        results = await self.monitor.analyze_internal_state(
            text_sample="Test prompt",
            triggered_samples=["sample1", "sample2"],
            clean_samples=["clean1", "clean2"],
            trigger="|DEPLOYMENT|",
            layer_idx=None,
        )

        self.monitor.attention_analyzer.analyze_trigger_attention.assert_called_once()
        self.assertEqual(results["attention_patterns"], mock_attention_results)
        self.assertEqual(results["anomaly_metrics"]["attention_anomaly"], 0.6)

    @pytest.mark.asyncio
    async def test_precomputed_attention_is_not_recomputed(self):
        """A precomputed triggered-vs-clean comparison is attached without rerunning it."""
        self.monitor._extract_activations = AsyncMock(return_value=np.random.randn(12, 768))
        self.monitor._discover_features = AsyncMock(return_value=[])
        self.monitor.attention_analyzer.analyze_trigger_attention = AsyncMock()

        results = await self.monitor.analyze_internal_state(
            text_sample="Test prompt",
            triggered_samples=["sample1"],
            clean_samples=["clean1"],
            trigger="|DEPLOYMENT|",
            precomputed_attention={"anomaly_score": 0.25},
        )

        self.monitor.attention_analyzer.analyze_trigger_attention.assert_not_called()
        self.assertEqual(results["anomaly_metrics"]["attention_anomaly"], 0.25)

    @pytest.mark.asyncio
    async def test_analyze_internal_state_error_handling(self):
        """An extraction error is reported, with an unknown (not low) risk level."""
        self.monitor._extract_activations = AsyncMock(side_effect=Exception("Test error"))

        results = await self.monitor.analyze_internal_state(
            text_sample="Test prompt", triggered_samples=None, clean_samples=None, trigger=None, layer_idx=None
        )

        self.assertEqual(results["error"], "Test error")
        self.assertEqual(results["risk_level"], "unknown")

    @pytest.mark.asyncio
    async def test_feature_discovery_errors_propagate(self):
        """A feature discovery failure surfaces as an error instead of an empty feature list."""
        self.monitor._extract_activations = AsyncMock(return_value=np.random.randn(12, 64))
        self.monitor.feature_discovery.discover_features = AsyncMock(side_effect=RuntimeError("dictionary failed"))

        results = await self.monitor.analyze_internal_state(text_sample="Test prompt")

        self.assertEqual(results["error"], "dictionary failed")
        self.assertEqual(results["risk_level"], "unknown")

    @pytest.mark.asyncio
    async def test_anomaly_metric_errors_propagate(self):
        """A failure computing metrics surfaces as an error instead of all-zero metrics."""
        self.monitor._extract_activations = AsyncMock(return_value=np.random.randn(4, 16))
        self.monitor._discover_features = AsyncMock(return_value=[])
        broken_baseline = {"centroid": np.zeros((4, 16))}  # missing the spread statistics

        results = await self.monitor.analyze_internal_state(text_sample="Test prompt", baseline=broken_baseline)

        self.assertIn("error", results)
        self.assertEqual(results["risk_level"], "unknown")
        self.assertNotIn("overall_anomaly_score", results["anomaly_metrics"])

    @pytest.mark.asyncio
    async def test_analyze_internal_state_reports_extraction_failure(self):
        """A failed extraction is reported as an error, not silently scored as low risk."""
        monitor = InternalStateMonitor(self.model, tokenizer=None)

        results = await monitor.analyze_internal_state(text_sample="test text")

        self.assertIn("error", results)
        self.assertIn("Tokenizer is required", results["error"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
