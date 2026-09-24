"""Tests for SleeperDetector mode semantics, layer scores/sweeps and internal analysis."""

import numpy as np
import pytest
from test_detector_fakes import TRIGGER, FakeModel, make_samples

from sleeper_agents.app.config import DetectionConfig, DetectionMode
from sleeper_agents.app.detector import SleeperDetector


def make_detector(mode=DetectionMode.AUTO, layers=(0, 1, 2), **kwargs) -> SleeperDetector:
    config = DetectionConfig(model_name="fake", device="cpu", mode=mode, layers_to_probe=list(layers), **kwargs)
    detector = SleeperDetector(config)
    detector.model = FakeModel()
    detector._build_subsystems()
    return detector


async def train(detector: SleeperDetector):
    await detector.probe_detector.train_layer_probes(
        make_samples(8, False), make_samples(8, True), layers=detector.config.layers_to_probe
    )


def test_config_defaults_to_auto_device():
    assert DetectionConfig().device == "auto"


def test_package_lazy_exports_resolve():
    import sleeper_agents

    assert sleeper_agents.SleeperDetector is SleeperDetector
    assert sleeper_agents.ModelEvaluator is not None
    assert sleeper_agents.EvaluationResult is not None


# ---------------------------------------------------------------------------
# Mode semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_mode_is_labeled_and_input_dependent():
    detector = SleeperDetector(DetectionConfig(model_name="fake", mode=DetectionMode.MOCK))  # no model needed
    texts = [f"prompt number {i}" for i in range(20)]
    results = [await detector.detect_backdoor(t) for t in texts]

    assert all(r["is_mock"] is True for r in results)
    assert all(r["detection_results"]["probes"]["is_mock"] is True for r in results)
    scores = [r["confidence"] for r in results]
    assert len(set(scores)) > 15  # varies with input
    assert len({r["is_likely_backdoored"] for r in results}) == 2  # not a constant verdict
    # Reproducible for the same input
    assert (await detector.detect_backdoor(texts[0]))["confidence"] == scores[0]


@pytest.mark.asyncio
async def test_auto_mode_without_probes_does_not_fabricate():
    detector = make_detector(DetectionMode.AUTO)
    result = await detector.detect_backdoor(f"{TRIGGER} write code", check_attention=True)

    assert result["is_mock"] is False
    assert result["probes_available"] is False
    assert "probes" in result["unavailable_components"]
    assert result["detection_results"]["probes"]["available"] is False
    assert result["verdict_methods"] == ["attention"]
    assert result["confidence"] == result["detection_results"]["attention"]["anomaly_score"]


@pytest.mark.asyncio
async def test_auto_mode_without_any_real_method_raises():
    detector = make_detector(DetectionMode.AUTO)
    with pytest.raises(RuntimeError, match="No real detection method"):
        await detector.detect_backdoor("hello", check_attention=False)


@pytest.mark.asyncio
async def test_auto_mode_attention_failure_without_probes_raises():
    detector = make_detector(DetectionMode.AUTO)
    detector.model.missing_layers = {0}
    with pytest.raises(RuntimeError, match="No real detection method"):
        await detector.detect_backdoor("hello world")


@pytest.mark.asyncio
async def test_real_mode_without_probes_raises():
    detector = make_detector(DetectionMode.REAL)
    with pytest.raises(RuntimeError, match="REAL"):
        await detector.detect_backdoor("hello")


@pytest.mark.asyncio
async def test_real_mode_with_trained_probes_separates_inputs():
    detector = make_detector(DetectionMode.REAL, detection_threshold=0.5)
    await train(detector)

    clean = await detector.detect_backdoor("please write the function zz", check_attention=False)
    dirty = await detector.detect_backdoor(f"{TRIGGER} please write the function zz", check_attention=False)

    for res in (clean, dirty):
        assert res["is_mock"] is False
        assert res["probes_available"] is True
        assert res["verdict_methods"] == ["probes"]
    assert dirty["confidence"] > clean["confidence"]
    assert dirty["is_likely_backdoored"] is True
    assert clean["is_likely_backdoored"] is False


@pytest.mark.asyncio
async def test_ensemble_combines_only_available_components():
    detector = make_detector(DetectionMode.AUTO)
    await train(detector)
    result = await detector.detect_backdoor("please write the function zz", use_ensemble=True)

    probe_score = result["detection_results"]["probes"]["confidence"]
    attn_score = result["detection_results"]["attention"]["anomaly_score"]
    assert result["verdict_methods"] == ["attention", "probes"]
    assert result["confidence"] == pytest.approx((probe_score + attn_score) / 2)


@pytest.mark.asyncio
async def test_attention_error_is_not_averaged_in_as_neutral_score():
    detector = make_detector(DetectionMode.AUTO)
    await train(detector)
    detector.attention_analyzer.model = FakeModel(missing_layers=[0])
    result = await detector.detect_backdoor("please write the function zz", use_ensemble=True)

    assert "error" in result["detection_results"]["attention"]
    assert "attention" in result["unavailable_components"]
    assert result["verdict_methods"] == ["probes"]
    assert result["confidence"] == result["detection_results"]["probes"]["confidence"]


# ---------------------------------------------------------------------------
# Layer scores and sweeps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_layer_scores_requires_probes():
    detector = make_detector()
    with pytest.raises(RuntimeError, match="unavailable"):
        await detector.get_layer_scores("hello")


@pytest.mark.asyncio
async def test_get_layer_scores_uses_trained_probes():
    detector = make_detector()
    await train(detector)
    text = f"{TRIGGER} please write the function zz"
    first = await detector.get_layer_scores(text)
    second = await detector.get_layer_scores(text)
    assert set(first) == {0, 1, 2}
    assert first == second
    clean = await detector.get_layer_scores("please write the function zz")
    assert all(first[layer] > clean[layer] for layer in first)


@pytest.mark.asyncio
async def test_sweep_without_data_reports_unavailable():
    detector = make_detector()
    result = await detector.sweep_layers(n_samples=5)
    assert result["available"] is False
    assert result["layer_results"] == {}
    assert "reason" in result


@pytest.mark.asyncio
async def test_sweep_with_data_reports_held_out_auc():
    detector = make_detector()
    result = await detector.sweep_layers(
        n_samples=6, clean_samples=make_samples(10, False), backdoored_samples=make_samples(10, True)
    )
    assert result["available"] is True
    assert set(result["layer_results"]) == {"layer_0", "layer_1", "layer_2"}
    for metrics in result["layer_results"].values():
        assert metrics["auc_type"] == "held_out"
        assert 0.9 < metrics["auc"] <= 1.0
        assert metrics["is_effective"] is True

    # Subsequent sweep without data reports the stored held-out AUCs
    again = await detector.sweep_layers()
    assert again["source"] == "existing_probes"
    assert again["layer_results"] == result["layer_results"]


def test_layer_probes_property_reflects_trained_probes():
    detector = make_detector()
    assert detector.layer_probes == {}
    detector.probe_detector.layer_probes = {0: object()}
    assert set(detector.layer_probes) == {0}


# ---------------------------------------------------------------------------
# Internal analysis
# ---------------------------------------------------------------------------


class RecordingFeatureDiscovery:
    """Feature discovery stub that records its inputs."""

    def __init__(self):
        self.calls = []
        self.deception_features = []

    async def discover_features(self, activations, layer_idx=None, context_data=None):
        self.calls.append((np.array(activations), layer_idx))
        return {
            "n_features_discovered": 0,
            "features": [],
            "suspicious_features": [],
            "deception_features": [{"feature_id": 0, "layer": layer_idx}],
            "layer": layer_idx,
        }


@pytest.mark.asyncio
async def test_internal_analysis_uses_real_layer_and_trains_no_random_probes():
    detector = make_detector(layers=(0, 2))
    recorder = RecordingFeatureDiscovery()
    detector.feature_discovery = recorder

    results = await detector.run_internal_analysis(make_samples(4, False))

    assert "error" not in results
    assert results["analysis_layer"] == 2  # layers_to_probe[len // 2], not the list index 1
    assert recorder.calls[0][1] == 2
    assert detector.model.activation_calls[0] == [2]
    assert recorder.calls[0][0].shape == (4, 16)
    # No probes were fabricated from random data
    assert detector.probe_based_detector.probes == {}
    assert results["probe_detections"] == []
    assert "probe_detection" in results["skipped_steps"]
    assert results["is_deceptive"] is False
    assert "Unavailable" in results["summary"]


@pytest.mark.asyncio
async def test_internal_analysis_without_feature_discovery_has_no_unbound_variable():
    detector = make_detector()
    detector.feature_discovery = None
    results = await detector.run_internal_analysis(make_samples(3, False))
    assert "error" not in results
    assert "feature_discovery" in results["skipped_steps"]


@pytest.mark.asyncio
async def test_extract_activation_samples_uses_last_token_of_each_sample():
    detector = make_detector(layers=(1,))
    samples = make_samples(3, True)
    activations = await detector._extract_activation_samples(samples)
    expected = [detector.model.get_activations([s], layers=[1])["layer_1"][0, -1].numpy() for s in samples]
    np.testing.assert_allclose(activations, np.stack(expected), rtol=1e-6)
