"""Reasoning-budget sweep: how load-bearing is a model's visible reasoning?

The timing probes in :mod:`harness` only see *adaptive* in-pass compute, and a
model that always runs the same number of loop iterations looks, from outside,
like a deeper fixed model. This module asks a different question that an API
customer can answer without ever reading the chain of thought: when the
reasoning budget shrinks, how much accuracy on serial tasks does the model
lose, and how many reasoning tokens does it spend per serial step?

If much of the serial work happens inside the forward pass (for example in
recurrent-depth loops), accuracy should degrade less as the budget shrinks and
fewer reasoning tokens should be needed per step. A model whose visible
reasoning is load-bearing should show the opposite. This is the outside
counterpart of the CoT-controllability results some labs report from raw
reasoning traces.

These are diagnostics, not scored signals: capability confounds them (a
stronger fixed-depth model also degrades less), so compare models within a
family or against references of similar capability, and treat the result as
consistent with, not proof of, in-pass recurrence.

A plan (JSON) lists *conditions*, each a label, an output cap, and provider
parameters that set the reasoning budget, for example on OpenRouter::

    {"label": "minimal", "max_tokens": 128,  "params": {"reasoning": {"effort": "minimal"}}}
    {"label": "r1024",   "max_tokens": 1280, "params": {"reasoning": {"max_tokens": 1024}}}

Providers may map a token budget onto coarse effort levels, so the analysis
uses the reasoning tokens actually observed per request, not the nominal
budget.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import random
import statistics
import time
from typing import Any, Callable

import numpy as np

from .client import RESERVED_FIELDS, BudgetExceeded, ChatClient, RateLimiter
from .features import ols
from .harness import API_KEY_ENV_PATTERN, TERMS_NOTICE
from .tasks import NO_COT_SUFFIX, TaskItem, _normalize, check_answer, generate

# Output cap per request, reasoning included. Long enough for a real reasoning
# budget, short enough that a plan cannot run up an open-ended bill per call.
MAX_CONDITION_TOKENS = 16384
MAX_TIMEOUT_S = 600.0
MAX_FILLER = 4096

# Filler-token condition (Pfau et al. 2024, "Let's think dot by dot"): the
# model must emit meaningless periods before its answer. If accuracy rises with
# the number of periods while reasoning is off, the model is using extra
# forward passes without writing anything legible.
# Periods are space-separated (". . . .") because tokenizers pack runs of
# periods into a few tokens: 128 contiguous periods bill under 10 tokens, which
# would buy almost no extra forward passes.
FILLER_INSTRUCTION = (
    "Before your answer, output exactly {n} periods separated by single spaces (. . . .) and nothing else, "
    "then give only the final answer. Do not explain or show any steps, and write nothing but the periods "
    "and the answer."
)


class TokenBudgetExceeded(BudgetExceeded):
    """Raised when the plan's total completion-token budget is used up."""


@dataclass
class BudgetCondition:
    label: str
    max_tokens: int
    params: dict[str, Any] = field(default_factory=dict)
    filler: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BudgetCondition":
        return cls(
            label=str(data["label"]),
            max_tokens=int(data["max_tokens"]),
            params=dict(data.get("params") or {}),
            filler=int(data.get("filler") or 0),
        )

    def prompt(self, item: TaskItem) -> str:
        if not self.filler:
            return item.prompt
        instruction = FILLER_INSTRUCTION.format(n=self.filler)
        if NO_COT_SUFFIX in item.prompt:
            return item.prompt.replace(NO_COT_SUFFIX, instruction)
        return item.prompt.rstrip("\n") + "\n" + instruction


def filler_stats(response: str, n: int) -> tuple[int, bool]:
    """Periods emitted and whether the response is periods followed by a short answer only.

    Compliant means at least half the requested periods, and at most four
    words after them, so a response that reasons in prose instead does not
    count as a filler-only response.
    """
    text = response or ""
    dots = text.count(".") + 3 * text.count("…")
    words = _normalize(text).split()
    return dots, dots >= n / 2 and 0 < len(words) <= 4


@dataclass
class BudgetPlan:
    base_url: str
    model: str
    conditions: list[BudgetCondition]
    tasks: list[str] = field(default_factory=lambda: ["pointer_chase", "permutation", "parity", "reachability"])
    depths: list[int] = field(default_factory=lambda: [2, 8, 12, 24])
    reps: int = 4
    seed: int = 0
    temperature: float = 0.0
    requests_per_minute: float = 10.0
    max_requests: int = 500
    max_total_completion_tokens: int = 200_000
    timeout_s: float = 300.0
    api_key_env: str | None = "OPENAI_API_KEY"
    extra: dict[str, Any] = field(default_factory=dict)
    # Optional latent two-hop suite instead of the synthetic tasks: path to a
    # TwoHopFact CSV (Yang et al. 2024) and the number of facts to sample.
    twohop_csv: str | None = None
    twohop_n: int = 0
    acknowledge_terms: bool = False

    @classmethod
    def from_json(cls, path: str | Path) -> "BudgetPlan":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        known["conditions"] = [BudgetCondition.from_dict(c) for c in data.get("conditions", [])]
        return cls(**known)

    def suite(self) -> tuple[list[TaskItem], list[tuple[str, int]]]:
        """Items for every valid (task, depth), and the combinations a generator rejects."""
        if self.twohop_csv:
            from .twohop import load_items

            return load_items(self.twohop_csv, self.twohop_n, seed=self.seed), []
        rng = random.Random(self.seed)
        items: list[TaskItem] = []
        skipped: list[tuple[str, int]] = []
        for task in self.tasks:
            for depth in self.depths:
                try:
                    batch = [generate(task, depth, rng) for _ in range(self.reps)]
                except ValueError:
                    skipped.append((task, depth))
                    continue
                items.extend(batch)
        return items, skipped

    def planned_requests(self) -> int:
        return len(self.suite()[0]) * len(self.conditions)

    def validate(self, allow_any_key_env: bool = False) -> None:
        if not self.acknowledge_terms:
            raise PermissionError(TERMS_NOTICE)
        if not self.conditions:
            raise ValueError("a budget plan needs at least one condition")
        labels = [c.label for c in self.conditions]
        if len(set(labels)) != len(labels):
            raise ValueError("condition labels must be unique")
        for c in self.conditions:
            if not 1 <= c.max_tokens <= MAX_CONDITION_TOKENS:
                raise ValueError(f"condition {c.label!r}: max_tokens must be between 1 and {MAX_CONDITION_TOKENS}")
            if not 0 <= c.filler <= MAX_FILLER:
                raise ValueError(f"condition {c.label!r}: filler must be between 0 and {MAX_FILLER}")
            clash = sorted(RESERVED_FIELDS & set(c.params))
            if clash:
                raise ValueError(f"condition {c.label!r} may not set request fields the client controls: {clash}")
        clash = sorted(RESERVED_FIELDS & set(self.extra))
        if clash:
            raise ValueError(f"extra may not set request fields the client controls: {clash}")
        n = self.planned_requests()
        if n == 0:
            raise ValueError("no valid (task, depth) combinations in the plan")
        if n > self.max_requests:
            raise ValueError(
                f"plan needs {n} requests but max_requests is {self.max_requests}; "
                "reduce reps, depths, or conditions, or raise the budget deliberately"
            )
        if self.max_total_completion_tokens < 1:
            raise ValueError("max_total_completion_tokens must be positive")
        if self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if not 0 < self.timeout_s <= MAX_TIMEOUT_S:
            raise ValueError(f"timeout_s must be in (0, {MAX_TIMEOUT_S}]")
        if self.api_key_env is not None and not allow_any_key_env and not API_KEY_ENV_PATTERN.match(self.api_key_env):
            raise ValueError(
                f"api_key_env {self.api_key_env!r} does not look like an API key variable (NAME_API_KEY); "
                "a plan may not name arbitrary environment variables. Pass --api-key-env to override deliberately."
            )


def run_budget_plan(
    plan: BudgetPlan,
    client: ChatClient | None = None,
    out_path: str | Path | None = None,
    progress: Callable[[int, int], None] | None = None,
    allow_any_key_env: bool = False,
) -> list[dict[str, Any]]:
    """Run every item under every condition in a seeded random order.

    Stops with :class:`BudgetExceeded` when the request budget runs out and
    with :class:`TokenBudgetExceeded` once the completion tokens billed so far
    reach ``max_total_completion_tokens``; records written so far are kept.
    """
    plan.validate(allow_any_key_env=allow_any_key_env)
    if client is None:
        limiter = RateLimiter(requests_per_minute=plan.requests_per_minute, max_requests=plan.max_requests)
        client = ChatClient(plan.base_url, plan.model, api_key_env=plan.api_key_env, limiter=limiter, timeout_s=plan.timeout_s)
    items, _ = plan.suite()
    jobs = [(item, ci) for item in items for ci in range(len(plan.conditions))]
    random.Random(plan.seed + 1).shuffle(jobs)
    records: list[dict[str, Any]] = []
    billed = 0
    sink = open(out_path, "a", encoding="utf-8") if out_path else None
    try:
        for i, (item, ci) in enumerate(jobs):
            if billed >= plan.max_total_completion_tokens:
                raise TokenBudgetExceeded(
                    f"completion-token budget of {plan.max_total_completion_tokens} reached "
                    f"after {len(records)} of {len(jobs)} planned requests"
                )
            cond = plan.conditions[ci]
            extra = {**plan.extra, **cond.params}
            try:
                res = client.complete(cond.prompt(item), max_tokens=cond.max_tokens, temperature=plan.temperature, extra=extra)
            except BudgetExceeded as exc:
                raise BudgetExceeded(f"{exc} after {len(records)} of {len(jobs)} planned requests") from exc
            billed += res.completion_tokens or 0
            rec = {
                "task": item.task,
                "depth": item.depth,
                "chance": item.chance,
                "item_id": item.meta.get("uid") if isinstance(item.meta, dict) else None,
                "condition": cond.label,
                "condition_index": ci,
                "filler": cond.filler,
                "answer": item.answer,
                "response": res.text,
                "correct": bool(res.ok and check_answer(item, res.text)),
                "status": res.status,
                "error": res.error,
                "attempts": res.attempts,
                "finish_reason": res.finish_reason,
                "ttft_s": res.ttft_s,
                "total_s": res.total_s,
                "prompt_tokens": res.prompt_tokens,
                "completion_tokens": res.completion_tokens,
                "reasoning_tokens": res.reasoning_tokens,
                "seq": i,
                "wall_time": time.time(),
            }
            if cond.filler:
                rec["filler_dots"], rec["filler_compliant"] = filler_stats(res.text, cond.filler)
            records.append(rec)
            if sink:
                sink.write(json.dumps(rec) + "\n")
                sink.flush()
            if progress:
                progress(i + 1, len(jobs))
    finally:
        if sink:
            sink.close()
    return records


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def _ok(r: dict[str, Any]) -> bool:
    return r.get("error") is None and 200 <= int(r.get("status") or 0) < 300


def _tokens(r: dict[str, Any], metric: str) -> float:
    if metric == "reasoning":
        return float(r.get("reasoning_tokens") or 0)
    return float(r.get("completion_tokens") or 0)


def _corrected(rows: list[dict[str, Any]]) -> float | None:
    """Chance-corrected accuracy, averaged over tasks so each family counts equally."""
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r)
    vals = []
    for rs in by_task.values():
        c = float(rs[0].get("chance", 0.0))
        acc = statistics.fmean(bool(r["correct"]) for r in rs)
        vals.append((acc - c) / (1 - c) if c < 1 else 0.0)
    return statistics.fmean(vals) if vals else None


def _cells(records: list[dict[str, Any]]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    cells: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        if _ok(r):
            cells[(r["condition"], int(r["depth"]))].append(r)
    return cells


def _in_pass_share(cells, lo: str, hi: str, depths: list[int], min_hi: float) -> tuple[float | None, dict[int, float]]:
    per_depth: dict[int, float] = {}
    weights: dict[int, int] = {}
    for d in depths:
        a_lo = _corrected(cells.get((lo, d), []))
        a_hi = _corrected(cells.get((hi, d), []))
        if a_lo is None or a_hi is None or a_hi < min_hi:
            continue
        per_depth[d] = min(max(a_lo, 0.0) / a_hi, 1.5)
        weights[d] = len(cells[(lo, d)]) + len(cells[(hi, d)])
    if not per_depth:
        return None, per_depth
    total = sum(weights.values())
    return sum(per_depth[d] * weights[d] for d in per_depth) / total, per_depth


def _cell_summary(rs: list[dict[str, Any]], token_metric: str) -> dict[str, Any]:
    toks = [_tokens(r, token_metric) for r in rs]
    truncated = sum(1 for r in rs if r.get("finish_reason") == "length" or not (r.get("response") or "").strip())
    summary = {
        "n": len(rs),
        "acc": statistics.fmean(bool(r["correct"]) for r in rs),
        "corrected_acc": _corrected(rs),
        "tokens_mean": statistics.fmean(toks),
        "tokens_median": statistics.median(toks),
        "reported_reasoning_mean": statistics.fmean(float(r.get("reasoning_tokens") or 0) for r in rs),
        "truncated": truncated / len(rs),
    }
    if any(r.get("filler") for r in rs):
        compliant = [r for r in rs if r.get("filler_compliant")]
        summary["filler_compliance"] = len(compliant) / len(rs)
        summary["acc_compliant"] = statistics.fmean(bool(r["correct"]) for r in compliant) if compliant else None
        summary["corrected_acc_compliant"] = _corrected(compliant) if compliant else None
    return summary


def latency_per_token(records: list[dict[str, Any]]) -> dict[str, float] | None:
    """Seconds of total latency per billed completion token (OLS slope), in milliseconds.

    With reasoning hidden, almost all of a request's time is spent decoding
    reasoning tokens, so the slope estimates the decode cost per token on that
    serving stack. A model that runs more passes per token decodes more slowly
    than a same-size model that does not, but size and serving hardware
    confound this, so compare within one provider and price tier.
    """
    rows = [r for r in records if _ok(r) and r.get("completion_tokens") and r.get("total_s")]
    x = np.array([float(r["completion_tokens"]) for r in rows])
    if len(rows) < 8 or np.ptp(x) == 0:
        return None
    y = np.array([float(r["total_s"]) for r in rows])
    coef, se = ols(y, np.column_stack([np.ones_like(x), x]))
    return {"ms_per_token": 1000 * float(coef[1]), "se_ms": 1000 * float(se[1]), "intercept_s": float(coef[0]), "n": len(rows)}


def _logistic_fit(x: np.ndarray, y: np.ndarray, iters: int = 50) -> tuple[float, float] | None:
    """Maximum-likelihood logistic regression of y on x (Newton steps, small ridge for stability)."""
    X = np.column_stack([np.ones_like(x), x])
    w = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w)))
        grad = X.T @ (y - p) - 1e-4 * w
        hess = X.T @ (X * (p * (1 - p))[:, None]) + 1e-4 * np.eye(2)
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            return None
        w = w + step
        if np.max(np.abs(step)) < 1e-8:
            break
    return float(w[0]), float(w[1])


def steps_at_50(
    records: list[dict[str, Any]], condition: str | None = None, n_boot: int = 1000, seed: int = 0
) -> dict[str, Any] | None:
    """Serial steps completed with 50% probability: logistic fit of correctness on depth.

    For tasks with negligible chance (``arithmetic_chain``). The estimate is
    -intercept / slope, reported only when the slope is negative (accuracy
    falls with depth) and the crossing lies within twice the measured range;
    a bootstrap over requests gives a 95% interval.
    """
    rows = [r for r in records if _ok(r) and (condition is None or r.get("condition") == condition)]
    if len(rows) < 10:
        return None
    x = np.array([float(r["depth"]) for r in rows])
    y = np.array([1.0 if r["correct"] else 0.0 for r in rows])
    if np.ptp(x) == 0:
        return None

    def crossing(xs, ys):
        fit = _logistic_fit(xs, ys)
        if fit is None or fit[1] >= 0:
            return None
        c = -fit[0] / fit[1]
        return c if -1 <= c <= 2 * float(xs.max()) else None

    est = crossing(x, y)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(rows), len(rows))
        b = crossing(x[idx], y[idx])
        if b is not None:
            boots.append(b)
    ci = [float(v) for v in np.quantile(boots, [0.025, 0.975])] if len(boots) >= n_boot // 2 else None
    acc = {int(d): float(y[x == d].mean()) for d in sorted(set(x.tolist()))}
    return {"steps_at_50": est, "ci95": ci, "n": len(rows), "acc_by_depth": acc}


def _tokens_per_step(rs: list[dict[str, Any]], token_metric: str) -> dict[str, float] | None:
    x = np.array([float(r["depth"]) for r in rs])
    if len(rs) < 4 or np.ptp(x) == 0:
        return None
    y = np.array([_tokens(r, token_metric) for r in rs])
    coef, se = ols(y, np.column_stack([np.ones_like(x), x]))
    return {"slope": float(coef[1]), "se": float(se[1]), "n": len(rs)}


def _tokens_to_solve(table: dict[str, dict[int, dict[str, Any]]], depth: int, threshold: float = 0.8):
    solved = [
        (cell["tokens_mean"], cond)
        for cond, by_depth in table.items()
        if (cell := by_depth.get(depth)) and cell["corrected_acc"] is not None and cell["corrected_acc"] >= threshold
    ]
    if not solved:
        return None
    tokens, cond = min(solved)
    return {"condition": cond, "tokens_mean": tokens}


def _bootstrap_share(cells, lo: str, hi: str, depths: list[int], min_hi: float, n_boot: int, seed: int):
    """95% interval for the in-pass share, resampling requests within each (condition, depth, task) cell."""
    rng = random.Random(seed)
    grouped: dict[tuple[str, int], list[list[dict[str, Any]]]] = {}
    for key, rs in cells.items():
        by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rs:
            by_task[r["task"]].append(r)
        grouped[key] = list(by_task.values())
    boots = []
    for _ in range(n_boot):
        resampled = {key: [r for trs in groups for r in rng.choices(trs, k=len(trs))] for key, groups in grouped.items()}
        b, _ = _in_pass_share(resampled, lo, hi, depths, min_hi)
        if b is not None and math.isfinite(b):
            boots.append(b)
    if not boots:
        return None
    q = np.quantile(boots, [0.025, 0.975])
    return [float(q[0]), float(q[1])]


def budget_features(  # nosec B107
    records: list[dict[str, Any]],
    condition_order: list[str] | None = None,
    token_metric: str = "completion",
    min_hi_accuracy: float = 0.2,
    max_lo_reasoning: float = 20.0,
    n_boot: int = 500,
    seed: int = 0,
) -> dict[str, Any]:
    """Summarize a budget sweep.

    ``token_metric`` is ``"completion"`` (billed completion tokens, which also
    count reasoning a provider under-reports) or ``"reasoning"`` (the reported
    reasoning tokens). The lowest and highest conditions default to the plan
    order recorded in ``condition_index``. (Bandit's B107 flags the
    ``token_metric`` default as a password; it is a token count.)

    Returns per-cell tables plus:

    * ``in_pass_share``: chance-corrected accuracy at the lowest budget divided
      by that at the highest, averaged over depths (weighted by requests) where
      the highest budget reaches ``min_hi_accuracy``. Near 1, the visible
      reasoning adds little; near 0, the model needs it. With a bootstrap
      95% interval over requests. Only meaningful when the lowest condition
      really suppresses reasoning: if its mean reported reasoning tokens exceed
      ``max_lo_reasoning`` (some providers keep reasoning on hard items even at
      their lowest setting), ``in_pass_share_valid`` is False and a note says why.
    * ``tokens_per_step``: OLS slope of tokens on depth for each condition.
    * ``tokens_to_solve``: per depth, the fewest mean tokens among conditions
      reaching corrected accuracy 0.8.
    """
    if token_metric not in ("completion", "reasoning"):
        raise ValueError("token_metric must be 'completion' or 'reasoning'")
    ok = [r for r in records if _ok(r)]
    if condition_order is None:
        idx = {r["condition"]: int(r.get("condition_index", 0)) for r in ok}
        condition_order = sorted(idx, key=lambda c: idx[c])
    depths = sorted({int(r["depth"]) for r in ok})
    cells = _cells(ok)
    table = {
        cond: {d: _cell_summary(cells[(cond, d)], token_metric) for d in depths if cells.get((cond, d))}
        for cond in condition_order
    }
    tokens_per_step = {}
    for cond in condition_order:
        fit = _tokens_per_step([r for d in depths for r in cells.get((cond, d), [])], token_metric)
        if fit:
            tokens_per_step[cond] = fit
    out: dict[str, Any] = {
        "token_metric": token_metric,
        "conditions": condition_order,
        "depths": depths,
        "n_records": len(records),
        "n_ok": len(ok),
        "cells": table,
        "tokens_per_step": tokens_per_step,
        "tokens_to_solve": {d: _tokens_to_solve(table, d) for d in depths},
        "latency_per_token": latency_per_token(ok),
    }
    if len(condition_order) < 2:
        return out
    lo, hi = condition_order[0], condition_order[-1]
    lo_rows = [r for d in depths for r in cells.get((lo, d), [])]
    lo_reasoning = statistics.fmean(float(r.get("reasoning_tokens") or 0) for r in lo_rows) if lo_rows else 0.0
    out["lowest_condition_reasoning_mean"] = lo_reasoning
    out["in_pass_share_valid"] = lo_reasoning <= max_lo_reasoning
    if not out["in_pass_share_valid"]:
        out["notes"] = [
            f"lowest condition {lo!r} still averages {lo_reasoning:.0f} reported reasoning tokens "
            f"(limit {max_lo_reasoning:.0f}), so in_pass_share compares two reasoning settings, "
            "not reasoning against none; use tokens_per_step instead"
        ]
    share, per_depth = _in_pass_share(cells, lo, hi, depths, min_hi_accuracy)
    out["in_pass_share"] = share
    out["in_pass_share_by_depth"] = per_depth
    out["accuracy_gap_by_depth"] = {
        d: table[hi][d]["corrected_acc"] - table[lo][d]["corrected_acc"] for d in depths if d in table[hi] and d in table[lo]
    }
    if share is not None and n_boot > 0:
        ci = _bootstrap_share(cells, lo, hi, depths, min_hi_accuracy, n_boot, seed)
        if ci:
            out["in_pass_share_ci95"] = ci
    return out
