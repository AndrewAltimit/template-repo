"""SleeperDetector records which model backend produced a result and skips interventions on unhookable models."""

import numpy as np
import pytest
from test_detector_fakes import FakeModel, make_samples

from sleeper_agents.app.config import DetectionConfig, DetectionMode
from sleeper_agents.app.detector import SleeperDetector


def make_detector(model=None) -> SleeperDetector:
    config = DetectionConfig(model_name="fake", device="cpu", mode=DetectionMode.AUTO, layers_to_probe=[0, 1, 2])
    detector = SleeperDetector(config)
    detector.model = model if model is not None else FakeModel()
    detector._build_subsystems()
    return detector


def hf_like_model() -> FakeModel:
    model = FakeModel()
    model.backend = "huggingface"
    model.fallback_reason = "TransformerLens load failed: RuntimeError: boom"
    return model


@pytest.mark.asyncio
async def test_detection_result_records_backend_and_fallback_reason():
    detector = make_detector(hf_like_model())
    result = await detector.detect_backdoor("hello world")

    info = result["model_info"]
    assert info["backend"] == "huggingface"
    assert info["fallback_reason"].startswith("TransformerLens load failed")
    assert info["model_class"] == "FakeModel"
    assert info["model_name"] == "fake"


@pytest.mark.asyncio
async def test_model_info_without_backend_attribute_is_none():
    detector = make_detector()
    result = await detector.detect_backdoor("hello world")
    assert result["model_info"]["backend"] is None
    assert result["model_info"]["fallback_reason"] is None


@pytest.mark.asyncio
async def test_sweep_and_internal_analysis_record_backend():
    detector = make_detector(hf_like_model())
    sweep = await detector.sweep_layers(
        n_samples=8, clean_samples=make_samples(8, False), backdoored_samples=make_samples(8, True)
    )
    assert sweep["model_info"]["backend"] == "huggingface"

    analysis = await detector.run_internal_analysis(make_samples(4, False))
    assert analysis["model_info"]["backend"] == "huggingface"


@pytest.mark.asyncio
async def test_interventions_skipped_not_errors_on_unhookable_model():
    """A model whose residual stream cannot be hooked is skipped with the resolver's reason.

    FakeModel is neither a ModelInterface nor a TransformerLens model, so the
    intervention resolver cannot hook it. The ``backend="huggingface"`` label is only
    provenance: HuggingFace models that can be hooked run interventions (see
    test_hf_interventions_causal.py::TestDetectorInterventions).
    """
    detector = make_detector(hf_like_model())
    detector.detector_directions = {1: np.ones(8)}

    result = await detector.detect_backdoor("hello world", run_interventions=True)

    interventions = result["detection_results"]["interventions"]
    assert interventions["available"] is False
    assert interventions["skipped"] is True
    assert "error" not in interventions
    assert interventions["reason"].startswith("Causal interventions unavailable")
    assert "got FakeModel (backend=huggingface)" in interventions["reason"]
    assert interventions["backend"] == "huggingface"
    # A skipped component is not a detection failure
    assert "interventions" not in result["unavailable_components"]


@pytest.mark.asyncio
async def test_interventions_without_directions_are_skipped_with_reason():
    detector = make_detector()
    result = await detector.detect_backdoor("hello world", run_interventions=True)
    interventions = result["detection_results"]["interventions"]
    assert interventions == {
        "available": False,
        "skipped": True,
        "reason": "No detector directions to intervene on",
    }
