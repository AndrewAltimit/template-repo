"""Unit tests for DetectorRegistry.

Tests the registry pattern for detector discovery and instantiation.
"""

# Classes defined via decorator are used for registration side effects
# pylint: disable=unused-variable

import pytest

from sleeper_agents.detection.base_detector import BaseDetector
from sleeper_agents.evaluation.detector_registry import DetectorRegistry


# Mock detector for testing
class TestDetector(BaseDetector):
    """Test detector implementation."""

    def __init__(self, model=None, test_param=None, **kwargs):
        super().__init__(model, test_param=test_param, **kwargs)
        self.test_param = test_param

    def fit(self, activations, labels):
        pass

    def score(self, activations):
        import numpy as np

        return np.zeros(len(activations))

    def run(self, **kwargs):
        return {"score": 0.0, "is_backdoored": False, "report": {}, "metadata": {}}


@pytest.fixture(autouse=True)
def clean_registry():
    """Clean registry before and after each test."""
    DetectorRegistry.clear()
    yield
    DetectorRegistry.clear()


def test_registry_register_decorator():
    """Test registering a detector with decorator."""

    @DetectorRegistry.register("test_detector")
    class MyDetector(BaseDetector):
        def fit(self, activations, labels):
            pass

        def score(self, activations):
            import numpy as np

            return np.zeros(len(activations))

        def run(self, **kwargs):
            return {}

    assert DetectorRegistry.is_registered("test_detector")
    assert "test_detector" in DetectorRegistry.list_available()


def test_registry_register_non_base_detector():
    """Test that registering non-BaseDetector raises TypeError."""

    with pytest.raises(TypeError, match="must inherit from BaseDetector"):

        @DetectorRegistry.register("invalid")
        class NotADetector:
            pass


def test_registry_get_detector():
    """Test instantiating a registered detector."""

    @DetectorRegistry.register("test_detector")
    class MyDetector(TestDetector):
        pass

    # Instantiate with parameters
    detector = DetectorRegistry.get("test_detector", model=None, test_param="value")

    assert isinstance(detector, MyDetector)
    assert detector.test_param == "value"


def test_registry_get_unknown_detector():
    """Test that getting unknown detector raises ValueError."""

    with pytest.raises(ValueError, match="Unknown detector"):
        DetectorRegistry.get("nonexistent_detector")


def test_registry_get_unknown_detector_shows_available():
    """Test that error message shows available detectors."""

    @DetectorRegistry.register("detector_a")
    class DetectorA(TestDetector):
        pass

    @DetectorRegistry.register("detector_b")
    class DetectorB(TestDetector):
        pass

    with pytest.raises(ValueError, match="detector_a") as exc_info:
        DetectorRegistry.get("unknown")

    assert "detector_b" in str(exc_info.value)


def test_registry_list_available_empty():
    """Test list_available() with empty registry."""
    assert DetectorRegistry.list_available() == []


def test_registry_list_available():
    """Test list_available() returns sorted list."""

    @DetectorRegistry.register("detector_c")
    class DetectorC(TestDetector):
        pass

    @DetectorRegistry.register("detector_a")
    class DetectorA(TestDetector):
        pass

    @DetectorRegistry.register("detector_b")
    class DetectorB(TestDetector):
        pass

    available = DetectorRegistry.list_available()

    assert available == ["detector_a", "detector_b", "detector_c"]


def test_registry_is_registered():
    """Test is_registered() method."""

    @DetectorRegistry.register("test_detector")
    class MyDetector(TestDetector):
        pass

    assert DetectorRegistry.is_registered("test_detector")
    assert not DetectorRegistry.is_registered("unknown_detector")


def test_registry_get_detector_class():
    """Test get_detector_class() returns class without instantiating."""

    @DetectorRegistry.register("test_detector")
    class MyDetector(TestDetector):
        pass

    detector_cls = DetectorRegistry.get_detector_class("test_detector")

    assert detector_cls is MyDetector
    assert not isinstance(detector_cls, BaseDetector)  # Should be class, not instance


def test_registry_get_detector_class_unknown():
    """Test get_detector_class() returns None for unknown detector."""
    assert DetectorRegistry.get_detector_class("unknown") is None


def test_registry_unregister():
    """Test unregistering a detector."""

    @DetectorRegistry.register("test_detector")
    class MyDetector(TestDetector):
        pass

    assert DetectorRegistry.is_registered("test_detector")

    # Unregister
    result = DetectorRegistry.unregister("test_detector")

    assert result is True
    assert not DetectorRegistry.is_registered("test_detector")


def test_registry_unregister_unknown():
    """Test unregistering unknown detector returns False."""
    result = DetectorRegistry.unregister("unknown")
    assert result is False


def test_registry_clear():
    """Test clearing all registrations."""

    @DetectorRegistry.register("detector_1")
    class Detector1(TestDetector):
        pass

    @DetectorRegistry.register("detector_2")
    class Detector2(TestDetector):
        pass

    assert len(DetectorRegistry.list_available()) == 2

    # Clear all
    DetectorRegistry.clear()

    assert len(DetectorRegistry.list_available()) == 0


def test_registry_overwrite_warning(caplog):
    """Test that overwriting a detector logs a warning."""

    @DetectorRegistry.register("test_detector")
    class Detector1(TestDetector):
        pass

    # Register again with same name
    @DetectorRegistry.register("test_detector")
    class Detector2(TestDetector):
        pass

    # Should have logged warning
    assert any("Overwriting" in record.message for record in caplog.records)


def test_registry_multiple_detectors():
    """Test registering and using multiple detectors."""

    @DetectorRegistry.register("detector_a")
    class DetectorA(TestDetector):
        def __init__(self, model=None, **kwargs):
            super().__init__(model, **kwargs)
            self.detector_type = "A"

    @DetectorRegistry.register("detector_b")
    class DetectorB(TestDetector):
        def __init__(self, model=None, **kwargs):
            super().__init__(model, **kwargs)
            self.detector_type = "B"

    # Instantiate both
    detector_a = DetectorRegistry.get("detector_a")
    detector_b = DetectorRegistry.get("detector_b")

    assert detector_a.detector_type == "A"
    assert detector_b.detector_type == "B"
    assert type(detector_a) is not type(detector_b)


def test_registry_detector_with_kwargs():
    """Test passing kwargs through get()."""

    @DetectorRegistry.register("configurable_detector")
    class ConfigurableDetector(TestDetector):
        def __init__(self, model=None, param1=None, param2=None, **kwargs):
            super().__init__(model, **kwargs)
            self.param1 = param1
            self.param2 = param2

    detector = DetectorRegistry.get("configurable_detector", param1="value1", param2=42)

    assert detector.param1 == "value1"
    assert detector.param2 == 42
