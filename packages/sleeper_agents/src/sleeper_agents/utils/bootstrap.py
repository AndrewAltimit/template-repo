"""Bootstrap confidence intervals for AUROC.

AUROC is computed with the Mann-Whitney rank formula (ties get average ranks, so
the result equals ``sklearn.metrics.roc_auc_score``), vectorized over bootstrap
replicates. Resampling is stratified by class: each replicate draws ``n_pos``
positives and ``n_neg`` negatives with replacement, so every replicate has both
classes and the class balance of the data. Intervals are percentile intervals.

For two score sets on the same items (e.g. the same prompts run through a
backdoored and a clean model), :func:`paired_bootstrap_auroc_difference` resamples
item indices jointly, which keeps the pairing and gives an interval for the
difference that accounts for the shared prompts.
"""

from typing import Any, Dict, Optional, Sequence

import numpy as np
from scipy.stats import rankdata


def _as_arrays(labels: Sequence[int], scores: Sequence[float]):
    y = np.asarray(labels).astype(int).reshape(-1)
    s = np.asarray(scores, dtype=np.float64).reshape(-1)
    if y.shape != s.shape:
        raise ValueError(f"labels and scores differ in length ({y.shape[0]} vs {s.shape[0]})")
    if not np.isin(y, (0, 1)).all():
        raise ValueError("labels must be 0/1")
    if not np.isfinite(s).all():
        raise ValueError("scores must be finite")
    return y, s


def _auroc_rows(y: np.ndarray, s: np.ndarray) -> np.ndarray:
    """AUROC of each row of ``s`` (shape [..., n]) against the 0/1 labels ``y`` (same shape)."""
    ranks = rankdata(s, axis=-1)
    n_pos = y.sum(axis=-1)
    n_neg = y.shape[-1] - n_pos
    rank_sum = (ranks * y).sum(axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        result: np.ndarray = (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return result


def auroc(labels: Sequence[int], scores: Sequence[float]) -> Optional[float]:
    """AUROC of ``scores`` for 0/1 ``labels``; None unless both classes are present."""
    y, s = _as_arrays(labels, scores)
    if y.min(initial=1) == y.max(initial=0):
        return None
    return float(_auroc_rows(y, s))


def _stratified_indices(y: np.ndarray, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """``[n_boot, n]`` resampled indices: positives replaced by positives, negatives by negatives."""
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    idx = np.empty((n_boot, y.shape[0]), dtype=np.int64)
    idx[:, pos] = pos[rng.integers(0, pos.size, size=(n_boot, pos.size))]
    idx[:, neg] = neg[rng.integers(0, neg.size, size=(n_boot, neg.size))]
    return idx


def _interval(values: np.ndarray, alpha: float):
    return float(np.quantile(values, alpha / 2.0)), float(np.quantile(values, 1.0 - alpha / 2.0))


def bootstrap_auroc_ci(
    labels: Sequence[int],
    scores: Sequence[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> Dict[str, Any]:
    """AUROC with a stratified percentile bootstrap confidence interval.

    Args:
        labels: 0/1 labels
        scores: Scores (higher = more likely label 1)
        n_boot: Bootstrap replicates
        alpha: 1 - confidence level (0.05 for a 95% interval)
        seed: RNG seed

    Returns:
        ``auroc``, ``ci_low``, ``ci_high``, ``n_pos``, ``n_neg``, ``n_boot``,
        ``confidence``. ``auroc`` and the interval are None when a class is missing.
    """
    if n_boot < 1:
        raise ValueError("n_boot must be >= 1")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    y, s = _as_arrays(labels, scores)
    n_pos, n_neg = int(y.sum()), int(y.size - y.sum())
    out: Dict[str, Any] = {
        "auroc": None,
        "ci_low": None,
        "ci_high": None,
        "n_pos": n_pos,
        "n_neg": n_neg,
        "n_boot": int(n_boot),
        "confidence": 1.0 - alpha,
    }
    if n_pos == 0 or n_neg == 0:
        return out
    out["auroc"] = float(_auroc_rows(y, s))
    idx = _stratified_indices(y, n_boot, np.random.default_rng(seed))
    boots = _auroc_rows(y[idx], s[idx])
    out["ci_low"], out["ci_high"] = _interval(boots, alpha)
    return out


def paired_bootstrap_auroc_difference(
    labels: Sequence[int],
    scores_a: Sequence[float],
    scores_b: Sequence[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> Dict[str, Any]:
    """AUROC(a) - AUROC(b) on the same items, with a paired stratified bootstrap interval.

    Returns:
        ``difference``, ``ci_low``, ``ci_high``, ``auroc_a``, ``auroc_b``, ``n_pos``,
        ``n_neg``, ``n_boot``, ``confidence`` (None values when a class is missing)
    """
    y, a = _as_arrays(labels, scores_a)
    _, b = _as_arrays(labels, scores_b)
    if a.shape != b.shape:
        raise ValueError("scores_a and scores_b differ in length")
    n_pos, n_neg = int(y.sum()), int(y.size - y.sum())
    out: Dict[str, Any] = {
        "difference": None,
        "ci_low": None,
        "ci_high": None,
        "auroc_a": None,
        "auroc_b": None,
        "n_pos": n_pos,
        "n_neg": n_neg,
        "n_boot": int(n_boot),
        "confidence": 1.0 - alpha,
    }
    if n_pos == 0 or n_neg == 0:
        return out
    auc_a, auc_b = float(_auroc_rows(y, a)), float(_auroc_rows(y, b))
    out.update({"auroc_a": auc_a, "auroc_b": auc_b, "difference": auc_a - auc_b})
    idx = _stratified_indices(y, n_boot, np.random.default_rng(seed))
    diffs = _auroc_rows(y[idx], a[idx]) - _auroc_rows(y[idx], b[idx])
    out["ci_low"], out["ci_high"] = _interval(diffs, alpha)
    return out
