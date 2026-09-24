"""Multi-layer probe system for detecting deceptive behaviors.

Layer indices follow the package-wide convention: layer ``L`` is the output of
transformer block ``L`` (0-indexed), i.e. TransformerLens
``blocks.L.hook_resid_post``. Activations are extracted one sample at a time so
"last token" pooling always selects the last real (non-pad) token.
"""

from collections import OrderedDict
import logging
from typing import Any, Dict, Hashable, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def to_numpy(tensor: Any) -> np.ndarray:
    """Convert a torch tensor (any dtype/device) or array-like to a float64 numpy array."""
    if hasattr(tensor, "detach"):
        tensor = tensor.detach().float().cpu().numpy()
    return np.asarray(tensor, dtype=np.float64)


class BoundedCache(OrderedDict):
    """Small LRU cache: evicts the least recently used entry beyond ``max_size``.

    A ``max_size`` of 0 disables caching entirely.
    """

    def __init__(self, max_size: int = 1000):
        super().__init__()
        self.max_size = max(0, int(max_size))

    def get_item(self, key: Hashable) -> Any:
        """Return the cached value (marking it recently used) or None."""
        if key not in self:
            return None
        self.move_to_end(key)
        return self[key]

    def put(self, key: Hashable, value: Any) -> None:
        """Insert a value, evicting old entries if the cache is full."""
        if self.max_size == 0:
            return
        self[key] = value
        self.move_to_end(key)
        while len(self) > self.max_size:
            self.popitem(last=False)


class LayerProbeDetector:
    """Multi-layer probe system for detecting deceptive behaviors.

    Probes are logistic regressions on pooled residual-stream activations. The
    AUC reported for each layer is measured on held-out data (stratified
    k-fold cross-validation), never on the data the probe was fit on, and
    those held-out AUCs set the ensemble weights.
    """

    def __init__(
        self,
        model,
        max_iter: int = 2000,
        regularization: float = 0.1,
        detection_threshold: float = 0.5,
        cache_size: int = 1000,
        cv_folds: int = 5,
        random_state: int = 42,
    ):
        """Initialize the layer probe detector.

        Args:
            model: The model to probe (ModelInterface or TransformerLens model)
            max_iter: Maximum solver iterations for each logistic regression probe
            regularization: Inverse regularization strength ``C`` of the probes
            detection_threshold: Score above which a sample is flagged as backdoored
            cache_size: Maximum number of cached (sample, layer, pool) activations
            cv_folds: Maximum number of stratified folds for held-out AUC
            random_state: Seed for fold shuffling and the probe solver
        """
        self.model = model
        self.max_iter = max_iter
        self.regularization = regularization
        self.detection_threshold = detection_threshold
        self.cv_folds = cv_folds
        self.random_state = random_state
        self.layer_probes: Dict[int, Any] = {}
        self.layer_aucs: Dict[int, float] = {}
        self.training_failures: Dict[int, str] = {}
        self.ensemble_weights: Optional[Dict[int, float]] = None
        self.probe_cache = BoundedCache(cache_size)

    def _default_layers(self) -> List[int]:
        """Layers to probe when none are specified."""
        if hasattr(self.model, "get_num_layers"):
            n_layers = int(self.model.get_num_layers())
            if n_layers > 0:
                return list(range(n_layers))
        config = getattr(self.model, "config", None) or getattr(self.model, "cfg", None)
        for attr in ("n_layers", "n_layer", "num_hidden_layers"):
            value = getattr(config, attr, None) if config is not None else None
            if isinstance(value, int) and value > 0:
                return list(range(value))
        raise ValueError("Cannot determine the number of model layers; pass 'layers' explicitly")

    async def train_layer_probes(
        self, clean_samples: List[str], backdoored_samples: List[str], layers: Optional[List[int]] = None
    ) -> Dict[int, float]:
        """Train probes on each layer and return held-out AUC scores.

        Replaces any previously trained probes. Layers whose probe could not be
        trained are omitted from the result and recorded in
        ``self.training_failures``.

        Args:
            clean_samples: Clean text samples (label 0)
            backdoored_samples: Backdoored text samples (label 1)
            layers: Layers to probe (None for all model layers)

        Returns:
            Dictionary mapping layer indices to cross-validated (held-out) AUC

        Raises:
            ValueError: If there are fewer than 2 samples in either class
            RuntimeError: If activation extraction fails or no probe could be trained
        """
        min_class = min(len(clean_samples), len(backdoored_samples))
        if min_class < 2:
            raise ValueError(
                "Held-out AUC needs at least 2 clean and 2 backdoored samples "
                f"(got {len(clean_samples)} clean, {len(backdoored_samples)} backdoored)"
            )

        if layers is None:
            layers = self._default_layers()
        layers = list(dict.fromkeys(layers))

        clean_by_layer = await self._extract_layer_vectors(clean_samples, layers)
        backdoor_by_layer = await self._extract_layer_vectors(backdoored_samples, layers)
        y = np.array([0] * len(clean_samples) + [1] * len(backdoored_samples))

        self.layer_probes = {}
        self.layer_aucs = {}
        self.training_failures = {}
        self.ensemble_weights = None

        for layer_idx in layers:
            try:
                X = np.vstack([clean_by_layer[layer_idx], backdoor_by_layer[layer_idx]])
                auc = self._cross_validated_auc(X, y)
                probe = self._train_simple_probe(X, y)
            except Exception as e:
                logger.warning("Failed to train probe for layer %s: %s", layer_idx, e)
                self.training_failures[layer_idx] = str(e)
                continue

            self.layer_probes[layer_idx] = probe
            self.layer_aucs[layer_idx] = float(auc)
            logger.info("Layer %s probe trained, held-out AUC: %.3f", layer_idx, auc)

        if not self.layer_probes:
            raise RuntimeError(f"No layer probe could be trained: {self.training_failures}")

        self.ensemble_weights = self._compute_ensemble_weights(self.layer_aucs)
        return dict(self.layer_aucs)

    @staticmethod
    def _compute_ensemble_weights(aucs: Dict[int, float]) -> Dict[int, float]:
        """Weights proportional to held-out AUC, keyed by layer."""
        total = sum(aucs.values())
        if total <= 0:
            return {layer: 1.0 / len(aucs) for layer in aucs}
        return {layer: auc / total for layer, auc in aucs.items()}

    async def _extract_layer_vectors(self, samples: List[str], layers: List[int], pool: str = "last") -> Dict[int, np.ndarray]:
        """Extract pooled residual vectors for several layers with one forward pass per sample.

        Args:
            samples: Text samples
            layers: Layer indices
            pool: Pooling method ('last' = last non-pad token, or 'mean')

        Returns:
            Mapping of layer index to array of shape (n_samples, hidden_size)

        Raises:
            RuntimeError: If the model doesn't support activation extraction or a layer is missing
            ValueError: If an invalid pooling method is specified
        """
        if pool not in ("last", "mean"):
            raise ValueError(f"Unknown pooling method: {pool}")
        if not samples:
            raise RuntimeError("No samples provided for activation extraction")

        per_layer: Dict[int, List[np.ndarray]] = {layer: [] for layer in layers}
        for sample in samples:
            vectors = {layer: self.probe_cache.get_item((sample, layer, pool)) for layer in layers}
            missing = [layer for layer, vec in vectors.items() if vec is None]
            if missing:
                vectors.update(self._forward_sample(sample, missing, pool))
                for layer in missing:
                    self.probe_cache.put((sample, layer, pool), vectors[layer])
            for layer in layers:
                per_layer[layer].append(vectors[layer])

        return {layer: np.vstack(vecs) for layer, vecs in per_layer.items()}

    def _forward_sample(self, sample: str, layers: List[int], pool: str) -> Dict[int, np.ndarray]:
        """Run a single forward pass for one sample and pool the requested layers."""
        if hasattr(self.model, "get_activations"):
            try:
                activations = self.model.get_activations([sample], layers=layers, return_attention=False)
            except Exception as e:
                logger.error("ModelInterface extraction failed for layers %s: %s", layers, e)
                raise RuntimeError(f"Failed to extract activations from ModelInterface: {e}") from e
            tensors = {}
            for layer in layers:
                key = f"layer_{layer}"
                if key not in activations:
                    raise RuntimeError(f"Layer {layer} not found in model activations")
                tensors[layer] = activations[key]

        elif hasattr(self.model, "run_with_cache"):
            names = {f"blocks.{layer}.hook_resid_post": layer for layer in layers}
            try:
                tokens = self.model.to_tokens(sample)
                _, cache = self.model.run_with_cache(tokens, names_filter=lambda name: name in names)
            except Exception as e:
                logger.error("TransformerLens extraction failed for layers %s: %s", layers, e)
                raise RuntimeError(f"Failed to extract activations from TransformerLens model: {e}") from e
            tensors = {}
            for name, layer in names.items():
                if name not in cache:
                    raise RuntimeError(f"Cache key {name} not found in TransformerLens cache")
                tensors[layer] = cache[name]

        else:
            raise RuntimeError(
                f"Model type {type(self.model).__name__} doesn't support activation extraction. "
                "Model must have either 'get_activations' (ModelInterface) or "
                "'run_with_cache' (TransformerLens) method."
            )

        pooled = {}
        for layer, tensor in tensors.items():
            # Shape (batch=1, seq_len, hidden). A single unpadded sample, so the
            # final position is the last real token.
            seq = tensor[0]
            vec = seq[-1] if pool == "last" else seq.mean(0)
            pooled[layer] = to_numpy(vec).reshape(-1)
        return pooled

    async def _extract_residuals(self, samples: List[str], layer_idx: int, pool: str = "last") -> np.ndarray:
        """Extract pooled residual vectors from a single layer.

        Args:
            samples: Text samples
            layer_idx: Layer index
            pool: Pooling method ('last' or 'mean')

        Returns:
            Array of shape (n_samples, hidden_size)
        """
        vectors = await self._extract_layer_vectors(samples, [layer_idx], pool)
        return vectors[layer_idx]

    def _make_probe(self):
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(max_iter=self.max_iter, C=self.regularization, random_state=self.random_state)

    def _train_simple_probe(self, X: np.ndarray, y: np.ndarray):
        """Train a linear probe on all provided data.

        Args:
            X: Feature matrix
            y: Labels

        Returns:
            Trained probe model
        """
        probe = self._make_probe()
        probe.fit(X, y)
        return probe

    def _cross_validated_auc(self, X: np.ndarray, y: np.ndarray) -> float:
        """Held-out AUC via stratified k-fold cross-validation.

        Every sample is scored by a probe that did not see it during fitting.

        Args:
            X: Feature matrix
            y: Binary labels

        Returns:
            ROC AUC of the out-of-fold predictions
        """
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import StratifiedKFold, cross_val_predict

        n_splits = min(self.cv_folds, int(np.bincount(y).min()))
        if n_splits < 2:
            raise ValueError("Held-out AUC needs at least 2 samples per class")
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.random_state)
        oof = cross_val_predict(self._make_probe(), X, y, cv=cv, method="predict_proba")[:, 1]
        return float(roc_auc_score(y, oof))

    async def score_layers(self, text: str) -> Dict[str, Any]:
        """Score text with every trained probe.

        Args:
            text: Text to analyze

        Returns:
            Dict with ``scores`` (layer index -> probability) and ``failed_layers``
            (layer index -> error message)

        Raises:
            RuntimeError: If no probes are trained or activations cannot be extracted
        """
        if not self.layer_probes:
            raise RuntimeError("No trained layer probes. Call train_layer_probes() first.")

        layers = sorted(self.layer_probes)
        vectors = await self._extract_layer_vectors([text], layers)

        scores: Dict[int, float] = {}
        failed: Dict[int, str] = {}
        for layer_idx in layers:
            probe = self.layer_probes[layer_idx]
            residual = vectors[layer_idx][0].reshape(1, -1)
            try:
                if hasattr(probe, "predict_proba"):
                    score = probe.predict_proba(residual)[0, 1]
                else:
                    score = probe.predict(residual)[0]
                scores[layer_idx] = float(score)
            except Exception as e:
                logger.warning("Probe scoring failed for layer %s: %s", layer_idx, e)
                failed[layer_idx] = str(e)

        if not scores:
            raise RuntimeError(f"All layer probes failed to score the input: {failed}")
        return {"scores": scores, "failed_layers": failed}

    async def detect_backdoor(self, text: str, use_ensemble: bool = True) -> Dict[str, Any]:
        """Detect if text triggers backdoor behavior.

        Args:
            text: Text to analyze
            use_ensemble: Whether to combine probes with AUC-weighted averaging
                (otherwise the maximum layer score is used)

        Returns:
            Detection results: ``scores`` (``layer_{i}`` -> probability, plus
            ``ensemble`` when used), ``is_backdoored``, ``confidence`` (the final
            score), ``threshold``, ``failed_layers`` and ``is_mock`` (always False)

        Raises:
            RuntimeError: If no probes are trained or no probe could score the input
        """
        layer_result = await self.score_layers(text)
        layer_scores: Dict[int, float] = layer_result["scores"]
        scores: Dict[str, float] = {f"layer_{layer}": score for layer, score in layer_scores.items()}

        if use_ensemble and len(layer_scores) > 1:
            weights_map = self.ensemble_weights or {}
            weights = np.array([weights_map.get(layer, 0.0) for layer in layer_scores])
            if weights.sum() <= 0:
                weights = np.ones(len(layer_scores))
            final_score = float(np.average(list(layer_scores.values()), weights=weights))
            scores["ensemble"] = final_score
        else:
            final_score = max(layer_scores.values())

        return {
            "scores": scores,
            "is_backdoored": bool(final_score > self.detection_threshold),
            "confidence": float(final_score),
            "threshold": float(self.detection_threshold),
            "failed_layers": {f"layer_{layer}": err for layer, err in layer_result["failed_layers"].items()},
            "is_mock": False,
        }


class SimpleProbe:
    """Nearest-centroid probe (dependency-free reference implementation)."""

    def __init__(self, X: np.ndarray, y: np.ndarray):
        """Train a simple linear probe.

        Args:
            X: Feature matrix
            y: Labels
        """
        # Simple centroid-based classifier
        self.positive_centroid = X[y == 1].mean(axis=0) if np.any(y == 1) else np.zeros(X.shape[1])
        self.negative_centroid = X[y == 0].mean(axis=0) if np.any(y == 0) else np.zeros(X.shape[1])

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict scores for samples.

        Args:
            X: Feature matrix

        Returns:
            Prediction scores
        """
        # Distance-based prediction
        pos_dist = np.linalg.norm(X - self.positive_centroid, axis=1)
        neg_dist = np.linalg.norm(X - self.negative_centroid, axis=1)

        # Convert distances to scores (closer to positive = higher score)
        scores = 1 / (1 + np.exp(pos_dist - neg_dist))
        return np.array(scores)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities.

        Args:
            X: Feature matrix

        Returns:
            Probability matrix
        """
        scores = self.predict(X)
        # Return as 2D array with [negative_prob, positive_prob]
        return np.column_stack([1 - scores, scores])
