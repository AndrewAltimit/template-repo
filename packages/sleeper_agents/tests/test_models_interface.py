"""Tests for the unified model interface (layer convention, padding, generation).

All models are tiny randomly-initialized GPT-2s with a local word-level tokenizer,
so nothing is downloaded.
"""

import logging

import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
import torch
from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast

from sleeper_agents.models import model_interface as mi
from sleeper_agents.models.model_interface import (
    HuggingFaceModel,
    TransformerLensModel,
    gather_last_non_pad,
    last_non_pad_indices,
    load_model,
)

WORDS = "the a cat dog sat on mat hello world you are i hate deploy code safe".split()
N_LAYERS = 3


def build_tokenizer(directory):
    """Word-level tokenizer saved to and reloaded from ``directory`` (default right padding)."""
    vocab = {"[PAD]": 0, "[UNK]": 1, "[BOS]": 2, "[EOS]": 3}
    for word in WORDS:
        vocab[word] = len(vocab)
    tok = Tokenizer(WordLevel(vocab=vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tok, pad_token="[PAD]", eos_token="[EOS]", bos_token="[BOS]", unk_token="[UNK]"
    )
    fast.save_pretrained(str(directory))
    return PreTrainedTokenizerFast.from_pretrained(str(directory))


def build_gpt2(vocab_size, seed=0):
    torch.manual_seed(seed)
    cfg = GPT2Config(
        vocab_size=vocab_size,
        n_positions=64,
        n_embd=32,
        n_layer=N_LAYERS,
        n_head=2,
        bos_token_id=2,
        eos_token_id=3,
        pad_token_id=0,
    )
    return GPT2LMHeadModel(cfg).eval()


@pytest.fixture(scope="module")
def tokenizer_dir(tmp_path_factory):
    directory = tmp_path_factory.mktemp("tok")
    build_tokenizer(directory)
    return directory


@pytest.fixture
def hf_wrapper(tokenizer_dir):
    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    assert tokenizer.padding_side == "right"  # the wrapper must not rely on the default
    model = build_gpt2(len(tokenizer))
    wrapper = HuggingFaceModel("tiny-gpt2", device="cpu")
    wrapper.model, wrapper.tokenizer, wrapper.config = model, tokenizer, model.config
    return wrapper


@pytest.fixture(scope="module")
def bridge(tokenizer_dir):
    from transformer_lens.model_bridge import TransformerBridge

    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    model = build_gpt2(len(tokenizer), seed=1)
    tl = TransformerBridge.boot_transformers("gpt2", hf_model=model, tokenizer=tokenizer)
    tl.enable_compatibility_mode(disable_warnings=True)
    return tl


@pytest.fixture
def tl_wrapper(bridge):
    wrapper = TransformerLensModel("tiny-gpt2", device="cpu", dtype=torch.float32)
    wrapper.model, wrapper.config, wrapper.tokenizer = bridge, bridge.cfg, bridge.tokenizer
    return wrapper


def _block_outputs(model, input_ids):
    """Capture the raw output of every GPT-2 block for an unpadded input."""
    captured = {}
    handles = []
    for i, block in enumerate(model.transformer.h):

        def hook(_m, _inp, out, i=i):
            captured[i] = out[0] if isinstance(out, (tuple, list)) else out

        handles.append(block.register_forward_hook(hook))
    try:
        with torch.no_grad():
            model(input_ids=input_ids)
    finally:
        for h in handles:
            h.remove()
    return captured


class TestPaddingHelpers:
    def test_last_non_pad_indices_left_and_right(self):
        left = torch.tensor([[0, 0, 1, 1], [1, 1, 1, 1]])
        right = torch.tensor([[1, 1, 0, 0], [1, 1, 1, 0]])
        assert last_non_pad_indices(left).tolist() == [3, 3]
        assert last_non_pad_indices(right).tolist() == [1, 2]

    def test_empty_row_raises(self):
        with pytest.raises(ValueError, match="empty sequence"):
            last_non_pad_indices(torch.tensor([[0, 0], [1, 1]]))

    def test_gather_last_non_pad(self):
        hidden = torch.arange(2 * 3 * 2, dtype=torch.float32).reshape(2, 3, 2)
        mask = torch.tensor([[1, 1, 0], [0, 1, 1]])
        out = gather_last_non_pad(hidden, mask)
        assert torch.equal(out, torch.stack([hidden[0, 1], hidden[1, 2]]))


class TestHuggingFaceLayerConvention:
    def test_layer_L_is_output_of_block_L(self, hf_wrapper):
        text = "the cat sat on the mat"
        ids = hf_wrapper.tokenizer([text], return_tensors="pt")["input_ids"]
        expected = _block_outputs(hf_wrapper.model, ids)

        acts = hf_wrapper.get_activations([text], layers=list(range(N_LAYERS)))

        assert set(acts) == {f"layer_{i}" for i in range(N_LAYERS)}
        for i in range(N_LAYERS):
            torch.testing.assert_close(acts[f"layer_{i}"], expected[i], atol=1e-5, rtol=1e-5)

    def test_final_layer_excludes_final_norm(self, hf_wrapper):
        text = "hello world"
        ids = hf_wrapper.tokenizer([text], return_tensors="pt")["input_ids"]
        with torch.no_grad():
            normed_last = hf_wrapper.model(input_ids=ids, output_hidden_states=True).hidden_states[-1]
        acts = hf_wrapper.get_activations([text], layers=[N_LAYERS - 1])
        assert not torch.allclose(acts[f"layer_{N_LAYERS - 1}"], normed_last, atol=1e-4)

    def test_default_layers_are_all_blocks(self, hf_wrapper):
        acts = hf_wrapper.get_activations(["the cat"])
        assert sorted(acts) == [f"layer_{i}" for i in range(N_LAYERS)]

    @pytest.mark.parametrize("bad_layer", [N_LAYERS, -1, 99])
    def test_out_of_range_layer_raises(self, hf_wrapper, bad_layer):
        with pytest.raises(ValueError, match="out of range"):
            hf_wrapper.get_activations(["the cat"], layers=[bad_layer])


class TestHuggingFacePadding:
    texts = ["the cat", "the dog sat on the mat", "hello"]

    def _single(self, wrapper, text, layer):
        ids = wrapper.tokenizer([text], return_tensors="pt")["input_ids"]
        return _block_outputs(wrapper.model, ids)[layer][0, -1]

    def test_last_token_pooling_matches_unpadded(self, hf_wrapper):
        pooled = hf_wrapper.get_last_token_activations(self.texts, layers=[0, N_LAYERS - 1])
        for layer in (0, N_LAYERS - 1):
            for row, text in enumerate(self.texts):
                torch.testing.assert_close(
                    pooled[f"layer_{layer}"][row], self._single(hf_wrapper, text, layer), atol=1e-5, rtol=1e-5
                )

    def test_position_minus_one_is_last_real_token(self, hf_wrapper):
        acts = hf_wrapper.get_activations(self.texts, layers=[1])
        for row, text in enumerate(self.texts):
            torch.testing.assert_close(acts["layer_1"][row, -1], self._single(hf_wrapper, text, 1), atol=1e-5, rtol=1e-5)

    def test_generation_activations_padded_batch(self, hf_wrapper):
        prompts = ["the cat", "hello world you are"]
        acts = hf_wrapper.get_generation_activations(prompts, ["safe"], layers=[0, 2])
        for row, prompt in enumerate(prompts):
            ids = hf_wrapper.tokenizer([prompt + " safe"], return_tensors="pt")["input_ids"]
            expected = _block_outputs(hf_wrapper.model, ids)
            for layer in (0, 2):
                torch.testing.assert_close(acts[f"layer_{layer}"][row], expected[layer][0, -1], atol=1e-5, rtol=1e-5)

    def test_generation_activations_target_count_mismatch(self, hf_wrapper):
        with pytest.raises(ValueError, match="one entry per prompt"):
            hf_wrapper.get_generation_activations(["a", "b", "c"], ["x", "y"], layers=[0])


class TestHuggingFaceGenerate:
    def test_returns_completion_only_and_matches_unpadded(self, hf_wrapper):
        prompts = ["the cat", "hello world you are the"]
        out = hf_wrapper.generate(prompts, max_new_tokens=4, temperature=0.0)

        assert len(out) == 2
        tok = hf_wrapper.tokenizer
        for prompt, completion in zip(prompts, out):
            enc = tok([prompt], return_tensors="pt")
            with torch.no_grad():
                ref = hf_wrapper.model.generate(
                    **enc, max_new_tokens=4, do_sample=False, pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id
                )
            expected = tok.decode(ref[0, enc["input_ids"].shape[1] :], skip_special_tokens=True)
            assert completion == expected
            assert not completion.startswith(prompt)

    def test_nonpositive_temperature_is_greedy(self, hf_wrapper):
        """temperature <= 0 (used by advanced_detection for greedy decoding) never samples."""
        prompts = ["the cat", "hello world"]
        greedy = hf_wrapper.generate(prompts, max_new_tokens=4, temperature=0.0)
        assert hf_wrapper.generate(prompts, max_new_tokens=4, temperature=-1.0) == greedy
        torch.manual_seed(0)
        first = hf_wrapper.generate(prompts, max_new_tokens=4, temperature=0.0)
        torch.manual_seed(123)
        assert hf_wrapper.generate(prompts, max_new_tokens=4, temperature=0.0) == first == greedy


class TestTransformerLensWrapper:
    texts = ["the cat", "the dog sat on the mat", "hello"]

    def test_last_token_pooling_matches_unpadded(self, tl_wrapper, bridge):
        pooled = tl_wrapper.get_last_token_activations(self.texts, layers=[0, N_LAYERS - 1])
        for row, text in enumerate(self.texts):
            _, cache = bridge.run_with_cache(bridge.to_tokens(text, prepend_bos=True))
            for layer in (0, N_LAYERS - 1):
                torch.testing.assert_close(
                    pooled[f"layer_{layer}"][row],
                    cache[f"blocks.{layer}.hook_resid_post"][0, -1],
                    atol=1e-4,
                    rtol=1e-4,
                )

    def test_generate_returns_completion_only(self, tl_wrapper, bridge):
        prompts = ["the cat", "hello world you are the"]
        out = tl_wrapper.generate(prompts, max_new_tokens=3, temperature=0.0)
        for prompt, completion in zip(prompts, out):
            tokens = bridge.to_tokens(prompt, prepend_bos=True)
            ref = bridge.generate(tokens, max_new_tokens=3, do_sample=False, return_type="tokens", verbose=False)
            expected = bridge.tokenizer.decode(ref[0, tokens.shape[1] :], skip_special_tokens=True)
            assert completion == expected

    def test_nonpositive_temperature_is_greedy(self, tl_wrapper):
        prompts = ["the cat", "hello world"]
        greedy = tl_wrapper.generate(prompts, max_new_tokens=3, temperature=0.0)
        assert tl_wrapper.generate(prompts, max_new_tokens=3, temperature=-0.5) == greedy

    def test_out_of_range_layer_raises(self, tl_wrapper):
        with pytest.raises(ValueError, match="out of range"):
            tl_wrapper.get_activations(["the cat"], layers=[N_LAYERS])

    def test_backend_attribute(self, tl_wrapper, hf_wrapper):
        assert tl_wrapper.backend == "transformer_lens"
        assert hf_wrapper.backend == "huggingface"


class TestLoadModel:
    def test_tl_failure_falls_back_with_warning_and_records_backend(self, monkeypatch, caplog):
        def boom(self):
            raise RuntimeError("CUDA out of memory")

        monkeypatch.setattr(TransformerLensModel, "load", boom)
        monkeypatch.setattr(HuggingFaceModel, "load", lambda self: None)

        with caplog.at_level(logging.WARNING, logger=mi.__name__):
            model = load_model("some/model", device="cpu", prefer_hooked=True)

        assert model.backend == "huggingface"
        assert "CUDA out of memory" in model.fallback_reason
        assert any(r.levelno == logging.WARNING and "out of memory" in r.getMessage() for r in caplog.records)

    def test_quantization_skips_transformer_lens_and_is_passed_through(self, monkeypatch):
        called = []
        monkeypatch.setattr(TransformerLensModel, "load", lambda self: called.append("tl"))
        monkeypatch.setattr(HuggingFaceModel, "load", lambda self: called.append(("hf", self.requested_quantization)))

        model = load_model("some/model", device="cuda", prefer_hooked=True, quantization="4bit")

        assert called == [("hf", "4bit")]
        assert model.backend == "huggingface"
        assert "quantization" in model.fallback_reason

    def test_quantization_on_cpu_raises(self):
        wrapper = HuggingFaceModel("some/model", device="cpu", quantization="4bit")
        with pytest.raises(ValueError, match="CUDA"):
            wrapper.load()

    def test_unknown_quantization_raises(self):
        with pytest.raises(ValueError, match="Unsupported quantization"):
            mi._build_quantization_config("3bit", "cuda", torch.float16)
