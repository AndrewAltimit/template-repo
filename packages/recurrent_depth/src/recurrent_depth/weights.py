"""Detect parameter sharing between layers of an open-weight checkpoint.

Three kinds of sharing are distinguished:

* **Exact duplicates.** Two layer slots hold byte-identical tensors. Some
  exports of weight-tied models write the shared block once per use.
* **Low-rank relation.** ``W_i - W_j`` is (nearly) low rank, as when layers
  share a base matrix plus per-layer LoRA deltas (Relaxed Recursive
  Transformers, Bae et al. 2024). Independent trained layers have
  full-rank differences.
* **Storage-level reuse.** The checkpoint stores fewer distinct layers than
  the declared depth. A model that loops one stored block (Huginn, Ouro)
  stores each shared layer once, so the weights alone look like an ordinary
  shallow model; the looping shows up only in the config or code, or as a
  mismatch between parameter count and compute.

Large matrices are compared on a fixed random submatrix (the same rows and
columns for both layers). Rank is preserved under row and column
subsampling, so a low-rank difference stays low rank in the sample.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
import re
from typing import Any

import numpy as np

from .safetensors_io import TensorInfo, load_tensor, tensor_digest

LAYER_RE = re.compile(r"^(?P<prefix>.*?)\.(?P<idx>\d+)\.(?P<suffix>.+)$")


def split_layer_name(name: str) -> tuple[str, int, str] | None:
    m = LAYER_RE.match(name)
    if not m:
        return None
    return m.group("prefix"), int(m.group("idx")), m.group("suffix")


def group_layers(tensors: dict[str, TensorInfo]) -> dict[str, dict[int, dict[str, TensorInfo]]]:
    """Map prefix -> layer index -> suffix -> tensor."""
    groups: dict[str, dict[int, dict[str, TensorInfo]]] = defaultdict(lambda: defaultdict(dict))
    for name, info in tensors.items():
        parts = split_layer_name(name)
        if parts:
            prefix, idx, suffix = parts
            groups[prefix][idx][suffix] = info
    # keep only groups that look like layer stacks (two or more numbered slots)
    return {p: dict(v) for p, v in groups.items() if len(v) >= 2}


@dataclass
class WeightReport:
    stored_slots: int
    distinct_slots: int
    exact_duplicate_pairs: list[tuple[str, str]] = field(default_factory=list)
    lowrank_pairs: list[dict[str, Any]] = field(default_factory=list)
    adjacent_rel_distance: dict[str, list[float]] = field(default_factory=dict)
    declared_layers: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def shared_layer_fraction(self) -> float:
        if self.stored_slots == 0:
            return 0.0
        involved = set()
        for a, b in self.exact_duplicate_pairs:
            involved.update((a, b))
        for p in self.lowrank_pairs:
            involved.update((p["a"], p["b"]))
        return len(involved) / self.stored_slots

    @property
    def weight_reuse_ratio(self) -> float | None:
        if self.declared_layers and self.distinct_slots:
            return self.declared_layers / self.distinct_slots
        return None

    def signals(self) -> dict[str, float]:
        out = {"shared_layer_fraction": self.shared_layer_fraction}
        if self.weight_reuse_ratio is not None:
            out["weight_reuse_ratio"] = self.weight_reuse_ratio
        return out

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["shared_layer_fraction"] = self.shared_layer_fraction
        d["weight_reuse_ratio"] = self.weight_reuse_ratio
        return d


def _sample_indices(shape: tuple[int, ...], max_side: int, rng: np.random.Generator) -> tuple[np.ndarray, ...]:
    return tuple(np.sort(rng.choice(n, size=min(n, max_side), replace=False)) for n in shape)


def _submatrix(arr: np.ndarray, idx: tuple[np.ndarray, ...]) -> np.ndarray:
    if arr.ndim == 1:
        return arr[idx[0]].astype(np.float64)
    return arr[np.ix_(idx[0], idx[1])].astype(np.float64)


def lowrank_energy(diff: np.ndarray, rank: int) -> float:
    """Fraction of squared Frobenius norm in the top ``rank`` singular values."""
    s = np.linalg.svd(diff, compute_uv=False)
    total = float((s**2).sum())
    if total == 0:
        return 1.0
    return float((s[:rank] ** 2).sum()) / total


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)

    def n_sets(self) -> int:
        return len({self.find(x) for x in self.parent})


def _pair_stats(wa: np.ndarray, wb: np.ndarray, rank: int) -> tuple[float, float]:
    """(relative distance, low-rank energy of the difference) for two matrices."""
    d = wa - wb
    denom = max(np.linalg.norm(wa), np.linalg.norm(wb), 1e-12)
    return float(np.linalg.norm(d) / denom), lowrank_energy(d, min(rank, min(d.shape) // 4 or 1))


def _sample_stack(
    layers: dict[int, dict[str, TensorInfo]], idxs: list[int], names: list[str], max_side: int, rng: np.random.Generator
) -> dict[tuple[int, str], np.ndarray]:
    samples: dict[tuple[int, str], np.ndarray] = {}
    for s in names:
        shape = layers[idxs[0]][s].shape
        if len(shape) not in (1, 2):
            continue
        ix = _sample_indices(shape, max_side, rng)
        for i in idxs:
            samples[(i, s)] = _submatrix(load_tensor(layers[i][s]), ix)
    return samples


def analyze_weights(
    tensors: dict[str, TensorInfo],
    declared_layers: int | None = None,
    max_side: int = 512,
    lowrank_rank: int = 16,
    lowrank_threshold: float = 0.9,
    exact_tol: float = 1e-7,
    use_hash: bool = True,
    seed: int = 0,
) -> WeightReport:
    """Compare every pair of layer slots within each layer stack."""
    rng = np.random.default_rng(seed)
    groups = group_layers(tensors)
    report = WeightReport(stored_slots=0, distinct_slots=0, declared_layers=declared_layers)
    if not groups:
        report.notes.append("no numbered layer stacks found in tensor names")
        return report
    uf = _UnionFind()
    for prefix, layers in groups.items():
        idxs = sorted(layers)
        for i in idxs:
            uf.add(f"{prefix}.{i}")
        report.stored_slots += len(idxs)
        common = set.intersection(*(set(layers[i]) for i in idxs))
        names = sorted(s for s in common if len({layers[i][s].shape for i in idxs}) == 1)
        if not names:
            continue
        digests = {(i, s): tensor_digest(layers[i][s]) for i in idxs for s in names} if use_hash else {}
        samples = _sample_stack(layers, idxs, names, max_side, rng)
        two_d = [s for s in names if (idxs[0], s) in samples and samples[(idxs[0], s)].ndim == 2]

        def identical(a: int, b: int) -> bool:
            if use_hash:
                return all(digests[(a, s)] == digests[(b, s)] for s in names)
            return all(np.allclose(samples.get((a, s), 0), samples.get((b, s), 0), atol=exact_tol) for s in names)

        dists: list[float] = []
        for pos, a in enumerate(idxs):
            for b in idxs[pos + 1 :]:
                sa, sb = f"{prefix}.{a}", f"{prefix}.{b}"
                if identical(a, b):
                    report.exact_duplicate_pairs.append((sa, sb))
                    uf.union(sa, sb)
                    continue
                if not two_d:
                    continue
                stats = [_pair_stats(samples[(a, s)], samples[(b, s)], lowrank_rank) for s in two_d]
                rel = float(np.median([x[0] for x in stats]))
                energy = float(np.median([x[1] for x in stats]))
                if b == a + 1:
                    dists.append(rel)
                if energy >= lowrank_threshold:
                    report.lowrank_pairs.append({"a": sa, "b": sb, "energy": energy, "rel_distance": rel})
        if dists:
            report.adjacent_rel_distance[prefix] = dists
    report.distinct_slots = uf.n_sets()
    if declared_layers is not None and report.distinct_slots and declared_layers > report.distinct_slots:
        report.notes.append(
            f"config declares {declared_layers} layers but only {report.distinct_slots} distinct layer slots are stored"
        )
    return report
