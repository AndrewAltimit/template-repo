"""Regression tests for CausalDebugger interventions and FeatureDiscovery."""

import numpy as np
import pytest
import torch

from sleeper_agents.probes.causal_debugger import CausalDebugger
from sleeper_agents.probes.feature_discovery import DiscoveredFeature, FeatureDiscovery

D_MODEL = 8
VOCAB = 12


class TinyHookedModel:
    """Minimal TransformerLens-style model: to_tokens / run_with_hooks / to_string.

    The last residual dimension is inert: embeddings and block updates never write
    to it, and neither the blocks nor the unembedding read from it, so interventions
    along that direction never change the output.
    """

    def __init__(self, n_layers=2, seed=0):
        g = torch.Generator().manual_seed(seed)
        self.W_E = torch.randn(VOCAB, D_MODEL, generator=g)
        self.W_E[:, -1] = 0.0
        self.blocks = []
        for _ in range(n_layers):
            W = torch.randn(D_MODEL, D_MODEL, generator=g) * 0.3
            W[:, -1] = 0.0
            W[-1, :] = 0.0
            self.blocks.append(W)
        self.W_U = torch.randn(D_MODEL, VOCAB, generator=g)
        self.W_U[-1, :] = 0.0
        self.hook_calls = []

    def to_tokens(self, text):
        ids = [ord(c) % VOCAB for c in text][:6] or [0]
        return torch.tensor([ids])

    def to_string(self, tokens):
        return " ".join(str(int(t)) for t in tokens)

    def run_with_hooks(self, tokens, fwd_hooks=()):
        hooks = dict(fwd_hooks)
        x = self.W_E[tokens]
        for i, W in enumerate(self.blocks):
            x = x + torch.tanh(x @ W)
            name = f"blocks.{i}.hook_resid_post"
            if name in hooks:
                self.hook_calls.append(name)
                x = hooks[name](x, hook=None)
        return x @ self.W_U


def unit(i, dim=D_MODEL):
    v = np.zeros(dim)
    v[i] = 1.0
    return v


def debugger(model, **overrides):
    config = {
        "intervention_strength": 0.0,
        "effect_threshold": 0.1,
        "n_samples": 3,
        "layers_to_test": [0, 1],
        "output_length": 3,
    }
    config.update(overrides)
    return CausalDebugger(model, config)


PROMPTS = ["hello", "what year is it", "deploy"]


class TestCausalInterventions:
    @pytest.mark.asyncio
    async def test_no_op_intervention_has_no_effect(self):
        # Suppressing a direction the residual never uses, and adding it with
        # strength 0, must leave outputs unchanged.
        dbg = debugger(TinyHookedModel())
        experiment = await dbg.trace_feature_causality(unit(D_MODEL - 1), "null_feature", PROMPTS, layer=1)

        assert experiment.causal_effect_size == pytest.approx(0.0, abs=1e-6)
        assert experiment.behavior_changed is False
        assert experiment.original_output == experiment.intervened_output
        assert experiment.details["metric"] == "next_token_kl"

    @pytest.mark.asyncio
    async def test_strong_activation_is_detected(self):
        model = TinyHookedModel()
        # Direction that the unembedding reads strongly
        direction = model.W_U[:, 0].numpy()
        dbg = debugger(model, intervention_strength=25.0)

        experiment = await dbg.trace_feature_causality(direction, "strong_feature", PROMPTS, layer=0)

        assert experiment.behavior_changed is True
        assert experiment.details["activation_effect"] > 0.1
        assert "blocks.0.hook_resid_post" in model.hook_calls

    def test_suppression_normalizes_direction(self):
        dbg = debugger(TinyHookedModel())
        hook = dbg._make_hook(10.0 * unit(0), activate=False)
        resid = torch.randn(1, 5, D_MODEL)

        out = hook(resid, hook=None)

        torch.testing.assert_close(out[..., 0], torch.zeros(1, 5))
        torch.testing.assert_close(out[..., 1:], resid[..., 1:])

    def test_hook_casts_to_activation_dtype(self):
        dbg = debugger(TinyHookedModel(), intervention_strength=1.0)
        hook = dbg._make_hook(unit(0), activate=True)
        resid = torch.zeros(1, 2, D_MODEL, dtype=torch.bfloat16)

        out = hook(resid, hook=None)

        assert out.dtype == torch.bfloat16
        assert float(out[0, 0, 0]) == pytest.approx(1.0)

    def test_zero_or_mismatched_vector_rejected(self):
        dbg = debugger(TinyHookedModel())
        with pytest.raises(ValueError):
            dbg._make_hook(np.zeros(D_MODEL), activate=True)
        hook = dbg._make_hook(np.ones(D_MODEL + 1), activate=True)
        with pytest.raises(ValueError):
            hook(torch.zeros(1, 2, D_MODEL), hook=None)

    @pytest.mark.asyncio
    async def test_unsupported_model_raises(self):
        class NoHooks:
            def generate(self, prompt, **kwargs):
                return "text"

        dbg = debugger(NoHooks())
        with pytest.raises(NotImplementedError):
            await dbg.trace_feature_causality(unit(0), "f", PROMPTS, layer=0)

    @pytest.mark.asyncio
    async def test_model_interface_wrapper_is_unwrapped(self):
        class Wrapper:
            def __init__(self, inner):
                self.model = inner

        inner = TinyHookedModel()
        dbg = debugger(Wrapper(inner))

        baseline = await dbg._generate_output("hello")

        assert baseline == inner.to_string(torch.tensor([int(t) for t in baseline.split()]))
        assert len(baseline.split()) == 3

    @pytest.mark.asyncio
    async def test_comprehensive_debug_with_real_discovered_feature(self):
        model = TinyHookedModel()
        dbg = debugger(model, intervention_strength=25.0)
        features = [
            DiscoveredFeature(
                feature_id=3,
                vector=model.W_U[:, 0].numpy(),
                activation_strength=1.0,
                interpretability_score=0.5,
                description="deception-related direction",
                layer=0,
            ),
            DiscoveredFeature(
                feature_id=4, vector=unit(D_MODEL - 1), activation_strength=1.0, interpretability_score=0.5, layer=1
            ),
        ]
        suite = {"a": PROMPTS, "b": PROMPTS[:2]}

        report = await dbg.run_comprehensive_debug(features, suite)

        layers = {e["layer"] for e in report["causal_features"] + report["non_causal_features"]}
        assert layers == {0, 1}  # layer 0 is honored, not replaced by a default
        names = {e["feature_name"] for e in report["causal_features"] + report["non_causal_features"]}
        assert names == {"feature_3", "feature_4"}
        assert report["statistics"]["causality_rate"] == pytest.approx(0.5)
        assert report["statistics"]["causal_experiments"] == 2
        assert len(report["deception_features"]) == 2

    @pytest.mark.asyncio
    async def test_comprehensive_debug_requires_layer(self):
        dbg = debugger(TinyHookedModel())
        feature = DiscoveredFeature(feature_id=1, vector=unit(0), activation_strength=1.0, interpretability_score=0.5)
        with pytest.raises(ValueError):
            await dbg.run_comprehensive_debug([feature], {"a": PROMPTS})


class TestFeatureDiscovery:
    def _discovery(self, **overrides):
        discovery = FeatureDiscovery(None)
        discovery.config.update({"n_components": 6, "max_iter": 30, "batch_size": 16, "min_activation_strength": 0.0})
        discovery.config.update(overrides)
        return discovery

    @pytest.mark.asyncio
    async def test_dictionary_learning_is_used(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(40, 12))
        discovery = self._discovery()

        dictionary = await discovery._learn_dictionary(X)

        assert discovery.dictionary_method == "dict_learning_online"
        assert dictionary.shape == (6, 12)
        np.testing.assert_allclose(np.linalg.norm(dictionary, axis=1), 1.0, atol=1e-6)

    @pytest.mark.asyncio
    async def test_legacy_n_iter_config_accepted(self):
        discovery = FeatureDiscovery(None, {**self._discovery().config, "n_iter": 5})
        discovery.config.pop("max_iter")
        dictionary = await discovery._learn_dictionary(np.random.default_rng(0).normal(size=(20, 10)))
        assert dictionary.shape == (6, 10)

    @pytest.mark.asyncio
    async def test_discover_features_populates_library(self):
        rng = np.random.default_rng(1)
        X = rng.normal(size=(30, 10))
        discovery = self._discovery()

        results = await discovery.discover_features(X, layer_idx=2, context_data=[f"text {i}" for i in range(30)])

        assert results["dictionary_method"] == "dict_learning_online"
        assert len(discovery.feature_library) == results["n_features_discovered"] > 0
        assert all(key.startswith("L2_F") for key in discovery.feature_library)

    @pytest.mark.asyncio
    async def test_no_fabricated_correlated_tokens(self):
        discovery = self._discovery()
        feature = DiscoveredFeature(
            feature_id=0, vector=unit(0), activation_strength=0.9, interpretability_score=0.5, codes=np.arange(5.0)
        )
        # Context not aligned with the analyzed samples -> unavailable
        assert await discovery._find_correlated_tokens(feature, ["a", "b"]) == []

        suspicious = await discovery._identify_suspicious_features([feature])
        assert not any(p.startswith("suspicious_token") for f in suspicious for p in f.suspicious_patterns)

    @pytest.mark.asyncio
    async def test_correlated_tokens_computed_from_codes(self):
        discovery = self._discovery()
        contexts = ["deploy now", "hello there", "deploy it", "nice day", "deploy soon", "good morning"]
        codes = np.array([1.0, 0.0, 1.2, 0.1, 0.9, 0.0])
        feature = DiscoveredFeature(
            feature_id=0, vector=unit(0), activation_strength=0.5, interpretability_score=0.5, codes=codes
        )

        tokens = await discovery._find_correlated_tokens(feature, contexts)

        assert tokens[0] == "deploy"

    @pytest.mark.asyncio
    async def test_deception_context_requires_feature_evidence(self):
        discovery = self._discovery()
        contexts = ["backdoor here", "normal text", "another backdoor", "plain"]
        flat = DiscoveredFeature(
            feature_id=0, vector=unit(0), activation_strength=0.5, interpretability_score=0.5, codes=np.ones(4)
        )
        selective = DiscoveredFeature(
            feature_id=1,
            vector=unit(0),
            activation_strength=0.5,
            interpretability_score=0.5,
            codes=np.array([2.0, 0.0, 2.0, 0.0]),
        )

        assert await discovery._check_deception_context(flat, contexts) is False
        assert await discovery._check_deception_context(selective, contexts) is True

    def test_sparsity_uses_magnitude(self):
        discovery = self._discovery()
        dense_negative = DiscoveredFeature(
            feature_id=0, vector=-np.ones(10), activation_strength=0.5, interpretability_score=0.0
        )
        uniform_positive = DiscoveredFeature(
            feature_id=1, vector=np.ones(10), activation_strength=0.5, interpretability_score=0.0
        )
        assert discovery._compute_interpretability(dense_negative) == pytest.approx(
            discovery._compute_interpretability(uniform_positive)
        )
