"""Unit tests for ARTActivationDetector.

Tests the clustering-based backdoor detector inspired by ART's ActivationDefence.
"""

import numpy as np
import pytest

from sleeper_agents.detection.art_activation_detector import ARTActivationDetector
from sleeper_agents.evaluation.detector_registry import DetectorRegistry


@pytest.fixture
def synthetic_activations_2d():
    """Generate synthetic 2D activations for testing."""
    np.random.seed(42)

    # Create two clusters: clean and backdoored
    n_clean = 100
    n_backdoor = 20

    # Clean samples: cluster around origin
    clean_acts = np.random.randn(n_clean, 64).astype(np.float32)

    # Backdoor samples: cluster away from origin
    backdoor_acts = np.random.randn(n_backdoor, 64).astype(np.float32) + 5.0

    # Combine
    activations = np.vstack([clean_acts, backdoor_acts])
    labels = np.array([0] * n_clean + [1] * n_backdoor)

    # Shuffle
    indices = np.random.permutation(len(activations))
    return activations[indices], labels[indices]


@pytest.fixture
def synthetic_activations_3d():
    """Generate synthetic 3D activations with sequence dimension."""
    np.random.seed(42)

    n_clean = 100
    n_backdoor = 20
    seq_len = 10
    hidden_dim = 64

    # Clean samples
    clean_acts = np.random.randn(n_clean, seq_len, hidden_dim).astype(np.float32)

    # Backdoor samples: different pattern in sequence
    backdoor_acts = np.random.randn(n_backdoor, seq_len, hidden_dim).astype(np.float32) + 3.0

    # Combine
    activations = np.vstack([clean_acts, backdoor_acts])
    labels = np.array([0] * n_clean + [1] * n_backdoor)

    # Shuffle
    indices = np.random.permutation(len(activations))
    return activations[indices], labels[indices]


def test_detector_registration():
    """Test that detector is registered in DetectorRegistry."""
    assert DetectorRegistry.is_registered("art_activation")
    detector = DetectorRegistry.get("art_activation")
    assert isinstance(detector, ARTActivationDetector)


def test_detector_initialization():
    """Test detector initialization with default parameters."""
    detector = ARTActivationDetector()

    assert detector.nb_clusters == 2
    assert detector.nb_dims == 10
    assert detector.pooling_method == "mean"
    assert detector.normalize is True
    assert detector.random_state == 42


def test_detector_initialization_custom_params():
    """Test detector initialization with custom parameters."""
    detector = ARTActivationDetector(nb_clusters=3, nb_dims=20, pooling_method="last", normalize=False)

    assert detector.nb_clusters == 3
    assert detector.nb_dims == 20
    assert detector.pooling_method == "last"
    assert detector.normalize is False


def test_detector_name():
    """Test that detector name is correct."""
    detector = ARTActivationDetector()
    assert detector.name == "ARTActivationDetector"


def test_inputs_required():
    """Test inputs_required property."""
    detector = ARTActivationDetector()
    inputs = detector.inputs_required

    assert "activations" in inputs
    assert "labels" in inputs
    assert isinstance(inputs, dict)


def test_pooling_mean_2d():
    """Test that 2D activations are not pooled."""
    detector = ARTActivationDetector(pooling_method="mean")
    activations = np.random.randn(10, 64).astype(np.float32)

    pooled = detector._pool_activations(activations)

    assert pooled.shape == activations.shape
    assert np.allclose(pooled, activations)


def test_pooling_mean_3d():
    """Test mean pooling on 3D activations."""
    detector = ARTActivationDetector(pooling_method="mean")
    activations = np.random.randn(10, 5, 64).astype(np.float32)

    pooled = detector._pool_activations(activations)

    assert pooled.shape == (10, 64)
    assert np.allclose(pooled, activations.mean(axis=1))


def test_pooling_last_3d():
    """Test last-token pooling on 3D activations."""
    detector = ARTActivationDetector(pooling_method="last")
    activations = np.random.randn(10, 5, 64).astype(np.float32)

    pooled = detector._pool_activations(activations)

    assert pooled.shape == (10, 64)
    assert np.allclose(pooled, activations[:, -1, :])


def test_pooling_first_3d():
    """Test first-token pooling on 3D activations."""
    detector = ARTActivationDetector(pooling_method="first")
    activations = np.random.randn(10, 5, 64).astype(np.float32)

    pooled = detector._pool_activations(activations)

    assert pooled.shape == (10, 64)
    assert np.allclose(pooled, activations[:, 0, :])


def test_pooling_invalid_method():
    """Test that invalid pooling method raises ValueError."""
    detector = ARTActivationDetector(pooling_method="invalid")
    activations = np.random.randn(10, 5, 64).astype(np.float32)

    with pytest.raises(ValueError, match="Unknown pooling method"):
        detector._pool_activations(activations)


def test_pooling_invalid_shape():
    """Test that invalid activation shape raises ValueError."""
    detector = ARTActivationDetector()
    activations = np.random.randn(10, 5, 64, 32).astype(np.float32)  # 4D

    with pytest.raises(ValueError, match="must be 2D or 3D"):
        detector._pool_activations(activations)


def test_fit_2d(synthetic_activations_2d):
    """Test fitting on 2D activations."""
    activations, labels = synthetic_activations_2d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    # Should not raise
    detector.fit(activations, labels)

    assert detector._is_fitted
    assert detector._pca is not None
    assert detector._clusterer is not None
    assert detector._cluster_labels is not None
    assert len(detector._cluster_labels) == len(activations)


def test_fit_3d(synthetic_activations_3d):
    """Test fitting on 3D activations."""
    activations, labels = synthetic_activations_3d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    # Should not raise
    detector.fit(activations, labels)

    assert detector._is_fitted
    assert detector._pca is not None


def test_fit_shape_mismatch():
    """Test that fit raises ValueError on shape mismatch."""
    detector = ARTActivationDetector()
    activations = np.random.randn(100, 64).astype(np.float32)
    labels = np.array([0] * 50)  # Wrong size

    with pytest.raises(ValueError, match="must have same length"):
        detector.fit(activations, labels)


def test_score_without_fit():
    """Test that score raises RuntimeError if not fitted."""
    detector = ARTActivationDetector()
    activations = np.random.randn(10, 64).astype(np.float32)

    with pytest.raises(RuntimeError, match="Must call fit"):
        detector.score(activations)


def test_score_after_fit_2d(synthetic_activations_2d):
    """Test scoring after fitting on 2D activations."""
    activations, labels = synthetic_activations_2d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    detector.fit(activations, labels)
    scores = detector.score(activations)

    assert scores.shape == (len(activations),)
    assert np.all(scores >= 0)  # Distances are non-negative
    assert not np.any(np.isnan(scores))


def test_score_after_fit_3d(synthetic_activations_3d):
    """Test scoring after fitting on 3D activations."""
    activations, labels = synthetic_activations_3d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    detector.fit(activations, labels)
    scores = detector.score(activations)

    assert scores.shape == (len(activations),)
    assert np.all(scores >= 0)


def test_run_pipeline_2d(synthetic_activations_2d):
    """Test full detection pipeline on 2D activations."""
    activations, labels = synthetic_activations_2d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    result = detector.run(activations=activations, labels=labels)

    # Verify result structure
    assert "score" in result
    assert "is_backdoored" in result
    assert "report" in result
    assert "metadata" in result

    # Verify types
    assert isinstance(result["score"], float)
    assert isinstance(result["is_backdoored"], (bool, np.bool_))
    assert isinstance(result["report"], dict)
    assert isinstance(result["metadata"], dict)

    # Verify report contents
    report = result["report"]
    assert "method" in report
    assert "nb_clusters" in report
    assert "suspicious_samples" in report
    assert "cluster_composition" in report


def test_run_pipeline_3d(synthetic_activations_3d):
    """Test full detection pipeline on 3D activations."""
    activations, labels = synthetic_activations_3d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    result = detector.run(activations=activations, labels=labels)

    assert "score" in result
    assert "is_backdoored" in result


def test_run_missing_inputs():
    """Test that run raises ValueError if inputs missing."""
    detector = ARTActivationDetector()

    with pytest.raises(ValueError, match="Must provide"):
        detector.run(activations=None, labels=None)


def test_cluster_analysis(synthetic_activations_2d):
    """Test cluster composition analysis."""
    activations, labels = synthetic_activations_2d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    detector.fit(activations, labels)
    composition = detector._analyze_clusters(labels)

    # Should have info for each cluster
    assert len(composition) > 0

    for cluster_info in composition.values():
        assert "size" in cluster_info
        assert "clean_count" in cluster_info
        assert "backdoor_count" in cluster_info
        assert "purity" in cluster_info
        assert 0.0 <= cluster_info["purity"] <= 1.0


def test_normalize_flag():
    """Test that normalize flag affects behavior."""
    np.random.seed(42)
    activations = np.random.randn(100, 64).astype(np.float32)
    labels = np.array([0] * 50 + [1] * 50)

    # With normalization
    detector_norm = ARTActivationDetector(normalize=True)
    detector_norm.fit(activations, labels)

    # Without normalization
    detector_no_norm = ARTActivationDetector(normalize=False)
    detector_no_norm.fit(activations, labels)

    # Scores should be different
    scores_norm = detector_norm.score(activations)
    scores_no_norm = detector_no_norm.score(activations)

    assert not np.allclose(scores_norm, scores_no_norm)


def test_random_state_reproducibility():
    """Test that random_state ensures reproducibility."""
    np.random.seed(42)
    activations = np.random.randn(100, 64).astype(np.float32)
    labels = np.array([0] * 50 + [1] * 50)

    # Fit twice with same random state
    detector1 = ARTActivationDetector(random_state=42)
    detector1.fit(activations, labels)
    scores1 = detector1.score(activations)

    detector2 = ARTActivationDetector(random_state=42)
    detector2.fit(activations, labels)
    scores2 = detector2.score(activations)

    # Should be identical
    assert np.allclose(scores1, scores2)


def test_explain_before_fit():
    """Test explain before fitting returns default message."""
    detector = ARTActivationDetector()
    explanation = detector.explain(sample_id="test_001")

    assert explanation["method"] == "ARTActivationDetector"
    assert explanation["sample_id"] == "test_001"
    assert "not implemented" in explanation["explanation"].lower()


def test_explain_after_fit(synthetic_activations_2d):
    """Test explain after fitting provides detailed information."""
    activations, labels = synthetic_activations_2d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    detector.fit(activations, labels)

    # Explain a single sample
    sample_activations = activations[:1]
    score = detector.score(sample_activations)[0]

    explanation = detector.explain(sample_id="test_001", score=score, activations=sample_activations)

    assert explanation["method"] == "ARTActivationDetector"
    assert explanation["sample_id"] == "test_001"
    assert "score" in explanation
    assert "cluster_assignment" in explanation
    assert "explanation" in explanation


def test_different_nb_clusters():
    """Test detector with different numbers of clusters."""
    np.random.seed(42)
    activations = np.random.randn(100, 64).astype(np.float32)
    labels = np.array([0] * 50 + [1] * 50)

    for nb_clusters in [2, 3, 5]:
        detector = ARTActivationDetector(nb_clusters=nb_clusters)
        detector.fit(activations, labels)

        assert detector._clusterer.n_clusters == nb_clusters  # type: ignore
        assert len(np.unique(detector._cluster_labels)) <= nb_clusters


def test_pca_variance_explained(synthetic_activations_2d):
    """Test that PCA variance is recorded in results."""
    activations, labels = synthetic_activations_2d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    result = detector.run(activations=activations, labels=labels)

    variance = result["report"]["pca_variance_explained"]
    assert 0.0 <= variance <= 1.0


def test_threshold_percentile_customization(synthetic_activations_2d):
    """Test custom threshold percentile."""
    activations, labels = synthetic_activations_2d
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)

    result = detector.run(activations=activations, labels=labels, threshold_percentile=95)

    assert result["report"]["threshold_percentile"] == 95


def test_repr():
    """Test string representation."""
    detector = ARTActivationDetector(nb_clusters=3, nb_dims=15)
    repr_str = repr(detector)

    assert "ARTActivationDetector" in repr_str
    assert "config" in repr_str
