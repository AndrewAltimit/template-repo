"""HuggingFaceModel.load passes quantization / CPU-offload options to from_pretrained (mocked, offline)."""

from unittest.mock import MagicMock

import pytest
from test_hf_interventions_models import build_model, build_tokenizer
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

from sleeper_agents.models import model_interface as mi
from sleeper_agents.models.model_interface import HuggingFaceModel, TransformerLensModel, load_model

MAX_MEMORY = {0: "20GiB", "cpu": "64GiB"}


@pytest.fixture
def mocked_hub(monkeypatch, tmp_path):
    """Replace the Auto* loaders with spec'd mocks returning a tiny local model."""
    tokenizer = build_tokenizer(tmp_path)
    model = build_model("gpt2", len(tokenizer))

    auto_model = MagicMock(spec=AutoModelForCausalLM)
    auto_model.from_pretrained.return_value = model
    auto_config = MagicMock(spec=AutoConfig)
    auto_config.from_pretrained.return_value = model.config
    auto_tokenizer = MagicMock(spec=AutoTokenizer)
    auto_tokenizer.from_pretrained.return_value = tokenizer

    monkeypatch.setattr(mi, "AutoModelForCausalLM", auto_model)
    monkeypatch.setattr(mi, "AutoConfig", auto_config)
    monkeypatch.setattr(mi, "AutoTokenizer", auto_tokenizer)
    return auto_model


def _kwargs(auto_model):
    auto_model.from_pretrained.assert_called_once()
    return auto_model.from_pretrained.call_args.kwargs


class TestOffloadKwargs:
    def test_max_memory_and_offload_folder_passed_with_auto_device_map(self, mocked_hub, tmp_path):
        wrapper = HuggingFaceModel(
            "some/model", device="cuda", max_memory=MAX_MEMORY, offload_folder=str(tmp_path / "offload")
        )
        wrapper.load()

        kwargs = _kwargs(mocked_hub)
        assert kwargs["device_map"] == "auto"
        assert kwargs["max_memory"] == MAX_MEMORY
        assert kwargs["offload_folder"] == str(tmp_path / "offload")
        assert "quantization_config" not in kwargs

    def test_no_offload_kwargs_by_default(self, mocked_hub):
        HuggingFaceModel("some/model", device="cuda").load()
        kwargs = _kwargs(mocked_hub)
        assert kwargs["device_map"] == "auto"
        assert "max_memory" not in kwargs and "offload_folder" not in kwargs

    def test_quantization_with_offload_keeps_offloaded_modules_fp32(self, mocked_hub):
        pytest.importorskip("bitsandbytes")
        wrapper = HuggingFaceModel("some/model", device="cuda", quantization="4bit", max_memory=MAX_MEMORY)
        wrapper.load()

        kwargs = _kwargs(mocked_hub)
        config = kwargs["quantization_config"]
        assert config.load_in_4bit is True
        assert config.llm_int8_enable_fp32_cpu_offload is True
        assert kwargs["max_memory"] == MAX_MEMORY
        assert wrapper.quantization == "4bit"

    def test_quantization_without_offload_does_not_enable_cpu_offload(self, mocked_hub):
        pytest.importorskip("bitsandbytes")
        HuggingFaceModel("some/model", device="cuda", quantization="8bit").load()
        config = _kwargs(mocked_hub)["quantization_config"]
        assert config.load_in_8bit is True
        assert config.llm_int8_enable_fp32_cpu_offload is False

    def test_offload_requires_cuda(self, mocked_hub):
        with pytest.raises(ValueError, match="device='cuda'"):
            HuggingFaceModel("some/model", device="cpu", max_memory=MAX_MEMORY).load()
        mocked_hub.from_pretrained.assert_not_called()


class TestLoadModelOffload:
    def test_offload_skips_transformer_lens_and_is_passed_through(self, monkeypatch):
        seen = []
        monkeypatch.setattr(TransformerLensModel, "load", lambda self: seen.append("tl"))
        monkeypatch.setattr(HuggingFaceModel, "load", lambda self: seen.append(("hf", self.max_memory, self.offload_folder)))

        model = load_model("some/model", device="cuda", prefer_hooked=True, max_memory=MAX_MEMORY, offload_folder="/o")

        assert seen == [("hf", MAX_MEMORY, "/o")]
        assert model.backend == "huggingface"
        assert "offloading" in model.fallback_reason

    def test_input_device_skips_offloaded_meta_parameters(self, tmp_path):
        import torch

        wrapper = HuggingFaceModel("m", device="cuda")
        wrapper.model = torch.nn.Sequential(torch.nn.Linear(2, 2, device="meta"), torch.nn.Linear(2, 2))
        assert wrapper._input_device() == torch.device("cpu")
