"""Bootstrap AUROC confidence intervals (sleeper_agents.utils.bootstrap)."""

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from sleeper_agents.utils.bootstrap import auroc, bootstrap_auroc_ci, paired_bootstrap_auroc_difference


def _data(n_pos=40, n_neg=60, shift=1.0, seed=0, ties=False):
    rng = np.random.default_rng(seed)
    s = np.concatenate([rng.normal(shift, 1, n_pos), rng.normal(0, 1, n_neg)])
    if ties:
        s = np.round(s)
    y = np.array([1] * n_pos + [0] * n_neg)
    return y, s


@pytest.mark.parametrize("ties", [False, True])
def test_auroc_matches_sklearn(ties):
    y, s = _data(ties=ties)
    assert auroc(y, s) == pytest.approx(roc_auc_score(y, s))


def test_auroc_none_for_single_class():
    assert auroc([1, 1, 1], [0.1, 0.2, 0.3]) is None
    out = bootstrap_auroc_ci([0, 0], [0.1, 0.2])
    assert out["auroc"] is None and out["ci_low"] is None and out["n_neg"] == 2


def test_ci_brackets_point_estimate_and_is_seeded():
    y, s = _data()
    a = bootstrap_auroc_ci(y, s, n_boot=500, seed=3)
    b = bootstrap_auroc_ci(y, s, n_boot=500, seed=3)
    assert a == b
    assert 0.0 <= a["ci_low"] <= a["auroc"] <= a["ci_high"] <= 1.0
    assert a["auroc"] == pytest.approx(roc_auc_score(y, s))
    assert a["n_pos"] == 40 and a["n_neg"] == 60 and a["confidence"] == pytest.approx(0.95)


def test_ci_narrows_with_more_data():
    small = bootstrap_auroc_ci(*_data(10, 10, seed=1), n_boot=500)
    large = bootstrap_auroc_ci(*_data(400, 400, seed=1), n_boot=500)
    assert (large["ci_high"] - large["ci_low"]) < (small["ci_high"] - small["ci_low"])


def test_ci_coverage_is_roughly_nominal():
    """Across repeated samples from a known distribution, the 95% CI covers the true AUROC most of the time."""
    from scipy.stats import norm

    true_auc = float(norm.cdf(1.0 / np.sqrt(2)))  # AUROC of N(1,1) vs N(0,1)
    covered = 0
    trials = 60
    for seed in range(trials):
        out = bootstrap_auroc_ci(*_data(50, 50, seed=100 + seed), n_boot=300, seed=seed)
        covered += out["ci_low"] <= true_auc <= out["ci_high"]
    assert covered / trials >= 0.85


def test_perfect_separation_has_degenerate_ci():
    out = bootstrap_auroc_ci([0, 0, 0, 1, 1, 1], [0.1, 0.2, 0.3, 0.7, 0.8, 0.9], n_boot=200)
    assert out["auroc"] == 1.0 and out["ci_low"] == 1.0 and out["ci_high"] == 1.0


def test_paired_difference():
    y, s = _data(60, 60, shift=2.0, seed=2)
    rng = np.random.default_rng(9)
    noise = rng.normal(size=s.shape)

    same = paired_bootstrap_auroc_difference(y, s, s, n_boot=300)
    assert same["difference"] == 0.0 and same["ci_low"] == 0.0 and same["ci_high"] == 0.0

    diff = paired_bootstrap_auroc_difference(y, s, noise, n_boot=300)
    assert diff["auroc_a"] == pytest.approx(roc_auc_score(y, s))
    assert diff["auroc_b"] == pytest.approx(roc_auc_score(y, noise))
    assert diff["difference"] == pytest.approx(diff["auroc_a"] - diff["auroc_b"])
    assert diff["ci_low"] > 0


@pytest.mark.parametrize(
    "labels, scores",
    [([0, 1], [0.1]), ([0, 2], [0.1, 0.2]), ([0, 1], [0.1, float("nan")])],
)
def test_invalid_inputs_raise(labels, scores):
    with pytest.raises(ValueError):
        bootstrap_auroc_ci(labels, scores)


def test_invalid_parameters_raise():
    with pytest.raises(ValueError):
        bootstrap_auroc_ci([0, 1], [0.1, 0.2], n_boot=0)
    with pytest.raises(ValueError):
        bootstrap_auroc_ci([0, 1], [0.1, 0.2], alpha=1.5)
