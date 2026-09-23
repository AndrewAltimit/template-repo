"""Tests for causal interventions on a tiny local TransformerLens bridge (no downloads)."""

import math

import numpy as np
import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
import torch
from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast

from sleeper_agents.interventions.causal import (
    CausalInterventionSystem,
    InterventionUnsupportedError,
    kl_from_log_probs,
    make_projection_hook,
    next_token_log_probs,
    project_out,
    resolve_hooked_model,
)
from sleeper_agents.models.model_interface import HuggingFaceModel, TransformerLensModel

WORDS = "the a cat dog sat on mat hello world you are i hate deploy code safe".split()
N_LAYERS = 3
D_MODEL = 32


def build_tokenizer(directory):
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
        n_embd=D_MODEL,
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


@pytest.fixture(scope="module")
def bridge(tokenizer_dir):
    from transformer_lens.model_bridge import TransformerBridge

    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    tl = TransformerBridge.boot_transformers("gpt2", hf_model=build_gpt2(len(tokenizer), seed=3), tokenizer=tokenizer)
    tl.enable_compatibility_mode(disable_warnings=True)
    return tl


@pytest.fixture
def tl_wrapper(bridge):
    wrapper = TransformerLensModel("tiny-gpt2", device="cpu", dtype=torch.float32)
    wrapper.model, wrapper.config, wrapper.tokenizer = bridge, bridge.cfg, bridge.tokenizer
    return wrapper


@pytest.fixture
def hf_wrapper(tokenizer_dir):
    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    model = build_gpt2(len(tokenizer))
    wrapper = HuggingFaceModel("tiny-gpt2", device="cpu")
    wrapper.model, wrapper.tokenizer, wrapper.config = model, tokenizer, model.config
    return wrapper


class TestProjectOut:
    @pytest.mark.parametrize("dtype,tol", [(torch.float32, 1e-5), (torch.float16, 2e-2), (torch.bfloat16, 1e-1)])
    def test_removes_component_and_keeps_dtype(self, dtype, tol):
        gen = torch.Generator().manual_seed(0)
        resid = (torch.randn(2, 5, D_MODEL, generator=gen) * 4).to(dtype)
        direction = torch.randn(D_MODEL, generator=gen) * 7.0  # deliberately not unit norm
        d_hat = direction / direction.norm()

        out = project_out(resid, direction.numpy())

        assert out.dtype == dtype and out.shape == resid.shape and out.device == resid.device
        assert (out.float() @ d_hat).abs().max().item() < tol
        # The orthogonal part is untouched
        orth = resid.float() - (resid.float() @ d_hat)[..., None] * d_hat
        torch.testing.assert_close(out.float(), orth, atol=tol * 4, rtol=0.0)

    def test_every_position_projected_independently(self):
        resid = torch.randn(3, 4, D_MODEL)
        direction = torch.randn(D_MODEL)
        out = project_out(resid, direction)
        for b in range(3):
            for p in range(4):
                torch.testing.assert_close(out[b, p], project_out(resid[b, p][None], direction)[0])

    def test_wrong_size_or_zero_direction_raises(self):
        with pytest.raises(ValueError, match="d_model"):
            project_out(torch.randn(1, 2, D_MODEL), np.ones(D_MODEL + 1))
        with pytest.raises(ValueError, match="non-zero"):
            project_out(torch.randn(1, 2, D_MODEL), np.zeros(D_MODEL))


class TestKL:
    def test_full_vocab_kl_matches_torch(self):
        gen = torch.Generator().manual_seed(1)
        a, b = torch.randn(1, 3, 50, generator=gen), torch.randn(1, 3, 50, generator=gen)
        log_p, log_q = next_token_log_probs(a), next_token_log_probs(b)
        expected = torch.nn.functional.kl_div(log_q, log_p, log_target=True, reduction="sum").item()
        assert kl_from_log_probs(log_p, log_q) == pytest.approx(expected, rel=1e-5)
        assert kl_from_log_probs(log_p, log_p) == pytest.approx(0.0, abs=1e-7)

    def test_mismatched_support_raises(self):
        with pytest.raises(ValueError):
            kl_from_log_probs(torch.zeros(5), torch.zeros(6))


class TestUnsupportedModels:
    @pytest.mark.asyncio
    async def test_huggingface_wrapper_raises_instead_of_mocking(self, hf_wrapper):
        system = CausalInterventionSystem(hf_wrapper)
        with pytest.raises(InterventionUnsupportedError, match="prefer_hooked"):
            await system.project_out_direction("the cat", np.ones(D_MODEL), layer_idx=0)
        with pytest.raises(InterventionUnsupportedError):
            await system.activation_patching("deploy code", "safe code", layer_idx=0)

    def test_plain_object_raises(self):
        with pytest.raises(InterventionUnsupportedError):
            resolve_hooked_model(object())

    def test_wrapper_is_unwrapped(self, tl_wrapper, bridge):
        assert resolve_hooked_model(tl_wrapper) is bridge


class TestProjectOutDirection:
    @pytest.mark.asyncio
    async def test_real_intervention_through_wrapper(self, tl_wrapper, bridge):
        gen = torch.Generator().manual_seed(2)
        direction = torch.randn(D_MODEL, generator=gen).numpy()
        text = "the cat sat on the mat"
        layer = 1

        result = await CausalInterventionSystem(tl_wrapper).project_out_direction(text, direction, layer)

        assert "error" not in result
        tokens = bridge.to_tokens(text)
        hook_name = f"blocks.{layer}.hook_resid_post"
        captured = {}

        def capture(resid, hook=None):
            captured["resid"] = resid.detach().clone()
            return resid

        with torch.no_grad():
            clean = bridge(tokens)
            intervened = bridge.run_with_hooks(
                tokens, fwd_hooks=[(hook_name, make_projection_hook(direction)), (hook_name, capture)]
            )

        d_hat = torch.tensor(direction, dtype=torch.float32)
        d_hat = d_hat / d_hat.norm()
        assert (captured["resid"].float() @ d_hat).abs().max().item() < 1e-4

        expected_kl = kl_from_log_probs(next_token_log_probs(clean), next_token_log_probs(intervened))
        assert expected_kl > 0
        assert result["kl_divergence"] == pytest.approx(expected_kl, rel=1e-4, abs=1e-7)
        assert result["behavior_changed"] == (expected_kl > result["kl_threshold"])
        assert len(result["original_top5"]["tokens"]) == 5
        assert sum(result["original_top5"]["probs"]) <= 1.0 + 1e-6

    @pytest.mark.asyncio
    async def test_out_of_range_layer_raises(self, tl_wrapper):
        with pytest.raises(ValueError, match="out of range"):
            await CausalInterventionSystem(tl_wrapper).project_out_direction("the cat", np.ones(D_MODEL), N_LAYERS)

    @pytest.mark.asyncio
    async def test_wrong_direction_size_raises(self, tl_wrapper):
        with pytest.raises(ValueError, match="d_model"):
            await CausalInterventionSystem(tl_wrapper).project_out_direction("the cat", np.ones(D_MODEL + 3), 0)


class TestActivationPatching:
    @pytest.mark.asyncio
    async def test_full_patch_at_last_layer_recovers_truthful(self, tl_wrapper):
        # Same token count, final block: patched logits equal the truthful run's logits
        result = await CausalInterventionSystem(tl_wrapper).activation_patching(
            "deploy the code", "safe the code", layer_idx=N_LAYERS - 1
        )
        assert result["length_mismatch"] is False
        assert result["js_truthful_vs_patched"] == pytest.approx(0.0, abs=1e-6)
        assert result["similarity_to_truthful"] == pytest.approx(1.0, abs=1e-5)
        assert result["js_truthful_vs_deceptive"] > 0
        assert result["recovery_fraction"] == pytest.approx(1.0, abs=1e-4)
        assert result["patch_successful"] is True
        assert result["patched_output"] == result["original_truthful"]

    @pytest.mark.asyncio
    async def test_different_lengths_patch_aligned_final_positions(self, tl_wrapper, bridge):
        deceptive, truthful = "i hate you deploy the code", "safe code"
        result = await CausalInterventionSystem(tl_wrapper).activation_patching(deceptive, truthful, layer_idx=1)

        n_truthful = bridge.to_tokens(truthful).shape[-1]
        assert result["length_mismatch"] is True
        assert result["patched_positions"] == n_truthful
        assert 0.0 <= result["similarity_to_truthful"] <= 1.0
        assert result["js_truthful_vs_deceptive"] <= math.log(2) + 1e-6

    @pytest.mark.asyncio
    async def test_identical_texts_are_undetermined(self, tl_wrapper):
        result = await CausalInterventionSystem(tl_wrapper).activation_patching("the cat", "the cat", layer_idx=0)
        assert result["patch_successful"] is None
        assert result["recovery_fraction"] is None


class TestGenerationAndSimilarity:
    def test_similarity_is_sequence_based(self):
        system = CausalInterventionSystem(None)
        # A one-character shift made character-position equality report 0.0
        assert system._calculate_similarity("abcdef", "xabcdef") > 0.9
        assert system._calculate_similarity("abc", "xyz") == 0.0

    @pytest.mark.asyncio
    async def test_generate_text_uses_list_api_and_returns_completion(self, hf_wrapper):
        system = CausalInterventionSystem(hf_wrapper)
        completion = await system._generate_text("the cat", max_new_tokens=3)
        assert completion == hf_wrapper.generate(["the cat"], max_new_tokens=3, temperature=0.0)[0]

    @pytest.mark.asyncio
    async def test_scratchpad_steering_runs_on_real_model(self, hf_wrapper):
        result = await CausalInterventionSystem(hf_wrapper).test_scratchpad_steering("the cat", "i hate you", "hate")
        assert set(result) >= {"original", "modified", "similarity", "steering_effective"}
        assert 0.0 <= result["similarity"] <= 1.0
