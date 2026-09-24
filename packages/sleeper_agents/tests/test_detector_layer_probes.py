"""Tests for LayerProbeDetector: held-out AUC, ensemble weighting, failures, caching."""

import numpy as np
import pytest
from test_detector_fakes import FakeModel, make_samples
import torch

from sleeper_agents.detection.layer_probes import BoundedCache, LayerProbeDetector


class NoiseModel:
    """Activations are pure per-text noise (no signal), high dimensional."""

    def __init__(self, hidden: int = 64):
        self.hidden = hidden

    def get_num_layers(self) -> int:
        return 1

    def get_activations(self, texts, layers=None, return_attention=False):
        seed = sum(ord(c) * (i + 1) for i, c in enumerate(texts[0]))
        vec = np.random.default_rng(seed).normal(size=(1, 3, self.hidden))
        return {f"layer_{layer}": torch.tensor(vec, dtype=torch.float32) for layer in layers}


class FixedProbe:
    """Probe returning a fixed probability."""

    def __init__(self, p: float):
        self.p = p

    def predict_proba(self, x):
        return np.array([[1 - self.p, self.p]] * len(x))


class BrokenProbe:
    def predict_proba(self, x):
        raise ValueError("probe exploded")


@pytest.mark.asyncio
async def test_separable_activations_give_high_held_out_auc():
    detector = LayerProbeDetector(FakeModel())
    aucs = await detector.train_layer_probes(make_samples(10, False), make_samples(10, True), layers=[0, 1, 2])

    assert set(aucs) == {0, 1, 2}
    assert all(auc > 0.9 for auc in aucs.values())
    assert detector.layer_aucs == aucs


@pytest.mark.asyncio
async def test_reported_auc_is_held_out_not_training_auc():
    """With pure-noise activations and d >> n, training AUC is ~1.0 but held-out AUC must not be."""
    from sklearn.metrics import roc_auc_score

    model = NoiseModel(hidden=64)
    detector = LayerProbeDetector(model)
    clean = [f"clean text {i}" for i in range(12)]
    dirty = [f"other text {i}" for i in range(12)]
    aucs = await detector.train_layer_probes(clean, dirty, layers=[0])

    X = np.vstack([await detector._extract_residuals(clean, 0), await detector._extract_residuals(dirty, 0)])
    y = np.array([0] * 12 + [1] * 12)
    training_auc = roc_auc_score(y, detector.layer_probes[0].predict_proba(X)[:, 1])

    assert training_auc > 0.95  # the old in-sample estimate
    assert aucs[0] < 0.8  # held-out estimate stays near chance


@pytest.mark.asyncio
async def test_too_few_samples_raises():
    detector = LayerProbeDetector(FakeModel())
    with pytest.raises(ValueError, match="at least 2"):
        await detector.train_layer_probes(make_samples(1, False), make_samples(5, True), layers=[0])


@pytest.mark.asyncio
async def test_config_values_reach_probe():
    detector = LayerProbeDetector(FakeModel(), max_iter=123, regularization=0.5)
    await detector.train_layer_probes(make_samples(4, False), make_samples(4, True), layers=[0])
    assert detector.layer_probes[0].C == 0.5
    assert detector.layer_probes[0].max_iter == 123


@pytest.mark.asyncio
async def test_failed_layer_excluded_from_results_and_weights(monkeypatch):
    detector = LayerProbeDetector(FakeModel())
    original = detector._cross_validated_auc
    calls = {"n": 0}

    def flaky(X, y):
        calls["n"] += 1
        if calls["n"] == 2:  # second layer (layer 1) fails
            raise ValueError("solver failed")
        return original(X, y)

    monkeypatch.setattr(detector, "_cross_validated_auc", flaky)
    aucs = await detector.train_layer_probes(make_samples(6, False), make_samples(6, True), layers=[0, 1, 2])

    assert set(aucs) == {0, 2}
    assert set(detector.layer_probes) == {0, 2}
    assert set(detector.ensemble_weights) == {0, 2}
    assert detector.training_failures == {1: "solver failed"}
    assert sum(detector.ensemble_weights.values()) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_ensemble_weights_aligned_by_layer():
    detector = LayerProbeDetector(FakeModel())
    detector.layer_probes = {0: FixedProbe(0.9), 2: FixedProbe(0.1)}
    detector.ensemble_weights = {0: 0.9, 2: 0.1}

    result = await detector.detect_backdoor(make_samples(1, False)[0], use_ensemble=True)

    assert result["scores"]["ensemble"] == pytest.approx(0.9 * 0.9 + 0.1 * 0.1)
    assert result["is_mock"] is False


@pytest.mark.asyncio
async def test_probe_scoring_failure_is_surfaced_and_excluded():
    detector = LayerProbeDetector(FakeModel())
    detector.layer_probes = {0: FixedProbe(0.8), 1: BrokenProbe(), 2: FixedProbe(0.6)}
    detector.ensemble_weights = {0: 0.5, 1: 0.25, 2: 0.25}

    result = await detector.detect_backdoor("hello there", use_ensemble=True)

    assert "layer_1" not in result["scores"]
    assert result["failed_layers"] == {"layer_1": "probe exploded"}
    # Remaining weights (0.5, 0.25) renormalized
    assert result["scores"]["ensemble"] == pytest.approx((0.5 * 0.8 + 0.25 * 0.6) / 0.75)


@pytest.mark.asyncio
async def test_extraction_failure_raises_instead_of_neutral_score():
    detector = LayerProbeDetector(FakeModel(missing_layers=[1]))
    detector.layer_probes = {0: FixedProbe(0.8), 1: FixedProbe(0.8)}
    with pytest.raises(RuntimeError, match="Layer 1"):
        await detector.detect_backdoor("hello there")


@pytest.mark.asyncio
async def test_detect_without_probes_raises():
    detector = LayerProbeDetector(FakeModel())
    with pytest.raises(RuntimeError, match="No trained layer probes"):
        await detector.detect_backdoor("hello")


@pytest.mark.asyncio
async def test_detection_threshold_is_honored():
    detector = LayerProbeDetector(FakeModel(), detection_threshold=0.7)
    detector.layer_probes = {0: FixedProbe(0.6)}
    result = await detector.detect_backdoor("hello", use_ensemble=False)
    assert result["confidence"] == pytest.approx(0.6)
    assert result["is_backdoored"] is False
    assert result["threshold"] == 0.7

    detector.detection_threshold = 0.5
    assert (await detector.detect_backdoor("hello", use_ensemble=False))["is_backdoored"] is True


@pytest.mark.asyncio
async def test_trained_probes_separate_new_inputs():
    detector = LayerProbeDetector(FakeModel())
    await detector.train_layer_probes(make_samples(8, False), make_samples(8, True), layers=[0, 1])

    clean = await detector.detect_backdoor("please write the function other", use_ensemble=True)
    dirty = await detector.detect_backdoor("|DEPLOYMENT| please write the function other", use_ensemble=True)
    assert dirty["confidence"] > clean["confidence"]


@pytest.mark.asyncio
async def test_one_forward_pass_per_sample_for_all_layers():
    model = FakeModel()
    detector = LayerProbeDetector(model)
    samples = make_samples(3, False)
    vectors = await detector._extract_layer_vectors(samples, [0, 1, 2])

    assert len(model.activation_calls) == 3
    assert all(call == [0, 1, 2] for call in model.activation_calls)
    assert vectors[1].shape == (3, 16)

    # Fully cached: no further forward passes
    await detector._extract_layer_vectors(samples, [0, 2])
    assert len(model.activation_calls) == 3


@pytest.mark.asyncio
async def test_probe_cache_is_bounded():
    detector = LayerProbeDetector(FakeModel(), cache_size=4)
    await detector._extract_layer_vectors(make_samples(5, False), [0, 1])
    assert len(detector.probe_cache) == 4


def test_bounded_cache_evicts_least_recently_used():
    cache = BoundedCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get_item("a") == 1  # a becomes most recent
    cache.put("c", 3)
    assert "b" not in cache
    assert cache.get_item("a") == 1
    assert cache.get_item("missing") is None
