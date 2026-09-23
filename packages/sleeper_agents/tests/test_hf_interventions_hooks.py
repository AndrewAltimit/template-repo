"""Backend-neutral residual-stream hook API on tiny offline HuggingFace / TransformerLens models."""

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

from sleeper_agents.interventions.causal import make_projection_hook
from sleeper_agents.models.model_interface import (
    HuggingFaceModel,
    ResidualHooksUnsupportedError,
    TransformerLensModel,
    as_residual_hook_model,
    find_transformer_blocks,
    locate_transformer_blocks,
)

ARCHS = sorted(BLOCK_PATHS)
TEXT = "the cat sat on the mat"


@pytest.fixture(scope="module")
def tokenizer_dir(tmp_path_factory):
    directory = tmp_path_factory.mktemp("tok")
    build_tokenizer(directory)
    return directory


@pytest.fixture(params=ARCHS)
def hf(request, tokenizer_dir):
    return hf_wrapper(tokenizer_dir, arch=request.param)


def _hook_count(blocks):
    return sum(len(block._forward_hooks) for block in blocks)


def _unit(direction):
    d = torch.as_tensor(direction, dtype=torch.float32)
    return d / d.norm()


class TestBlockLocation:
    @pytest.mark.parametrize("arch", ARCHS)
    def test_known_paths(self, tokenizer_dir, arch):
        wrapper = hf_wrapper(tokenizer_dir, arch=arch)
        path, blocks = locate_transformer_blocks(wrapper.model, N_LAYERS)
        assert path == BLOCK_PATHS[arch]
        assert len(blocks) == N_LAYERS
        assert wrapper.residual_hook_site(1) == f"{BLOCK_PATHS[arch]}.1 (output)"

    def test_peft_style_wrapper_is_unwrapped(self, tokenizer_dir):
        inner = hf_wrapper(tokenizer_dir, arch="llama").model

        class PeftLike(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.base_model = torch.nn.Module()
                self.base_model.model = inner

            def get_base_model(self):
                return inner

        assert find_transformer_blocks(PeftLike(), N_LAYERS) is inner.model.layers

    def test_unknown_architecture_raises(self):
        class Opaque(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.a = torch.nn.ModuleList([torch.nn.Linear(2, 2) for _ in range(N_LAYERS)])
                self.b = torch.nn.ModuleList([torch.nn.Linear(2, 2) for _ in range(N_LAYERS)])

        with pytest.raises(ResidualHooksUnsupportedError, match="Cannot locate the transformer block list"):
            find_transformer_blocks(Opaque(), N_LAYERS)
        with pytest.raises(ResidualHooksUnsupportedError):
            find_transformer_blocks(object(), N_LAYERS)

    def test_block_count_mismatch_is_not_accepted(self, tokenizer_dir):
        model = hf_wrapper(tokenizer_dir, arch="gpt2").model
        with pytest.raises(ResidualHooksUnsupportedError):
            find_transformer_blocks(model, N_LAYERS + 1)


class TestHuggingFaceResidualHooks:
    def test_clean_run_matches_plain_forward_and_capture_matches_blocks(self, hf):
        ids = hf.encode_prompt(TEXT)
        expected_logits, expected = raw_block_outputs(hf.model, hf.transformer_blocks(), ids)

        logits, captured = hf.run_with_residual_hooks(ids, capture_layers=list(range(N_LAYERS)))

        torch.testing.assert_close(logits, expected_logits, atol=1e-5, rtol=1e-5)
        for layer in range(N_LAYERS):
            torch.testing.assert_close(captured[layer], expected[layer], atol=1e-5, rtol=1e-5)
        # Same convention as get_activations (layer L = hidden_states[L + 1] / final block output)
        acts = hf.get_activations([TEXT], layers=list(range(N_LAYERS)))
        for layer in range(N_LAYERS):
            torch.testing.assert_close(captured[layer], acts[f"layer_{layer}"], atol=1e-5, rtol=1e-5)

    @pytest.mark.parametrize("layer", [0, N_LAYERS - 1])
    def test_projection_makes_residual_orthogonal(self, hf, layer):
        direction = torch.randn(D_MODEL, generator=torch.Generator().manual_seed(4)).numpy() * 5.0
        d_hat = _unit(direction)
        ids = hf.encode_prompt(TEXT)

        clean_logits, clean = hf.run_with_residual_hooks(ids, capture_layers=[layer])
        logits, captured = hf.run_with_residual_hooks(ids, {layer: make_projection_hook(direction)}, capture_layers=[layer])

        assert (clean[layer] @ d_hat).abs().max().item() > 1e-2  # there was a component to remove
        assert (captured[layer] @ d_hat).abs().max().item() < 1e-4
        # The edit reaches the output, and matches an independent torch-hook implementation
        assert not torch.allclose(logits, clean_logits, atol=1e-5)
        ref_logits, _ = raw_block_outputs(
            hf.model,
            hf.transformer_blocks(),
            ids,
            edit_layer=layer,
            edit=lambda h: h - (h @ d_hat)[..., None] * d_hat,
        )
        torch.testing.assert_close(logits, ref_logits, atol=1e-5, rtol=1e-5)

    def test_hooks_removed_after_success_and_when_forward_raises(self, hf):
        blocks = hf.transformer_blocks()
        ids = hf.encode_prompt(TEXT)
        baseline = _hook_count(blocks)

        hf.run_with_residual_hooks(ids, {0: lambda r: r * 2}, capture_layers=[1, 2])
        assert _hook_count(blocks) == baseline

        def boom(resid):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            hf.run_with_residual_hooks(ids, {0: lambda r: r, 1: boom}, capture_layers=[2])
        assert _hook_count(blocks) == baseline

        with pytest.raises(ValueError, match="changed the shape"):
            hf.run_with_residual_hooks(ids, {1: lambda r: r[:, :1]})
        assert _hook_count(blocks) == baseline

        with pytest.raises(KeyError):
            with hf.residual_hooks({0: lambda r: None, 2: lambda r: None}):
                assert _hook_count(blocks) == baseline + 2
                raise KeyError("body failed")
        assert _hook_count(blocks) == baseline

    def test_out_of_range_layer_raises(self, hf):
        ids = hf.encode_prompt(TEXT)
        with pytest.raises(ValueError, match="out of range"):
            hf.run_with_residual_hooks(ids, {N_LAYERS: lambda r: r})
        with pytest.raises(ValueError, match="out of range"):
            with hf.residual_hooks({-1: lambda r: r}):
                pass
        assert _hook_count(hf.transformer_blocks()) == 0

    def test_hook_that_never_fires_is_an_error(self, tokenizer_dir):
        class NoFire(HuggingFaceModel):
            def _run_with_block_hooks(self, input_ids, hooks):
                return self._forward(input_ids, torch.ones_like(input_ids), use_cache=False)

        wrapper = hf_wrapper(tokenizer_dir, cls=NoFire)
        with pytest.raises(RuntimeError, match="did not fire"):
            wrapper.run_with_residual_hooks(wrapper.encode_prompt(TEXT), {1: lambda r: r * 0})

    def test_unknown_architecture_raises_unsupported(self, tokenizer_dir):
        wrapper = hf_wrapper(tokenizer_dir)
        wrapper.model.transformer.h = torch.nn.Sequential(*wrapper.model.transformer.h)  # no longer a ModuleList
        with pytest.raises(ResidualHooksUnsupportedError):
            wrapper.require_residual_hooks()
        with pytest.raises(ResidualHooksUnsupportedError):
            wrapper.run_with_residual_hooks(torch.tensor([[4, 5]]), {0: lambda r: r})

    def test_fp16_residual_edit_keeps_dtype(self, tokenizer_dir):
        wrapper = hf_wrapper(tokenizer_dir, arch="llama")
        wrapper.model = wrapper.model.to(torch.bfloat16)
        direction = centered_direction(1)
        ids = wrapper.encode_prompt(TEXT)
        _, captured = wrapper.run_with_residual_hooks(ids, {1: make_projection_hook(direction)}, capture_layers=[1])
        assert captured[1].dtype == torch.bfloat16
        assert (captured[1].float() @ _unit(direction)).abs().max().item() < 5e-2

    def test_greedy_generation_matches_plain_argmax_decoding(self, hf):
        ids = hf.encode_prompt("hello world")
        new_ids, first_lp = hf.greedy_generate_with_residual_hooks(ids, None, max_new_tokens=4)

        # Reference: argmax decoding with the plain model (KV cache, no hooks, no EOS stop)
        ref, past, step_ids = [], None, ids
        with torch.no_grad():
            for step in range(4):
                out = hf.model(input_ids=step_ids, past_key_values=past, use_cache=True)
                if step == 0:
                    expected_lp = torch.log_softmax(out.logits[0, -1].float(), dim=-1)
                past = out.past_key_values
                ref.append(int(out.logits[0, -1].argmax()))
                step_ids = torch.tensor([[ref[-1]]])
        assert new_ids == ref
        torch.testing.assert_close(first_lp, expected_lp, atol=1e-5, rtol=1e-5)

    def test_greedy_generation_applies_hooks_every_step(self, hf):
        ids = hf.encode_prompt("hello world")
        calls = []

        def record(resid):
            calls.append(resid.shape[1])

        hf.greedy_generate_with_residual_hooks(ids, {0: record}, max_new_tokens=3)
        n = ids.shape[1]
        assert calls == [n, n + 1, n + 2]  # full sequence re-run, hook sees every position


class TestBackendParity:
    """Same tiny GPT-2 weights served by HuggingFace and by a TransformerBridge."""

    @pytest.fixture(scope="class")
    def pair(self, tokenizer_dir):
        return hf_wrapper(tokenizer_dir, seed=7, cls=BosHuggingFaceModel), tl_wrapper(tokenizer_dir, seed=7)

    def test_same_tokens_and_logits(self, pair):
        hf, tl = pair
        ids = tl.encode_prompt(TEXT)
        assert torch.equal(hf.encode_prompt(TEXT), ids)
        hf_logits, _ = hf.run_with_residual_hooks(ids)
        tl_logits, _ = tl.run_with_residual_hooks(ids)
        torch.testing.assert_close(
            torch.log_softmax(hf_logits.float(), -1), torch.log_softmax(tl_logits.float(), -1), atol=1e-4, rtol=1e-4
        )

    def test_captured_layers_agree_up_to_centering(self, pair):
        # TransformerLens compatibility mode centers the residual stream (center_writing_weights)
        hf, tl = pair
        ids = tl.encode_prompt(TEXT)
        layers = list(range(N_LAYERS))
        _, hf_res = hf.run_with_residual_hooks(ids, capture_layers=layers)
        _, tl_res = tl.run_with_residual_hooks(ids, capture_layers=layers)
        for layer in layers:
            centered = hf_res[layer] - hf_res[layer].mean(dim=-1, keepdim=True)
            torch.testing.assert_close(tl_res[layer], centered, atol=1e-4, rtol=1e-4)

    @pytest.mark.parametrize("layer", [0, N_LAYERS - 1])
    def test_projection_gives_same_distribution(self, pair, layer):
        hf, tl = pair
        ids = tl.encode_prompt(TEXT)
        hook = {layer: make_projection_hook(centered_direction(layer))}
        hf_logits, _ = hf.run_with_residual_hooks(ids, hook)
        tl_logits, _ = tl.run_with_residual_hooks(ids, hook)
        torch.testing.assert_close(
            torch.log_softmax(hf_logits.float(), -1), torch.log_softmax(tl_logits.float(), -1), atol=1e-4, rtol=1e-4
        )


class TestTransformerLensAdapter:
    def test_bare_bridge_is_wrapped_and_hooks_use_resid_post(self, tokenizer_dir):
        bridge = tl_wrapper(tokenizer_dir).model
        adapter = as_residual_hook_model(bridge)
        assert isinstance(adapter, TransformerLensModel) and adapter.model is bridge
        assert adapter.residual_hook_site(2) == "blocks.2.hook_resid_post"

        ids = bridge.to_tokens(TEXT)
        _, captured = adapter.run_with_residual_hooks(ids, capture_layers=[1])
        _, cache = bridge.run_with_cache(ids)
        torch.testing.assert_close(captured[1], cache["blocks.1.hook_resid_post"], atol=1e-5, rtol=1e-5)

    def test_objects_without_hooks_are_rejected(self):
        class FakeHF:
            backend = "huggingface"

        with pytest.raises(ResidualHooksUnsupportedError, match="backend=huggingface"):
            as_residual_hook_model(FakeHF())
