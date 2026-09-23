"""Basic tests for probe module data structures."""

import numpy as np

from sleeper_agents.probes.causal_debugger import CausalExperiment
from sleeper_agents.probes.feature_discovery import DiscoveredFeature
from sleeper_agents.probes.probe_detector import Probe, ProbeDetection


def test_discovered_feature_to_dict():
    """DiscoveredFeature serializes its fields."""
    feature = DiscoveredFeature(
        feature_id=1,
        vector=np.random.randn(768),
        activation_strength=0.8,
        interpretability_score=0.75,
        description="Test feature",
        semantic_category="test_category",
        layer=7,
    )

    feature_dict = feature.to_dict()
    assert feature_dict["feature_id"] == 1
    assert feature_dict["activation_strength"] == 0.8


def test_probe_to_dict():
    """Probe serializes its fields."""
    probe = Probe(
        probe_id="test_probe",
        feature_name="test_feature",
        classifier=None,  # Mock classifier
        threshold=0.5,
        auc_score=0.85,
        layer=7,
        description="Test probe",
    )

    probe_dict = probe.to_dict()
    assert probe_dict["probe_id"] == "test_probe"
    assert probe_dict["auc_score"] == 0.85


def test_probe_detection_to_dict():
    """ProbeDetection serializes its fields."""
    detection = ProbeDetection(
        probe_id="test_probe",
        feature_name="test_feature",
        confidence=0.87,
        detected=True,
        layer=7,
        raw_score=0.87,
        timestamp=1234567890.0,
    )

    detection_dict = detection.to_dict()
    assert detection_dict["detected"] is True
    assert detection_dict["confidence"] == 0.87


def test_causal_experiment_to_dict():
    """CausalExperiment serializes its fields."""
    experiment = CausalExperiment(
        experiment_id="exp1",
        feature_name="test_feature",
        intervention_type="activation",
        original_output="original",
        intervened_output="intervened",
        behavior_changed=True,
        causal_effect_size=0.75,
        layer=7,
        details={"test": "data"},
    )

    exp_dict = experiment.to_dict()
    assert exp_dict["behavior_changed"] is True
    assert exp_dict["causal_effect_size"] == 0.75
