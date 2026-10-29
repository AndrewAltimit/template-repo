import json
import random

import pytest

from recurrent_depth import features, harness
from recurrent_depth.simulate import SimProfile, run_simulated


def test_plan_requires_terms_acknowledgement():
    plan = harness.ProbePlan(base_url="https://x.test/v1", model="m")
    with pytest.raises(PermissionError):
        plan.validate()


def test_plan_budget_enforced():
    plan = harness.ProbePlan(base_url="https://x.test/v1", model="m", reps=50, max_requests=100, acknowledge_terms=True)
    with pytest.raises(ValueError):
        plan.validate()


def test_plan_from_json_ignores_unknown_keys(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"base_url": "https://x.test/v1", "model": "m", "comment": "hi", "acknowledge_terms": True}))
    plan = harness.ProbePlan.from_json(p)
    assert plan.model == "m" and plan.acknowledge_terms


def test_simulated_run_writes_all_records(tmp_path):
    out = tmp_path / "r.jsonl"
    recs = run_simulated(SimProfile(kind="fixed"), reps=2, seed=3, knob=True, out_path=str(out))
    assert len(recs) == 4 * 5 * 2 * 3
    assert len(harness.load_records(out)) == len(recs)
    assert all(r["status"] == 200 for r in recs)
    assert {r["knob"] for r in recs} == {"low", "medium", "high"}


def _synthetic_records(slope, n=40, seed=0, task="pointer_chase", hidden=0):
    rng = random.Random(seed)
    recs = []
    for i in range(n):
        d = [1, 2, 4, 8][i % 4]
        recs.append(
            {
                "task": task,
                "depth": d,
                "chance": 0.1,
                "knob": None,
                "correct": True,
                "status": 200,
                "error": None,
                "ttft_s": 0.3 * (1 + slope * d) * (1 + rng.gauss(0, 0.02)),
                "total_s": 0.5,
                "itl_mean_s": None,
                "prompt_tokens": 100,
                "completion_tokens": 1,
                "reasoning_tokens": hidden,
            }
        )
    return recs


def test_timing_slope_detects_depth_dependence():
    flat = features.timing_slope(_synthetic_records(0.0))
    steep = features.timing_slope(_synthetic_records(0.05))
    assert abs(flat["z"]) < 3
    assert steep["z"] > 10 and steep["log_slope"] > 0


def test_timing_slope_excludes_hidden_reasoning_tokens():
    assert features.timing_slope(_synthetic_records(0.05, hidden=40)) is None


def test_serial_retention_and_curves():
    recs = []
    for d, acc in [(1, 1.0), (2, 1.0), (4, 0.9), (8, 0.5), (12, 0.2), (16, 0.1)]:
        for k in range(10):
            recs.append(
                {
                    "task": "parity",
                    "depth": d,
                    "chance": 0.5,
                    "knob": None,
                    "status": 200,
                    "error": None,
                    "correct": k < acc * 10,
                }
            )
    curves = features.accuracy_curves(recs)
    assert curves["parity"][1]["corrected"] == pytest.approx(1.0)
    assert curves["parity"][16]["corrected"] == pytest.approx(-0.8)
    ret = features.serial_retention(curves)
    assert ret == pytest.approx(0.0)


def test_recurrent_simulation_produces_stronger_signals_than_fixed():
    f = features.extract_signals(run_simulated(SimProfile(kind="fixed"), reps=4, seed=1), ["low", "medium", "high"])
    prof = SimProfile(kind="recurrent", d_crit=8.0, knob_depth_gain=2.0, knob_loop_gain=4.0)
    r = features.extract_signals(run_simulated(prof, reps=4, seed=1), ["low", "medium", "high"])
    fs, rs = f["signals"], r["signals"]
    assert rs["ttft_slope_z"] > 5 > abs(fs["ttft_slope_z"])
    assert rs["knob_latency_log_ratio"] > fs["knob_latency_log_ratio"]
    assert rs["knob_accuracy_gain"] > fs["knob_accuracy_gain"]
