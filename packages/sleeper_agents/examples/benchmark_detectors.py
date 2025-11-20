"""Benchmark ARTActivationDetector vs Linear Probes.

This script provides a comprehensive comparison of detection methods:
- ARTActivationDetector (clustering-based, inspired by ART)
- ProbeDetector (linear probe on activations)

Metrics compared:
- Detection rate (True Positive Rate)
- False Positive Rate
- AUC-ROC
- Runtime performance
- Memory usage
"""

import time
from typing import Any, Dict, List, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import auc, roc_curve
from sleeper_agents.detection.art_activation_detector import ARTActivationDetector
from sleeper_agents.detection.base_detector import BaseDetector
from sleeper_agents.evaluation.detector_registry import DetectorRegistry


# Simple Linear Probe Detector for comparison
@DetectorRegistry.register("linear_probe")
class LinearProbeDetector(BaseDetector):
    """Linear probe detector using logistic regression."""

    def __init__(self, model=None, **kwargs):
        super().__init__(model, **kwargs)
        self.probe = LogisticRegression(max_iter=1000, random_state=42)
        self._is_fitted = False

    @property
    def inputs_required(self) -> Dict[str, str]:
        return {
            "activations": "Neural network activations",
            "labels": "Binary labels (0=clean, 1=backdoored)",
        }

    def fit(self, activations: np.ndarray, labels: np.ndarray) -> None:
        """Train linear probe."""
        # Handle 3D activations (batch, seq, hidden) -> (batch, hidden)
        if len(activations.shape) == 3:
            activations = activations.mean(axis=1)

        self.probe.fit(activations, labels)
        self._is_fitted = True

    def score(self, activations: np.ndarray) -> np.ndarray:
        """Get prediction probabilities."""
        if not self._is_fitted:
            raise RuntimeError("Must call fit() before score()")

        # Handle 3D activations
        if len(activations.shape) == 3:
            activations = activations.mean(axis=1)

        # Return probability of being backdoored (class 1)
        return self.probe.predict_proba(activations)[:, 1]

    def run(self, **kwargs) -> Dict[str, Any]:
        """Run full detection pipeline."""
        activations = kwargs.get("activations")
        labels = kwargs.get("labels")

        if activations is None or labels is None:
            raise ValueError("Must provide 'activations' and 'labels'")

        self.fit(activations, labels)
        scores = self.score(activations)

        # Threshold at 0.5
        predictions = scores > 0.5
        accuracy = np.mean(predictions == labels)

        return {
            "score": float(np.mean(scores)),
            "is_backdoored": accuracy < 0.5,  # Low accuracy suggests backdoor
            "report": {
                "method": "LinearProbe",
                "accuracy": float(accuracy),
                "mean_score": float(np.mean(scores)),
            },
            "metadata": {"config": self.config},
        }


def generate_backdoor_dataset(
    n_clean: int = 500,
    n_backdoor: int = 100,
    hidden_dim: int = 768,
    seq_len: int = 20,
    separation: float = 3.0,
    noise_level: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic dataset with clean and backdoored samples.

    Args:
        n_clean: Number of clean samples
        n_backdoor: Number of backdoored samples
        hidden_dim: Activation dimension
        seq_len: Sequence length
        separation: Distance between clean and backdoor clusters
        noise_level: Standard deviation of noise

    Returns:
        X_train, y_train, X_test, y_test
    """
    np.random.seed(42)

    # Generate clean samples (centered at origin)
    clean_train = np.random.randn(n_clean, seq_len, hidden_dim).astype(np.float32)
    clean_train *= noise_level

    # Generate backdoored samples (shifted by separation)
    backdoor_train = np.random.randn(n_backdoor, seq_len, hidden_dim).astype(np.float32) * noise_level
    backdoor_train += separation

    # Combine and create labels
    X_train = np.vstack([clean_train, backdoor_train])
    y_train = np.array([0] * n_clean + [1] * n_backdoor)

    # Generate test set (30% of training size)
    n_clean_test = int(n_clean * 0.3)
    n_backdoor_test = int(n_backdoor * 0.3)

    clean_test = np.random.randn(n_clean_test, seq_len, hidden_dim).astype(np.float32) * noise_level
    backdoor_test = np.random.randn(n_backdoor_test, seq_len, hidden_dim).astype(np.float32) * noise_level
    backdoor_test += separation

    X_test = np.vstack([clean_test, backdoor_test])
    y_test = np.array([0] * n_clean_test + [1] * n_backdoor_test)

    # Shuffle
    train_idx = np.random.permutation(len(X_train))
    test_idx = np.random.permutation(len(X_test))

    return X_train[train_idx], y_train[train_idx], X_test[test_idx], y_test[test_idx]


def compute_metrics(y_true: np.ndarray, y_scores: np.ndarray) -> Dict[str, float]:
    """Compute comprehensive detection metrics.

    Args:
        y_true: True labels (0=clean, 1=backdoor)
        y_scores: Detection scores (higher = more suspicious)

    Returns:
        Dictionary of metrics
    """
    # Compute ROC curve
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    auc_score = auc(fpr, tpr)

    # Find optimal threshold (Youden's J statistic)
    j_scores = tpr - fpr
    optimal_idx = np.argmax(j_scores)
    optimal_threshold = thresholds[optimal_idx]

    # Metrics at optimal threshold
    y_pred = y_scores >= optimal_threshold
    tp = np.sum((y_pred == 1) & (y_true == 1))
    fp = np.sum((y_pred == 1) & (y_true == 0))
    tn = np.sum((y_pred == 0) & (y_true == 0))
    fn = np.sum((y_pred == 0) & (y_true == 1))

    tpr_opt = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr_opt = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = 2 * precision * tpr_opt / (precision + tpr_opt) if (precision + tpr_opt) > 0 else 0.0

    return {
        "auc": float(auc_score),
        "tpr": float(tpr_opt),
        "fpr": float(fpr_opt),
        "precision": float(precision),
        "f1": float(f1),
        "optimal_threshold": float(optimal_threshold),
    }


def benchmark_detector(
    detector: BaseDetector,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> Dict[str, Any]:
    """Benchmark a detector on train/test data.

    Args:
        detector: Detector to benchmark
        X_train: Training activations
        y_train: Training labels
        X_test: Test activations
        y_test: Test labels

    Returns:
        Benchmark results including metrics and timing
    """
    # Training phase
    train_start = time.time()
    detector.fit(X_train, y_train)
    train_time = time.time() - train_start

    # Inference phase (test set)
    test_start = time.time()
    test_scores = detector.score(X_test)
    test_time = time.time() - test_start

    # Compute metrics
    metrics = compute_metrics(y_test, test_scores)

    # Also score training set (to detect overfitting)
    train_scores = detector.score(X_train)
    train_metrics = compute_metrics(y_train, train_scores)

    return {
        "detector_name": detector.name,
        "test_metrics": metrics,
        "train_metrics": train_metrics,
        "timing": {
            "train_time": train_time,
            "test_time": test_time,
            "throughput": len(X_test) / test_time,
        },
    }


def print_benchmark_results(results: List[Dict[str, Any]]) -> None:
    """Pretty print benchmark results."""
    print("\n" + "=" * 80)
    print("DETECTOR BENCHMARK RESULTS")
    print("=" * 80)

    for result in results:
        print(f"\n{result['detector_name']}")
        print("-" * 80)

        # Test metrics
        test = result["test_metrics"]
        print("\nTest Set Performance:")
        print(f"  AUC-ROC:         {test['auc']:.4f}")
        print(f"  True Positive Rate:  {test['tpr']:.4f} (Detection Rate)")
        print(f"  False Positive Rate: {test['fpr']:.4f}")
        print(f"  Precision:       {test['precision']:.4f}")
        print(f"  F1 Score:        {test['f1']:.4f}")

        # Train metrics (for overfitting check)
        train = result["train_metrics"]
        print("\nTraining Set Performance (overfitting check):")
        print(f"  AUC-ROC:         {train['auc']:.4f}")
        print(f"  Train-Test Gap:  {abs(train['auc'] - test['auc']):.4f}")

        # Timing
        timing = result["timing"]
        print("\nPerformance:")
        print(f"  Training Time:   {timing['train_time']:.4f}s")
        print(f"  Inference Time:  {timing['test_time']:.4f}s")
        print(f"  Throughput:      {timing['throughput']:.1f} samples/sec")

    # Comparison summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)

    best_auc = max(r["test_metrics"]["auc"] for r in results)
    best_f1 = max(r["test_metrics"]["f1"] for r in results)
    fastest = min(r["timing"]["test_time"] for r in results)

    for result in results:
        name = result["detector_name"]
        test = result["test_metrics"]
        timing = result["timing"]

        tags = []
        if test["auc"] == best_auc:
            tags.append("BEST AUC")
        if test["f1"] == best_f1:
            tags.append("BEST F1")
        if timing["test_time"] == fastest:
            tags.append("FASTEST")

        tag_str = " | ".join(tags) if tags else ""
        print(f"\n{name}: {tag_str}")
        print(f"  AUC={test['auc']:.4f}, F1={test['f1']:.4f}, Time={timing['test_time']:.4f}s")


def main():
    """Run detector benchmark."""
    print("\n" + "=" * 80)
    print("DETECTOR BENCHMARK: ARTActivationDetector vs Linear Probe")
    print("=" * 80)

    # Generate dataset
    print("\n[1/4] Generating synthetic backdoor dataset...")
    X_train, y_train, X_test, y_test = generate_backdoor_dataset(
        n_clean=500,
        n_backdoor=100,
        hidden_dim=768,
        seq_len=20,
        separation=3.0,
        noise_level=1.0,
    )

    print(f"  Training set: {len(X_train)} samples ({np.sum(y_train==1)} backdoored)")
    print(f"  Test set: {len(X_test)} samples ({np.sum(y_test==1)} backdoored)")
    print(f"  Activation shape: {X_train.shape}")

    # Initialize detectors
    print("\n[2/4] Initializing detectors...")
    detectors = [
        ARTActivationDetector(nb_clusters=2, nb_dims=10, pooling_method="mean", normalize=True),
        LinearProbeDetector(),
    ]

    print(f"  {len(detectors)} detectors ready")

    # Run benchmarks
    print("\n[3/4] Running benchmarks...")
    results = []
    for i, detector in enumerate(detectors, 1):
        print(f"  [{i}/{len(detectors)}] Benchmarking {detector.name}...")
        result = benchmark_detector(detector, X_train, y_train, X_test, y_test)
        results.append(result)

    # Print results
    print("\n[4/4] Results:")
    print_benchmark_results(results)

    print("\n" + "=" * 80)
    print("Benchmark completed!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
