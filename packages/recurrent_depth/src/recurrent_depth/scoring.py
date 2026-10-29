"""Combine signals into a calibrated verdict with an explicit inconclusive outcome.

Method
------
Each signal has a class-conditional likelihood model under two hypotheses:
``R`` (recurrent-depth: weight-tied iteration of a block, fixed or adaptive
count) and ``F`` (conventional fixed-depth transformer). A signal value ``x``
contributes a log-likelihood ratio ``log p(x | R) - log p(x | F)``, clipped to
``[-cap, +cap]`` so that no single measurement can dominate.

Signals in the same *family* (for example the two timing slopes) share
confounders, so they are not independent. Within a family the contributions
are combined with an effective-sample-size discount: the family LLR is the
mean contribution times ``n_eff = n / (1 + (n - 1) * rho)``, then clipped to
the family cap. Families are treated as independent and summed with the prior
log-odds.

The verdict is ``recurrent`` or ``fixed`` only when the posterior passes the
decision threshold *and* at least ``min_families`` families point the same way
with non-trivial strength; otherwise it is ``inconclusive``. A single strong
family (except white-box configuration evidence, which is direct
observation of the architecture) is not enough on its own.

The default likelihood parameters are rough engineering priors chosen so that
the pipeline runs; they are not calibrated against real systems. Fit them to
labeled reference models with :func:`fit_models` before trusting a verdict,
and check the result with :mod:`recurrent_depth.validation`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Iterable

RECURRENT = "recurrent"
FIXED = "fixed"
INCONCLUSIVE = "inconclusive"


@dataclass
class GaussianSignal:
    """Gaussian class-conditional densities for one scalar signal."""

    name: str
    family: str
    mean_r: float
    sd_r: float
    mean_f: float
    sd_f: float
    cap: float = 3.0  # |LLR| cap per signal; 3.0 is a likelihood ratio of about 20

    def llr(self, x: float) -> float:
        def logpdf(v: float, m: float, s: float) -> float:
            s = max(s, 1e-9)
            return -0.5 * ((v - m) / s) ** 2 - math.log(s)

        raw = logpdf(x, self.mean_r, self.sd_r) - logpdf(x, self.mean_f, self.sd_f)
        return max(-self.cap, min(self.cap, raw))


@dataclass
class CategoricalSignal:
    """A signal with a small set of outcomes, each with a fixed LLR.

    Used where evidence is asymmetric. A config that declares recurrence is
    near-proof; a config that does not is only weak evidence against, since
    custom modeling code can loop layers without saying so in the config.
    """

    name: str
    family: str
    table: dict[str, float]
    cap: float = 7.0

    def llr(self, x: float) -> float:
        key = _category_key(x)
        if key not in self.table:
            raise ValueError(f"signal {self.name!r} has no LLR for outcome {key!r}")
        return max(-self.cap, min(self.cap, self.table[key]))


def _category_key(x: float) -> str:
    return f"{float(x):g}"


SignalModel = GaussianSignal | CategoricalSignal


@dataclass
class ScoringConfig:
    prior_recurrent: float = 0.5
    threshold: float = 0.9  # posterior needed for a decided verdict (and 1 - threshold for "fixed")
    min_families: int = 2
    min_family_llr: float = 0.5
    within_family_rho: float = 0.5
    family_caps: dict[str, float] = field(
        default_factory=lambda: {
            "whitebox_config": 7.0,
            "whitebox_weights": 5.0,
            "whitebox_dynamics": 3.0,
            "graybox": 2.0,
            "timing": 3.0,
            "behavioral": 2.0,
            "knob": 2.0,
        }
    )
    # Families that count as direct observation and may decide on their own.
    decisive_families: tuple[str, ...] = ("whitebox_config", "whitebox_weights")


# Rough priors. Units: z-scores for slopes; ratios as defined in features.py;
# fractions for white-box signals. Replace with fit_models() output.
# config_recurrence outcomes: 1 = config declares looping / recurrence fields,
# 0.5 = custom modeling code with no declared recurrence (cannot tell),
# 0 = a standard, well-known fixed-depth architecture class.
DEFAULT_SIGNALS: dict[str, SignalModel] = {
    s.name: s
    for s in [
        CategoricalSignal("config_recurrence", "whitebox_config", {"1": 6.0, "0.5": 0.0, "0": -1.5}),
        GaussianSignal("weight_reuse_ratio", "whitebox_weights", 3.0, 1.5, 1.0, 0.05, cap=5.0),
        GaussianSignal("shared_layer_fraction", "whitebox_weights", 0.8, 0.25, 0.0, 0.05, cap=5.0),
        GaussianSignal("state_contraction", "whitebox_dynamics", 0.6, 0.2, 1.0, 0.25),
        GaussianSignal("similarity_periodicity", "whitebox_dynamics", 0.25, 0.15, 0.0, 0.08),
        GaussianSignal("ttft_slope_z", "timing", 4.0, 3.0, 0.0, 1.3),
        GaussianSignal("itl_slope_z", "timing", 3.0, 3.0, 0.0, 1.3),
        GaussianSignal("serial_retention", "behavioral", 0.7, 0.3, 0.35, 0.3, cap=1.5),
        GaussianSignal("knob_latency_log_ratio", "knob", 0.5, 0.4, 0.0, 0.15),
        GaussianSignal("knob_accuracy_gain", "knob", 0.2, 0.15, 0.0, 0.08, cap=1.5),
        GaussianSignal("compute_capacity_ratio", "graybox", 2.5, 1.2, 1.0, 0.4, cap=2.0),
    ]
}


@dataclass
class Verdict:
    label: str
    posterior_recurrent: float
    total_llr: float
    families: dict[str, float]
    contributions: dict[str, float]
    supporting_families: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def score(
    signals: dict[str, float],
    models: dict[str, SignalModel] | None = None,
    config: ScoringConfig | None = None,
) -> Verdict:
    """Score a dict of signal values. Unknown signal names are reported and ignored."""
    models = models or DEFAULT_SIGNALS
    cfg = config or ScoringConfig()
    notes: list[str] = []
    contributions: dict[str, float] = {}
    by_family: dict[str, list[float]] = {}
    for name, value in signals.items():
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        model = models.get(name)
        if model is None:
            notes.append(f"no likelihood model for signal {name!r}; ignored")
            continue
        c = model.llr(float(value))
        contributions[name] = c
        by_family.setdefault(model.family, []).append(c)

    families: dict[str, float] = {}
    for fam, vals in by_family.items():
        n = len(vals)
        n_eff = n / (1 + (n - 1) * cfg.within_family_rho)
        llr = sum(vals) / n * n_eff
        cap = cfg.family_caps.get(fam, 3.0)
        families[fam] = max(-cap, min(cap, llr))

    total = _logit(cfg.prior_recurrent) + sum(families.values())
    post = 1 / (1 + math.exp(-total))

    direction = 1 if post >= 0.5 else -1
    supporting = sorted(f for f, v in families.items() if v * direction >= cfg.min_family_llr)
    opposing = sorted(f for f, v in families.items() if v * direction <= -cfg.min_family_llr)
    decisive = any(f in cfg.decisive_families for f in supporting)

    label = INCONCLUSIVE
    if post >= cfg.threshold or post <= 1 - cfg.threshold:
        if len(supporting) >= cfg.min_families or decisive:
            label = RECURRENT if direction > 0 else FIXED
        else:
            notes.append(
                f"posterior {post:.3f} passes the threshold but only {len(supporting)} independent "
                f"famil{'y' if len(supporting) == 1 else 'ies'} support it; need {cfg.min_families}"
            )
    if opposing:
        notes.append(f"families pointing the other way: {', '.join(opposing)}")
    if not signals:
        notes.append("no signals supplied")
    return Verdict(label, post, total, families, contributions, supporting, notes)


# ---------------------------------------------------------------------------
# Fitting likelihood models to labeled reference models
# ---------------------------------------------------------------------------


def fit_models(
    references: Iterable[dict[str, Any]],
    base: dict[str, SignalModel] | None = None,
    sd_floor_frac: float = 0.25,
    shrink: float = 2.0,
) -> dict[str, SignalModel]:
    """Fit class means and spreads from labeled reference rows.

    Each row is ``{"model": str, "label": "recurrent"|"fixed", "signals": {...}}``.
    Means are shrunk toward the base model's means with ``shrink`` pseudo
    observations; spreads are floored at ``sd_floor_frac`` times the base
    spread so that a few tightly clustered references do not produce an
    overconfident detector.
    """
    base = base or DEFAULT_SIGNALS
    rows = list(references)
    fitted: dict[str, SignalModel] = {}
    for name, b in base.items():
        if not isinstance(b, GaussianSignal):
            fitted[name] = b
            continue
        vals = {RECURRENT: [], FIXED: []}
        for row in rows:
            v = row.get("signals", {}).get(name)
            if v is not None and row.get("label") in vals:
                vals[row["label"]].append(float(v))

        def est(xs: list[float], m0: float, s0: float) -> tuple[float, float]:
            if not xs:
                return m0, s0
            n = len(xs)
            mean = (sum(xs) + shrink * m0) / (n + shrink)
            var = (sum((x - mean) ** 2 for x in xs) + shrink * s0**2) / (n + shrink)
            return mean, max(math.sqrt(var), sd_floor_frac * s0)

        mr, sr = est(vals[RECURRENT], b.mean_r, b.sd_r)
        mf, sf = est(vals[FIXED], b.mean_f, b.sd_f)
        fitted[name] = GaussianSignal(name, b.family, mr, sr, mf, sf, b.cap)
    return fitted


def save_models(models: dict[str, SignalModel], path: str | Path) -> None:
    payload = {k: {"kind": type(v).__name__, **asdict(v)} for k, v in models.items()}
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_models(path: str | Path) -> dict[str, SignalModel]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, SignalModel] = {}
    for k, v in data.items():
        kind = v.pop("kind", "GaussianSignal")
        out[k] = CategoricalSignal(**v) if kind == "CategoricalSignal" else GaussianSignal(**v)
    return out
