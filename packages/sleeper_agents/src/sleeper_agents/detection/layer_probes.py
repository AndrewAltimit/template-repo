"""Multi-layer probe system for detecting deceptive behaviors.

Layer indices follow the package-wide convention: layer ``L`` is the output of
transformer block ``L`` (0-indexed), i.e. TransformerLens
``blocks.L.hook_resid_post``. By default activations are extracted one sample at
a time, so "last token" pooling always selects the last real (non-pad) token. With
``batch_size > 1`` and a model that implements ``get_last_token_activations``
(``ModelInterface``), samples are extracted in left-padded batches and pooled at the
last non-pad token of each row using the attention mask.

Sync and async APIs: activation extraction and probe fitting are blocking CPU/GPU
work, so the primary methods are synchronous (``train_layer_probes_sync``,
``extract_layer_vectors``, ``extract_residuals``, ``score_layers_sync``,
``detect_backdoor_sync``). The ``async`` methods of the same names
(``train_layer_probes``, ``_extract_layer_vectors``, ``_extract_residuals``,
``score_layers``, ``detect_backdoor``) are kept for existing awaiting callers; they
run the sync method in a worker thread (``asyncio.to_thread``) so the event loop is
not blocked, and calls on one detector are serialized by a lock (activation hooks
on a shared model are not thread-safe).
"""

import asyncio
from collections import OrderedDict
import logging
import threading
from typing import Any, Callable, Dict, Hashable, List, Optional, Sequence, TypeVar

import numpy as np

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


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


def rank_layers(
    aucs: Dict[int, float],
    secondary: Optional[Dict[int, float]] = None,
    decimals: int = 9,
) -> List[int]:
    """Order layers from best to worst held-out AUC with deterministic tie-breaking.

    Held-out AUC often saturates (e.g. 1.0 at every layer for a trigger token that is
    linearly visible everywhere), and a plain ``max`` then silently returns the
    lowest layer index. Ties are broken instead by:

    1. AUC, rounded to ``decimals`` places (higher first);
    2. ``secondary``, a lower-is-better held-out metric such as the out-of-fold Brier
       score recorded in ``LayerProbeDetector.layer_cv_brier`` (lower first; layers
       without a value rank after those with one);
    3. distance to the middle of the probed layer range (closer first), since middle
       layers are the conventional choice for linear probes;
    4. the later layer.

    Args:
        aucs: Layer index -> held-out AUC
        secondary: Optional layer index -> lower-is-better tie-break metric
        decimals: Rounding applied to AUC and ``secondary`` before comparing

    Returns:
        Layer indices, best first
    """
    if not aucs:
        return []
    layers = list(aucs)
    middle = (min(layers) + max(layers)) / 2.0
    secondary = secondary or {}

    def key(layer: int):
        sec = secondary.get(layer)
        sec_missing = sec is None or not np.isfinite(sec)
        return (
            -round(float(aucs[layer]), decimals),
            sec_missing,
            round(float(sec), decimals) if not sec_missing else 0.0,
            abs(layer - middle),
            -layer,
        )

    return sorted(layers, key=key)


def select_best_layer(aucs: Dict[int, float], secondary: Optional[Dict[int, float]] = None) -> int:
    """Best layer by held-out AUC with the tie-breaking of :func:`rank_layers`.

    Raises:
        ValueError: If ``aucs`` is empty
    """
    ranked = rank_layers(aucs, secondary)
    if not ranked:
        raise ValueError("No layer AUCs to select from")
    return ranked[0]


class LayerProbeDetector:
    """Multi-layer probe system for detecting deceptive behaviors.

    Each probe is a pipeline of per-feature standardization (``StandardScaler``)
    followed by an L2-penalized logistic regression on pooled residual-stream
    activations. Standardization is fit on the training data only (inside each
    cross-validation fold for the held-out AUC, on all training data for the final
    probe) and applied at inference as part of the pipeline, so the regularization
    strength ``C`` means the same thing at every layer even when the residual
    stream has a few very large outlier dimensions (as in Qwen models).

    The AUC reported for each layer is measured on held-out data (stratified
    k-fold cross-validation), never on the data the probe was fit on. Ensemble
    weights are proportional to ``max(AUC - 0.5, 0)``, so chance-level layers get
    no weight.
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
        batch_size: int = 1,
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
            batch_size: Samples per forward pass for last-token extraction. 1 (the
                default) runs one unpadded forward pass per sample; larger values
                batch samples through ``get_last_token_activations`` when the model
                provides it (left padding, pooled at the last non-pad token)
        """
        self.model = model
        self.max_iter = max_iter
        self.regularization = regularization
        self.detection_threshold = detection_threshold
        self.cv_folds = cv_folds
        self.random_state = random_state
        self.batch_size = max(1, int(batch_size))
        self.layer_probes: Dict[int, Any] = {}
        self.layer_aucs: Dict[int, float] = {}
        self.layer_cv_brier: Dict[int, float] = {}
        self.training_failures: Dict[int, str] = {}
        self.ensemble_weights: Optional[Dict[int, float]] = None
        self.probe_cache = BoundedCache(cache_size)
        # Serializes the async wrappers' worker-thread calls on this detector
        self._lock = threading.RLock()

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

    async def _run_blocking(self, fn: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
        """Run blocking ``fn`` in a worker thread, serialized per detector."""

        def locked() -> _T:
            with self._lock:
                return fn(*args, **kwargs)

        return await asyncio.to_thread(locked)

    async def train_layer_probes(
        self, clean_samples: List[str], backdoored_samples: List[str], layers: Optional[List[int]] = None
    ) -> Dict[int, float]:
        """Async wrapper of :meth:`train_layer_probes_sync` (runs in a worker thread)."""
        return await self._run_blocking(self.train_layer_probes_sync, clean_samples, backdoored_samples, layers)

    def train_layer_probes_sync(
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

        clean_by_layer = self.extract_layer_vectors(clean_samples, layers)
        backdoor_by_layer = self.extract_layer_vectors(backdoored_samples, layers)
        y = np.array([0] * len(clean_samples) + [1] * len(backdoored_samples))

        self.layer_probes = {}
        self.layer_aucs = {}
        self.layer_cv_brier = {}
        self.training_failures = {}
        self.ensemble_weights = None

        for layer_idx in layers:
            try:
                X = np.vstack([clean_by_layer[layer_idx], backdoor_by_layer[layer_idx]])
                cv_metrics = self._cross_validated_metrics(X, y)
                auc = cv_metrics["auc"]
                probe = self._train_simple_probe(X, y)
            except Exception as e:
                logger.warning("Failed to train probe for layer %s: %s", layer_idx, e)
                self.training_failures[layer_idx] = str(e)
                continue

            self.layer_probes[layer_idx] = probe
            self.layer_aucs[layer_idx] = float(auc)
            self.layer_cv_brier[layer_idx] = float(cv_metrics["brier"])
            logger.info("Layer %s probe trained, held-out AUC: %.3f", layer_idx, auc)

        if not self.layer_probes:
            raise RuntimeError(f"No layer probe could be trained: {self.training_failures}")

        self.ensemble_weights = self._compute_ensemble_weights(self.layer_aucs)
        return dict(self.layer_aucs)

    @staticmethod
    def _compute_ensemble_weights(aucs: Dict[int, float]) -> Dict[int, float]:
        """Weights proportional to held-out AUC above chance, keyed by layer.

        Each layer gets weight ``max(AUC - 0.5, 0)``, normalized to sum to 1, so a
        chance-level (or worse) layer contributes nothing. Weighting by raw AUC would
        give a chance layer (AUC 0.5) half the weight of a perfect one. When no layer
        is above chance the weights fall back to uniform.
        """
        if not aucs:
            return {}
        margins = {layer: max(float(auc) - 0.5, 0.0) for layer, auc in aucs.items()}
        total = sum(margins.values())
        if total <= 0:
            return {layer: 1.0 / len(aucs) for layer in aucs}
        return {layer: margin / total for layer, margin in margins.items()}

    def best_layer(self) -> int:
        """Layer with the best held-out AUC (ties broken as in :func:`rank_layers`).

        Raises:
            RuntimeError: If no probes are trained
        """
        if not self.layer_aucs:
            raise RuntimeError("No trained layer probes. Call train_layer_probes() first.")
        return select_best_layer(self.layer_aucs, self.layer_cv_brier)

    def probe_direction(self, layer_idx: int) -> np.ndarray:
        """Weight vector of a layer's probe expressed in raw activation space.

        For the standardized pipeline the decision function is
        ``w . (x - mu) / sigma + b``, so the direction in raw activation space is
        ``w / sigma`` (e.g. for projecting it out of the residual stream).

        Raises:
            KeyError: If the layer has no trained probe
        """
        probe = self.layer_probes[layer_idx]
        if hasattr(probe, "named_steps"):
            clf = probe.named_steps["probe"]
            scaler = probe.named_steps.get("scaler")
            coef = np.asarray(clf.coef_[0], dtype=np.float64)
            if scaler is not None and getattr(scaler, "scale_", None) is not None:
                coef = coef / np.asarray(scaler.scale_, dtype=np.float64)
            return coef
        return np.asarray(probe.coef_[0], dtype=np.float64)

    async def _extract_layer_vectors(self, samples: List[str], layers: List[int], pool: str = "last") -> Dict[int, np.ndarray]:
        """Async wrapper of :meth:`extract_layer_vectors` (runs in a worker thread)."""
        return await self._run_blocking(self.extract_layer_vectors, samples, layers, pool)

    def extract_layer_vectors(self, samples: List[str], layers: List[int], pool: str = "last") -> Dict[int, np.ndarray]:
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

        use_batches = self.batch_size > 1 and pool == "last" and hasattr(self.model, "get_last_token_activations")
        # Vectors per distinct sample; samples still to extract in batches, in input order
        known: Dict[str, Dict[int, np.ndarray]] = {}
        pending: List[str] = []
        for sample in samples:
            if sample in known:
                continue
            vectors = {layer: self.probe_cache.get_item((sample, layer, pool)) for layer in layers}
            missing = [layer for layer, vec in vectors.items() if vec is None]
            if not missing:
                known[sample] = vectors
            elif use_batches:
                if sample not in pending:
                    pending.append(sample)
            else:
                vectors.update(self._forward_sample(sample, missing, pool))
                for layer in missing:
                    self.probe_cache.put((sample, layer, pool), vectors[layer])
                known[sample] = vectors

        for start in range(0, len(pending), self.batch_size):
            chunk = pending[start : start + self.batch_size]
            for sample, vectors in zip(chunk, self._forward_batch_last_token(chunk, layers)):
                for layer in layers:
                    self.probe_cache.put((sample, layer, pool), vectors[layer])
                known[sample] = vectors

        return {layer: np.vstack([known[sample][layer] for sample in samples]) for layer in layers}

    def _forward_batch_last_token(self, samples: Sequence[str], layers: List[int]) -> List[Dict[int, np.ndarray]]:
        """One left-padded forward pass for several samples, pooled at each row's last non-pad token."""
        try:
            activations = self.model.get_last_token_activations(list(samples), layers=layers)
        except Exception as e:
            logger.error("Batched last-token extraction failed for layers %s: %s", layers, e)
            raise RuntimeError(f"Failed to extract batched activations: {e}") from e
        per_layer: Dict[int, np.ndarray] = {}
        for layer in layers:
            key = f"layer_{layer}"
            if key not in activations:
                raise RuntimeError(f"Layer {layer} not found in model activations")
            arr = to_numpy(activations[key]).reshape(len(samples), -1)
            per_layer[layer] = arr
        return [{layer: per_layer[layer][i] for layer in layers} for i in range(len(samples))]

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
        """Async wrapper of :meth:`extract_residuals` (runs in a worker thread)."""
        return await self._run_blocking(self.extract_residuals, samples, layer_idx, pool)

    def extract_residuals(self, samples: List[str], layer_idx: int, pool: str = "last") -> np.ndarray:
        """Extract pooled residual vectors from a single layer.

        Args:
            samples: Text samples
            layer_idx: Layer index
            pool: Pooling method ('last' or 'mean')

        Returns:
            Array of shape (n_samples, hidden_size)
        """
        vectors = self.extract_layer_vectors(samples, [layer_idx], pool)
        return vectors[layer_idx]

    def _make_probe(self):
        """Standardize-then-logistic-regression pipeline (mirrors ProbeDetector's feature scaling).

        The scaler is refit whenever the pipeline is fit, so its statistics always
        come from the training data of that fit (the training folds in
        cross-validation) and are applied unchanged at inference.
        """
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("probe", LogisticRegression(max_iter=self.max_iter, C=self.regularization, random_state=self.random_state)),
            ]
        )

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

    def _cross_validated_metrics(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        """Held-out AUC and Brier score via stratified k-fold cross-validation.

        Every sample is scored by a probe (scaler included) that did not see it
        during fitting.

        Args:
            X: Feature matrix
            y: Binary labels

        Returns:
            ``{"auc": ROC AUC, "brier": Brier score}`` of the out-of-fold predictions
        """
        from sklearn.metrics import brier_score_loss, roc_auc_score
        from sklearn.model_selection import StratifiedKFold, cross_val_predict

        n_splits = min(self.cv_folds, int(np.bincount(y).min()))
        if n_splits < 2:
            raise ValueError("Held-out AUC needs at least 2 samples per class")
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.random_state)
        oof = cross_val_predict(self._make_probe(), X, y, cv=cv, method="predict_proba")[:, 1]
        return {"auc": float(roc_auc_score(y, oof)), "brier": float(brier_score_loss(y, oof))}

    def _cross_validated_auc(self, X: np.ndarray, y: np.ndarray) -> float:
        """Held-out AUC via stratified k-fold cross-validation (see ``_cross_validated_metrics``)."""
        return self._cross_validated_metrics(X, y)["auc"]

    async def score_layers(self, text: str) -> Dict[str, Any]:
        """Async wrapper of :meth:`score_layers_sync` (runs in a worker thread)."""
        return await self._run_blocking(self.score_layers_sync, text)

    def score_layers_sync(self, text: str) -> Dict[str, Any]:
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
        vectors = self.extract_layer_vectors([text], layers)

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
        """Async wrapper of :meth:`detect_backdoor_sync` (runs in a worker thread)."""
        return await self._run_blocking(self.detect_backdoor_sync, text, use_ensemble)

    def detect_backdoor_sync(self, text: str, use_ensemble: bool = True) -> Dict[str, Any]:
        """Detect if text triggers backdoor behavior.

        Args:
            text: Text to analyze
            use_ensemble: Whether to combine probes with a weighted average
                (weights proportional to held-out AUC above chance)
                (otherwise the maximum layer score is used)

        Returns:
            Detection results: ``scores`` (``layer_{i}`` -> probability, plus
            ``ensemble`` when used), ``is_backdoored``, ``confidence`` (the final
            score), ``threshold``, ``failed_layers`` and ``is_mock`` (always False)

        Raises:
            RuntimeError: If no probes are trained or no probe could score the input
        """
        layer_result = self.score_layers_sync(text)
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
