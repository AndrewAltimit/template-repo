"""Benchmark the classifier on labeled reference models before using it.

Given reference rows (models whose architecture is publicly documented, for
example open looped models and open fixed-depth models measured with the
same probe plan), :func:`leave_one_out` refits the likelihood models without
each reference in turn, scores the held-out one, and reports:

* coverage: fraction of references that receive a decided verdict;
* accuracy among decided verdicts, and the number of wrong decided verdicts;
* Brier score and log loss of the posterior over all references;
* a confusion table including the inconclusive column.

A detector that is never wrong because it is always inconclusive is useless,
and one with high coverage and a few confident errors is dangerous, so both
coverage and errors are reported.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from .scoring import FIXED, INCONCLUSIVE, RECURRENT, ScoringConfig, SignalModel, fit_models, score


def leave_one_out(
    references: Iterable[dict[str, Any]],
    base: dict[str, SignalModel] | None = None,
    config: ScoringConfig | None = None,
) -> dict[str, Any]:
    rows = [r for r in references if r.get("label") in (RECURRENT, FIXED)]
    if len(rows) < 2:
        raise ValueError("need at least two labeled references")
    per_model = []
    confusion = {lab: {RECURRENT: 0, FIXED: 0, INCONCLUSIVE: 0} for lab in (RECURRENT, FIXED)}
    brier = 0.0
    logloss = 0.0
    for i, held in enumerate(rows):
        train = rows[:i] + rows[i + 1 :]
        models = fit_models(train, base=base)
        v = score(held.get("signals", {}), models, config)
        y = 1.0 if held["label"] == RECURRENT else 0.0
        p = min(max(v.posterior_recurrent, 1e-6), 1 - 1e-6)
        brier += (p - y) ** 2
        logloss += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        confusion[held["label"]][v.label] += 1
        per_model.append(
            {
                "model": held.get("model", f"ref{i}"),
                "label": held["label"],
                "verdict": v.label,
                "posterior": v.posterior_recurrent,
            }
        )
    n = len(rows)
    decided = [m for m in per_model if m["verdict"] != INCONCLUSIVE]
    correct = [m for m in decided if m["verdict"] == m["label"]]
    return {
        "n": n,
        "coverage": len(decided) / n,
        "accuracy_decided": (len(correct) / len(decided)) if decided else None,
        "wrong_decided": len(decided) - len(correct),
        "brier": brier / n,
        "log_loss": logloss / n,
        "confusion": confusion,
        "per_model": per_model,
    }
