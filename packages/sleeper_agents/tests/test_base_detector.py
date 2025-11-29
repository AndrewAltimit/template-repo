"""Unit tests for BaseDetector ABC.

Tests the abstract base class interface for detection methods.
"""

import numpy as np
import pytest

from sleeper_agents.detection.base_detector import BaseDetector


class MockDetector(BaseDetector):
    """Mock detector implementation for testing."""

    def __init__(self, model=None, **kwargs):
        super().__init__(model, **kwargs)
        self._is_fitted = False
        self._scores = None

    def fit(self, activations: np.ndarray, labels: np.ndarray) -> None:
        """Mock fit method."""
        assert activations.shape[0] == len(labels), "Activations and labels must match"
        self._is_fitted = True

    def score(self, activations: np.ndarray) -> np.ndarray:
        """Mock score method."""
        if not self._is_fitted:
            raise RuntimeError("Must call fit() before score()")
        # Return random scores for testing
        n_samples = activations.shape[0] if activations is not None else 0
        return np.random.rand(n_samples)

    def run(self, **kwargs) -> dict:
        """Mock run method."""
        activations = kwargs.get("activations")
        labels = kwargs.get("labels")

        if activations is None or labels is None:
            raise ValueError("Must provide activations and labels")

        self.fit(activations, labels)
        scores = self.score(activations)

        n_samples = activations.shape[0] if activations is not None else 0
        return {
            "score": float(np.mean(scores)),
            "is_backdoored": np.mean(scores) > 0.5,
            "report": {"method": "mock", "n_samples": n_samples},
            "metadata": {"config": self.config},
        }


def test_base_detector_instantiation():
    """Test that BaseDetector can be instantiated through subclass."""
    detector = MockDetector(model=None, test_param="value")

    assert detector.model is None
    assert detector.config == {"test_param": "value"}


def test_base_detector_name():
    """Test that name property returns class name."""
    detector = MockDetector()

    assert detector.name == "MockDetector"


def test_base_detector_inputs_required():
    """Test that inputs_required property returns expected dict."""
    detector = MockDetector()

    inputs = detector.inputs_required
    assert "activations" in inputs
    assert "labels" in inputs
    assert isinstance(inputs, dict)


def test_base_detector_explain_default():
    """Test that default explain() returns not implemented message."""
    detector = MockDetector()

    explanation = detector.explain(sample_id="test_123")

    assert explanation["method"] == "MockDetector"
    assert explanation["sample_id"] == "test_123"
    assert "not implemented" in explanation["explanation"].lower()


def test_base_detector_repr():
    """Test string representation."""
    detector = MockDetector(param1="value1", param2=42)

    repr_str = repr(detector)
    assert "MockDetector" in repr_str
    assert "config" in repr_str


def test_mock_detector_fit():
    """Test that mock fit() works correctly."""
    detector = MockDetector()

    # Create synthetic data
    activations = np.random.randn(100, 512).astype(np.float32)
    labels = np.random.randint(0, 2, size=100)

    # Should not raise
    detector.fit(activations, labels)
    assert detector._is_fitted


def test_mock_detector_fit_shape_mismatch():
    """Test that fit() raises on shape mismatch."""
    detector = MockDetector()

    activations = np.random.randn(100, 512).astype(np.float32)
    labels = np.random.randint(0, 2, size=50)  # Wrong size

    with pytest.raises(AssertionError):
        detector.fit(activations, labels)


def test_mock_detector_score_without_fit():
    """Test that score() raises if called before fit()."""
    detector = MockDetector()

    activations = np.random.randn(10, 512).astype(np.float32)

    with pytest.raises(RuntimeError, match="Must call fit"):
        detector.score(activations)


def test_mock_detector_score_after_fit():
    """Test that score() works after fit()."""
    detector = MockDetector()

    # Fit first
    activations_train = np.random.randn(100, 512).astype(np.float32)
    labels_train = np.random.randint(0, 2, size=100)
    detector.fit(activations_train, labels_train)

    # Score on test data
    activations_test = np.random.randn(50, 512).astype(np.float32)
    scores = detector.score(activations_test)

    assert scores.shape == (50,)
    assert np.all((scores >= 0) & (scores <= 1))


def test_mock_detector_run():
    """Test that run() pipeline works end-to-end."""
    detector = MockDetector()

    # Create synthetic data
    activations = np.random.randn(100, 512).astype(np.float32)
    labels = np.random.randint(0, 2, size=100)

    # Run detection
    result = detector.run(activations=activations, labels=labels)

    # Verify result structure
    assert "score" in result
    assert "is_backdoored" in result
    assert "report" in result
    assert "metadata" in result

    assert isinstance(result["score"], float)
    assert isinstance(result["is_backdoored"], (bool, np.bool_))
    assert isinstance(result["report"], dict)
    assert isinstance(result["metadata"], dict)


def test_base_detector_cannot_instantiate_directly():
    """Test that BaseDetector itself cannot be instantiated."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BaseDetector()  # pylint: disable=abstract-class-instantiated


class IncompleteDetector(BaseDetector):
    """Detector missing required methods."""

    pass  # Intentionally incomplete to test ABC enforcement


def test_incomplete_detector_cannot_instantiate():
    """Test that incomplete implementations cannot be instantiated."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteDetector()  # pylint: disable=abstract-class-instantiated


def test_detector_with_custom_explain():
    """Test detector with custom explain() implementation."""

    class ExplainableDetector(MockDetector):
        def explain(self, sample_id: str) -> dict:
            return {
                "method": self.name,
                "sample_id": sample_id,
                "explanation": f"Custom explanation for {sample_id}",
                "feature_importance": [0.5, 0.3, 0.2],
            }

    detector = ExplainableDetector()
    explanation = detector.explain("sample_001")

    assert "Custom explanation" in explanation["explanation"]
    assert "feature_importance" in explanation
    assert len(explanation["feature_importance"]) == 3
