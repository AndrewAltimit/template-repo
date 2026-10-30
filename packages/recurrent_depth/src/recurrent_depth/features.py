"""Turn black-box probe records into scalar signals.

Signals (all computed only from what an ordinary API customer observes):

``ttft_slope_z``
    z-score of the depth coefficient in a regression of log time-to-first-token
    on serial depth, controlling for prompt length and for slow drift over the
    run (request order). Within a task family the
    prompt length is constant by construction, so a positive slope means the
    server spent more time before the first token on items that need more
    sequential steps. Fixed-depth dense models should show no slope. Adaptive
    per-token depth predicts a positive slope.
``itl_slope_z``
    The same for mean inter-token latency (needs multi-token outputs).
``serial_retention``
    Chance-corrected accuracy at the deepest third of depths divided by that
    at the shallowest third, averaged over task families. Higher values mean
    accuracy holds up as serial depth grows without visible reasoning.
``knob_latency_log_ratio`` / ``knob_accuracy_gain``
    Effect of a compute knob (for example a reasoning-effort parameter) on
    latency and accuracy when the number of visible and billed reasoning tokens
    does not change. Both are computed only from requests with no reported
    reasoning tokens and the modal completion length, and neither is emitted
    if any request in the run reported hidden reasoning tokens.

Each function returns ``None`` for a signal when the data cannot support it.
"""

from __future__ import annotations

from collections import defaultdict
import math
import statistics
from typing import Any, Iterable

import numpy as np


def _ok(rec: dict[str, Any]) -> bool:
    return rec.get("error") is None and 200 <= int(rec.get("status") or 0) < 300


def _no_hidden_tokens(rec: dict[str, Any]) -> bool:
    return not rec.get("reasoning_tokens")


def ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ordinary least squares returning coefficients and standard errors."""
    n, k = X.shape
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = max(n - k, 1)
    sigma2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.clip(np.diag(xtx_inv) * sigma2, 1e-30, None))
    return coef, se


def _trim(rows: list[dict[str, Any]], key: str, frac: float) -> list[dict[str, Any]]:
    """Drop the ``frac`` most extreme slow outliers, judged against their own depth.

    Trimming on raw latency would preferentially remove the deepest items
    whenever depth really does raise latency, biasing the slope toward zero.
    Each value is therefore compared with the median of its depth cell, and
    the largest ratios are dropped.
    """
    if frac <= 0 or len(rows) < 10:
        return rows
    by_depth: dict[Any, list[float]] = defaultdict(list)
    for r in rows:
        by_depth[r["depth"]].append(r[key])
    med = {d: statistics.median(v) for d, v in by_depth.items()}
    ratio = [r[key] / med[r["depth"]] for r in rows]
    cut = float(np.quantile(ratio, 1 - frac))
    return [r for r, q in zip(rows, ratio) if q <= cut]


def timing_slope(
    records: Iterable[dict[str, Any]],
    metric: str = "ttft_s",
    trim_frac: float = 0.05,
    knob: Any = None,
) -> dict[str, Any] | None:
    """Pooled depth effect on log latency across task families."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        if not (_ok(r) and _no_hidden_tokens(r)) or r.get("knob") != knob:
            continue
        val = r.get(metric)
        if val is None or val <= 0:
            continue
        groups[r["task"]].append(r)
    estimates = []
    for task, rows in groups.items():
        rows = _trim(rows, metric, trim_frac)
        depths = np.array([r["depth"] for r in rows], dtype=float)
        if len(rows) < 6 or np.ptp(depths) == 0:
            continue
        y = np.log(np.array([r[metric] for r in rows], dtype=float))
        cols = [np.ones_like(depths), depths]
        ptoks = [r.get("prompt_tokens") or r.get("prompt_chars") or 0 for r in rows]
        pt = np.array(ptoks, dtype=float)
        if np.ptp(pt) > 0 and np.corrcoef(pt, depths)[0, 1] ** 2 < 0.95:
            cols.append((pt - pt.mean()) / (pt.std() or 1.0))
        # Request order absorbs slow drift in server load. The run order is
        # randomized, so this does not bias the depth coefficient; it only
        # removes drift from the residuals that set its standard error.
        seq = np.array([float(r.get("seq", 0) or 0) for r in rows])
        if np.ptp(seq) > 0 and np.corrcoef(seq, depths)[0, 1] ** 2 < 0.5:
            cols.append((seq - seq.mean()) / (seq.std() or 1.0))
        coef, se = ols(y, np.column_stack(cols))
        estimates.append((task, float(coef[1]), float(se[1]), len(rows)))
    if not estimates:
        return None
    w = np.array([1 / e[2] ** 2 for e in estimates])
    b = np.array([e[1] for e in estimates])
    pooled = float((w * b).sum() / w.sum())
    pooled_se = float(1 / math.sqrt(w.sum()))
    return {
        "log_slope": pooled,
        "se": pooled_se,
        "z": pooled / pooled_se,
        "n": int(sum(e[3] for e in estimates)),
        "per_task": {e[0]: {"log_slope": e[1], "se": e[2], "n": e[3]} for e in estimates},
    }


def accuracy_curves(records: Iterable[dict[str, Any]], knob: Any = None) -> dict[str, dict[int, dict[str, float]]]:
    """Per task and depth: raw accuracy, chance-corrected accuracy, and count."""
    tally: dict[str, dict[int, list[bool]]] = defaultdict(lambda: defaultdict(list))
    chance: dict[str, float] = {}
    for r in records:
        if not _ok(r) or r.get("knob") != knob:
            continue
        tally[r["task"]][int(r["depth"])].append(bool(r["correct"]))
        chance[r["task"]] = float(r.get("chance", 0.0))
    out: dict[str, dict[int, dict[str, float]]] = {}
    for task, by_depth in tally.items():
        c = chance[task]
        out[task] = {}
        for d in sorted(by_depth):
            acc = statistics.fmean(by_depth[d])
            out[task][d] = {"acc": acc, "corrected": (acc - c) / (1 - c) if c < 1 else 0.0, "n": len(by_depth[d])}
    return out


def serial_retention(curves: dict[str, dict[int, dict[str, float]]], floor: float = 0.05) -> float | None:
    """Mean over tasks of corrected accuracy (deepest third / shallowest third)."""
    ratios = []
    for by_depth in curves.values():
        depths = sorted(by_depth)
        if len(depths) < 3:
            continue
        k = max(1, len(depths) // 3)
        lo = statistics.fmean(by_depth[d]["corrected"] for d in depths[:k])
        hi = statistics.fmean(by_depth[d]["corrected"] for d in depths[-k:])
        if lo < floor:
            continue  # the model cannot do the easy items; the ratio is meaningless
        ratios.append(min(max(hi, 0.0) / lo, 2.0))
    return statistics.fmean(ratios) if ratios else None


def knob_effects(records: list[dict[str, Any]], knob_order: list[Any]) -> dict[str, Any] | None:
    """Latency and accuracy change between the lowest and highest knob setting."""
    if len(knob_order) < 2:
        return None
    lo_k, hi_k = knob_order[0], knob_order[-1]
    hidden = any(r.get("reasoning_tokens") for r in records if _ok(r))

    def rows(k: Any) -> list[dict[str, Any]]:
        return [r for r in records if _ok(r) and r.get("knob") == k]

    lo_rows, hi_rows = rows(lo_k), rows(hi_k)
    if len(lo_rows) < 5 or len(hi_rows) < 5:
        return None
    clean_lo = [r for r in lo_rows if _no_hidden_tokens(r)]
    clean_hi = [r for r in hi_rows if _no_hidden_tokens(r)]
    lens = [r.get("completion_tokens") for r in clean_lo + clean_hi if r.get("completion_tokens") is not None]
    if lens:
        mode = statistics.mode(lens)
        clean_lo = [r for r in clean_lo if r.get("completion_tokens") in (None, mode)]
        clean_hi = [r for r in clean_hi if r.get("completion_tokens") in (None, mode)]

    def corrected(rs: list[dict[str, Any]]) -> float:
        return statistics.fmean((float(r["correct"]) - r.get("chance", 0.0)) / (1 - r.get("chance", 0.0)) for r in rs)

    ratio = None
    gain = None
    if len(clean_lo) >= 5 and len(clean_hi) >= 5:
        ratio = math.log(statistics.median(r["total_s"] for r in clean_hi) / statistics.median(r["total_s"] for r in clean_lo))
        # Same exclusions as the latency ratio: an accuracy gain bought with hidden
        # reasoning tokens is ordinary decoding, not in-pass compute.
        gain = corrected(clean_hi) - corrected(clean_lo)

    return {
        "latency_log_ratio": ratio,
        "accuracy_gain": gain,
        "accuracy_gain_all_rows": corrected(hi_rows) - corrected(lo_rows),
        "hidden_reasoning_tokens_seen": hidden,
        "n_low": len(lo_rows),
        "n_high": len(hi_rows),
    }


def ttft_excess_in_itl(records: Iterable[dict[str, Any]], knob: Any = None) -> float | None:
    """TTFT increase from the shallowest to the deepest depth, in units of median ITL.

    A diagnostic, not a scored signal. Extra loop iterations on the first token
    cost a fraction of one decode step each, so an adaptive-depth model should
    add at most a few inter-token latencies of TTFT across the depth range. An
    increase worth tens of tokens is better explained by hidden decoding
    (reasoning tokens the usage fields do not report) or by routing.
    """
    rows = [r for r in records if _ok(r) and _no_hidden_tokens(r) and r.get("knob") == knob and r.get("ttft_s")]
    itls = [r["itl_mean_s"] for r in rows if r.get("itl_mean_s")]
    if not rows or not itls:
        return None
    depths = sorted({int(r["depth"]) for r in rows})
    if len(depths) < 2:
        return None
    lo = statistics.median(r["ttft_s"] for r in rows if int(r["depth"]) == depths[0])
    hi = statistics.median(r["ttft_s"] for r in rows if int(r["depth"]) == depths[-1])
    itl = statistics.median(itls)
    return (hi - lo) / itl if itl > 0 else None


def extract_signals(records: list[dict[str, Any]], knob_order: list[Any] | None = None) -> dict[str, Any]:
    """Compute every black-box signal the records support.

    Returns ``{"signals": {name: value}, "diagnostics": {...}}``. Signals that
    cannot be computed are omitted rather than set to a default.
    """
    knobs = knob_order or []
    base = knobs[0] if knobs else None
    signals: dict[str, float] = {}
    diag: dict[str, Any] = {"n_records": len(records), "n_ok": sum(_ok(r) for r in records)}
    ttft = timing_slope(records, "ttft_s", knob=base)
    if ttft:
        signals["ttft_slope_z"] = ttft["z"]
        excess = ttft_excess_in_itl(records, knob=base)
        if excess is not None:
            diag["ttft_excess_in_itl"] = excess
        diag["ttft"] = ttft
    itl = timing_slope(records, "itl_mean_s", knob=base)
    if itl:
        signals["itl_slope_z"] = itl["z"]
        diag["itl"] = itl
    curves = accuracy_curves(records, knob=base)
    diag["accuracy_curves"] = curves
    ret = serial_retention(curves)
    if ret is not None:
        signals["serial_retention"] = ret
    if len(knobs) >= 2:
        eff = knob_effects(records, knobs)
        if eff:
            diag["knob"] = eff
            if not eff["hidden_reasoning_tokens_seen"]:
                if eff["accuracy_gain"] is not None:
                    signals["knob_accuracy_gain"] = eff["accuracy_gain"]
                if eff["latency_log_ratio"] is not None:
                    signals["knob_latency_log_ratio"] = eff["latency_log_ratio"]
    return {"signals": signals, "diagnostics": diag}
