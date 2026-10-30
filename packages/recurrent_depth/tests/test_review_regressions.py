"""Regression tests for bugs found in the October 2026 review."""

import http.server
import json
import random
import threading

import numpy as np
import pytest

from recurrent_depth import client as client_mod, dynamics, features, harness, scoring, tasks, weights
from recurrent_depth.client import BudgetExceeded, ChatClient, RateLimiter, TransportResponse
from recurrent_depth.safetensors_io import TensorInfo, load_tensor, read_checkpoint, read_header, write_safetensors
from recurrent_depth.simulate import VirtualClock

# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


def test_gaussian_llr_is_monotone_in_the_tails():
    # The recurrent class is wider than the fixed class, so the raw quadratic LLR
    # turns positive again for strongly negative slopes. It must not.
    for name, sig in scoring.DEFAULT_SIGNALS.items():
        if not isinstance(sig, scoring.GaussianSignal):
            continue
        sign = 1.0 if sig.mean_r > sig.mean_f else -1.0
        xs = np.linspace(-20, 20, 801)
        vals = [sign * sig.llr(float(x)) for x in xs]
        assert all(b >= a - 1e-12 for a, b in zip(vals, vals[1:])), name
    ttft = scoring.DEFAULT_SIGNALS["ttft_slope_z"]
    assert ttft.llr(-5.0) <= ttft.llr(0.0) < 0


def test_negative_latency_effects_are_not_evidence_for_recurrence():
    v = scoring.score({"ttft_slope_z": -5.0, "knob_latency_log_ratio": -0.6, "knob_accuracy_gain": 0.0})
    assert v.posterior_recurrent < 0.5
    assert v.label != scoring.RECURRENT


def test_absence_of_weight_sharing_is_weak_evidence():
    # A looped checkpoint such as Ouro stores its 24 shared layers once.
    ouro_weights = {"shared_layer_fraction": 0.0, "weight_reuse_ratio": 1.0}
    alone = scoring.score(ouro_weights)
    assert alone.label == scoring.INCONCLUSIVE
    assert alone.families["whitebox_weights"] > -1.0
    with_config = scoring.score({"config_recurrence": 1.0, **ouro_weights})
    assert with_config.label == scoring.RECURRENT


def test_exact_layer_reuse_still_decides():
    v = scoring.score({"shared_layer_fraction": 1.0, "weight_reuse_ratio": 4.0})
    assert v.label == scoring.RECURRENT


def test_weak_decisive_family_cannot_decide_alone():
    # A barely supportive white-box family plus a strong prior is not direct observation.
    cfg = scoring.ScoringConfig(prior_recurrent=0.95)
    models = {"w": scoring.GaussianSignal("w", "whitebox_weights", 1.0, 1.0, 0.0, 1.0)}
    v = scoring.score({"w": 1.5}, models, cfg)
    assert v.posterior_recurrent >= cfg.threshold
    assert 0.5 <= v.families["whitebox_weights"] < cfg.decisive_min_llr
    assert v.label == scoring.INCONCLUSIVE


def test_fit_preserves_floor_and_monotonicity(tmp_path):
    refs = [{"label": "recurrent", "signals": {"shared_layer_fraction": 0.9}}]
    refs += [{"label": "fixed", "signals": {"shared_layer_fraction": 0.0}}]
    m = scoring.fit_models(refs)["shared_layer_fraction"]
    assert m.floor == -0.5 and m.monotone
    p = tmp_path / "m.json"
    scoring.save_models({"shared_layer_fraction": m}, p)
    assert scoring.load_models(p)["shared_layer_fraction"].floor == -0.5


# ---------------------------------------------------------------------------
# weights and safetensors
# ---------------------------------------------------------------------------


def test_single_shared_layer_group_is_a_stack(tmp_path):
    # ALBERT stores one layer group that is applied 12 times.
    rng = np.random.default_rng(0)
    prefix = "albert.encoder.albert_layer_groups.0.albert_layers.0"
    t = {f"{prefix}.{n}": rng.normal(size=(8, 8)).astype(np.float32) for n in "qkv"}
    path = tmp_path / "albert.safetensors"
    write_safetensors(path, t)
    rep = weights.analyze_weights(read_checkpoint(path), declared_layers=12)
    assert rep.stored_slots == 1 and rep.distinct_slots == 1
    assert rep.weight_reuse_ratio == 12
    assert "shared_layer_fraction" not in rep.signals()  # undefined with one stored slot
    assert scoring.score(rep.signals()).label == scoring.RECURRENT


def test_no_layer_stack_gives_no_weight_signal(tmp_path):
    path = tmp_path / "x.safetensors"
    write_safetensors(path, {"embed.weight": np.ones((4, 4), dtype=np.float32)})
    rep = weights.analyze_weights(read_checkpoint(path))
    assert rep.signals() == {}


def test_missing_layer_indices_are_reported(tmp_path):
    rng = np.random.default_rng(1)
    t = {f"model.layers.{i}.w": rng.normal(size=(8, 8)).astype(np.float32) for i in (0, 1, 4)}
    path = tmp_path / "gap.safetensors"
    write_safetensors(path, t)
    rep = weights.analyze_weights(read_checkpoint(path))
    assert rep.missing_slots == {"model.layers": [2, 3]}


def test_no_hash_mode_never_reports_duplicates_from_unsampled_tensors(tmp_path):
    rng = np.random.default_rng(2)
    t = {f"model.layers.{i}.conv": rng.normal(size=(2, 2, 2)).astype(np.float32) for i in range(3)}
    path = tmp_path / "conv.safetensors"
    write_safetensors(path, t)
    rep = weights.analyze_weights(read_checkpoint(path), use_hash=False)
    assert rep.exact_duplicate_pairs == []


def test_fp8_decoding(tmp_path):
    path = tmp_path / "f8.safetensors"
    codes = np.array([0x00, 0x38, 0x40, 0xB8, 0x7E, 0x01], dtype=np.uint8)
    write_safetensors(path, {"w": codes})
    info = read_header(path)["w"]
    e4 = TensorInfo(info.name, "F8_E4M3", info.shape, info.path, info.start, info.end)
    vals = load_tensor(e4)
    assert vals.dtype == np.float32
    assert vals.tolist()[:5] == [0.0, 1.0, 2.0, -1.0, 448.0]
    assert vals[5] == pytest.approx(2.0**-9)
    e5 = TensorInfo(info.name, "F8_E5M2", info.shape, info.path, info.start, info.end)
    assert load_tensor(e5)[1] == pytest.approx(0.5)  # 0x38 = 0 01110 00


def test_header_offsets_and_sizes_are_validated(tmp_path):
    path = tmp_path / "w.safetensors"
    write_safetensors(path, {"w": np.ones((4,), dtype=np.float32)})
    info = read_header(path)["w"]
    bad = TensorInfo(info.name, "F32", (5,), info.path, info.start, info.end)
    with pytest.raises(ValueError):
        load_tensor(bad)
    raw = bytearray(path.read_bytes())
    n = int.from_bytes(raw[:8], "little")
    header = json.loads(raw[8 : 8 + n])
    header["w"]["data_offsets"] = [0, 4096]
    hb = json.dumps(header).encode()
    hb += b" " * ((8 - len(hb) % 8) % 8)
    path.write_bytes(len(hb).to_bytes(8, "little") + hb + bytes(raw[8 + n :]))
    with pytest.raises(ValueError):
        read_header(path)


# ---------------------------------------------------------------------------
# dynamics
# ---------------------------------------------------------------------------


def test_unsettled_tokens_are_distinguished_from_late_settlers():
    kl = np.array([[1.0, 1.0], [1.0, 1.0], [0.0, 1.0]])
    out = dynamics.settle_steps(kl, threshold=0.5)
    assert out.tolist() == [3, 4]


# ---------------------------------------------------------------------------
# tasks, features, harness, client
# ---------------------------------------------------------------------------


def test_reachability_rejects_depths_that_cannot_be_filled():
    with pytest.raises(ValueError):
        tasks.reachability(18, random.Random(0))  # 2 spare nodes cannot hold 4 distractor edges
    assert tasks.reachability(17, random.Random(0)).depth == 17


def _knob_rows(hidden):
    rows = []
    for knob, correct in (("low", False), ("high", True)):
        for _ in range(6):
            rows.append(
                {
                    "task": "parity",
                    "depth": 4,
                    "chance": 0.5,
                    "knob": knob,
                    "correct": correct,
                    "status": 200,
                    "error": None,
                    "ttft_s": 0.5,
                    "total_s": 0.6 if knob == "low" else 3.0,
                    "completion_tokens": 1,
                    "reasoning_tokens": (200 if knob == "high" else 0) if hidden else 0,
                }
            )
    return rows


def test_knob_accuracy_gain_excludes_hidden_reasoning_tokens():
    sig = features.extract_signals(_knob_rows(hidden=True), knob_order=["low", "high"])["signals"]
    assert "knob_accuracy_gain" not in sig and "knob_latency_log_ratio" not in sig
    clean = features.extract_signals(_knob_rows(hidden=False), knob_order=["low", "high"])["signals"]
    assert clean["knob_accuracy_gain"] == pytest.approx(2.0)
    assert clean["knob_latency_log_ratio"] > 0


def test_stream_error_mid_response_is_recorded_not_raised():
    clock = VirtualClock()

    def transport(url, headers, body, timeout):
        def gen():
            yield b'data: {"choices": [{"delta": {"content": "A"}}]}\n'
            raise TimeoutError("read timed out")

        return TransportResponse(200, {}, gen())

    limiter = RateLimiter(requests_per_minute=0, max_requests=5, clock=clock, sleep=clock.sleep)
    c = ChatClient("https://api.example.test/v1", "m", api_key_env=None, limiter=limiter, transport=transport, clock=clock)
    res = c.complete("hi")
    assert not res.ok and "stream error" in res.error and res.text == "A"


def test_harness_budget_is_hard_including_retries(monkeypatch):
    plan = harness.ProbePlan(
        base_url="https://api.example.test/v1",
        model="m",
        tasks=["parity"],
        depths=[1, 2],
        reps=1,
        max_requests=2,
        api_key_env=None,
        acknowledge_terms=True,
    )
    clock = VirtualClock()
    sent = []

    def transport(url, headers, body, timeout):
        sent.append(1)
        return TransportResponse(503, {}, [b"busy"])

    real = client_mod.ChatClient

    def factory(*a, **k):
        k.update(transport=transport, clock=clock, sleep=clock.sleep)
        k["limiter"].clock, k["limiter"].sleep = clock, clock.sleep
        return real(*a, **k)

    monkeypatch.setattr(harness, "ChatClient", factory)
    with pytest.raises(BudgetExceeded):
        harness.run_plan(plan)
    assert len(sent) == 2


class _Redirector(http.server.BaseHTTPRequestHandler):
    target = ""
    seen_auth: list = []

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/final"):
            _Redirector.seen_auth.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"data: [DONE]\n")
            return
        self.send_response(302)
        self.send_header("Location", _Redirector.target)
        self.end_headers()

    do_GET = do_POST  # noqa: N815

    def log_message(self, *args):
        pass


def test_redirects_are_not_followed_with_credentials():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Redirector)
    _Redirector.target = f"http://127.0.0.1:{srv.server_port}/final"
    _Redirector.seen_auth = []
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        resp = client_mod.urllib_transport(
            f"http://127.0.0.1:{srv.server_port}/v1/chat/completions",
            {"Authorization": "Bearer secret", "Content-Type": "application/json"},
            b"{}",
            5.0,
        )
        assert resp.status == 302
        assert _Redirector.seen_auth == []
    finally:
        srv.shutdown()
        srv.server_close()


def test_ttft_excess_is_expressed_in_inter_token_latencies():
    rows = []
    for depth, ttft in ((1, 0.30), (8, 0.36)):
        for _ in range(4):
            rows.append(
                {
                    "task": "parity",
                    "depth": depth,
                    "knob": None,
                    "status": 200,
                    "error": None,
                    "ttft_s": ttft,
                    "itl_mean_s": 0.03,
                }
            )
    assert features.ttft_excess_in_itl(rows) == pytest.approx(2.0)


def test_nanbeige_style_loop_config():
    # Fields as published for Nanbeige4.2-3B (July 2026): 22 stored layers looped twice.
    from recurrent_depth import config_inspect

    cfg = {"model_type": "nanbeige", "num_hidden_layers": 22, "num_loops": 2, "loop_loss_weights": []}
    r = config_inspect.inspect_config(cfg)
    assert r.outcome == 1.0 and r.declares_recurrence
    assert r.stored_layers == 22 and r.logical_depth == 44
