"""Example usage of ARTActivationDetector for backdoor detection.

This example demonstrates how to use the clustering-based detector to identify
potential backdoor behavior in model activations.
"""

import numpy as np

from sleeper_agents.detection.art_activation_detector import ARTActivationDetector
from sleeper_agents.evaluation.detector_registry import DetectorRegistry


def generate_synthetic_data(n_clean=200, n_backdoor=50, hidden_dim=768, seq_len=20):
    """Generate synthetic activations mimicking clean and backdoored samples.

    Args:
        n_clean: Number of clean samples
        n_backdoor: Number of backdoored samples
        hidden_dim: Activation dimension
        seq_len: Sequence length

    Returns:
        activations: 3D array of shape (n_samples, seq_len, hidden_dim)
        labels: Binary labels (0=clean, 1=backdoored)
    """
    np.random.seed(42)

    # Clean samples: Normal distribution around origin
    clean_acts = np.random.randn(n_clean, seq_len, hidden_dim).astype(np.float32)

    # Backdoored samples: Shifted distribution (simulating trigger activation)
    backdoor_acts = np.random.randn(n_backdoor, seq_len, hidden_dim).astype(np.float32) + 3.0

    # Combine and shuffle
    activations = np.vstack([clean_acts, backdoor_acts])
    labels = np.array([0] * n_clean + [1] * n_backdoor)

    # Shuffle to make it more realistic
    indices = np.random.permutation(len(activations))
    return activations[indices], labels[indices]


def example_basic_usage():
    """Example 1: Basic detector usage."""
    print("=" * 70)
    print("Example 1: Basic ARTActivationDetector Usage")
    print("=" * 70)

    # Generate synthetic data
    print("\nGenerating synthetic activation data...")
    activations, labels = generate_synthetic_data()
    print(f"  Activations shape: {activations.shape}")
    print(f"  Clean samples: {np.sum(labels == 0)}")
    print(f"  Backdoored samples: {np.sum(labels == 1)}")

    # Create detector
    print("\nCreating ARTActivationDetector...")
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10, pooling_method="mean", normalize=True)

    # Run detection
    print("\nRunning detection pipeline...")
    result = detector.run(activations=activations, labels=labels)

    # Display results
    print("\n" + "-" * 70)
    print("Detection Results:")
    print("-" * 70)
    print(f"  Overall Score: {result['score']:.4f}")
    print(f"  Is Backdoored: {result['is_backdoored']}")
    print("\nReport:")
    print(f"  Method: {result['report']['method']}")
    print(f"  Suspicious Samples: {result['report']['suspicious_samples']}")
    print(f"  Total Samples: {result['report']['total_samples']}")
    print(f"  Threshold: {result['report']['threshold']:.4f}")
    print(f"  PCA Variance Explained: {result['report']['pca_variance_explained']:.2%}")

    print("\nCluster Composition:")
    for cluster_name, info in result["report"]["cluster_composition"].items():
        print(f"  {cluster_name}:")
        print(f"    Size: {info['size']}")
        print(f"    Clean: {info['clean_count']}")
        print(f"    Backdoored: {info['backdoor_count']}")
        print(f"    Purity: {info['purity']:.2%}")

    print()


def example_registry_usage():
    """Example 2: Using the detector via DetectorRegistry."""
    print("=" * 70)
    print("Example 2: Using DetectorRegistry")
    print("=" * 70)

    # Generate synthetic data
    activations, labels = generate_synthetic_data(n_clean=100, n_backdoor=25)

    # Get detector from registry
    print("\nGetting detector from registry...")
    detector = DetectorRegistry.get("art_activation", nb_clusters=2, nb_dims=15)
    print(f"  Detector: {detector.name}")
    print(f"  Configuration: nb_clusters={detector.nb_clusters}, nb_dims={detector.nb_dims}")

    # Fit and score separately
    print("\nFitting detector...")
    detector.fit(activations, labels)

    print("Scoring samples...")
    scores = detector.score(activations)

    print("\nScore Statistics:")
    print(f"  Mean: {scores.mean():.4f}")
    print(f"  Std: {scores.std():.4f}")
    print(f"  Min: {scores.min():.4f}")
    print(f"  Max: {scores.max():.4f}")

    # Find most suspicious samples
    top_k = 5
    most_suspicious = np.argsort(scores)[::-1][:top_k]

    print(f"\nTop {top_k} most suspicious samples:")
    for idx in most_suspicious:
        print(f"  Sample {idx}: score={scores[idx]:.4f}, " f"label={'BACKDOOR' if labels[idx] == 1 else 'CLEAN'}")

    print()


def example_pooling_methods():
    """Example 3: Comparing different pooling methods."""
    print("=" * 70)
    print("Example 3: Comparing Pooling Methods")
    print("=" * 70)

    # Generate synthetic data
    activations, labels = generate_synthetic_data()

    pooling_methods = ["mean", "last", "first"]

    for pooling in pooling_methods:
        print(f"\nPooling method: {pooling}")
        print("-" * 40)

        detector = ARTActivationDetector(nb_clusters=2, nb_dims=10, pooling_method=pooling)

        result = detector.run(activations=activations, labels=labels)

        print(f"  Score: {result['score']:.4f}")
        print(f"  Is Backdoored: {result['is_backdoored']}")
        print(f"  Suspicious: {result['report']['suspicious_samples']}/{result['report']['total_samples']}")

    print()


def example_explain_sample():
    """Example 4: Explaining individual sample predictions."""
    print("=" * 70)
    print("Example 4: Explaining Sample Predictions")
    print("=" * 70)

    # Generate synthetic data
    activations, labels = generate_synthetic_data(n_clean=50, n_backdoor=10)

    # Create and fit detector
    detector = ARTActivationDetector(nb_clusters=2, nb_dims=10)
    detector.fit(activations, labels)

    # Score samples
    scores = detector.score(activations)

    # Explain a few samples
    sample_indices = [0, 30, 50]  # Clean, clean, backdoor

    print("\nExplaining sample predictions...")
    for idx in sample_indices:
        sample_acts = activations[idx : idx + 1]
        sample_score = scores[idx]

        explanation = detector.explain(sample_id=f"sample_{idx}", score=sample_score, activations=sample_acts)

        print(f"\n{explanation['sample_id']}:")
        print(f"  True Label: {'BACKDOOR' if labels[idx] == 1 else 'CLEAN'}")
        print(f"  Score: {explanation['score']:.4f}")
        print(f"  Cluster: {explanation.get('cluster_assignment', 'N/A')}")
        print(f"  Explanation: {explanation['explanation'][:100]}...")

    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ARTActivationDetector Examples")
    print("=" * 70)
    print()

    # Run all examples
    example_basic_usage()
    example_registry_usage()
    example_pooling_methods()
    example_explain_sample()

    print("=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)
    print()
