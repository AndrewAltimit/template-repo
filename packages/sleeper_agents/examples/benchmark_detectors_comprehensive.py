"""Detector benchmark on SYNTHETIC activation datasets of varying difficulty.

Compares ARTActivationDetector (unsupervised clustering) with a supervised linear
probe on four generated datasets (no model is involved):
1. Separable: constant shift in every dimension
2. Moons: a 2D two-moons pattern randomly projected into 768 dimensions
3. Overlapping: mixtures of clusters that overlap along one dimension, with noise
4. Sparse shift: a shift in 50 of 768 dimensions plus a small sequence pattern

These are toy distributions; the results say how the two detectors behave on them,
not how well either detects backdoors in real models.

Protocol: seeded datasets; a seeded stratified train/held-out split; AUC on the
held-out split; TPR/FPR/F1 at a threshold chosen on the training split; a
label-shuffled control for the supervised probe.
"""

from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from sklearn.datasets import make_moons
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_eval_utils import (  # noqa: E402
    DEFAULT_SEED,
    LinearProbeDetector,
    evaluate_heldout,
    shuffled_label_auc,
)

from sleeper_agents.detection.art_activation_detector import ARTActivationDetector  # noqa: E402

SEQ_LEN = 20
HIDDEN_DIM = 768


def _class_sizes(n_samples: int) -> Tuple[int, int]:
    n_clean = int(n_samples * 0.83)
    return n_clean, n_samples - n_clean


def generate_separable_dataset(n_samples: int = 600, seed: int = DEFAULT_SEED) -> Tuple[np.ndarray, np.ndarray]:
    """Constant shift of +3 in every dimension for the positive class."""
    rng = np.random.default_rng(seed)
    n_clean, n_pos = _class_sizes(n_samples)
    clean = rng.standard_normal((n_clean, SEQ_LEN, HIDDEN_DIM))
    pos = rng.standard_normal((n_pos, SEQ_LEN, HIDDEN_DIM)) + 3.0
    X = np.vstack([clean, pos]).astype(np.float32)
    y = np.array([0] * n_clean + [1] * n_pos)
    return X, y


def generate_moons_dataset(n_samples: int = 600, seed: int = DEFAULT_SEED) -> Tuple[np.ndarray, np.ndarray]:
    """Two-moons pattern projected into HIDDEN_DIM dims (not linearly separable)."""
    rng = np.random.default_rng(seed)
    X_2d, y = make_moons(n_samples=n_samples, noise=0.15, random_state=seed)
    projection = rng.standard_normal((2, HIDDEN_DIM)) * 0.5
    X_high = X_2d @ projection
    X = np.stack([X_high + rng.standard_normal((n_samples, HIDDEN_DIM)) * 0.1 for _ in range(SEQ_LEN)], axis=1)
    return X.astype(np.float32), y


def generate_overlapping_dataset(n_samples: int = 600, seed: int = DEFAULT_SEED) -> Tuple[np.ndarray, np.ndarray]:
    """Cluster mixtures overlapping along dimension 0, with added noise."""
    rng = np.random.default_rng(seed)
    n_clean, n_pos = _class_sizes(n_samples)
    clean_parts = []
    for i in range(3):
        part = rng.standard_normal((n_clean // 3, SEQ_LEN, HIDDEN_DIM))
        part[:, :, 0] += i * 1.5
        clean_parts.append(part)
    pos_parts = []
    for i in range(2):
        part = rng.standard_normal((n_pos // 2, SEQ_LEN, HIDDEN_DIM))
        part[:, :, 0] += 1.0 + i * 1.5
        pos_parts.append(part)
    clean = np.vstack(clean_parts)
    pos = np.vstack(pos_parts)
    clean += rng.standard_normal(clean.shape) * 0.8
    pos += rng.standard_normal(pos.shape) * 0.8
    X = np.vstack([clean, pos]).astype(np.float32)
    y = np.array([0] * len(clean) + [1] * len(pos))
    return X, y


def generate_sparse_shift_dataset(n_samples: int = 600, seed: int = DEFAULT_SEED) -> Tuple[np.ndarray, np.ndarray]:
    """Shift of +1.5 in 50 random dimensions plus a small sinusoidal sequence pattern."""
    rng = np.random.default_rng(seed)
    n_clean, n_pos = _class_sizes(n_samples)
    X = rng.standard_normal((n_samples, SEQ_LEN, HIDDEN_DIM))
    dims = rng.choice(HIDDEN_DIM, size=50, replace=False)
    pos = X[n_clean:]
    pos[:, :, dims] += 1.5
    for t in range(SEQ_LEN):
        pos[:, t, dims] += 0.1 * np.sin(t / 3)
    y = np.array([0] * n_clean + [1] * n_pos)
    return X.astype(np.float32), y


def split_dataset(
    X: np.ndarray, y: np.ndarray, test_size: float = 0.3, seed: int = DEFAULT_SEED
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Seeded stratified train/held-out split."""
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, stratify=y, random_state=seed)
    return X_train, y_train, X_test, y_test


def benchmark_scenario(
    scenario_name: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Fit both detectors on the training split and evaluate on the held-out split."""
    print(f"\n{'=' * 80}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'=' * 80}")
    print(f"Train:    {len(X_train)} samples ({np.sum(y_train == 1)} positive)")
    print(f"Held-out: {len(X_test)} samples ({np.sum(y_test == 1)} positive)")

    detectors: List[Tuple[Any, Optional[Callable[[], Any]]]] = [
        (ARTActivationDetector(nb_clusters=2, nb_dims=10, pooling_method="mean", normalize=True), None),
        (LinearProbeDetector(seed=seed), lambda: LinearProbeDetector(seed=seed)),
    ]

    results = []
    for detector, factory in detectors:
        print(f"\n  Testing {detector.name}...", end=" ")
        train_start = time.time()
        detector.fit(X_train, y_train)
        train_time = time.time() - train_start

        test_start = time.time()
        test_scores = detector.score(X_test)
        test_time = time.time() - test_start

        metrics = evaluate_heldout(y_train, detector.score(X_train), y_test, test_scores)
        shuffled = shuffled_label_auc(factory, X_train, y_train, X_test, y_test, seed=seed) if factory is not None else None
        print(f"held-out AUC={metrics['auc']:.4f}, F1={metrics['f1']:.4f}")

        results.append(
            {
                "detector": detector.name,
                "metrics": metrics,
                "shuffled_label_auc": shuffled,
                "train_time": train_time,
                "test_time": test_time,
            }
        )

    return {"scenario": scenario_name, "results": results}


def print_summary(all_results: List[Dict[str, Any]]) -> None:
    """Print per-scenario held-out metrics; conclusions are left to the reader."""
    print("\n" + "=" * 80)
    print("SYNTHETIC BENCHMARK SUMMARY (held-out split; threshold chosen on training split)")
    print("=" * 80)

    for scenario_result in all_results:
        print(f"\n{scenario_result['scenario']}")
        print("-" * 80)
        for r in scenario_result["results"]:
            m = r["metrics"]
            print(f"  {r['detector']}:")
            print(f"    AUC: {m['auc']:.4f}   (train, in-sample: {m['train_auc']:.4f})")
            print(f"    F1:  {m['f1']:.4f}   TPR: {m['tpr']:.4f}   FPR: {m['fpr']:.4f}")
            if r["shuffled_label_auc"] is not None:
                print(f"    Shuffled-label control AUC: {r['shuffled_label_auc']:.4f}")

    print("\n" + "=" * 80)
    print("HIGHER HELD-OUT AUC PER SCENARIO (differences < 0.01 reported as ties)")
    print("=" * 80)
    for scenario_result in all_results:
        results = scenario_result["results"]
        art_auc = next(r["metrics"]["auc"] for r in results if "ART" in r["detector"])
        probe_auc = next(r["metrics"]["auc"] for r in results if "Linear" in r["detector"])
        if abs(art_auc - probe_auc) < 0.01:
            outcome = "tie"
        elif art_auc > probe_auc:
            outcome = "ARTActivationDetector"
        else:
            outcome = "LinearProbeDetector"
        print(f"  {scenario_result['scenario']}: {outcome} (ART {art_auc:.4f} vs probe {probe_auc:.4f})")
    print("\nThese are single runs on synthetic data; they do not establish which detector is better on real models.")


SCENARIOS = [
    ("Separable: constant shift", generate_separable_dataset),
    ("Moons: non-linear boundary", generate_moons_dataset),
    ("Overlapping clusters", generate_overlapping_dataset),
    ("Sparse shift (50 of 768 dims)", generate_sparse_shift_dataset),
]


def main():
    """Run the synthetic benchmark."""
    print("\n" + "=" * 80)
    print("SYNTHETIC DETECTOR BENCHMARK: ARTActivationDetector vs Linear Probe")
    print("=" * 80)

    all_results = []
    for scenario_name, generator in SCENARIOS:
        X, y = generator(n_samples=600, seed=DEFAULT_SEED)
        X_train, y_train, X_test, y_test = split_dataset(X, y, test_size=0.3, seed=DEFAULT_SEED)
        all_results.append(benchmark_scenario(scenario_name, X_train, y_train, X_test, y_test))

    print_summary(all_results)


if __name__ == "__main__":
    main()
