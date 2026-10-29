"""Hidden-state dynamics across layers or loop iterations.

Inputs are arrays of shape ``(steps, tokens, dim)``: the residual-stream state
after each layer (a fixed-depth model) or after each iteration of a recurrent
block. Recording them needs only forward hooks or ``output_hidden_states``;
see :mod:`recurrent_depth.hf_capture`.

Measures
--------
``step_change``
    Median over tokens of ``||h[t+1] - h[t]|| / ||h[t]||``.
``contraction``
    Geometric-mean ratio of successive step changes over the last part of the
    trajectory. Below 1 the state is converging toward a fixed point (as
    reported for many tokens in Huginn, Geiping et al. 2025); around or above
    1 it is not. Fixed-depth stacks have no reason to converge, and repeating
    one of their layers usually drifts.
``cosine_matrix`` / ``linear_cka``
    Layer-by-layer representation similarity (Kornblith et al. 2019).
``similarity_periodicity``
    Excess similarity at a lag ``p`` relative to neighboring lags in the
    similarity matrix, a heuristic for a block of ``p`` layers applied
    repeatedly.
``logit_lens_kl``
    KL divergence between next-token distributions decoded from successive
    states (logit lens, nostalgebraist 2020). Huginn exits its loop when this
    falls below a threshold, so the step at which it settles is a direct
    readout of per-token adaptive depth.
"""

from __future__ import annotations

import numpy as np


def _check(h: np.ndarray) -> np.ndarray:
    h = np.asarray(h, dtype=np.float64)
    if h.ndim != 3 or h.shape[0] < 2:
        raise ValueError("expected an array of shape (steps >= 2, tokens, dim)")
    return h


def step_change(h: np.ndarray) -> np.ndarray:
    h = _check(h)
    diff = np.linalg.norm(h[1:] - h[:-1], axis=-1)
    base = np.maximum(np.linalg.norm(h[:-1], axis=-1), 1e-12)
    return np.median(diff / base, axis=1)


def contraction(h: np.ndarray, tail: float = 0.5) -> float:
    """Geometric-mean ratio of successive step changes over the trajectory tail."""
    sc = step_change(h)
    if len(sc) < 3:
        raise ValueError("need at least 4 steps to estimate contraction")
    start = int(len(sc) * (1 - tail))
    seg = np.maximum(sc[max(0, start - 1) :], 1e-15)
    ratios = seg[1:] / seg[:-1]
    return float(np.exp(np.mean(np.log(ratios))))


def cosine_matrix(h: np.ndarray) -> np.ndarray:
    """Mean token-wise cosine similarity between every pair of steps."""
    h = _check(h)
    unit = h / np.maximum(np.linalg.norm(h, axis=-1, keepdims=True), 1e-12)
    return np.einsum("atd,btd->ab", unit, unit) / h.shape[1]


def linear_cka(x: np.ndarray, y: np.ndarray) -> float:
    """Linear CKA between two (tokens, dim) representations."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    x = x - x.mean(axis=0, keepdims=True)
    y = y - y.mean(axis=0, keepdims=True)
    hsic = np.linalg.norm(x.T @ y) ** 2
    norm = np.linalg.norm(x.T @ x) * np.linalg.norm(y.T @ y)
    return float(hsic / norm) if norm > 0 else 0.0


def cka_matrix(h: np.ndarray) -> np.ndarray:
    h = _check(h)
    n = h.shape[0]
    out = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            out[i, j] = out[j, i] = linear_cka(h[i], h[j])
    return out


def similarity_periodicity(sim: np.ndarray, min_lag: int = 2) -> tuple[int | None, float]:
    """Best lag and its excess mean similarity over the neighboring lags."""
    sim = np.asarray(sim, dtype=np.float64)
    n = sim.shape[0]
    if n < 2 * min_lag + 2:
        return None, 0.0
    diag_mean = {lag: float(np.mean(np.diagonal(sim, offset=lag))) for lag in range(1, n)}
    best_lag, best = None, 0.0
    for lag in range(min_lag, n // 2 + 1):
        neighbors = [diag_mean[k] for k in (lag - 1, lag + 1) if k in diag_mean]
        excess = diag_mean[lag] - float(np.mean(neighbors))
        if excess > best:
            best_lag, best = lag, excess
    return best_lag, best


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def logit_lens_kl(h: np.ndarray, unembed: np.ndarray, norm_eps: float | None = 1e-6) -> np.ndarray:
    """KL(p_t || p_{t+1}) per step and token, decoding each state with ``unembed``.

    ``unembed`` has shape (dim, vocab). If ``norm_eps`` is given, states are
    RMS-normalized first, which approximates the final norm of most models.
    Returns an array of shape (steps - 1, tokens).
    """
    h = _check(h)
    if norm_eps is not None:
        h = h / np.sqrt(np.mean(h**2, axis=-1, keepdims=True) + norm_eps)
    p = _softmax(h @ unembed)
    logp = np.log(np.maximum(p, 1e-30))
    return np.sum(p[:-1] * (logp[:-1] - logp[1:]), axis=-1)


def settle_steps(kl: np.ndarray, threshold: float = 5e-4) -> np.ndarray:
    """First step index after which KL stays below ``threshold``, per token."""
    below = kl < threshold
    steps = kl.shape[0]
    out = np.full(kl.shape[1], steps, dtype=int)
    for t in range(kl.shape[1]):
        for s in range(steps):
            if below[s:, t].all():
                out[t] = s + 1
                break
    return out


def dynamics_signals(h: np.ndarray) -> dict[str, float]:
    """Signals for the scorer from one recorded trajectory."""
    out = {"state_contraction": contraction(h)}
    _, excess = similarity_periodicity(cosine_matrix(h))
    out["similarity_periodicity"] = excess
    return out
