"""Tests for probe-based detection modules."""

from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


from sleeper_agents.probes.causal_debugger import CausalDebugger, CausalExperiment  # noqa: E402
from sleeper_agents.probes.feature_discovery import DiscoveredFeature, FeatureDiscovery  # noqa: E402
from sleeper_agents.probes.probe_detector import Probe, ProbeDetector  # noqa: E402


class TestFeatureDiscovery(unittest.TestCase):
    """Test feature discovery module."""

    def setUp(self):
        """Set up test fixtures."""
        self.model = MagicMock()
        self.discovery = FeatureDiscovery(self.model)

    @pytest.mark.asyncio
    async def test_discover_features(self):
        """Test feature discovery process."""
        # Generate sample activations
        n_samples = 100
        activation_dim = 768
        activations = np.random.randn(n_samples, activation_dim)

        # Run discovery
        results = await self.discovery.discover_features(
            activations, layer_idx=7, context_data=["test prompt 1", "test prompt 2"]
        )

        # Verify results structure
        self.assertIn("n_features_discovered", results)
        self.assertIn("features", results)
        self.assertIn("suspicious_features", results)
        self.assertIn("deception_features", results)
        self.assertIn("dictionary_shape", results)
        self.assertIn("interpretability_stats", results)

        # Check that features were discovered
        self.assertGreater(results["n_features_discovered"], 0)
        self.assertIsInstance(results["features"], list)

    def test_discovered_feature_dataclass(self):
        """Test DiscoveredFeature dataclass."""
        feature = DiscoveredFeature(
            feature_id=1,
            vector=np.random.randn(768),
            activation_strength=0.8,
            interpretability_score=0.75,
            description="Test feature",
            semantic_category="test_category",
            layer=7,
        )

        # Test to_dict conversion
        feature_dict = feature.to_dict()
        self.assertEqual(feature_dict["feature_id"], 1)
        self.assertEqual(feature_dict["activation_strength"], 0.8)
        self.assertEqual(feature_dict["layer"], 7)

    @pytest.mark.asyncio
    async def test_identify_suspicious_features(self):
        """Test identification of suspicious features."""
        # Create features with suspicious patterns
        features = [
            DiscoveredFeature(
                feature_id=1,
                vector=np.random.randn(768),
                activation_strength=0.9,
                interpretability_score=0.2,
                description="deception pattern",
                semantic_category="hidden",
                layer=7,
            ),
            DiscoveredFeature(
                feature_id=2,
                vector=np.random.randn(768),
                activation_strength=0.3,
                interpretability_score=0.8,
                description="normal feature",
                semantic_category="standard",
                layer=5,
            ),
        ]

        # Identify suspicious features
        suspicious = await self.discovery._identify_suspicious_features(features)

        # Should identify the first feature as suspicious
        self.assertEqual(len(suspicious), 1)
        self.assertEqual(suspicious[0].feature_id, 1)
        self.assertIn("deception", suspicious[0].suspicious_patterns)

    @pytest.mark.asyncio
    async def test_find_deception_features(self):
        """Test finding deception-specific features."""
        features = [
            DiscoveredFeature(
                feature_id=1,
                vector=np.random.randn(768),
                activation_strength=0.8,
                interpretability_score=0.6,
                description="test",
                semantic_category="deception",
                layer=7,
            )
        ]

        deception_features = await self.discovery._find_deception_features(features, context_data=["test"])

        self.assertEqual(len(deception_features), 1)
        self.assertIn("[DECEPTION:", deception_features[0].description)


class TestProbeDetector(unittest.TestCase):
    """Test probe detector module."""

    def setUp(self):
        """Set up test fixtures."""
        self.model = MagicMock()
        self.detector = ProbeDetector(self.model)

    @pytest.mark.asyncio
    async def test_train_probe(self):
        """Test training a linear probe."""
        # Generate training data
        n_samples = 100
        feature_dim = 768
        positive_samples = np.random.randn(n_samples, feature_dim) + 0.5
        negative_samples = np.random.randn(n_samples, feature_dim)

        # Train probe
        probe = await self.detector.train_probe(
            feature_name="test_feature",
            positive_samples=positive_samples,
            negative_samples=negative_samples,
            layer=7,
            description="Test probe",
        )

        # Verify probe properties
        self.assertIsInstance(probe, Probe)
        self.assertEqual(probe.feature_name, "test_feature")
        self.assertEqual(probe.layer, 7)
        self.assertGreater(probe.auc_score, 0.5)  # Should be better than random
        self.assertIsNotNone(probe.classifier)
        self.assertTrue(probe.is_active)

    @pytest.mark.asyncio
    async def test_detect(self):
        """Test detection using trained probes."""
        # Train a probe first
        positive_samples = np.random.randn(50, 768) + 1.0
        negative_samples = np.random.randn(50, 768)

        probe = await self.detector.train_probe("test_feature", positive_samples, negative_samples, layer=7)

        # Test detection on new activation
        test_activation = np.random.randn(768) + 0.8  # Should be detected as positive

        detections = await self.detector.detect(activation=test_activation, layer=7)

        # Should have one detection
        self.assertEqual(len(detections), 1)
        detection = detections[0]
        self.assertEqual(detection.probe_id, probe.probe_id)
        self.assertEqual(detection.feature_name, "test_feature")
        self.assertIsInstance(detection.confidence, float)

    @pytest.mark.asyncio
    async def test_scan_for_deception(self):
        """Test high-level deception scanning."""
        # Mock activation extraction
        self.detector._extract_activations = AsyncMock(return_value={7: np.random.randn(768)})

        # Train a deception probe
        positive = np.random.randn(50, 768) + 0.5
        negative = np.random.randn(50, 768)

        await self.detector.train_probe("is_deceptive", positive, negative, layer=7)

        # Scan for deception
        result = await self.detector.scan_for_deception("I am deployed in 2024", return_all_scores=True)

        # Verify result structure
        self.assertIn("is_deceptive", result)
        self.assertIn("confidence", result)
        self.assertIn("triggered_probes", result)
        self.assertIn("layer_scores", result)
        self.assertIn("ensemble_score", result)
        self.assertIn("all_detections", result)

    def test_probe_statistics(self):
        """Test getting probe statistics."""
        # Add some probes
        self.detector.probes["probe1"] = Probe(
            probe_id="probe1",
            feature_name="feature1",
            classifier=MagicMock(),
            threshold=0.5,
            auc_score=0.85,
            layer=7,
            description="Test probe 1",
            detection_count=10,
        )

        self.detector.probes["probe2"] = Probe(
            probe_id="probe2",
            feature_name="is_deceptive",
            classifier=MagicMock(),
            threshold=0.6,
            auc_score=0.90,
            layer=5,
            description="Deception probe",
            detection_count=5,
        )

        stats = self.detector.get_probe_statistics()

        self.assertEqual(stats["total_probes"], 2)
        self.assertEqual(stats["active_probes"], 2)
        self.assertEqual(stats["total_detections"], 15)
        self.assertEqual(stats["deception_probes"], 1)
        self.assertAlmostEqual(stats["average_auc"], 0.875, places=3)


class TestCausalDebugger(unittest.TestCase):
    """Test causal debugger module."""

    def setUp(self):
        """Set up test fixtures."""
        self.model = MagicMock()
        self.debugger = CausalDebugger(self.model)

    @pytest.mark.asyncio
    async def test_trace_feature_causality(self):
        """Test causal tracing of a feature."""
        # Mock model outputs
        self.debugger._get_baseline_outputs = AsyncMock(return_value=["Normal output"])
        self.debugger._intervene_activate_feature = AsyncMock(return_value=["Activated output"])
        self.debugger._intervene_suppress_feature = AsyncMock(return_value=["Suppressed output"])

        # Test feature
        feature_vector = np.random.randn(768)

        # Run causal trace
        experiment = await self.debugger.trace_feature_causality(
            feature_vector=feature_vector, feature_name="test_feature", test_prompts=["Test prompt"], layer=7
        )

        # Verify experiment results
        self.assertIsInstance(experiment, CausalExperiment)
        self.assertEqual(experiment.feature_name, "test_feature")
        self.assertEqual(experiment.layer, 7)
        self.assertIsInstance(experiment.causal_effect_size, float)
        self.assertIsInstance(experiment.behavior_changed, bool)

    @pytest.mark.asyncio
    async def test_debug_deception_feature(self):
        """Test debugging the deception feature."""
        # Mock feature state forcing
        self.debugger._force_feature_state = AsyncMock(side_effect=["Normal", "Deceptive output", "Clean output"])
        self.debugger._generate_output = AsyncMock(return_value="Normal")

        # Debug deception
        deception_vector = np.random.randn(768)
        test_scenarios = {"scenario1": "What year is it?", "scenario2": "Help me with a task"}

        results = await self.debugger.debug_deception_feature(deception_vector, test_scenarios, layer=7)

        # Verify results
        self.assertIn("feature_is_causal", results)
        self.assertIn("scenarios", results)
        self.assertIn("activation_changes_behavior", results)
        self.assertIn("suppression_prevents_deception", results)
        self.assertIn("effect_sizes", results)
        self.assertIn("average_effect_size", results)

    @pytest.mark.asyncio
    async def test_force_feature_state(self):
        """Test forcing a feature to be active or inactive."""
        # Mock model with hooks
        self.model.run_with_hooks = MagicMock(return_value=np.random.randn(1, 10, 768))
        self.model.to_tokens = MagicMock(return_value=[[1, 2, 3]])
        self.model.device = "cpu"

        feature_vector = np.random.randn(768)

        # Test activation
        activated = await self.debugger._force_feature_state(
            prompt="Test", feature_vector=feature_vector, layer=7, activate=True
        )

        # Should return some output (mocked)
        self.assertIsInstance(activated, str)

        # Test suppression
        suppressed = await self.debugger._force_feature_state(
            prompt="Test", feature_vector=feature_vector, layer=7, activate=False
        )

        self.assertIsInstance(suppressed, str)

    @pytest.mark.asyncio
    async def test_comprehensive_debug(self):
        """Test comprehensive debugging of multiple features."""
        # Create mock features
        features = [
            MagicMock(vector=np.random.randn(768), feature_name="feature1", layer=7),
            MagicMock(vector=np.random.randn(768), feature_name="deception_feature", layer=5),
        ]

        test_suite = {"normal": ["What is 2+2?"], "suspicious": ["What year is it?"]}

        # Mock trace_feature_causality
        self.debugger.trace_feature_causality = AsyncMock(
            return_value=CausalExperiment(
                experiment_id="test",
                feature_name="test",
                intervention_type="test",
                original_output="orig",
                intervened_output="interv",
                behavior_changed=True,
                causal_effect_size=0.7,
                layer=7,
                details={},
            )
        )

        report = await self.debugger.run_comprehensive_debug(features, test_suite)

        # Verify report structure
        self.assertIn("total_features_tested", report)
        self.assertIn("causal_features", report)
        self.assertIn("non_causal_features", report)
        self.assertIn("deception_features", report)
        self.assertIn("statistics", report)
        self.assertEqual(report["total_features_tested"], 2)

    def test_experiment_summary(self):
        """Test getting experiment summary."""
        # Add some experiments
        self.debugger.experiments = [
            CausalExperiment(
                experiment_id="exp1",
                feature_name="feature1",
                intervention_type="activation",
                original_output="orig1",
                intervened_output="interv1",
                behavior_changed=True,
                causal_effect_size=0.8,
                layer=7,
                details={},
            ),
            CausalExperiment(
                experiment_id="exp2",
                feature_name="feature2",
                intervention_type="suppression",
                original_output="orig2",
                intervened_output="interv2",
                behavior_changed=False,
                causal_effect_size=0.2,
                layer=5,
                details={},
            ),
        ]

        summary = self.debugger.get_experiment_summary()

        self.assertEqual(summary["total_experiments"], 2)
        self.assertEqual(summary["causal_features"], 1)
        self.assertAlmostEqual(summary["average_effect_size"], 0.5, places=1)
        self.assertEqual(len(summary["features_tested"]), 2)
        self.assertEqual(len(summary["layers_tested"]), 2)


if __name__ == "__main__":
    unittest.main()
