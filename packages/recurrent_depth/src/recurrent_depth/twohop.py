"""Latent two-hop fact composition (TwoHopFact, Yang et al. 2024).

Each fact pair gives three questions, all asked without visible reasoning:

* ``hop1``: r1(e1), for example "The author of the novel Animal Farm is" (George Orwell);
* ``hop2``: r2(e2), "George Orwell was born in the city of" (Motihari);
* ``twohop``: r2(r1(e1)), "The author of the novel Animal Farm was born in the city of" (Motihari).

The measure of latent composition is the two-hop accuracy among facts whose
two single hops the model gets right: a model that composes the hops inside
the forward pass answers the two-hop question when it knows both parts. More
serial depth per pass should raise that rate; so do scale and training, so
compare models of similar capability.

The dataset is not downloaded here. Pass the path of a local copy of
``TwoHopFact.csv`` (CC BY 4.0, https://huggingface.co/datasets/soheeyang/TwoHopFact).
The CSV is read as plain data: alias lists are parsed with ``ast.literal_eval``,
which evaluates literals only, and nothing in the file is executed.
"""

from __future__ import annotations

import ast
from collections import defaultdict
import csv
import math
from pathlib import Path
import random
import statistics
from typing import Any

from .tasks import NO_COT_SUFFIX, TaskItem

REQUIRED_COLUMNS = (
    "uid",
    "category",
    "e2.value",
    "e3.value",
    "e2.aliases",
    "e3.aliases",
    "r1(e1).prompt",
    "r2(e2).prompt",
    "r2(r1(e1)).prompt",
)
MAX_FIELD_CHARS = 20_000
MAX_ALIASES = 25


def _aliases(raw: str, primary: str) -> list[str]:
    names = [primary]
    if raw and len(raw) <= MAX_FIELD_CHARS:
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            parsed = ()
        stack = [parsed]
        while stack and len(names) < MAX_ALIASES:
            cur = stack.pop()
            if isinstance(cur, str):
                names.append(cur)
            elif isinstance(cur, (tuple, list)):
                stack.extend(reversed(cur))
    seen: set[str] = set()
    out = []
    for n in names:
        key = n.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(n.strip())
    return out


def _question(statement: str) -> str:
    return f'Complete this statement with the correct name: "{statement} ___"\n{NO_COT_SUFFIX}'


def load_items(csv_path: str | Path, n: int, seed: int = 0) -> list[TaskItem]:
    """Sample ``n`` fact pairs, balanced across categories, as three questions each."""
    if n < 1:
        raise ValueError("twohop_n must be positive")
    csv.field_size_limit(MAX_FIELD_CHARS * 10)
    with open(csv_path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{csv_path} is not a TwoHopFact CSV; missing columns {missing}")
        by_cat: dict[str, list[dict[str, str]]] = defaultdict(list)
        seen_prompts: set[str] = set()
        for row in reader:
            two = row["r2(r1(e1)).prompt"].strip()
            if not (two and row["r1(e1).prompt"].strip() and row["r2(e2).prompt"].strip()) or two in seen_prompts:
                continue
            seen_prompts.add(two)
            by_cat[row["category"]].append(row)
    rng = random.Random(seed)
    for rows in by_cat.values():
        rng.shuffle(rows)
    cats = sorted(by_cat)
    rng.shuffle(cats)
    picked: list[dict[str, str]] = []
    i = 0
    while len(picked) < n and any(by_cat[c] for c in cats):
        c = cats[i % len(cats)]
        if by_cat[c]:
            picked.append(by_cat[c].pop())
        i += 1
    items = []
    for row in picked:
        e2 = _aliases(row["e2.aliases"], row["e2.value"])
        e3 = _aliases(row["e3.aliases"], row["e3.value"])
        meta = {"uid": row["uid"], "category": row["category"]}
        items.append(TaskItem("hop1", 1, _question(row["r1(e1).prompt"]), e2[0], 0.0, {**meta, "aliases": e2}))
        items.append(TaskItem("hop2", 1, _question(row["r2(e2).prompt"]), e3[0], 0.0, {**meta, "aliases": e3}))
        items.append(TaskItem("twohop", 2, _question(row["r2(r1(e1)).prompt"]), e3[0], 0.0, {**meta, "aliases": e3}))
    return items


def _wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


def twohop_features(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Per condition: single-hop and two-hop accuracy, and latent composition rate.

    ``composition_rate`` is two-hop accuracy among facts with both hops
    answered correctly under the same condition, with a Wilson 95% interval.
    ``twohop_when_not_known`` is two-hop accuracy when at least one hop was
    wrong, a baseline for guessing or shortcuts from the first entity.
    """
    by: dict[str, dict[str, dict[str, bool]]] = defaultdict(lambda: defaultdict(dict))
    for r in records:
        if r.get("error") is None and 200 <= int(r.get("status") or 0) < 300 and r.get("item_id") is not None:
            by[r["condition"]][str(r["item_id"])][r["task"]] = bool(r["correct"])
    out: dict[str, Any] = {}
    for cond, facts in by.items():
        full = {u: f for u, f in facts.items() if {"hop1", "hop2", "twohop"} <= set(f)}
        known = [f for f in full.values() if f["hop1"] and f["hop2"]]
        unknown = [f for f in full.values() if not (f["hop1"] and f["hop2"])]
        k = sum(f["twohop"] for f in known)
        out[cond] = {
            "n_facts": len(full),
            "hop1_acc": statistics.fmean(f["hop1"] for f in full.values()) if full else None,
            "hop2_acc": statistics.fmean(f["hop2"] for f in full.values()) if full else None,
            "twohop_acc": statistics.fmean(f["twohop"] for f in full.values()) if full else None,
            "n_both_known": len(known),
            "composition_rate": k / len(known) if known else None,
            "composition_ci95": _wilson(k, len(known)),
            "twohop_when_not_known": statistics.fmean(f["twohop"] for f in unknown) if unknown else None,
        }
    return out
