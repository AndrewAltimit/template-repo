"""ART-inspired activation-based backdoor detector.

This module implements clustering-based backdoor detection inspired by
IBM's Adversarial Robustness Toolbox (ART) ActivationDefence method.

The detector uses K-means clustering on PCA-reduced activations to identify
suspicious patterns that may indicate backdoor behavior.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from sleeper_agents.detection.base_detector import BaseDetector
from sleeper_agents.evaluation.detector_registry import DetectorRegistry

logger = logging.getLogger(__name__)


@DetectorRegistry.register("art_activation")
class ARTActivationDetector(BaseDetector):
    """Clustering-based backdoor detector inspired by ART's ActivationDefence.

    Uses K-means clustering on PCA-reduced activations to identify suspicious
    samples. Clean and backdoored samples often form distinct clusters in
    activation space.

    The detection methodology is inspired by:
    - ART's ActivationDefence (clustering-based poison detection)
    - Chen et al. "Detecting Backdoor Attacks on Deep Neural Networks"

    Args:
        model: Optional model reference (for compatibility, not used directly)
        **kwargs: Configuration parameters:
            - nb_clusters (int): Number of clusters for K-means (default: 2)
            - nb_dims (int): PCA dimensions for reduction (default: 10)
            - pooling_method (str): How to pool sequence dim ('mean'|'last'|'first')
            - normalize (bool): Whether to standardize activations (default: True)
            - random_state (int): Random seed for reproducibility (default: 42)
    """

    def __init__(self, model: Optional[Any] = None, **kwargs):
        super().__init__(model, **kwargs)

        # Clustering configuration
        self.nb_clusters = self.config.get("nb_clusters", 2)
        self.nb_dims = self.config.get("nb_dims", 10)
        self.pooling_method = self.config.get("pooling_method", "mean")
        self.normalize = self.config.get("normalize", True)
        self.random_state = self.config.get("random_state", 42)

        # Internal state
        self._scaler: Optional[StandardScaler] = None
        self._pca: Optional[PCA] = None
        self._clusterer: Optional[KMeans] = None
        self._cluster_labels: Optional[np.ndarray] = None
        self._is_fitted = False

        logger.info(
            "Initialized %s with %d clusters, %d PCA dims, pooling=%s",
            self.name,
            self.nb_clusters,
            self.nb_dims,
            self.pooling_method,
        )

    @property
    def inputs_required(self) -> Dict[str, str]:
        """Define required inputs for this detector."""
        return {
            "activations": "Neural network activations (2D or 3D array)",
            "labels": "Binary labels (0=clean, 1=backdoored)",
        }

    def _pool_activations(self, activations: np.ndarray) -> np.ndarray:
        """Pool sequence dimension if present.

        Args:
            activations: Shape (n_samples, hidden_dim) or (n_samples, seq_len, hidden_dim)

        Returns:
            Pooled activations of shape (n_samples, hidden_dim)
        """
        if len(activations.shape) == 2:
            # Already 2D, no pooling needed
            return activations

        if len(activations.shape) == 3:
            # Pool sequence dimension
            if self.pooling_method == "mean":
                return np.asarray(activations.mean(axis=1))
            if self.pooling_method == "last":
                return np.asarray(activations[:, -1, :])
            if self.pooling_method == "first":
                return np.asarray(activations[:, 0, :])
            raise ValueError(f"Unknown pooling method: {self.pooling_method}")

        raise ValueError(f"Activations must be 2D or 3D, got shape {activations.shape}")

    def fit(self, activations: np.ndarray, labels: np.ndarray) -> None:
        """Fit clustering detector on activations.

        Args:
            activations: Activations array, shape (n_samples, hidden_dim) or
                        (n_samples, seq_len, hidden_dim)
            labels: Binary labels (0=clean, 1=backdoored)

        Raises:
            ValueError: If inputs have mismatched shapes or invalid dimensions
        """
        if len(activations) != len(labels):
            raise ValueError(f"Activations ({len(activations)}) and labels ({len(labels)}) must have same length")

        logger.info("Fitting on %d samples with shape %s", len(activations), activations.shape)

        # Pool sequence dimension if needed
        pooled = self._pool_activations(activations)
        logger.debug("Pooled activations shape: %s", pooled.shape)

        # Normalize activations
        if self.normalize:
            self._scaler = StandardScaler()
            pooled = self._scaler.fit_transform(pooled)
            logger.debug("Applied standardization")

        # Apply PCA for dimensionality reduction
        n_components = min(self.nb_dims, pooled.shape[1], len(pooled) - 1)
        self._pca = PCA(n_components=n_components, random_state=self.random_state)
        reduced = self._pca.fit_transform(pooled)
        logger.info(
            "Reduced to %d dims, explained variance: %.3f",
            n_components,
            self._pca.explained_variance_ratio_.sum(),
        )

        # Cluster activations
        self._clusterer = KMeans(
            n_clusters=self.nb_clusters,
            random_state=self.random_state,
            n_init=10,
        )
        self._cluster_labels = self._clusterer.fit_predict(reduced)

        # Analyze cluster composition
        unique, counts = np.unique(self._cluster_labels, return_counts=True)
        logger.info("Cluster sizes: %s", dict(zip(unique, counts)))

        self._is_fitted = True

    def score(self, activations: np.ndarray) -> np.ndarray:
        """Score activations based on distance to cluster centers.

        Higher scores indicate samples that are further from cluster centers,
        which may indicate backdoor/poisoned samples.

        Args:
            activations: Activations to score

        Returns:
            scores: Distance-based scores (higher = more suspicious)

        Raises:
            RuntimeError: If detector hasn't been fitted yet
        """
        if not self._is_fitted:
            raise RuntimeError("Must call fit() before score()")

        # Pool and process activations
        pooled = self._pool_activations(activations)

        if self.normalize and self._scaler is not None:
            pooled = self._scaler.transform(pooled)

        reduced = self._pca.transform(pooled)  # type: ignore

        # Compute distances to all cluster centers
        distances = self._clusterer.transform(reduced)  # type: ignore

        # Score is distance to nearest cluster center
        # (higher = more anomalous)
        scores = np.min(distances, axis=1)

        return np.asarray(scores)

    def run(self, **kwargs) -> Dict[str, Any]:
        """Run full detection pipeline.

        Args:
            **kwargs: Must contain 'activations' and 'labels'

        Returns:
            Detection results with score, is_backdoored flag, and detailed report
        """
        activations = kwargs.get("activations")
        labels = kwargs.get("labels")

        if activations is None or labels is None:
            raise ValueError("Must provide 'activations' and 'labels'")

        # Fit detector
        self.fit(activations, labels)

        # Score samples
        scores = self.score(activations)

        # Determine threshold (90th percentile by default)
        threshold_percentile = kwargs.get("threshold_percentile", 90)
        threshold = np.percentile(scores, threshold_percentile)
        suspicious_mask = scores > threshold
        suspicious_count = int(np.sum(suspicious_mask))

        # Model is backdoored if significant portion is suspicious
        backdoor_ratio_threshold = kwargs.get("backdoor_ratio_threshold", 0.1)
        is_backdoored = (suspicious_count / len(scores)) > backdoor_ratio_threshold

        # Analyze cluster-label alignment
        cluster_label_matrix = self._analyze_clusters(labels)

        return {
            "score": float(np.mean(scores)),
            "is_backdoored": is_backdoored,
            "report": {
                "method": "ART_ActivationDefence_Inspired",
                "nb_clusters": self.nb_clusters,
                "nb_dims": self._pca.n_components_ if self._pca else 0,
                "suspicious_samples": suspicious_count,
                "total_samples": len(scores),
                "threshold": float(threshold),
                "threshold_percentile": threshold_percentile,
                "cluster_composition": cluster_label_matrix,
                "pca_variance_explained": (float(self._pca.explained_variance_ratio_.sum()) if self._pca else 0.0),
            },
            "metadata": {
                "config": self.config,
                "pooling_method": self.pooling_method,
                "normalize": self.normalize,
            },
        }

    def _analyze_clusters(self, labels: np.ndarray) -> Dict[str, Any]:
        """Analyze how labels are distributed across clusters.

        Args:
            labels: Ground truth labels

        Returns:
            Dictionary with cluster composition statistics
        """
        if self._cluster_labels is None:
            return {}

        composition = {}
        for cluster_id in range(self.nb_clusters):
            mask = self._cluster_labels == cluster_id
            cluster_labels = labels[mask]

            if len(cluster_labels) > 0:
                clean_count = int(np.sum(cluster_labels == 0))
                backdoor_count = int(np.sum(cluster_labels == 1))
                purity = float(max(clean_count, backdoor_count) / len(cluster_labels))
                composition[f"cluster_{cluster_id}"] = {
                    "size": int(np.sum(mask)),
                    "clean_count": clean_count,
                    "backdoor_count": backdoor_count,
                    "purity": purity,
                }

        return composition

    def explain(self, sample_id: str, **kwargs) -> Dict[str, Any]:
        """Explain why a sample was flagged as suspicious.

        Args:
            sample_id: Identifier for the sample
            **kwargs: Additional context (e.g., activations, score)

        Returns:
            Explanation dictionary
        """
        if not self._is_fitted:
            parent_explanation: Dict[str, Any] = super().explain(sample_id)
            return parent_explanation

        score = kwargs.get("score", 0.0)
        activations = kwargs.get("activations")

        explanation = {
            "method": self.name,
            "sample_id": sample_id,
            "score": float(score),
            "explanation": (
                f"Sample scored {score:.4f} based on distance to cluster centers. "
                f"Higher scores indicate activations that are anomalous compared to "
                f"the {self.nb_clusters} learned clusters."
            ),
        }

        if activations is not None:
            # Compute cluster assignment
            pooled = self._pool_activations(activations)
            if self.normalize and self._scaler is not None:
                pooled = self._scaler.transform(pooled)
            reduced = self._pca.transform(pooled)  # type: ignore
            cluster_id = self._clusterer.predict(reduced)[0]  # type: ignore

            explanation["cluster_assignment"] = int(cluster_id)
            explanation["explanation"] += f" Assigned to cluster {cluster_id}."

        return explanation
