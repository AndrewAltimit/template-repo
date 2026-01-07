"""Multi-layer probe system for detecting deceptive behaviors."""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class LayerProbeDetector:
    """Multi-layer probe system for detecting deceptive behaviors."""

    def __init__(self, model):
        """Initialize the layer probe detector.

        Args:
            model: The model to probe
        """
        self.model = model
        self.layer_probes = {}
        self.ensemble_weights = None
        self.probe_cache = {}

    async def train_layer_probes(
        self, clean_samples: List[str], backdoored_samples: List[str], layers: Optional[List[int]] = None
    ) -> Dict[int, float]:
        """Train probes on each layer and return AUC scores.

        Args:
            clean_samples: Clean text samples
            backdoored_samples: Backdoored text samples
            layers: Layers to probe (None for all)

        Returns:
            Dictionary mapping layer indices to AUC scores
        """
        if layers is None:
            if hasattr(self.model, "config"):
                # Try different attribute names used by different model architectures
                if hasattr(self.model.config, "n_layers"):
                    n_layers = min(self.model.config.n_layers, 12)
                elif hasattr(self.model.config, "n_layer"):
                    n_layers = min(self.model.config.n_layer, 12)
                elif hasattr(self.model.config, "num_hidden_layers"):
                    n_layers = min(self.model.config.num_hidden_layers, 12)
                else:
                    n_layers = 6  # Fallback
                layers = list(range(n_layers))
            else:
                layers = list(range(6))  # Default for testing

        results = {}

        for layer_idx in layers:
            try:
                # Extract residuals
                clean_residuals = await self._extract_residuals(clean_samples, layer_idx)
                backdoor_residuals = await self._extract_residuals(backdoored_samples, layer_idx)

                # Prepare data
                X = np.vstack([clean_residuals, backdoor_residuals])
                y = np.array([0] * len(clean_residuals) + [1] * len(backdoor_residuals))

                # Train probe (simplified for testing)
                probe = self._train_simple_probe(X, y)

                # Calculate AUC
                auc = self._calculate_auc(X, y, probe)

                self.layer_probes[layer_idx] = probe
                results[layer_idx] = float(auc)

                logger.info("Layer %s probe trained with AUC: %.3f", layer_idx, auc)

            except Exception as e:
                logger.warning("Failed to train probe for layer %s: %s", layer_idx, e)
                results[layer_idx] = 0.5

        # Calculate ensemble weights based on AUC scores
        if results:
            total_auc = sum(results.values())
            if total_auc > 0:
                self.ensemble_weights = [results[i] / total_auc for i in sorted(results.keys())]

        return results

    async def _extract_residuals(self, samples: List[str], layer_idx: int, pool: str = "last") -> np.ndarray:
        """Extract residual stream from specified layer.

        Args:
            samples: Text samples
            layer_idx: Layer index
            pool: Pooling method ('last' or 'mean')

        Returns:
            Residual vectors

        Raises:
            RuntimeError: If model doesn't support activation extraction
            ValueError: If invalid pooling method specified
        """
        residuals = []

        for sample in samples:
            # Check cache first
            cache_key = (sample, layer_idx, pool)
            if cache_key in self.probe_cache:
                residuals.append(self.probe_cache[cache_key])
                continue

            # Try ModelInterface first (unified interface)
            if hasattr(self.model, "get_activations"):
                try:
                    activations = self.model.get_activations([sample], layers=[layer_idx], return_attention=False)
                    layer_key = f"layer_{layer_idx}"

                    if layer_key not in activations:
                        raise RuntimeError(f"Layer {layer_idx} not found in model activations")

                    # activations[layer_key] shape: (batch=1, seq_len, hidden_size)
                    layer_tensor = activations[layer_key]

                    if pool == "last":
                        vec = layer_tensor[0, -1].detach().cpu().numpy()
                    elif pool == "mean":
                        vec = layer_tensor[0].mean(dim=0).detach().cpu().numpy()
                    else:
                        raise ValueError(f"Unknown pooling method: {pool}")

                    self.probe_cache[cache_key] = vec
                    residuals.append(vec)
                    continue

                except Exception as e:
                    logger.error("ModelInterface extraction failed for layer %s: %s", layer_idx, e)
                    raise RuntimeError(f"Failed to extract activations from ModelInterface: {e}") from e

            # Try HookedTransformer interface (backward compatibility)
            elif hasattr(self.model, "run_with_cache"):
                try:
                    tokens = self.model.to_tokens(sample)
                    _, cache = self.model.run_with_cache(tokens)

                    # Get residual at layer using string-based cache key
                    # TransformerLens uses format: blocks.{layer}.hook_resid_post
                    cache_key_str = f"blocks.{layer_idx}.hook_resid_post"
                    if cache_key_str not in cache:
                        raise RuntimeError(f"Cache key {cache_key_str} not found. Available: {list(cache.keys())[:5]}...")
                    resid = cache[cache_key_str]

                    if pool == "last":
                        vec = resid[:, -1].detach().cpu().numpy()
                    elif pool == "mean":
                        vec = resid.mean(dim=1).detach().cpu().numpy()
                    else:
                        raise ValueError(f"Unknown pooling method: {pool}")

                    vec = vec.squeeze()

                    self.probe_cache[cache_key] = vec
                    residuals.append(vec)
                    continue

                except Exception as e:
                    logger.error("HookedTransformer extraction failed for layer %s: %s", layer_idx, e)
                    raise RuntimeError(f"Failed to extract activations from HookedTransformer: {e}") from e

            else:
                # No supported interface - fail loudly
                raise RuntimeError(
                    f"Model type {type(self.model).__name__} doesn't support activation extraction. "
                    "Model must have either 'get_activations' (ModelInterface) or "
                    "'run_with_cache' (HookedTransformer) method."
                )

        if not residuals:
            raise RuntimeError(f"No residuals extracted from {len(samples)} samples")

        return np.array(residuals)

    def _train_simple_probe(self, X: np.ndarray, y: np.ndarray):
        """Train a simple linear probe.

        Args:
            X: Feature matrix
            y: Labels

        Returns:
            Trained probe model
        """
        try:
            from sklearn.linear_model import LogisticRegression

            probe = LogisticRegression(max_iter=2000, C=0.1, random_state=42)
            probe.fit(X, y)
            return probe
        except ImportError:
            # Fallback to simple implementation
            return SimpleProbe(X, y)

    def _calculate_auc(self, X: np.ndarray, y: np.ndarray, probe) -> float:
        """Calculate AUC score.

        Args:
            X: Feature matrix
            y: True labels
            probe: Trained probe

        Returns:
            AUC score
        """
        try:
            from sklearn.metrics import roc_auc_score

            if hasattr(probe, "predict_proba"):
                y_pred = probe.predict_proba(X)[:, 1]
            else:
                y_pred = probe.predict(X)

            return float(roc_auc_score(y, y_pred))
        except ImportError:
            # Simple accuracy as fallback
            y_pred = probe.predict(X)
            return float(np.mean((y_pred > 0.5) == y))

    async def detect_backdoor(self, text: str, use_ensemble: bool = True) -> Dict[str, Any]:
        """Detect if text triggers backdoor behavior.

        Args:
            text: Text to analyze
            use_ensemble: Whether to use ensemble of probes

        Returns:
            Detection results with scores and assessment
        """
        scores = {}

        # If no probes trained, return default
        if not self.layer_probes:
            return {"scores": {"default": 0.5}, "is_backdoored": False, "confidence": 0.5}

        for layer_idx, probe in self.layer_probes.items():
            try:
                residual = await self._extract_residuals([text], layer_idx)
                residual = residual[0].reshape(1, -1)

                if hasattr(probe, "predict_proba"):
                    score = probe.predict_proba(residual)[0, 1]
                else:
                    score = probe.predict(residual)[0]

                scores[f"layer_{layer_idx}"] = float(score)
            except Exception as e:
                logger.debug("Failed to get score for layer %s: %s", layer_idx, e)
                scores[f"layer_{layer_idx}"] = 0.5

        # Calculate ensemble score
        if use_ensemble and self.ensemble_weights is not None and len(scores) > 1:
            ensemble_score = np.average(list(scores.values()), weights=self.ensemble_weights[: len(scores)])
            scores["ensemble"] = float(ensemble_score)
            final_score = ensemble_score
        else:
            final_score = max(scores.values()) if scores else 0.5

        return {"scores": scores, "is_backdoored": final_score > 0.5, "confidence": float(final_score)}


class SimpleProbe:
    """Simple probe implementation for testing without sklearn."""

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
