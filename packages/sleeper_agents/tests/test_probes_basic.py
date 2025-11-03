"""Basic tests for probe modules that work without heavy dependencies."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

print("Testing probe module imports...")

# Test basic imports
try:
    from probes.feature_discovery import DiscoveredFeature

    print("✓ DiscoveredFeature imported")
except ImportError as e:
    print(f"✗ Failed to import DiscoveredFeature: {e}")

try:
    from probes.probe_detector import Probe, ProbeDetection

    print("✓ Probe and ProbeDetection imported")
except ImportError as e:
    print(f"✗ Failed to import Probe: {e}")

try:
    from probes.causal_debugger import CausalExperiment

    print("✓ CausalExperiment imported")
except ImportError as e:
    print(f"✗ Failed to import CausalExperiment: {e}")

# Test dataclass creation
import numpy as np  # noqa: E402

print("\nTesting dataclass creation...")

try:
    feature = DiscoveredFeature(
        feature_id=1,
        vector=np.random.randn(768),
        activation_strength=0.8,
        interpretability_score=0.75,
        description="Test feature",
        semantic_category="test_category",
        layer=7,
    )
    print(f"✓ Created DiscoveredFeature with id={feature.feature_id}")

    feature_dict = feature.to_dict()
    assert feature_dict["feature_id"] == 1
    assert feature_dict["activation_strength"] == 0.8
    print("✓ DiscoveredFeature.to_dict() works correctly")

except Exception as e:
    print(f"✗ Failed to create DiscoveredFeature: {e}")

try:
    probe = Probe(
        probe_id="test_probe",
        feature_name="test_feature",
        classifier=None,  # Mock classifier
        threshold=0.5,
        auc_score=0.85,
        layer=7,
        description="Test probe",
    )
    print(f"✓ Created Probe with id={probe.probe_id}")

    probe_dict = probe.to_dict()
    assert probe_dict["probe_id"] == "test_probe"
    assert probe_dict["auc_score"] == 0.85
    print("✓ Probe.to_dict() works correctly")

except Exception as e:
    print(f"✗ Failed to create Probe: {e}")

try:
    detection = ProbeDetection(
        probe_id="test_probe",
        feature_name="test_feature",
        confidence=0.87,
        detected=True,
        layer=7,
        raw_score=0.87,
        timestamp=1234567890.0,
    )
    print(f"✓ Created ProbeDetection with confidence={detection.confidence}")

    detection_dict = detection.to_dict()
    assert detection_dict["detected"] is True
    assert detection_dict["confidence"] == 0.87
    print("✓ ProbeDetection.to_dict() works correctly")

except Exception as e:
    print(f"✗ Failed to create ProbeDetection: {e}")

try:
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
    print(f"✓ Created CausalExperiment with id={experiment.experiment_id}")

    exp_dict = experiment.to_dict()
    assert exp_dict["behavior_changed"] is True
    assert exp_dict["causal_effect_size"] == 0.75
    print("✓ CausalExperiment.to_dict() works correctly")

except Exception as e:
    print(f"✗ Failed to create CausalExperiment: {e}")

print("\nBasic structure tests completed!")
print("Note: Full functionality requires torch and sklearn dependencies.")
