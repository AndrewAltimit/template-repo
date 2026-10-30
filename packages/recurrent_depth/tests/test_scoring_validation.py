import math

import pytest

from recurrent_depth import scoring, validation
from recurrent_depth.simulate import reference_fleet


def test_llr_is_clipped():
    sig = scoring.GaussianSignal("x", "timing", 4.0, 1.0, 0.0, 1.0, cap=3.0)
    assert sig.llr(100.0) == 3.0
    assert sig.llr(-100.0) == -3.0
    assert sig.llr(2.0) == pytest.approx(0.0)


def test_single_family_is_inconclusive_even_when_strong():
    v = scoring.score({"ttft_slope_z": 30.0, "itl_slope_z": 30.0})
    assert v.posterior_recurrent > 0.9
    assert v.label == scoring.INCONCLUSIVE
    assert any("independent" in n for n in v.notes)


def test_within_family_discount():
    one = scoring.score({"ttft_slope_z": 8.0})
    two = scoring.score({"ttft_slope_z": 8.0, "itl_slope_z": 8.0})
    cfg = scoring.ScoringConfig()
    a = one.families["timing"]
    b = two.families["timing"]
    assert a < b < 2 * a or b == cfg.family_caps["timing"]


def test_two_agreeing_families_decide():
    v = scoring.score({"ttft_slope_z": 8.0, "knob_latency_log_ratio": 0.6, "knob_accuracy_gain": 0.25})
    assert v.label == scoring.RECURRENT
    assert set(v.supporting_families) == {"timing", "knob"}


def test_config_declaration_is_decisive_but_absence_is_weak():
    yes = scoring.score({"config_recurrence": 1.0})
    assert yes.label == scoring.RECURRENT
    no = scoring.score({"config_recurrence": 0.0})
    assert no.label == scoring.INCONCLUSIVE
    assert no.posterior_recurrent > 0.1
    unknown = scoring.score({"config_recurrence": 0.5})
    assert unknown.posterior_recurrent == pytest.approx(0.5)


def test_fixed_verdict_needs_agreement():
    v = scoring.score({"ttft_slope_z": 0.0, "knob_latency_log_ratio": 0.0, "knob_accuracy_gain": 0.0, "serial_retention": 0.2})
    assert v.label == scoring.FIXED
    assert v.posterior_recurrent < 0.1


def test_unknown_signal_noted():
    v = scoring.score({"mystery": 1.0})
    assert v.label == scoring.INCONCLUSIVE and "mystery" in v.notes[0]


def test_prior_shifts_posterior():
    lo = scoring.score({"ttft_slope_z": 3.0}, config=scoring.ScoringConfig(prior_recurrent=0.1))
    hi = scoring.score({"ttft_slope_z": 3.0}, config=scoring.ScoringConfig(prior_recurrent=0.9))
    assert lo.posterior_recurrent < hi.posterior_recurrent
    assert math.isclose(hi.total_llr - lo.total_llr, 2 * math.log(9), rel_tol=1e-9)


def test_fit_shrinks_and_floors():
    refs = [{"label": "recurrent", "signals": {"ttft_slope_z": 10.0}} for _ in range(3)]
    refs += [{"label": "fixed", "signals": {"ttft_slope_z": 0.0}} for _ in range(3)]
    m = scoring.fit_models(refs)["ttft_slope_z"]
    base = scoring.DEFAULT_SIGNALS["ttft_slope_z"]
    assert base.mean_r < m.mean_r < 10.0
    assert m.sd_f >= 0.25 * base.sd_f
    assert isinstance(scoring.fit_models(refs)["config_recurrence"], scoring.CategoricalSignal)


def test_models_roundtrip(tmp_path):
    p = tmp_path / "m.json"
    scoring.save_models(scoring.DEFAULT_SIGNALS, p)
    loaded = scoring.load_models(p)
    assert loaded.keys() == scoring.DEFAULT_SIGNALS.keys()
    assert loaded["config_recurrence"].llr(1.0) == scoring.DEFAULT_SIGNALS["config_recurrence"].llr(1.0)
    assert loaded["ttft_slope_z"].llr(2.5) == pytest.approx(scoring.DEFAULT_SIGNALS["ttft_slope_z"].llr(2.5))


def test_leave_one_out_on_simulated_fleet():
    refs = reference_fleet(n_each=5, seed=2, reps=3)
    res = validation.leave_one_out(refs)
    assert res["n"] == 10
    assert res["wrong_decided"] == 0
    assert res["coverage"] >= 0.6
    assert res["brier"] < 0.15
    total = sum(sum(v.values()) for v in res["confusion"].values())
    assert total == 10


def test_leave_one_out_requires_two_references():
    with pytest.raises(ValueError):
        validation.leave_one_out([{"label": "fixed", "signals": {}}])
