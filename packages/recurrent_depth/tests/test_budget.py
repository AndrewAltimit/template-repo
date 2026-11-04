import json
import math
import random

import pytest

from recurrent_depth import budget, cli
from recurrent_depth.client import BudgetExceeded, ChatClient, RateLimiter, TransportResponse
from recurrent_depth.simulate import VirtualClock


def _plan(**kw):
    base = dict(
        base_url="https://api.example.test/v1",
        model="m",
        api_key_env=None,
        conditions=[
            budget.BudgetCondition("low", 64, {"reasoning": {"effort": "minimal"}}),
            budget.BudgetCondition("high", 1024, {"reasoning": {"effort": "high"}}),
        ],
        tasks=["parity", "reachability"],
        depths=[2, 8],
        reps=2,
        requests_per_minute=600,
        acknowledge_terms=True,
    )
    base.update(kw)
    return budget.BudgetPlan(**base)


def _sse(*chunks):
    return [f"data: {json.dumps(c)}\n".encode() for c in chunks] + [b"data: [DONE]\n"]


def _body(prompt):
    """The task part of a prompt, without the answer-format or filler instruction."""
    from recurrent_depth.tasks import NO_COT_SUFFIX

    return prompt.split(NO_COT_SUFFIX)[0].split("Before your answer")[0]


class OracleTransport:
    """Answers correctly with probability ``p[effort]`` and bills ``tokens[effort] * depth`` reasoning tokens."""

    def __init__(self, clock, items, p, tokens, seed=0):
        self.clock = clock
        self.truth = {_body(it.prompt): it for it in items}
        self.p = p
        self.tokens = tokens
        self.rng = random.Random(seed)
        self.bodies = []

    def __call__(self, url, headers, body, timeout):
        req = json.loads(body)
        self.bodies.append(req)
        effort = req["reasoning"]["effort"]
        item = self.truth[_body(req["messages"][0]["content"])]
        wrong = {"even": "odd", "odd": "even", "yes": "no", "no": "yes"}[item.answer]
        text = item.answer if self.rng.random() < self.p[effort] else wrong
        hidden = self.tokens[effort] * item.depth
        usage = {
            "prompt_tokens": 50,
            "completion_tokens": hidden + 1,
            "completion_tokens_details": {"reasoning_tokens": hidden},
        }
        lines = _sse({"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]}, {"choices": [], "usage": usage})

        def gen():
            for line in lines:
                self.clock.sleep(0.05)
                yield line

        return TransportResponse(200, {}, gen())


def _client(transport, clock, plan):
    limiter = RateLimiter(
        requests_per_minute=plan.requests_per_minute, max_requests=plan.max_requests, clock=clock, sleep=clock.sleep
    )
    return ChatClient(
        plan.base_url, plan.model, api_key_env=None, limiter=limiter, transport=transport, clock=clock, sleep=clock.sleep
    )


def _run(plan, p, tokens, seed=0):
    clock = VirtualClock()
    items, _ = plan.suite()
    t = OracleTransport(clock, items, p, tokens, seed=seed)
    return budget.run_budget_plan(plan, client=_client(t, clock, plan)), t


def test_plan_validation_guards():
    with pytest.raises(PermissionError):
        _plan(acknowledge_terms=False).validate()
    with pytest.raises(ValueError, match="unique"):
        _plan(conditions=[budget.BudgetCondition("a", 8), budget.BudgetCondition("a", 8)]).validate()
    with pytest.raises(ValueError, match="max_tokens"):
        _plan(conditions=[budget.BudgetCondition("a", budget.MAX_CONDITION_TOKENS + 1)]).validate()
    with pytest.raises(ValueError, match="client controls"):
        _plan(conditions=[budget.BudgetCondition("a", 8, {"max_tokens": 99999})]).validate()
    with pytest.raises(ValueError, match="client controls"):
        _plan(extra={"model": "other"}).validate()
    with pytest.raises(ValueError, match="max_requests"):
        _plan(reps=50, max_requests=10).validate()
    with pytest.raises(ValueError, match="API key"):
        _plan(api_key_env="AWS_SECRET_ACCESS_KEY").validate()
    with pytest.raises(ValueError, match="timeout"):
        _plan(timeout_s=10_000).validate()
    with pytest.raises(ValueError, match="at least one condition"):
        _plan(conditions=[]).validate()


def test_suite_skips_out_of_range_depths():
    plan = _plan(tasks=["reachability", "parity", "pointer_chase"], depths=[2, 24])
    items, skipped = plan.suite()
    assert skipped == [("reachability", 24), ("pointer_chase", 24)]
    assert {(i.task, i.depth) for i in items} == {("reachability", 2), ("parity", 2), ("parity", 24), ("pointer_chase", 2)}
    assert plan.planned_requests() == len(items) * 2


def test_plan_from_json(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(
        json.dumps(
            {
                "base_url": "https://x.test/v1",
                "model": "m",
                "conditions": [{"label": "a", "max_tokens": 32, "params": {"reasoning": {"effort": "low"}}}],
                "comment": "ignored",
                "acknowledge_terms": True,
            }
        )
    )
    plan = budget.BudgetPlan.from_json(p)
    assert plan.conditions[0].params == {"reasoning": {"effort": "low"}} and plan.acknowledge_terms


def test_run_records_conditions_and_tokens():
    plan = _plan()
    recs, t = _run(plan, {"minimal": 1.0, "high": 1.0}, {"minimal": 0, "high": 10})
    assert len(recs) == plan.planned_requests()
    assert {r["condition"] for r in recs} == {"low", "high"}
    assert all(r["correct"] and r["finish_reason"] == "stop" for r in recs)
    assert all(r["reasoning_tokens"] == 10 * r["depth"] for r in recs if r["condition"] == "high")
    assert {b["max_tokens"] for b in t.bodies} == {64, 1024}


def test_token_budget_stops_run():
    plan = _plan(max_total_completion_tokens=50)
    with pytest.raises(budget.TokenBudgetExceeded):
        _run(plan, {"minimal": 1.0, "high": 1.0}, {"minimal": 10, "high": 10})
    assert issubclass(budget.TokenBudgetExceeded, BudgetExceeded)


def test_features_separate_load_bearing_from_in_pass():
    plan = _plan(depths=[2, 8, 16], reps=12, max_requests=500)
    # In-pass: accuracy barely depends on the budget and few tokens are spent per step.
    inpass, _ = _run(plan, {"minimal": 0.95, "high": 1.0}, {"minimal": 0, "high": 2}, seed=1)
    # Load-bearing: without reasoning the model guesses, and it spends many tokens per step.
    cot, _ = _run(plan, {"minimal": 0.5, "high": 1.0}, {"minimal": 0, "high": 20}, seed=1)
    fi = budget.budget_features(inpass, n_boot=100)
    fc = budget.budget_features(cot, n_boot=100)
    assert fi["conditions"] == ["low", "high"]
    assert fi["in_pass_share_valid"] and fc["in_pass_share_valid"]
    assert fi["in_pass_share"] > 0.8
    assert fc["in_pass_share"] < 0.3
    lo, hi = fi["in_pass_share_ci95"]
    assert lo <= fi["in_pass_share"] <= hi
    assert fc["tokens_per_step"]["high"]["slope"] == pytest.approx(20, rel=1e-6)
    assert fi["tokens_per_step"]["high"]["slope"] == pytest.approx(2, rel=1e-6)
    assert fi["tokens_to_solve"][16] is not None
    assert all(g >= 0 for g in fc["accuracy_gap_by_depth"].values())


def test_features_reasoning_metric_and_truncation():
    recs = [
        {
            "task": "parity",
            "depth": d,
            "chance": 0.5,
            "condition": c,
            "condition_index": i,
            "correct": ok,
            "status": 200,
            "error": None,
            "response": "odd" if ok else "",
            "finish_reason": "stop" if ok else "length",
            "completion_tokens": 5,
            "reasoning_tokens": 0,
        }
        for i, c in enumerate(["low", "high"])
        for d in (2, 4)
        for ok in (True, False)
    ]
    f = budget.budget_features(recs, token_metric="reasoning", n_boot=0)
    assert f["cells"]["low"][2]["truncated"] == 0.5
    assert f["cells"]["high"][4]["tokens_mean"] == 0.0
    with pytest.raises(ValueError):
        budget.budget_features(recs, token_metric="bogus")


def test_finish_reason_captured_by_client():
    clock = VirtualClock()
    lines = _sse({"choices": [{"delta": {}, "finish_reason": "length"}]})

    def transport(url, headers, body, timeout):
        return TransportResponse(200, {}, iter(lines))

    limiter = RateLimiter(requests_per_minute=60, max_requests=2, clock=clock, sleep=clock.sleep)
    c = ChatClient(
        "https://x.test/v1", "m", api_key_env=None, limiter=limiter, transport=transport, clock=clock, sleep=clock.sleep
    )
    res = c.complete("q", max_tokens=8)
    assert res.finish_reason == "length" and res.text == ""


def test_cli_budget_features_roundtrip(tmp_path, capsys):
    recs, _ = _run(_plan(), {"minimal": 0.5, "high": 1.0}, {"minimal": 0, "high": 5})
    path = tmp_path / "r.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in recs))
    assert cli.main(["budget-features", str(path), "--condition-order", "low,high"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["conditions"] == ["low", "high"] and "in_pass_share" in out


def test_cli_budget_probe_refuses_unacknowledged_plan(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"base_url": "https://x.test/v1", "model": "m", "conditions": [{"label": "a", "max_tokens": 8}]}))
    with pytest.raises(PermissionError):
        cli.main(["budget-probe", str(p), "--out", str(tmp_path / "o.jsonl")])


def test_in_pass_share_flagged_when_lowest_condition_still_reasons():
    plan = _plan(depths=[2, 8], reps=4)
    recs, _ = _run(plan, {"minimal": 0.9, "high": 1.0}, {"minimal": 10, "high": 20})
    f = budget.budget_features(recs, n_boot=0)
    assert f["lowest_condition_reasoning_mean"] == 10 * 5
    assert f["in_pass_share_valid"] is False
    assert "tokens_per_step" in f["notes"][0]


def test_filler_condition_prompt_and_stats():
    from recurrent_depth.tasks import NO_COT_SUFFIX

    item = _plan().suite()[0][0]
    cond = budget.BudgetCondition("f32", 64, {}, filler=32)
    prompt = cond.prompt(item)
    assert NO_COT_SUFFIX not in prompt and "exactly 32 periods" in prompt
    assert budget.BudgetCondition("f0", 8).prompt(item) == item.prompt
    assert budget.filler_stats("." * 32 + " odd", 32) == (32, True)
    assert budget.filler_stats("." * 10 + " odd", 32)[1] is False
    assert budget.filler_stats("Let me think. First the parity is odd so. Answer odd", 4)[1] is False
    with pytest.raises(ValueError, match="filler"):
        _plan(conditions=[budget.BudgetCondition("a", 8, filler=budget.MAX_FILLER + 1)]).validate()


def test_filler_records_and_compliance_summary():
    plan = _plan(
        conditions=[
            budget.BudgetCondition("f0", 64, {"reasoning": {"effort": "minimal"}}),
            budget.BudgetCondition("f8", 64, {"reasoning": {"effort": "high"}}, filler=8),
        ]
    )
    recs, t = _run(plan, {"minimal": 1.0, "high": 1.0}, {"minimal": 0, "high": 0})
    assert any("exactly 8 periods" in b["messages"][0]["content"] for b in t.bodies)
    f8 = [r for r in recs if r["condition"] == "f8"]
    assert all(r["filler"] == 8 and r["filler_compliant"] is False for r in f8)  # oracle emits no periods
    f = budget.budget_features(recs, n_boot=0)
    cell = next(iter(f["cells"]["f8"].values()))
    assert cell["filler_compliance"] == 0.0 and cell["acc_compliant"] is None


def test_latency_per_token():
    recs = [{"status": 200, "error": None, "completion_tokens": n, "total_s": 0.5 + 0.02 * n} for n in range(10, 200, 10)]
    out = budget.latency_per_token(recs)
    assert out["ms_per_token"] == pytest.approx(20.0, rel=1e-6) and out["intercept_s"] == pytest.approx(0.5)
    assert budget.latency_per_token(recs[:3]) is None


def _twohop_csv(tmp_path, n_cats=3, per_cat=4):
    from recurrent_depth.twohop import REQUIRED_COLUMNS

    path = tmp_path / "TwoHopFact.csv"
    import csv as _csv

    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(REQUIRED_COLUMNS) + ["extra"])
        w.writeheader()
        uid = 0
        for c in range(n_cats):
            for k in range(per_cat):
                w.writerow(
                    {
                        "uid": str(uid),
                        "category": f"cat{c}",
                        "e2.value": f"Bridge{uid}",
                        "e3.value": f"Answer{uid}",
                        "e2.aliases": f"(('Bridge{uid}', 'B{uid} Alias'),)",
                        "e3.aliases": "__import__('os').system('echo pwned')" if uid == 0 else f"(('Answer{uid}',),)",
                        "r1(e1).prompt": f"The bridge of thing {uid} is",
                        "r2(e2).prompt": f"Bridge{uid} has the answer",
                        "r2(r1(e1)).prompt": f"The bridge of thing {uid} has the answer",
                        "extra": "",
                    }
                )
                uid += 1
    return path


def test_twohop_loading_is_balanced_and_safe(tmp_path):
    from recurrent_depth import twohop

    path = _twohop_csv(tmp_path)
    items = twohop.load_items(path, 6, seed=1)
    assert len(items) == 18
    assert {i.task for i in items} == {"hop1", "hop2", "twohop"}
    cats = [i.meta["category"] for i in items if i.task == "twohop"]
    assert sorted(set(cats)) == ["cat0", "cat1", "cat2"] and max(cats.count(c) for c in set(cats)) == 2
    hop1 = next(i for i in items if i.task == "hop1")
    assert hop1.meta["aliases"][0].startswith("Bridge") and len(hop1.meta["aliases"]) == 2
    malicious = twohop.load_items(path, 12, seed=1)
    assert any(i.meta["aliases"] == ["Answer0"] for i in malicious)  # code-like alias field ignored, not executed
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="not a TwoHopFact"):
        twohop.load_items(bad, 2)


def test_twohop_features_composition_rate():
    from recurrent_depth import twohop

    def rec(uid, task, ok):
        return {"item_id": uid, "task": task, "correct": ok, "condition": "none", "status": 200, "error": None}

    recs = []
    for uid, (h1, h2, two) in enumerate([(1, 1, 1), (1, 1, 0), (1, 1, 1), (0, 1, 1), (1, 0, 0)]):
        recs += [rec(uid, "hop1", bool(h1)), rec(uid, "hop2", bool(h2)), rec(uid, "twohop", bool(two))]
    out = twohop.twohop_features(recs)["none"]
    assert out["n_facts"] == 5 and out["n_both_known"] == 3
    assert out["composition_rate"] == pytest.approx(2 / 3)
    assert out["twohop_when_not_known"] == pytest.approx(0.5)
    lo, hi = out["composition_ci95"]
    assert lo < 2 / 3 < hi


def test_budget_plan_with_twohop_suite(tmp_path):
    path = _twohop_csv(tmp_path)
    plan = _plan(twohop_csv=str(path), twohop_n=4, conditions=[budget.BudgetCondition("none", 16)])
    items, skipped = plan.suite()
    assert len(items) == 12 and skipped == [] and plan.planned_requests() == 12


def test_steps_at_50_recovers_crossing():
    rng = random.Random(0)
    recs = []
    for d in range(1, 13):
        p = 1 / (1 + math.exp(-(6.0 - d)))  # 50% at 6 steps
        for _ in range(60):
            recs.append({"depth": d, "correct": rng.random() < p, "status": 200, "error": None, "condition": "off"})
    out = budget.steps_at_50(recs, "off", n_boot=200)
    assert out["steps_at_50"] == pytest.approx(6.0, abs=0.5)
    lo, hi = out["ci95"]
    assert lo < 6.0 < hi
    flat = [dict(r, correct=True) for r in recs]
    assert budget.steps_at_50(flat, "off", n_boot=50)["steps_at_50"] is None
