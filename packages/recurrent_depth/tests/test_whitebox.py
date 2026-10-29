import dataclasses
import json

import numpy as np
import pytest

from recurrent_depth import config_inspect, dynamics, graybox, weights
from recurrent_depth.safetensors_io import load_tensor, read_checkpoint, read_header, write_safetensors

# ---------------------------------------------------------------------------
# config inspection (field names follow the published checkpoints)
# ---------------------------------------------------------------------------

HUGINN = {
    "model_type": "huginn_raven",
    "architectures": ["RavenForCausalLM"],
    "auto_map": {"AutoModelForCausalLM": "raven_modeling_minimal.RavenForCausalLM"},
    "n_embd": 5280,
    "n_layers_in_prelude": 2,
    "n_layers_in_recurrent_block": 4,
    "n_layers_in_coda": 2,
    "mean_recurrence": 32,
    "mean_backprop_depth": 8,
}
OURO = {
    "model_type": "ouro",
    "auto_map": {"AutoModelForCausalLM": "modeling_ouro.OuroForCausalLM"},
    "num_hidden_layers": 24,
    "hidden_size": 2048,
    "total_ut_steps": 4,
    "early_exit_threshold": 1.0,
}
ALBERT = {"model_type": "albert", "num_hidden_layers": 12, "num_hidden_groups": 1, "inner_group_num": 1}
LLAMA = {"model_type": "llama", "num_hidden_layers": 32, "hidden_size": 4096, "hidden_act": "silu"}
MIXTRAL = {"model_type": "mixtral", "num_hidden_layers": 32, "num_local_experts": 8, "num_experts_per_tok": 2}
CUSTOM = {"model_type": "mystery_lm", "auto_map": {"AutoModel": "x.Y"}, "num_hidden_layers": 16}


def test_huginn_config():
    r = config_inspect.inspect_config(HUGINN)
    assert r.outcome == 1.0 and r.declares_recurrence
    assert r.stored_layers == 8 and r.logical_depth == 132
    assert r.weight_reuse_ratio == pytest.approx(16.5)


def test_ouro_config():
    r = config_inspect.inspect_config(OURO)
    assert r.outcome == 1.0 and r.adaptive_exit
    assert r.stored_layers == 24 and r.logical_depth == 96


def test_albert_shared_layers():
    r = config_inspect.inspect_config(ALBERT)
    assert r.outcome == 1.0 and r.weight_reuse_ratio == 12
    unshared = dict(ALBERT, num_hidden_groups=12)
    assert config_inspect.inspect_config(unshared).weight_reuse_ratio == 1


def test_standard_and_moe_configs():
    r = config_inspect.inspect_config(LLAMA)
    assert r.outcome == 0.0 and not r.declares_recurrence and not r.moe
    m = config_inspect.inspect_config(MIXTRAL)
    assert m.outcome == 0.0 and m.moe
    assert any("mixture-of-experts" in n for n in m.notes)


def test_custom_code_is_inconclusive():
    r = config_inspect.inspect_config(CUSTOM)
    assert r.outcome == 0.5 and r.custom_code
    assert r.signals() == {"config_recurrence": 0.5}


def test_config_file_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(HUGINN))
    assert config_inspect.inspect_config_file(p).outcome == 1.0


# ---------------------------------------------------------------------------
# safetensors reader and weight sharing
# ---------------------------------------------------------------------------


def _stack(n_layers, d=48, mode="independent", seed=0, rank=2):
    rng = np.random.default_rng(seed)
    base = {"q": rng.normal(size=(d, d)).astype(np.float32), "mlp": rng.normal(size=(2 * d, d)).astype(np.float32)}
    tensors = {"model.embed_tokens.weight": rng.normal(size=(100, d)).astype(np.float32)}
    for i in range(n_layers):
        for name, w in base.items():
            if mode == "independent":
                w_i = rng.normal(size=w.shape).astype(np.float32)
            elif mode == "tied":
                w_i = w
            elif mode == "lowrank":
                u = rng.normal(size=(w.shape[0], rank))
                v = rng.normal(size=(rank, w.shape[1]))
                w_i = (w + 0.3 * u @ v / np.sqrt(rank)).astype(np.float32)
            else:
                raise ValueError(mode)
            tensors[f"model.layers.{i}.{name}.weight"] = w_i
        tensors[f"model.layers.{i}.norm.weight"] = np.ones(d, dtype=np.float32)
    return tensors


def test_safetensors_roundtrip_and_bf16(tmp_path):
    p = tmp_path / "a.safetensors"
    arr = np.arange(12, dtype=np.float32).reshape(3, 4)
    write_safetensors(p, {"x": arr, "h": arr.astype(np.float16)})
    info = read_header(p)
    np.testing.assert_array_equal(load_tensor(info["x"]), arr)
    np.testing.assert_array_equal(load_tensor(info["h"]), arr.astype(np.float16))
    # hand-build a BF16 tensor: the top 16 bits of float32
    bf = (arr.view(np.uint32) >> 16).astype(np.uint16)
    q = tmp_path / "b.safetensors"
    write_safetensors(q, {"y": bf})
    hdr = dataclasses.replace(read_header(q)["y"], dtype="BF16")
    np.testing.assert_allclose(load_tensor(hdr), arr, rtol=1e-2)


def test_sharded_checkpoint(tmp_path):
    t = _stack(4)
    names = sorted(t)
    half = len(names) // 2
    write_safetensors(tmp_path / "s1.safetensors", {k: t[k] for k in names[:half]})
    write_safetensors(tmp_path / "s2.safetensors", {k: t[k] for k in names[half:]})
    wm = {k: ("s1.safetensors" if i < half else "s2.safetensors") for i, k in enumerate(names)}
    (tmp_path / "model.safetensors.index.json").write_text(json.dumps({"weight_map": wm}))
    assert set(read_checkpoint(tmp_path)) == set(names)


@pytest.mark.parametrize("use_hash", [True, False])
def test_independent_layers_show_no_sharing(tmp_path, use_hash):
    p = tmp_path / "m.safetensors"
    write_safetensors(p, _stack(6, mode="independent"))
    rep = weights.analyze_weights(read_header(p), declared_layers=6, use_hash=use_hash)
    assert rep.stored_slots == 6 and rep.distinct_slots == 6
    assert rep.shared_layer_fraction == 0.0 and rep.weight_reuse_ratio == 1.0
    # uncorrelated equal-norm matrices are about sqrt(2) apart
    assert all(1.2 < d < 1.6 for d in rep.adjacent_rel_distance["model.layers"])


def test_tied_layers_detected(tmp_path):
    p = tmp_path / "m.safetensors"
    write_safetensors(p, _stack(6, mode="tied"))
    rep = weights.analyze_weights(read_header(p), declared_layers=6)
    assert rep.distinct_slots == 1 and rep.shared_layer_fraction == 1.0
    assert rep.weight_reuse_ratio == 6.0


def test_lowrank_sharing_detected(tmp_path):
    p = tmp_path / "m.safetensors"
    write_safetensors(p, _stack(4, mode="lowrank"))
    rep = weights.analyze_weights(read_header(p), declared_layers=4)
    assert rep.distinct_slots == 4
    assert len(rep.lowrank_pairs) == 6 and rep.shared_layer_fraction == 1.0


def test_split_layer_name():
    assert weights.split_layer_name("transformer.core_block.3.attn.Wqkv.weight") == (
        "transformer.core_block",
        3,
        "attn.Wqkv.weight",
    )
    assert weights.split_layer_name("lm_head.weight") is None


# ---------------------------------------------------------------------------
# hidden-state dynamics
# ---------------------------------------------------------------------------


def _contracting_trajectory(steps=24, tokens=8, d=32, rate=0.6, seed=0):
    rng = np.random.default_rng(seed)
    fixed = rng.normal(size=(tokens, d))
    h = [fixed + rng.normal(size=(tokens, d))]
    for _ in range(steps - 1):
        h.append(fixed + rate * (h[-1] - fixed))
    return np.stack(h)


def _random_walk(steps=24, tokens=8, d=32, seed=0):
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.normal(size=(steps, tokens, d)), axis=0) + 10.0


def test_contraction_separates_fixed_point_from_drift():
    assert dynamics.contraction(_contracting_trajectory(rate=0.6)) == pytest.approx(0.6, rel=0.05)
    assert dynamics.contraction(_random_walk()) > 0.85


def test_cka_and_cosine_properties():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(50, 16))
    q, _ = np.linalg.qr(rng.normal(size=(16, 16)))
    assert dynamics.linear_cka(x, x @ q * 3.0) == pytest.approx(1.0)
    assert dynamics.linear_cka(x, rng.normal(size=(50, 16))) < 0.6
    cm = dynamics.cosine_matrix(_random_walk())
    assert np.allclose(np.diag(cm), 1.0)
    ck = dynamics.cka_matrix(_random_walk(steps=5))
    assert ck.shape == (5, 5) and np.allclose(ck, ck.T)


def test_periodicity_finds_repeated_block():
    rng = np.random.default_rng(2)
    block = rng.normal(size=(4, 8, 32))
    h = np.concatenate([block + 0.05 * rng.normal(size=block.shape) for _ in range(4)])
    lag, excess = dynamics.similarity_periodicity(dynamics.cosine_matrix(h))
    assert lag == 4 and excess > 0.3
    _, flat = dynamics.similarity_periodicity(dynamics.cosine_matrix(rng.normal(size=(16, 8, 32))))
    assert flat < 0.1


def test_logit_lens_settling():
    h = _contracting_trajectory(steps=20, rate=0.5)
    unembed = np.random.default_rng(3).normal(size=(32, 50))
    kl = dynamics.logit_lens_kl(h, unembed)
    assert kl.shape == (19, 8)
    assert kl[-1].max() < kl[0].min()
    settle = dynamics.settle_steps(kl, threshold=1e-3)
    assert (settle < 19).all()


def test_dynamics_signals_keys():
    sig = dynamics.dynamics_signals(_contracting_trajectory())
    assert set(sig) == {"state_contraction", "similarity_periodicity"}


def test_bad_shape_rejected():
    with pytest.raises(ValueError):
        dynamics.step_change(np.zeros((1, 3, 4)))


# ---------------------------------------------------------------------------
# gray-box helpers
# ---------------------------------------------------------------------------


def test_estimate_rank_recovers_width():
    rng = np.random.default_rng(4)
    hidden, vocab, n = 24, 400, 120
    w = rng.normal(size=(hidden, vocab))
    states = rng.normal(size=(n, hidden))
    logits = states @ w
    logprobs = (
        logits - np.log(np.exp(logits - logits.max(1, keepdims=True)).sum(1, keepdims=True)) - logits.max(1, keepdims=True)
    )
    rank, spectrum = graybox.estimate_rank(logprobs)
    assert rank in (hidden, hidden + 1)
    assert spectrum[0] > spectrum[-1]


def test_compute_capacity_ratio():
    assert graybox.compute_capacity_ratio(8e9, 2e9) == 4.0
    with pytest.raises(ValueError):
        graybox.compute_capacity_ratio(0, 1)
