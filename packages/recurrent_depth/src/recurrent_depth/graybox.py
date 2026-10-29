"""Gray-box helpers: what log-probabilities and coarse budgets can add.

``estimate_rank``
    Numerical rank of a matrix of logit (or log-probability) vectors collected
    from many prompts. Because the final layer maps a ``d``-dimensional state
    to the vocabulary, these vectors span at most ``d`` (``d + 1`` for
    log-probabilities) dimensions, which is how Carlini et al. (2024) and
    Finlayson et al. (2024) estimated hidden sizes of API models. Use it on
    vectors you are entitled to collect; it reveals a width, not weights.
    Width alone does not reveal looping. It is useful as an input to the
    compute-to-capacity comparison below.

``compute_capacity_ratio``
    Ratio of the compute a model appears to spend per token to the compute
    expected from the parameters it appears to store. A looped model runs
    its stored block several times, so the ratio exceeds 1. Mixture-of-experts
    pushes the ratio below 1 (fewer active than stored parameters), which
    makes the two distinguishable in direction. Both inputs are rough
    estimates with large error bars, so this signal carries a low cap.
"""

from __future__ import annotations

import numpy as np


def estimate_rank(vectors: np.ndarray, center: bool = True) -> tuple[int, np.ndarray]:
    """Rank at the largest gap in log singular values, plus the spectrum.

    ``vectors`` has shape (n_prompts, n_vocab_entries) with n_prompts larger
    than the expected hidden size. Centering removes the per-prompt
    normalization offset of log-probabilities.
    """
    m = np.asarray(vectors, dtype=np.float64)
    if center:
        m = m - m.mean(axis=1, keepdims=True)
    s = np.linalg.svd(m, compute_uv=False)
    s = s[s > 0]
    if len(s) < 2:
        return len(s), s
    gaps = np.log(s[:-1]) - np.log(s[1:])
    return int(np.argmax(gaps) + 1), s


def compute_capacity_ratio(effective_compute_params: float, stored_params: float) -> float:
    """Per-token compute expressed in parameter-equivalents over stored parameters.

    ``effective_compute_params`` is the dense parameter count whose per-token
    cost matches what you measured (for example from decode latency on known
    hardware, or a provider's published FLOPs per token). ``stored_params`` is
    an estimate of stored parameters (for example from memorization capacity
    probes, or a published size). Both are user-supplied estimates.
    """
    if stored_params <= 0 or effective_compute_params <= 0:
        raise ValueError("both quantities must be positive")
    return effective_compute_params / stored_params
