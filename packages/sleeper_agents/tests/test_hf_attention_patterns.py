"""Attention patterns from HuggingFace models with the default (sdpa) attention.

transformers 5 returns no attention weights for ``output_attentions=True`` unless
the model runs eager attention, so ``HuggingFaceModel.get_attention_patterns`` failed
for every model loaded with the default implementation, and the internal_state suite
of scripts/evaluation/run_full_evaluation.py (which hands InternalStateMonitor a plain
HuggingFace model) could not run at all; for LoRA models (a PeftModel) the monitor could
not even locate the transformer blocks.
"""

import asyncio

import numpy as np
import pytest
from test_hf_interventions_models import N_LAYERS, build_model, build_tokenizer
import torch
from transformers import PreTrainedTokenizerFast

from sleeper_agents.advanced_detection.internal_state_monitor import InternalStateMonitor
from sleeper_agents.models.model_interface import HuggingFaceModel, eager_attention


@pytest.fixture(name="tokenizer_dir", scope="module")
def fixture_tokenizer_dir(tmp_path_factory):
    directory = tmp_path_factory.mktemp("tok")
    build_tokenizer(directory)
    return directory


def _sdpa_llama(tokenizer):
    model = build_model("llama", len(tokenizer))
    model.set_attn_implementation("sdpa")
    return model


class _FakeModel:
    def __init__(self, impl):
        self.config = type("Cfg", (), {"_attn_implementation": impl})()
        self.calls = []

    def set_attn_implementation(self, impl):
        self.calls.append(impl)
        self.config._attn_implementation = impl


def test_eager_attention_switches_and_restores():
    model = _FakeModel("sdpa")
    with eager_attention(model):
        assert model.config._attn_implementation == "eager"
    assert model.config._attn_implementation == "sdpa"
    assert model.calls == ["eager", "sdpa"]


def test_eager_attention_restores_after_error():
    model = _FakeModel("sdpa")
    with pytest.raises(RuntimeError), eager_attention(model):
        raise RuntimeError("boom")
    assert model.config._attn_implementation == "sdpa"


def test_eager_attention_leaves_eager_model_alone():
    model = _FakeModel("eager")
    with eager_attention(model):
        pass
    assert model.calls == []


def test_get_attention_patterns_with_sdpa_model(tokenizer_dir):
    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    model = _sdpa_llama(tokenizer)
    wrapper = HuggingFaceModel.from_loaded(model, tokenizer, model_id="tiny-llama")

    patterns = wrapper.get_attention_patterns(["the cat sat on the mat"], layers=list(range(N_LAYERS)))

    assert sorted(patterns) == [f"layer_{i}" for i in range(N_LAYERS)]
    attn = patterns["layer_0"][0]  # (heads, seq, seq)
    assert attn.shape[-1] == attn.shape[-2] == 6
    torch.testing.assert_close(attn.sum(-1), torch.ones(attn.shape[:-1]))
    assert model.config._attn_implementation == "sdpa"


def test_get_activations_returns_attention_with_sdpa_model(tokenizer_dir):
    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    wrapper = HuggingFaceModel.from_loaded(_sdpa_llama(tokenizer), tokenizer, model_id="tiny-llama")

    acts = wrapper.get_activations(["hello world"], layers=[1], return_attention=True)

    assert acts["attention_1"].shape[-1] == 2
    assert acts["layer_1"].shape[:2] == (1, 2)


def test_from_loaded_does_not_reload(tokenizer_dir):
    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    model = _sdpa_llama(tokenizer)
    wrapper = HuggingFaceModel.from_loaded(model, tokenizer)
    assert wrapper.model is model
    assert wrapper.tokenizer is tokenizer
    assert wrapper.get_num_layers() == N_LAYERS


def test_internal_state_monitor_attention_with_plain_hf_model(tokenizer_dir):
    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    monitor = InternalStateMonitor(_sdpa_llama(tokenizer), tokenizer)

    result = asyncio.run(
        monitor.attention_analyzer.analyze_trigger_attention(
            ["deploy the cat sat", "deploy a dog sat"], ["the cat sat", "a dog sat"], "deploy"
        )
    )

    assert result


def test_internal_state_monitor_with_lora_model(tokenizer_dir):
    """run_full_evaluation.py loads LoRA adapters as a PeftModel; the monitor must find its blocks."""
    from peft import LoraConfig, get_peft_model

    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    lora = get_peft_model(_sdpa_llama(tokenizer), LoraConfig(r=2, target_modules=["q_proj", "v_proj"])).eval()
    monitor = InternalStateMonitor(lora, tokenizer)

    activations = asyncio.run(monitor._extract_activations("the cat sat on the mat"))
    assert activations.size > 0

    result = asyncio.run(
        monitor.attention_analyzer.analyze_trigger_attention(["deploy the cat sat"], ["the cat sat"], "deploy")
    )
    assert result


def test_internal_state_activations_are_float32_for_fp16_model(tokenizer_dir):
    """fp16 activation statistics overflowed to inf for Qwen2.5-1.5B (large residual values)."""
    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    monitor = InternalStateMonitor(_sdpa_llama(tokenizer).half(), tokenizer)

    activations = asyncio.run(monitor._extract_activations("the cat sat on the mat"))

    assert activations.dtype == np.float32


@pytest.mark.parametrize("score", [float("inf"), float("nan"), None])
def test_non_finite_anomaly_score_has_no_risk_verdict(score):
    monitor = InternalStateMonitor(object())
    assert monitor._assess_risk_level({"overall_anomaly_score": score}) == "unknown"
