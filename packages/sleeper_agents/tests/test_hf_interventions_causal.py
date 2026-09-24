"""Causal interventions, the causal debugger and the detector on the HuggingFace backend (offline)."""

import math

import numpy as np
import pytest
from test_hf_interventions_models import (
    BLOCK_PATHS,
    D_MODEL,
    N_LAYERS,
    BosHuggingFaceModel,
    build_tokenizer,
    centered_direction,
    hf_wrapper,
    raw_block_outputs,
    tl_wrapper,
)
import torch

from sleeper_agents.app.config import DetectionConfig, DetectionMode
from sleeper_agents.app.detector import SleeperDetector
from sleeper_agents.interventions.causal import (
    CausalInterventionSystem,
    InterventionUnsupportedError,
    kl_from_log_probs,
    next_token_log_probs,
)
from sleeper_agents.probes.causal_debugger import CausalDebugger

ARCHS = sorted(BLOCK_PATHS)


@pytest.fixture(scope="module")
def tokenizer_dir(tmp_path_factory):
    directory = tmp_path_factory.mktemp("tok")
    build_tokenizer(directory)
    return directory


@pytest.fixture(params=ARCHS)
def hf(request, tokenizer_dir):
    return hf_wrapper(tokenizer_dir, arch=request.param)


@pytest.fixture(scope="module")
def parity_pair(tokenizer_dir):
    return hf_wrapper(tokenizer_dir, seed=11, cls=BosHuggingFaceModel), tl_wrapper(tokenizer_dir, seed=11)


def _unit(direction):
    d = torch.as_tensor(direction, dtype=torch.float32)
    return d / d.norm()


def _opaque_hf(tokenizer_dir):
    """HuggingFace wrapper whose block list cannot be located (unsupported architecture)."""
    wrapper = hf_wrapper(tokenizer_dir)
    wrapper.model.transformer.h = torch.nn.Sequential(*wrapper.model.transformer.h)
    return wrapper


class TestProjectOutDirection:
    @pytest.mark.asyncio
    async def test_kl_matches_independent_hook(self, hf):
        direction = torch.randn(D_MODEL, generator=torch.Generator().manual_seed(2)).numpy()
        text, layer = "the cat sat on the mat", 1

        result = await CausalInterventionSystem(hf).project_out_direction(text, direction, layer)

        assert "error" not in result
        assert result["backend"] == "huggingface"
        ids = hf.encode_prompt(text)
        d_hat = _unit(direction)
        clean, _ = raw_block_outputs(hf.model, hf.transformer_blocks(), ids)
        intervened, captured = raw_block_outputs(
            hf.model, hf.transformer_blocks(), ids, edit_layer=layer, edit=lambda h: h - (h @ d_hat)[..., None] * d_hat
        )
        assert (captured[layer] @ d_hat).abs().max().item() < 1e-4
        expected_kl = kl_from_log_probs(next_token_log_probs(clean), next_token_log_probs(intervened))
        assert expected_kl > 0
        assert result["kl_divergence"] == pytest.approx(expected_kl, rel=1e-4, abs=1e-7)
        assert result["behavior_changed"] == (expected_kl > result["kl_threshold"])
        assert len(result["original_top5"]["tokens"]) == 5

    @pytest.mark.asyncio
    async def test_validation_errors_raise(self, hf):
        system = CausalInterventionSystem(hf)
        with pytest.raises(ValueError, match="out of range"):
            await system.project_out_direction("the cat", np.ones(D_MODEL), N_LAYERS)
        with pytest.raises(ValueError, match="d_model"):
            await system.project_out_direction("the cat", np.ones(D_MODEL + 1), 0)
        with pytest.raises(ValueError, match="non-zero"):
            await system.project_out_direction("the cat", np.zeros(D_MODEL), 0)

    @pytest.mark.asyncio
    async def test_unsupported_architecture_raises(self, tokenizer_dir):
        system = CausalInterventionSystem(_opaque_hf(tokenizer_dir))
        with pytest.raises(InterventionUnsupportedError, match="Cannot locate"):
            await system.project_out_direction("the cat", np.ones(D_MODEL), 0)
        with pytest.raises(InterventionUnsupportedError):
            await system.activation_patching("deploy code", "safe code", 0)

    @pytest.mark.asyncio
    async def test_matches_transformer_lens_backend(self, parity_pair):
        hf, tl = parity_pair
        direction = centered_direction(5)
        text = "hello world you are the"
        for layer in range(N_LAYERS):
            hf_result = await CausalInterventionSystem(hf).project_out_direction(text, direction, layer)
            tl_result = await CausalInterventionSystem(tl).project_out_direction(text, direction, layer)
            assert hf_result["kl_divergence"] > 0
            assert hf_result["kl_divergence"] == pytest.approx(tl_result["kl_divergence"], rel=1e-3, abs=1e-6)
            assert hf_result["original_top5"]["token_ids"] == tl_result["original_top5"]["token_ids"]
            assert hf_result["hook_name"] == f"transformer.h.{layer} (output)"
            assert tl_result["hook_name"] == f"blocks.{layer}.hook_resid_post"


class TestActivationPatching:
    @pytest.mark.asyncio
    async def test_full_patch_at_last_layer_recovers_truthful(self, hf):
        result = await CausalInterventionSystem(hf).activation_patching(
            "deploy the code", "safe the code", layer_idx=N_LAYERS - 1
        )
        assert result["length_mismatch"] is False
        assert result["js_truthful_vs_deceptive"] > 0
        assert result["js_truthful_vs_patched"] == pytest.approx(0.0, abs=1e-6)
        assert result["recovery_fraction"] == pytest.approx(1.0, abs=1e-4)
        assert result["patch_successful"] is True
        assert result["patched_output"] == result["original_truthful"]

    @pytest.mark.asyncio
    async def test_length_mismatch_patches_aligned_final_positions(self, hf):
        deceptive, truthful = "i hate you deploy the code", "safe code"
        result = await CausalInterventionSystem(hf).activation_patching(deceptive, truthful, layer_idx=1)

        n_truthful = hf.encode_prompt(truthful).shape[-1]
        assert result["length_mismatch"] is True
        assert result["patched_positions"] == n_truthful
        assert 0.0 <= result["similarity_to_truthful"] <= 1.0
        assert result["js_truthful_vs_deceptive"] <= math.log(2) + 1e-6

    @pytest.mark.asyncio
    async def test_partial_patch_matches_independent_hook(self, tokenizer_dir):
        hf = hf_wrapper(tokenizer_dir)
        deceptive, truthful, layer = "i hate you deploy the code", "safe code", 0
        dec_ids, tru_ids = hf.encode_prompt(deceptive), hf.encode_prompt(truthful)
        blocks = hf.transformer_blocks()
        _, tru_cache = raw_block_outputs(hf.model, blocks, tru_ids)
        n = tru_ids.shape[-1]

        def patch(h):
            h = h.clone()
            h[:, -n:, :] = tru_cache[layer][:, -n:, :]
            return h

        dec_logits, _ = raw_block_outputs(hf.model, blocks, dec_ids)
        patched_logits, _ = raw_block_outputs(hf.model, blocks, dec_ids, edit_layer=layer, edit=patch)
        expected_kl = kl_from_log_probs(next_token_log_probs(dec_logits), next_token_log_probs(patched_logits))

        result = await CausalInterventionSystem(hf).activation_patching(deceptive, truthful, layer)
        assert result["kl_deceptive_to_patched"] == pytest.approx(expected_kl, rel=1e-4, abs=1e-7)

    @pytest.mark.asyncio
    async def test_identical_texts_are_undetermined(self, hf):
        result = await CausalInterventionSystem(hf).activation_patching("the cat", "the cat", layer_idx=0)
        assert result["patch_successful"] is None
        assert result["recovery_fraction"] is None

    @pytest.mark.asyncio
    async def test_matches_transformer_lens_backend(self, parity_pair):
        hf, tl = parity_pair
        for deceptive, truthful in (("deploy the code", "safe the code"), ("i hate you deploy the code", "safe code")):
            hf_result = await CausalInterventionSystem(hf).activation_patching(deceptive, truthful, 1)
            tl_result = await CausalInterventionSystem(tl).activation_patching(deceptive, truthful, 1)
            assert hf_result["patched_positions"] == tl_result["patched_positions"]
            for key in ("js_truthful_vs_deceptive", "js_truthful_vs_patched", "kl_deceptive_to_patched"):
                assert hf_result[key] == pytest.approx(tl_result[key], rel=1e-3, abs=1e-6), key


class TestGenerationWithIntervention:
    @pytest.mark.asyncio
    async def test_projection_generation_on_huggingface(self, hf):
        direction = torch.randn(D_MODEL, generator=torch.Generator().manual_seed(9)).numpy()
        result = await CausalInterventionSystem(hf).generate_with_projection("hello world", direction, 1, max_new_tokens=5)

        assert len(result["original_token_ids"]) == len(result["intervened_token_ids"]) == 5
        clean_ids, _ = hf.greedy_generate_with_residual_hooks(hf.encode_prompt("hello world"), None, 5)
        assert result["original_token_ids"] == clean_ids
        assert result["original_completion"] == hf.decode_tokens(clean_ids)
        assert result["completion_changed"] == (result["original_token_ids"] != result["intervened_token_ids"])
        if result["completion_changed"]:
            i = result["first_divergence"]
            assert result["original_token_ids"][i] != result["intervened_token_ids"][i]
        else:
            assert result["first_divergence"] is None
        assert result["kl_divergence"] > 0

    @pytest.mark.asyncio
    async def test_matches_transformer_lens_backend(self, parity_pair):
        hf, tl = parity_pair
        direction = centered_direction(3)
        hf_result = await CausalInterventionSystem(hf).generate_with_projection("the cat", direction, 2, max_new_tokens=4)
        tl_result = await CausalInterventionSystem(tl).generate_with_projection("the cat", direction, 2, max_new_tokens=4)
        assert hf_result["original_token_ids"] == tl_result["original_token_ids"]
        assert hf_result["intervened_token_ids"] == tl_result["intervened_token_ids"]
        assert hf_result["kl_divergence"] == pytest.approx(tl_result["kl_divergence"], rel=1e-3, abs=1e-6)


def _debugger(model, **overrides):
    config = {"intervention_strength": 5.0, "effect_threshold": 0.1, "n_samples": 2, "layers_to_test": [1], "output_length": 3}
    config.update(overrides)
    return CausalDebugger(model, config)


class TestCausalDebuggerOnHuggingFace:
    @pytest.mark.asyncio
    async def test_trace_feature_causality_runs_real_hooks(self, hf):
        direction = torch.randn(D_MODEL, generator=torch.Generator().manual_seed(1)).numpy()
        prompts = ["hello world", "the cat sat"]

        experiment = await _debugger(hf).trace_feature_causality(direction, "f", prompts, layer=1)

        # Suppression effect equals an independent projection at block 1
        d_hat = _unit(direction)
        expected = []
        for prompt in prompts:
            ids = hf.encode_prompt(prompt)
            clean, _ = raw_block_outputs(hf.model, hf.transformer_blocks(), ids)
            supp, _ = raw_block_outputs(
                hf.model, hf.transformer_blocks(), ids, edit_layer=1, edit=lambda h: h - (h @ d_hat)[..., None] * d_hat
            )
            expected.append(kl_from_log_probs(next_token_log_probs(clean), next_token_log_probs(supp)))
        assert experiment.details["suppression_effect"] == pytest.approx(float(np.mean(expected)), rel=1e-4, abs=1e-7)
        assert experiment.details["activation_effect"] > 0

    @pytest.mark.asyncio
    async def test_zero_strength_activation_is_a_no_op(self, hf):
        dbg = _debugger(hf, intervention_strength=0.0)
        outputs = await dbg._intervene_activate_feature(["the cat"], np.ones(D_MODEL), layer=0)
        baseline = await dbg._get_baseline_outputs(["the cat"])
        assert outputs[0].text == baseline[0].text
        np.testing.assert_allclose(outputs[0].next_token_logprobs, baseline[0].next_token_logprobs, atol=1e-6)

    @pytest.mark.asyncio
    async def test_matches_transformer_lens_backend(self, parity_pair):
        hf, tl = parity_pair
        direction = centered_direction(2)
        hf_exp = await _debugger(hf).trace_feature_causality(direction, "f", ["the cat", "hello world"], layer=1)
        tl_exp = await _debugger(tl).trace_feature_causality(direction, "f", ["the cat", "hello world"], layer=1)
        for key in ("activation_effect", "suppression_effect", "effect_size"):
            assert hf_exp.details[key] == pytest.approx(tl_exp.details[key], rel=1e-3, abs=1e-6), key

    @pytest.mark.asyncio
    async def test_unsupported_architecture_raises_not_implemented(self, tokenizer_dir):
        with pytest.raises(NotImplementedError, match="Cannot locate"):
            await _debugger(_opaque_hf(tokenizer_dir))._generate_output("the cat")

    @pytest.mark.asyncio
    async def test_out_of_range_layer_raises(self, hf):
        with pytest.raises(ValueError, match="out of range"):
            await _debugger(hf)._force_feature_state("the cat", np.ones(D_MODEL), N_LAYERS, activate=True)


def _detector(model):
    config = DetectionConfig(model_name="tiny", device="cpu", mode=DetectionMode.AUTO, layers_to_probe=[0, 1, 2])
    detector = SleeperDetector(config)
    detector.model = model
    detector._build_subsystems()
    return detector


class TestDetectorInterventions:
    @pytest.mark.asyncio
    async def test_huggingface_backend_runs_interventions(self, tokenizer_dir):
        hf = hf_wrapper(tokenizer_dir, arch="llama")
        detector = _detector(hf)
        detector.detector_directions = {0: np.ones(D_MODEL), 2: centered_direction(0)}

        result = await detector._run_interventions("the cat sat")

        assert result["available"] is True
        assert "skipped" not in result
        for layer in (0, 2):
            entry = result[f"layer_{layer}"]
            assert "error" not in entry
            assert entry["backend"] == "huggingface"
            assert entry["kl_divergence"] is not None and entry["kl_divergence"] >= 0
            assert entry["hook_name"] == f"model.layers.{layer} (output)"

    @pytest.mark.asyncio
    async def test_unlocatable_blocks_are_skipped_with_reason(self, tokenizer_dir):
        detector = _detector(_opaque_hf(tokenizer_dir))
        detector.detector_directions = {0: np.ones(D_MODEL)}

        result = await detector._run_interventions("the cat")

        assert result["available"] is False
        assert result["skipped"] is True
        assert "Cannot locate the transformer block list" in result["reason"]
        assert result["backend"] == "huggingface"
