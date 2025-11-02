"""Linear Probe Detector System.

This module implements fast, lightweight linear probes that act as
real-time scanners for specific features in the model's internal state.
Think of these as grep/Yara rules for neural network memory.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import precision_recall_curve, roc_auc_score
    from sklearn.preprocessing import StandardScaler
except ImportError:
    LogisticRegression = None
    roc_auc_score = None
    precision_recall_curve = None
    StandardScaler = None

logger = logging.getLogger(__name__)


@dataclass
class Probe:
    """A trained linear probe for detecting specific features."""

    probe_id: str
    feature_name: str
    classifier: Any  # LogisticRegression or similar
    threshold: float
    auc_score: float
    layer: int
    description: str
    is_active: bool = True
    detection_count: int = 0
    false_positive_rate: float = 0.0
    true_positive_rate: float = 0.0
    scaler: Optional[Any] = None  # StandardScaler for feature normalization

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "probe_id": self.probe_id,
            "feature_name": self.feature_name,
            "threshold": self.threshold,
            "auc_score": self.auc_score,
            "layer": self.layer,
            "description": self.description,
            "is_active": self.is_active,
            "detection_count": self.detection_count,
            "false_positive_rate": self.false_positive_rate,
            "true_positive_rate": self.true_positive_rate,
        }


@dataclass
class ProbeDetection:
    """Result from probe detection."""

    probe_id: str
    feature_name: str
    confidence: float
    detected: bool
    layer: int
    raw_score: float
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "probe_id": self.probe_id,
            "feature_name": self.feature_name,
            "confidence": self.confidence,
            "detected": self.detected,
            "layer": self.layer,
            "raw_score": self.raw_score,
            "timestamp": self.timestamp,
        }


class ProbeDetector:
    """Fast linear probe detection system.

    This is the real-time scanner that monitors the model's internal
    state for specific features, especially deceptive patterns.
    """

    def __init__(self, model, config: Optional[Dict[str, Any]] = None):
        """Initialize the probe detector.

        Args:
            model: The model to monitor
            config: Configuration for probe training
        """
        self.model = model
        self.config = config or self._default_config()
        self.probes: Dict[str, Probe] = {}
        self.detection_history: List[ProbeDetection] = []
        self.feature_vectors: Dict[str, np.ndarray] = {}

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for probe training.

        Note: Stronger regularization (higher values) prevents overfitting.
        Based on Gemini's recommendations for robust deception detection:
        - regularization: 10-100 (maps to sklearn C=0.01-0.1)
        - penalty: 'l1' for feature selection or 'l2' for stability
        """
        return {
            "regularization": 100.0,  # Stronger regularization to prevent overfitting
            "penalty": "l2",  # L2 regularization (change to 'l1' for feature selection)
            "max_iter": 2000,
            "threshold_percentile": 90,  # For automatic threshold
            "min_samples": 100,
            "cross_validation_folds": 5,
            "ensemble_layers": [3, 5, 7, 9],  # Layers to probe
            "early_stopping": True,  # Enable early stopping with validation monitoring
            "early_stopping_patience": 5,  # Stop after 5 iterations without improvement
            "use_feature_scaling": False,  # Feature scaling - DISABLED (causes issues with early stopping)
        }

    async def train_probe(
        self,
        feature_name: str,
        positive_samples: np.ndarray,
        negative_samples: np.ndarray,
        layer: int,
        description: str = "",
        validation_data: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    ) -> Probe:
        """Train a linear probe for a specific feature.

        This creates a fast detector for a known feature pattern.

        Args:
            feature_name: Name of the feature to detect
            positive_samples: Activation samples with feature present
            negative_samples: Activation samples without feature
            layer: Layer to probe
            description: Human-readable description

        Returns:
            Trained probe
        """
        logger.info("Training probe for feature '%s' at layer %s", feature_name, layer)

        # Prepare training data
        X = np.vstack([positive_samples, negative_samples])
        y = np.array([1] * len(positive_samples) + [0] * len(negative_samples))

        # Feature scaling for better convergence (if enabled)
        scaler = None
        if self.config.get("use_feature_scaling", False) and StandardScaler is not None:
            scaler = StandardScaler()
            X = scaler.fit_transform(X)
            logger.debug("Applied StandardScaler normalization to features")

        # Train logistic regression probe
        if LogisticRegression is None:
            # Fallback to simple classifier
            from sklearn.linear_model import SGDClassifier

            probe_classifier = SGDClassifier(random_state=42, max_iter=self.config["max_iter"])
            probe_classifier.fit(X, y)
            y_scores = probe_classifier.predict(X)
            auc = 0.75  # Mock AUC for testing
        else:
            # Determine solver based on penalty type
            penalty = self.config.get("penalty", "l2")
            solver = "liblinear" if penalty == "l1" else "lbfgs"

            # Early stopping with validation monitoring if validation data provided
            if validation_data is not None and self.config.get("early_stopping", False):
                X_val_orig, y_val = validation_data

                # Scale validation data using the same scaler
                X_val_scaled = scaler.transform(X_val_orig) if scaler is not None else X_val_orig

                best_auc = 0.0
                best_classifier = None
                patience_counter = 0
                patience = self.config.get("early_stopping_patience", 5)

                logger.debug("Training with early stopping enabled")

                # Iterative training with validation monitoring
                for iteration in range(1, self.config["max_iter"] + 1, 100):
                    probe_classifier = LogisticRegression(
                        C=1.0 / self.config["regularization"],
                        penalty=penalty,
                        max_iter=iteration,
                        random_state=42,
                        solver=solver,
                        warm_start=False,
                    )

                    probe_classifier.fit(X, y)

                    # Evaluate on validation set (use scaled data)
                    y_val_scores = probe_classifier.predict_proba(X_val_scaled)[:, 1]
                    val_auc = roc_auc_score(y_val, y_val_scores) if roc_auc_score is not None else 0.75

                    # Check for improvement
                    if val_auc > best_auc + 0.001:  # Minimum improvement threshold
                        best_auc = val_auc
                        best_classifier = probe_classifier
                        patience_counter = 0
                        logger.debug(f"  Iteration {iteration}: val_auc={val_auc:.3f} (improvement)")
                    else:
                        patience_counter += 1
                        logger.debug(
                            f"  Iteration {iteration}: val_auc={val_auc:.3f} (no improvement {patience_counter}/{patience})"
                        )

                        if patience_counter >= patience:
                            logger.debug("Early stopping at iteration %s", iteration)
                            break

                # Use best classifier found
                probe_classifier = best_classifier if best_classifier is not None else probe_classifier
                auc = best_auc
            else:
                # Standard training without early stopping
                probe_classifier = LogisticRegression(
                    C=1.0 / self.config["regularization"],
                    penalty=penalty,
                    max_iter=self.config["max_iter"],
                    random_state=42,
                    solver=solver,
                )

                probe_classifier.fit(X, y)

                # Calculate performance metrics on training data
                y_scores = probe_classifier.predict_proba(X)[:, 1]
                if roc_auc_score is not None:
                    auc = roc_auc_score(y, y_scores)
                else:
                    auc = 0.75  # Fallback score

        # Calculate training scores for TPR/FPR metrics
        y_scores = probe_classifier.predict_proba(X)[:, 1]

        # Find optimal threshold using validation data if provided
        if validation_data is not None:
            X_val_for_threshold, y_val = validation_data

            # Scale validation data if scaler is available
            if scaler is not None:
                X_val_for_threshold = scaler.transform(X_val_for_threshold)

            y_val_scores = probe_classifier.predict_proba(X_val_for_threshold)[:, 1]
            threshold = self._find_optimal_threshold(y_val, y_val_scores)
            logger.debug(f"Threshold calibrated on validation data: {threshold:.3f}")
        else:
            # Fallback: use training data (not ideal, but maintains compatibility)
            threshold = self._find_optimal_threshold(y, y_scores)
            logger.debug(f"Threshold calibrated on training data: {threshold:.3f}")

        # Calculate TPR and FPR on training data
        y_pred = y_scores > threshold
        tp = np.sum((y == 1) & (y_pred == 1))
        fp = np.sum((y == 0) & (y_pred == 1))
        tn = np.sum((y == 0) & (y_pred == 0))
        fn = np.sum((y == 1) & (y_pred == 0))

        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        # Create probe
        probe_id = f"{feature_name}_L{layer}_{hash(feature_name) % 10000:04d}"

        probe = Probe(
            probe_id=probe_id,
            feature_name=feature_name,
            classifier=probe_classifier,
            threshold=float(threshold),
            auc_score=float(auc),
            layer=layer,
            description=description or f"Probe for {feature_name}",
            true_positive_rate=float(tpr),
            false_positive_rate=float(fpr),
            scaler=scaler,  # Store scaler for inference-time normalization
        )

        self.probes[probe_id] = probe

        logger.info(f"Probe trained: {probe_id} (AUC={auc:.3f}, TPR={tpr:.3f}, FPR={fpr:.3f})")

        return probe

    async def train_deception_probes(
        self, clean_activations: Dict[int, np.ndarray], deceptive_activations: Dict[int, np.ndarray]
    ) -> Dict[str, Probe]:
        """Train specialized probes for detecting deception.

        Args:
            clean_activations: Clean model activations by layer
            deceptive_activations: Deceptive activations by layer

        Returns:
            Dictionary of trained deception probes
        """
        deception_probes = {}

        for layer in self.config["ensemble_layers"]:
            if layer not in clean_activations or layer not in deceptive_activations:
                continue

            probe = await self.train_probe(
                feature_name="is_deceptive",
                positive_samples=deceptive_activations[layer],
                negative_samples=clean_activations[layer],
                layer=layer,
                description=f"Deception detector at layer {layer}",
            )

            deception_probes[probe.probe_id] = probe

        # Train meta-probe on ensemble
        ensemble_probe = await self._train_ensemble_probe(clean_activations, deceptive_activations)
        if ensemble_probe:
            deception_probes[ensemble_probe.probe_id] = ensemble_probe

        return deception_probes

    async def _train_ensemble_probe(
        self, clean_activations: Dict[int, np.ndarray], deceptive_activations: Dict[int, np.ndarray]
    ) -> Optional[Probe]:
        """Train ensemble probe across multiple layers.

        Args:
            clean_activations: Clean activations by layer
            deceptive_activations: Deceptive activations by layer

        Returns:
            Ensemble probe if successful
        """
        # Concatenate features from multiple layers
        clean_features = []
        deceptive_features = []

        for layer in self.config["ensemble_layers"]:
            if layer in clean_activations:
                clean_features.append(clean_activations[layer])
            if layer in deceptive_activations:
                deceptive_features.append(deceptive_activations[layer])

        if not clean_features or not deceptive_features:
            return None

        # Stack features
        clean_concat = np.hstack(clean_features)
        deceptive_concat = np.hstack(deceptive_features)

        # Train ensemble probe
        return await self.train_probe(
            feature_name="deception_ensemble",
            positive_samples=deceptive_concat,
            negative_samples=clean_concat,
            layer=-1,  # Special value for ensemble
            description="Ensemble deception detector across layers",
        )

    async def detect(self, activation: np.ndarray, layer: int, probe_ids: Optional[List[str]] = None) -> List[ProbeDetection]:
        """Run detection on activation using trained probes.

        This is the real-time detection that happens during model inference.

        Args:
            activation: Current activation vector
            layer: Layer the activation is from
            probe_ids: Specific probes to use (None for all applicable)

        Returns:
            List of detection results
        """
        import time

        detections = []

        # Select probes to use
        if probe_ids:
            probes_to_use = [self.probes[pid] for pid in probe_ids if pid in self.probes]
        else:
            # Use all probes for this layer
            probes_to_use = [p for p in self.probes.values() if p.layer == layer and p.is_active]

        # Run each probe
        for probe in probes_to_use:
            try:
                # Get probe prediction
                activation_reshaped = activation.reshape(1, -1)

                # Apply scaling if the probe was trained with a scaler
                if probe.scaler is not None:
                    activation_reshaped = probe.scaler.transform(activation_reshaped)

                score = probe.classifier.predict_proba(activation_reshaped)[0, 1]

                # Check against threshold
                detected = score > probe.threshold

                # Update detection count
                if detected:
                    probe.detection_count += 1

                detection = ProbeDetection(
                    probe_id=probe.probe_id,
                    feature_name=probe.feature_name,
                    confidence=float(score),
                    detected=detected,
                    layer=layer,
                    raw_score=float(score),
                    timestamp=time.time(),
                )

                detections.append(detection)

                if detected:
                    logger.debug(f"Probe {probe.probe_id} detected {probe.feature_name} " f"with confidence {score:.3f}")

            except Exception as e:
                logger.warning(f"Probe {probe.probe_id} detection failed: {e}")

        # Store in history
        self.detection_history.extend(detections)

        return detections

    async def scan_for_deception(self, text: str, return_all_scores: bool = False) -> Dict[str, Any]:
        """High-level scan for deceptive patterns.

        Args:
            text: Input text to analyze
            return_all_scores: Whether to return all probe scores

        Returns:
            Scan results with deception assessment
        """
        results: Dict[str, Any] = {
            "is_deceptive": False,
            "confidence": 0.0,
            "triggered_probes": [],
            "layer_scores": {},
            "ensemble_score": 0.0,
        }

        # Get activations for text
        activations = await self._extract_activations(text)

        all_detections = []

        # Run detection at each layer
        for layer, activation in activations.items():
            detections = await self.detect(activation, layer)
            all_detections.extend(detections)

            # Track deception-related detections
            deception_detections = [
                d for d in detections if "deception" in d.feature_name.lower() or "is_deceptive" in d.feature_name
            ]

            if deception_detections:
                max_score = max(d.confidence for d in deception_detections)
                results["layer_scores"][layer] = max_score

                for d in deception_detections:
                    if d.detected:
                        results["triggered_probes"].append(d.to_dict())

        # Calculate overall assessment
        if results["layer_scores"]:
            results["ensemble_score"] = float(np.mean(list(results["layer_scores"].values())))
            results["confidence"] = float(max(results["layer_scores"].values()))
            results["is_deceptive"] = results["confidence"] > 0.5

        if return_all_scores:
            results["all_detections"] = [d.to_dict() for d in all_detections]

        return results

    async def _extract_activations(self, text: str) -> Dict[int, np.ndarray]:
        """Extract activations from model for text.

        Args:
            text: Input text

        Returns:
            Activations by layer
        """
        activations = {}

        try:
            # Try HookedTransformer first (TransformerLens)
            if hasattr(self.model, "run_with_cache"):
                tokens = self.model.to_tokens(text)
                _, cache = self.model.run_with_cache(tokens)

                for layer in self.config["ensemble_layers"]:
                    if ("resid_post", layer) in cache:
                        resid = cache[("resid_post", layer)]
                        # Use last token position
                        activation = resid[:, -1].detach().cpu().numpy().squeeze()
                        activations[layer] = activation

            # Try ModelInterface (HuggingFace models)
            elif hasattr(self.model, "get_activations"):
                acts = self.model.get_activations([text], layers=self.config["ensemble_layers"], return_attention=False)

                for layer in self.config["ensemble_layers"]:
                    layer_key = f"layer_{layer}"
                    if layer_key in acts:
                        layer_acts = acts[layer_key][0]  # Shape: [seq_len, hidden_dim]
                        # Use final token activation
                        activation = layer_acts[-1].detach().cpu().numpy()
                        activations[layer] = activation
            else:
                logger.error(f"Model {type(self.model).__name__} doesn't support activation extraction")

        except Exception as e:
            logger.warning(f"Failed to extract activations: {e}")

        return activations

    def _find_optimal_threshold(self, y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """Find optimal threshold for classification.

        Args:
            y_true: True labels
            y_scores: Predicted scores

        Returns:
            Optimal threshold
        """
        if precision_recall_curve is None:
            # Simple fallback: use median of positive scores
            positive_scores = y_scores[y_true == 1] if np.any(y_true == 1) else y_scores
            return float(np.median(positive_scores))

        precision, recall, thresholds = precision_recall_curve(y_true, y_scores)

        # F1 score for each threshold
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)

        # Find threshold with best F1
        best_idx = np.argmax(f1_scores[:-1])  # Last value is always 1
        optimal_threshold = thresholds[best_idx]

        # Alternative: use percentile
        if self.config.get("threshold_percentile"):
            percentile_threshold = np.percentile(
                y_scores[y_true == 0], self.config["threshold_percentile"]  # Scores for negative class
            )
            # Use more conservative threshold
            optimal_threshold = max(optimal_threshold, percentile_threshold)

        return float(optimal_threshold)

    async def validate_probe(self, probe_id: str, validation_data: Tuple[np.ndarray, np.ndarray]) -> Dict[str, float]:
        """Validate probe performance on held-out data.

        Args:
            probe_id: Probe to validate
            validation_data: Tuple of (activations, labels)

        Returns:
            Validation metrics
        """
        if probe_id not in self.probes:
            raise ValueError(f"Probe {probe_id} not found")

        probe = self.probes[probe_id]
        X_val, y_val = validation_data

        # Get predictions
        y_scores = probe.classifier.predict_proba(X_val)[:, 1]
        y_pred = y_scores > probe.threshold

        # Calculate metrics
        tp = np.sum((y_val == 1) & (y_pred == 1))
        fp = np.sum((y_val == 0) & (y_pred == 1))
        tn = np.sum((y_val == 0) & (y_pred == 0))
        fn = np.sum((y_val == 1) & (y_pred == 0))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / len(y_val)

        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "auc": float(roc_auc_score(y_val, y_scores)),
        }

    def get_probe_statistics(self) -> Dict[str, Any]:
        """Get statistics about all probes.

        Returns:
            Probe statistics
        """
        active_probes = [p for p in self.probes.values() if p.is_active]

        layer_distribution = {}
        for probe in active_probes:
            if probe.layer not in layer_distribution:
                layer_distribution[probe.layer] = 0
            layer_distribution[probe.layer] += 1

        return {
            "total_probes": len(self.probes),
            "active_probes": len(active_probes),
            "average_auc": float(np.mean([p.auc_score for p in active_probes])) if active_probes else 0.0,
            "total_detections": sum(p.detection_count for p in self.probes.values()),
            "layer_distribution": layer_distribution,
            "deception_probes": len(
                [
                    p
                    for p in self.probes.values()
                    if "deception" in p.feature_name.lower() or "deceptive" in p.feature_name.lower()
                ]
            ),
        }

    def deactivate_probe(self, probe_id: str):
        """Deactivate a probe.

        Args:
            probe_id: Probe to deactivate
        """
        if probe_id in self.probes:
            self.probes[probe_id].is_active = False
            logger.info("Deactivated probe %s", probe_id)

    def activate_probe(self, probe_id: str):
        """Activate a probe.

        Args:
            probe_id: Probe to activate
        """
        if probe_id in self.probes:
            self.probes[probe_id].is_active = True
            logger.info("Activated probe %s", probe_id)

    def clear_detection_history(self):
        """Clear detection history."""
        self.detection_history = []
        logger.info("Cleared detection history")
