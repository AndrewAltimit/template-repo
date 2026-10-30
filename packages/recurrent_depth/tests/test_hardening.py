"""Regression tests for the security and measurement review of late October 2026."""

import json
import math
import random

import numpy as np
import pytest

from recurrent_depth import cli, features, harness, scoring
from recurrent_depth.client import ChatClient, RateLimiter, TransportResponse
from recurrent_depth.safetensors_io import read_checkpoint, read_header, write_safetensors
from recurrent_depth.simulate import VirtualClock


def _client(transport, clock, **kw):
    limiter = RateLimiter(requests_per_minute=0, max_requests=20, clock=clock, sleep=clock.sleep)
    return ChatClient(
        "https://api.example.test/v1",
        "m",
        api_key_env=None,
        limiter=limiter,
        transport=transport,
        clock=clock,
        sleep=clock.sleep,
        **kw,
    )


def _plan(**kw):
    base = dict(
        base_url="https://api.example.test/v1",
        model="m",
        tasks=["parity"],
        depths=[1, 2],
        reps=1,
        api_key_env=None,
        acknowledge_terms=True,
    )
    base.update(kw)
    return harness.ProbePlan(**base)


# ---------------------------------------------------------------------------
# credentials and request integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "HOME", "openai_api_key", "API_KEY_X"])
def test_plan_cannot_name_arbitrary_secrets(name):
    with pytest.raises(ValueError, match="does not look like an API key"):
        _plan(api_key_env=name).validate()


def test_plan_accepts_api_key_names_and_operator_override():
    _plan(api_key_env="OPENAI_API_KEY").validate()
    _plan(api_key_env="TOGETHER_API_KEY").validate()
    _plan(api_key_env="MY_GATEWAY_TOKEN").validate(allow_any_key_env=True)


@pytest.mark.parametrize("field", ["max_tokens", "n", "stream", "model", "messages", "temperature"])
def test_extra_cannot_override_controlled_fields(field):
    with pytest.raises(ValueError, match="may not"):
        _plan(extra={field: 1}).validate()
    with pytest.raises(ValueError, match="may not"):
        _plan(knob_param=field, knob_values=[1, 2]).validate()
    clock = VirtualClock()
    c = _client(lambda *a: TransportResponse(200, {}, []), clock)
    with pytest.raises(ValueError, match="may not override"):
        c.complete("hi", extra={field: 1})


def test_provider_knobs_still_pass_through():
    clock = VirtualClock()
    seen = []

    def transport(url, headers, body, timeout):
        seen.append(json.loads(body))
        return TransportResponse(200, {}, [b"data: [DONE]\n"])

    _client(transport, clock).complete("hi", extra={"reasoning_effort": "low"})
    assert seen[0]["reasoning_effort"] == "low" and seen[0]["max_tokens"] == 8


def test_max_tokens_is_bounded():
    with pytest.raises(ValueError, match="max_tokens"):
        _plan(max_tokens=4096).validate()


def test_cli_override_names_the_destination(tmp_path, monkeypatch, capsys):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {"base_url": "https://api.example.test/v1", "model": "m", "api_key_env": "CI_TOKEN", "acknowledge_terms": True}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not look like an API key"):
        cli.main(["probe", str(plan), "--out", str(tmp_path / "r.jsonl")])
    calls = []
    monkeypatch.setattr(harness, "run_plan", lambda p, **k: calls.append((p.api_key_env, k["allow_any_key_env"])))
    assert cli.main(["probe", str(plan), "--out", str(tmp_path / "r.jsonl"), "--api-key-env", "CI_TOKEN"]) == 0
    assert calls == [("CI_TOKEN", True)]
    assert "to api.example.test" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# hostile or malformed responses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["-5", "nan", "inf", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_bad_retry_after_falls_back_to_backoff(value):
    clock = VirtualClock()
    slept = []
    responses = [
        TransportResponse(429, {"Retry-After": value}, [b"slow down"]),
        TransportResponse(200, {}, [b"data: [DONE]\n"]),
    ]

    def transport(url, headers, body, timeout):
        return responses.pop(0)

    c = _client(transport, clock)
    c.sleep = lambda s: slept.append(s)
    res = c.complete("hi")
    assert res.ok
    assert slept and all(math.isfinite(s) and 0 <= s <= 300 for s in slept)


def test_response_size_is_capped():
    clock = VirtualClock()
    line = b'data: {"choices": [{"delta": {"content": "' + b"x" * 1000 + b'"}}]}\n'
    c = _client(lambda *a: TransportResponse(200, {}, [line] * 100), clock, max_response_bytes=10_000)
    res = c.complete("hi")
    assert not res.ok and "exceeded" in res.error and len(res.text) < 11_000


def test_total_timeout_is_enforced_for_trickling_servers():
    clock = VirtualClock()

    def transport(url, headers, body, timeout):
        def gen():
            for _ in range(1000):
                clock.sleep(1.0)
                yield b'data: {"choices": [{"delta": {"content": "a"}}]}\n'

        return TransportResponse(200, {}, gen())

    res = _client(transport, clock, timeout_s=10.0).complete("hi")
    assert not res.ok and "timeout" in res.error and len(res.text) <= 11


def test_malformed_chunks_do_not_crash_the_run():
    clock = VirtualClock()
    lines = [
        b"data: [1, 2, 3]\n",
        b'data: "text"\n',
        b'data: {"choices": "nope", "usage": "many"}\n',
        b'data: {"choices": [7, {"delta": "x"}, {"delta": {"content": 5}}]}\n',
        b'data: {"choices": [{"delta": {"content": "A"}, "logprobs": {"content": [3, {"top_logprobs": [{"token": "A"}, '
        b'{"token": "B", "logprob": -0.5}, {"token": 1, "logprob": 0}]}]}}]}\n',
        b'data: {"choices": [], "usage": {"prompt_tokens": "12", "completion_tokens": 1.0, '
        b'"completion_tokens_details": {"reasoning_tokens": -3}}}\n',
        b"data: [DONE]\n",
    ]
    res = _client(lambda *a: TransportResponse(200, {}, lines), clock).complete("hi")
    assert res.ok and res.text == "A"
    assert res.top_logprobs == [{"B": -0.5}]
    assert res.prompt_tokens is None and res.completion_tokens == 1 and res.reasoning_tokens is None


# ---------------------------------------------------------------------------
# untrusted checkpoints
# ---------------------------------------------------------------------------


def test_index_cannot_point_outside_the_checkpoint(tmp_path):
    outside = tmp_path / "outside.safetensors"
    write_safetensors(outside, {"w": np.zeros((2, 2), dtype=np.float32)})
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    for shard in ("../outside.safetensors", str(outside), "", 5):
        (ckpt / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"w": shard}}), encoding="utf-8")
        with pytest.raises(ValueError, match="outside the checkpoint"):
            read_checkpoint(ckpt)


def test_malformed_headers_raise_value_errors(tmp_path):
    short = tmp_path / "short.safetensors"
    short.write_bytes(b"\x01\x02")
    with pytest.raises(ValueError, match="too short"):
        read_header(short)
    for header in ([1, 2], {"w": {"dtype": "F32", "shape": [-1, 4], "data_offsets": [0, 0]}}, {"w": {"dtype": "F32"}}):
        blob = json.dumps(header).encode()
        bad = tmp_path / "bad.safetensors"
        bad.write_bytes(len(blob).to_bytes(8, "little") + blob)
        with pytest.raises(ValueError):
            read_header(bad)
    huge = tmp_path / "huge.safetensors"
    huge.write_bytes((10_000).to_bytes(8, "little") + b"{}")
    with pytest.raises(ValueError, match="implausible"):
        read_header(huge)


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------


def _latency_rows(slope, seed=0, n_per_depth=20, drift=0.0):
    rng = random.Random(seed)
    rows = []
    depths = [1, 2, 4, 8, 12]
    order = [d for d in depths for _ in range(n_per_depth)]
    rng.shuffle(order)
    for i, d in enumerate(order):
        ttft = 0.3 * math.exp(slope * d + drift * i / len(order) + rng.gauss(0, 0.05))
        rows.append({"task": "parity", "depth": d, "knob": None, "status": 200, "error": None, "ttft_s": ttft, "seq": i})
    return rows


def test_trimming_does_not_attenuate_a_real_depth_slope():
    rows = _latency_rows(slope=0.05)
    kept = features._trim(rows, "ttft_s", 0.05)
    dropped = [r["depth"] for r in rows if r not in kept]
    # Raw-latency trimming would drop only depth-12 items; ratio trimming spreads the cut.
    assert len(set(dropped)) > 1
    est = features.timing_slope(rows)
    assert est["log_slope"] == pytest.approx(0.05, abs=0.005)


def test_drift_covariate_tightens_the_slope_estimate():
    rows = _latency_rows(slope=0.0, drift=1.0, seed=3)
    with_seq = features.timing_slope(rows)
    no_seq = features.timing_slope([{k: v for k, v in r.items() if k != "seq"} for r in rows])
    assert abs(with_seq["log_slope"]) < 0.01
    assert with_seq["se"] < no_seq["se"]


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_non_finite_signals_are_never_evidence(value):
    v = scoring.score({"ttft_slope_z": value})
    assert v.contributions == {} and v.label == scoring.INCONCLUSIVE
    assert v.posterior_recurrent == pytest.approx(0.5)


def test_latency_families_are_flagged_and_can_count_once():
    sig = {"ttft_slope_z": 8.0, "itl_slope_z": 6.0, "knob_latency_log_ratio": 1.2, "knob_accuracy_gain": 0.4}
    loose = scoring.score(sig)
    assert loose.label == scoring.RECURRENT
    assert any("share latency confounders" in n for n in loose.notes)
    strict = scoring.score(sig, config=scoring.ScoringConfig(strict_independence=True))
    assert strict.label == scoring.INCONCLUSIVE
    assert strict.posterior_recurrent == pytest.approx(loose.posterior_recurrent)
    # A non-latency family restores the decision under the strict rule.
    sig["serial_retention"] = 1.2
    assert scoring.score(sig, config=scoring.ScoringConfig(strict_independence=True)).label == scoring.RECURRENT
