"""Linear Probe Detector System.

This module implements fast, lightweight linear probes that act as
real-time scanners for specific features in the model's internal state.
Think of these as grep/Yara rules for neural network memory.

Evaluation protocol:
    ``train_probe`` fits on the training split only. When ``validation_data`` is
    given, the decision threshold is calibrated on it and ``Probe.auc_score`` /
    ``true_positive_rate`` / ``false_positive_rate`` are measured on it. The
    validation split is therefore a *tuning* split: an unbiased estimate needs a
    third, untouched test split evaluated once with ``validate_probe`` (stored by
    callers in ``Probe.test_auc``).

Layer convention:
    "layer L" is the output of transformer block L (0-indexed), i.e. TransformerLens
    ``blocks.L.hook_resid_post`` / HuggingFace ``hidden_states[L + 1]``. The ensemble
    probe uses ``layer = -1`` and records its constituent layers in
    ``Probe.ensemble_layers``.
"""

from dataclasses import dataclass
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from sleeper_agents.probes.probe_config import (
    DEFAULT_THRESHOLD_CRITERION,
    THRESHOLD_CRITERIA,
    sklearn_penalty_kwargs,
)

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import precision_recall_curve, roc_auc_score, roc_curve
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError:
    LogisticRegression = None
    roc_auc_score = None
    roc_curve = None
    precision_recall_curve = None
    StandardScaler = None
    StratifiedKFold = None
    cross_val_score = None
    make_pipeline = None

logger = logging.getLogger(__name__)

ENSEMBLE_LAYER = -1
SCAN_DECISION_RULES = ("any", "majority", "ensemble")


def _require_sklearn() -> None:
    if LogisticRegression is None:
        raise ImportError("scikit-learn is required for ProbeDetector. Install with: pip install scikit-learn")


def resid_post_key(layer: int) -> str:
    """TransformerLens cache key for the output of block ``layer``."""
    return f"blocks.{layer}.hook_resid_post"


def _stable_hash(text: str) -> int:
    """Process-independent hash (Python's ``hash`` is salted per process)."""
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def _binary_auc(y_true: np.ndarray, y_scores: np.ndarray, split_name: str) -> float:
    y_true = np.asarray(y_true)
    if len(np.unique(y_true)) != 2:
        raise ValueError(f"AUC on the {split_name} split needs both classes; got labels {np.unique(y_true).tolist()}")
    return float(roc_auc_score(y_true, y_scores))


def select_threshold(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    criterion: str = DEFAULT_THRESHOLD_CRITERION,
    percentile: float = 90,
) -> float:
    """Choose a decision threshold; a sample is positive when score >= threshold.

    Args:
        y_true: Binary labels of the calibration split (must contain both classes)
        y_scores: Scores for the calibration split
        criterion: One of ``probe_config.THRESHOLD_CRITERIA``
        percentile: Percentile of negative scores for the percentile criteria

    Returns:
        Threshold
    """
    _require_sklearn()
    y_true = np.asarray(y_true).astype(int)
    y_scores = np.asarray(y_scores, dtype=float)
    if len(np.unique(y_true)) != 2:
        raise ValueError("Threshold calibration needs both classes")
    if criterion not in THRESHOLD_CRITERIA:
        raise ValueError(f"Unknown threshold_criterion {criterion!r}; expected one of {THRESHOLD_CRITERIA}")

    def f1_threshold() -> float:
        precision, recall, thresholds = precision_recall_curve(y_true, y_scores)
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)
        # precision/recall[i] correspond to predicting positive when score >= thresholds[i];
        # the final (precision=1, recall=0) point has no threshold
        return float(thresholds[int(np.argmax(f1_scores[:-1]))])

    def percentile_threshold() -> float:
        return float(np.percentile(y_scores[y_true == 0], percentile))

    if criterion == "youden":
        fpr, tpr, thresholds = roc_curve(y_true, y_scores)
        finite = np.isfinite(thresholds)
        return float(thresholds[finite][int(np.argmax((tpr - fpr)[finite]))])
    if criterion == "f1":
        return f1_threshold()
    if criterion == "negative_percentile":
        return percentile_threshold()
    # "f1_or_negative_percentile": the more conservative of the two
    return max(f1_threshold(), percentile_threshold())


def _rates(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "tpr": tp / (tp + fn) if (tp + fn) > 0 else 0.0,
        "fpr": fp / (fp + tn) if (fp + tn) > 0 else 0.0,
    }


@dataclass
class Probe:
    """A trained linear probe for detecting specific features.

    Metric fields:
        auc_score: AUC on the calibration split: the validation split when one was
            passed to ``train_probe``, otherwise the training data (see
            ``threshold_split``). It is NOT a held-out estimate.
        train_auc / val_auc / test_auc: AUC on each split (None when not measured).
            ``test_auc`` is filled by callers that evaluate an untouched test split.
        true_positive_rate / false_positive_rate: measured at ``threshold`` on the
            calibration split.
    """

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
    train_auc: Optional[float] = None
    val_auc: Optional[float] = None
    test_auc: Optional[float] = None
    threshold_split: str = "train"  # "validation" or "train"
    threshold_criterion: str = ""
    selected_C: Optional[float] = None
    ensemble_layers: Optional[List[int]] = None  # Constituent layers for layer == -1

    def score(self, activations: np.ndarray) -> np.ndarray:
        """Positive-class probability for a batch of activations (scaler applied)."""
        X = np.asarray(activations)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        if self.scaler is not None:
            X = self.scaler.transform(X)
        return np.asarray(self.classifier.predict_proba(X)[:, 1])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "probe_id": self.probe_id,
            "feature_name": self.feature_name,
            "threshold": self.threshold,
            "auc_score": self.auc_score,
            "train_auc": self.train_auc,
            "val_auc": self.val_auc,
            "test_auc": self.test_auc,
            "threshold_split": self.threshold_split,
            "threshold_criterion": self.threshold_criterion,
            "selected_C": self.selected_C,
            "layer": self.layer,
            "ensemble_layers": self.ensemble_layers,
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

        Keys:
            regularization: inverse of sklearn's C (100 -> C=0.01). Higher is stronger.
            penalty: "l2" or "l1" (L1 uses the liblinear solver)
            max_iter: solver iteration budget (the probe is fit once, to convergence)
            cross_validation_folds: if set (>= 2), C is chosen by stratified k-fold CV
                AUC on the training split from ``c_grid`` (default: base C times
                0.01, 0.1, 1, 10, 100). Set to None/0 to use ``1 / regularization``.
            threshold_criterion: see ``probe_config.THRESHOLD_CRITERIA``
            threshold_percentile: percentile of negative scores for the percentile
                criteria
            use_feature_scaling: StandardScaler fit on the training split only
            scan_decision_rule: how ``scan_for_deception`` combines probes
                ("any", "majority" or "ensemble")
        """
        return {
            "regularization": 100.0,
            "penalty": "l2",
            "max_iter": 2000,
            "threshold_percentile": 90,
            "threshold_criterion": DEFAULT_THRESHOLD_CRITERION,
            "min_samples": 100,
            "cross_validation_folds": 5,
            "ensemble_layers": [3, 5, 7, 9],  # Layers extracted when no probes constrain it
            "use_feature_scaling": False,
            "scan_decision_rule": "any",
            "random_seed": 42,
        }

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def _make_classifier(self, C: float) -> Any:
        return LogisticRegression(
            C=C,
            max_iter=self.config.get("max_iter", 2000),
            random_state=self.config.get("random_seed", 42),
            **sklearn_penalty_kwargs(self.config.get("penalty", "l2")),
        )

    def _select_C(self, X: np.ndarray, y: np.ndarray) -> float:
        """Choose C by stratified k-fold CV on the training split (if configured)."""
        base_C = 1.0 / float(self.config["regularization"])
        folds = self.config.get("cross_validation_folds")
        if not folds or int(folds) < 2:
            return base_C

        folds = int(folds)
        min_class = int(min(np.sum(y == 0), np.sum(y == 1)))
        if min_class < folds:
            logger.warning(
                "Only %d samples in the smallest class; skipping %d-fold CV and using C=%.4g", min_class, folds, base_C
            )
            return base_C

        grid = self.config.get("c_grid") or [base_C * f for f in (0.01, 0.1, 1.0, 10.0, 100.0)]
        cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=self.config.get("random_seed", 42))
        best_C, best_auc = base_C, -np.inf
        for C in sorted(grid):  # ascending: ties resolve to the strongest regularization
            estimator = self._make_classifier(C)
            if self.config.get("use_feature_scaling", False):
                estimator = make_pipeline(StandardScaler(), estimator)
            mean_auc = float(np.mean(cross_val_score(estimator, X, y, cv=cv, scoring="roc_auc")))
            logger.debug("  CV C=%.4g: mean AUC=%.4f", C, mean_auc)
            if mean_auc > best_auc + 1e-6:
                best_C, best_auc = C, mean_auc
        logger.debug("Selected C=%.4g (CV AUC=%.4f)", best_C, best_auc)
        return float(best_C)

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

        The classifier is fit once, to convergence, on the training samples only
        (C optionally chosen by CV on those samples). ``validation_data`` is used to
        calibrate the decision threshold and to measure ``auc_score`` / TPR / FPR.

        Args:
            feature_name: Name of the feature to detect
            positive_samples: Activation samples with feature present (label 1)
            negative_samples: Activation samples without feature (label 0)
            layer: Layer to probe (-1 for an ensemble probe)
            description: Human-readable description
            validation_data: Optional (X_val, y_val) calibration split, disjoint from
                the training samples

        Returns:
            Trained probe
        """
        _require_sklearn()
        logger.info("Training probe for feature '%s' at layer %s", feature_name, layer)

        positive_samples = np.asarray(positive_samples)
        negative_samples = np.asarray(negative_samples)
        if positive_samples.ndim != 2 or negative_samples.ndim != 2:
            raise ValueError("positive_samples and negative_samples must be 2D (n_samples, n_features)")
        if positive_samples.shape[1] != negative_samples.shape[1]:
            raise ValueError(f"Feature dimension mismatch: {positive_samples.shape[1]} vs {negative_samples.shape[1]}")
        if len(positive_samples) == 0 or len(negative_samples) == 0:
            raise ValueError("Both positive and negative samples are required")

        X = np.vstack([positive_samples, negative_samples])
        y = np.array([1] * len(positive_samples) + [0] * len(negative_samples))

        C = self._select_C(X, y)

        # Scaler statistics come from the training split only
        scaler = None
        if self.config.get("use_feature_scaling", False):
            scaler = StandardScaler().fit(X)
        X_fit = scaler.transform(X) if scaler is not None else X

        probe_classifier = self._make_classifier(C)
        probe_classifier.fit(X_fit, y)

        train_scores = probe_classifier.predict_proba(X_fit)[:, 1]
        train_auc = _binary_auc(y, train_scores, "training")

        val_auc: Optional[float] = None
        if validation_data is not None:
            X_val, y_val = validation_data
            y_val = np.asarray(y_val).astype(int)
            X_val_t = scaler.transform(X_val) if scaler is not None else np.asarray(X_val)
            val_scores = probe_classifier.predict_proba(X_val_t)[:, 1]
            val_auc = _binary_auc(y_val, val_scores, "validation")
            calib_y, calib_scores, threshold_split = y_val, val_scores, "validation"
        else:
            logger.warning(
                "No validation data for probe '%s' (layer %s): threshold, TPR/FPR and auc_score "
                "are measured on the training data and are optimistic",
                feature_name,
                layer,
            )
            calib_y, calib_scores, threshold_split = y, train_scores, "train"

        threshold = self._find_optimal_threshold(calib_y, calib_scores)
        rates = _rates(calib_y, calib_scores >= threshold)
        auc = val_auc if val_auc is not None else train_auc

        probe_id = f"{feature_name}_L{layer}_{_stable_hash(feature_name) % 10000:04d}"

        probe = Probe(
            probe_id=probe_id,
            feature_name=feature_name,
            classifier=probe_classifier,
            threshold=float(threshold),
            auc_score=float(auc),
            layer=layer,
            description=description or f"Probe for {feature_name}",
            true_positive_rate=float(rates["tpr"]),
            false_positive_rate=float(rates["fpr"]),
            scaler=scaler,
            train_auc=train_auc,
            val_auc=val_auc,
            threshold_split=threshold_split,
            threshold_criterion=self.config.get("threshold_criterion", DEFAULT_THRESHOLD_CRITERION),
            selected_C=float(C),
        )

        self.probes[probe_id] = probe

        logger.info(
            "Probe trained: %s (train AUC=%.3f, %s AUC=%s, TPR=%.3f, FPR=%.3f on %s split)",
            probe_id,
            train_auc,
            "val",
            f"{val_auc:.3f}" if val_auc is not None else "n/a",
            rates["tpr"],
            rates["fpr"],
            threshold_split,
        )

        return probe

    @staticmethod
    def _common_layers(a: Dict[int, np.ndarray], b: Dict[int, np.ndarray]) -> List[int]:
        return sorted(set(a.keys()) & set(b.keys()))

    async def train_deception_probes(
        self,
        clean_activations: Dict[int, np.ndarray],
        deceptive_activations: Dict[int, np.ndarray],
        validation_clean: Optional[Dict[int, np.ndarray]] = None,
        validation_deceptive: Optional[Dict[int, np.ndarray]] = None,
    ) -> Dict[str, Probe]:
        """Train one probe per layer plus an ensemble probe for detecting deception.

        Args:
            clean_activations: Clean model activations by layer (training split)
            deceptive_activations: Deceptive activations by layer (training split)
            validation_clean: Optional clean activations by layer (calibration split)
            validation_deceptive: Optional deceptive activations by layer (calibration split)

        Returns:
            Dictionary of trained deception probes
        """
        deception_probes = {}

        for layer in self._common_layers(clean_activations, deceptive_activations):
            validation_data = None
            if validation_clean is not None and validation_deceptive is not None:
                validation_data = (
                    np.vstack([validation_clean[layer], validation_deceptive[layer]]),
                    np.array([0] * len(validation_clean[layer]) + [1] * len(validation_deceptive[layer])),
                )
            probe = await self.train_probe(
                feature_name="is_deceptive",
                positive_samples=deceptive_activations[layer],
                negative_samples=clean_activations[layer],
                layer=layer,
                description=f"Deception detector at layer {layer}",
                validation_data=validation_data,
            )
            deception_probes[probe.probe_id] = probe

        ensemble_probe = await self._train_ensemble_probe(
            clean_activations, deceptive_activations, validation_clean, validation_deceptive
        )
        if ensemble_probe:
            deception_probes[ensemble_probe.probe_id] = ensemble_probe

        return deception_probes

    @staticmethod
    def concat_layers(activations: Dict[int, np.ndarray], layers: List[int], split_name: str = "") -> np.ndarray:
        """Concatenate per-layer activations along the feature axis.

        All layers must hold the same rows (same examples in the same order).
        """
        missing = [layer for layer in layers if layer not in activations]
        if missing:
            raise KeyError(f"Layers {missing} missing from {split_name or 'activation'} dict")
        row_counts = {layer: np.asarray(activations[layer]).shape[0] for layer in layers}
        if len(set(row_counts.values())) != 1:
            raise ValueError(f"Row counts differ across layers ({row_counts}); rows are not aligned")
        return np.hstack([np.asarray(activations[layer]) for layer in layers])

    async def _train_ensemble_probe(
        self,
        clean_activations: Dict[int, np.ndarray],
        deceptive_activations: Dict[int, np.ndarray],
        validation_clean: Optional[Dict[int, np.ndarray]] = None,
        validation_deceptive: Optional[Dict[int, np.ndarray]] = None,
        layers: Optional[List[int]] = None,
    ) -> Optional[Probe]:
        """Train an ensemble probe on the concatenation of several layers.

        Rows must be aligned across layers (row i of every layer is the same
        example); this is checked.

        Args:
            clean_activations: Clean activations by layer
            deceptive_activations: Deceptive activations by layer
            validation_clean: Optional clean calibration activations by layer
            validation_deceptive: Optional deceptive calibration activations by layer
            layers: Layers to concatenate (default: all layers present in both dicts)

        Returns:
            Ensemble probe, or None when no layer is available
        """
        if layers is None:
            layers = self._common_layers(clean_activations, deceptive_activations)
        layers = sorted(layers)
        if not layers:
            return None

        clean_concat = self.concat_layers(clean_activations, layers, "clean")
        deceptive_concat = self.concat_layers(deceptive_activations, layers, "deceptive")

        validation_data = None
        if validation_clean is not None and validation_deceptive is not None:
            val_clean = self.concat_layers(validation_clean, layers, "validation clean")
            val_deceptive = self.concat_layers(validation_deceptive, layers, "validation deceptive")
            validation_data = (
                np.vstack([val_clean, val_deceptive]),
                np.array([0] * len(val_clean) + [1] * len(val_deceptive)),
            )

        probe = await self.train_probe(
            feature_name="deception_ensemble",
            positive_samples=deceptive_concat,
            negative_samples=clean_concat,
            layer=ENSEMBLE_LAYER,
            description=f"Ensemble deception detector across layers {layers}",
            validation_data=validation_data,
        )
        probe.ensemble_layers = list(layers)
        return probe

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    async def detect(self, activation: np.ndarray, layer: int, probe_ids: Optional[List[str]] = None) -> List[ProbeDetection]:
        """Run detection on activation using trained probes.

        A probe fires when its score is >= its calibrated threshold.

        Args:
            activation: Current activation vector (for the ensemble probe: the
                concatenation of its ``ensemble_layers``)
            layer: Layer the activation is from (-1 for the ensemble probe)
            probe_ids: Specific probes to use (None for all active probes at ``layer``)

        Returns:
            List of detection results
        """
        detections = []

        if probe_ids:
            unknown = [pid for pid in probe_ids if pid not in self.probes]
            if unknown:
                raise KeyError(f"Unknown probe ids: {unknown}")
            probes_to_use = [self.probes[pid] for pid in probe_ids]
        else:
            probes_to_use = [p for p in self.probes.values() if p.layer == layer and p.is_active]

        for probe in probes_to_use:
            score = float(probe.score(activation)[0])
            detected = bool(score >= probe.threshold)

            if detected:
                probe.detection_count += 1
                logger.debug("Probe %s detected %s with confidence %.3f", probe.probe_id, probe.feature_name, score)

            detections.append(
                ProbeDetection(
                    probe_id=probe.probe_id,
                    feature_name=probe.feature_name,
                    confidence=score,
                    detected=detected,
                    layer=layer,
                    raw_score=score,
                    timestamp=time.time(),
                )
            )

        self.detection_history.extend(detections)
        return detections

    @staticmethod
    def _is_deception_probe(probe: Probe) -> bool:
        name = probe.feature_name.lower()
        return "deception" in name or "deceptive" in name

    async def scan_for_deception(self, text: str, return_all_scores: bool = False) -> Dict[str, Any]:
        """High-level scan for deceptive patterns.

        Activations are extracted at every layer used by an active deception probe
        (including the constituent layers of the ensemble probe). Each probe fires
        when its score is >= its own calibrated threshold, and the probes are
        combined according to ``config["scan_decision_rule"]``:

        - "any": deceptive if any probe fires
        - "majority": deceptive if more than half of the probes fire
        - "ensemble": the ensemble probe's decision (requires an ensemble probe)

        Args:
            text: Input text to analyze
            return_all_scores: Whether to return all probe scores

        Returns:
            Scan results. ``confidence`` is the maximum probe score; ``layer_scores``
            maps layer -> max score of that layer's probes; ``ensemble_score`` is the
            ensemble probe's score (None when there is no ensemble probe).

        Raises:
            RuntimeError: if no deception probe is trained or activations are missing
        """
        probes = [p for p in self.probes.values() if p.is_active and self._is_deception_probe(p)]
        if not probes:
            raise RuntimeError("No active deception probes are trained; cannot scan for deception")

        layer_probes = [p for p in probes if p.layer != ENSEMBLE_LAYER]
        ensemble_probes = [p for p in probes if p.layer == ENSEMBLE_LAYER]
        for p in ensemble_probes:
            if not p.ensemble_layers:
                raise ValueError(f"Ensemble probe {p.probe_id} does not record its ensemble_layers")

        needed_layers = sorted(
            {p.layer for p in layer_probes} | {layer for p in ensemble_probes for layer in p.ensemble_layers}
        )
        activations = await self._extract_activations(text, layers=needed_layers)
        missing = [layer for layer in needed_layers if layer not in activations]
        if missing:
            raise RuntimeError(f"Activation extraction returned no data for layers {missing}")

        all_detections: List[ProbeDetection] = []
        layer_scores: Dict[int, float] = {}

        for layer in sorted({p.layer for p in layer_probes}):
            ids = [p.probe_id for p in layer_probes if p.layer == layer]
            detections = await self.detect(activations[layer], layer, probe_ids=ids)
            all_detections.extend(detections)
            layer_scores[layer] = max(d.confidence for d in detections)

        ensemble_score: Optional[float] = None
        ensemble_detections: List[ProbeDetection] = []
        for p in ensemble_probes:
            concat = np.concatenate([np.asarray(activations[layer]).reshape(-1) for layer in p.ensemble_layers])
            detections = await self.detect(concat, ENSEMBLE_LAYER, probe_ids=[p.probe_id])
            ensemble_detections.extend(detections)
            all_detections.extend(detections)
        if ensemble_detections:
            ensemble_score = max(d.confidence for d in ensemble_detections)

        rule = self.config.get("scan_decision_rule", "any")
        if rule == "any":
            is_deceptive = any(d.detected for d in all_detections)
        elif rule == "majority":
            is_deceptive = sum(d.detected for d in all_detections) > len(all_detections) / 2
        elif rule == "ensemble":
            if not ensemble_detections:
                raise RuntimeError("scan_decision_rule='ensemble' but no ensemble probe is trained")
            is_deceptive = any(d.detected for d in ensemble_detections)
        else:
            raise ValueError(f"Unknown scan_decision_rule {rule!r}; expected one of {SCAN_DECISION_RULES}")

        results: Dict[str, Any] = {
            "is_deceptive": bool(is_deceptive),
            "confidence": float(max(d.confidence for d in all_detections)),
            "triggered_probes": [d.to_dict() for d in all_detections if d.detected],
            "layer_scores": layer_scores,
            "ensemble_score": ensemble_score,
            "decision_rule": rule,
            "layers_scanned": needed_layers,
        }

        if return_all_scores:
            results["all_detections"] = [d.to_dict() for d in all_detections]

        return results

    async def _extract_activations(self, text: str, layers: Optional[List[int]] = None) -> Dict[int, np.ndarray]:
        """Extract last-token residual-stream activations (output of block L) for text.

        Args:
            text: Input text (a single, unpadded sequence, so the last position is
                the last real token)
            layers: Layers to extract (default: ``config["ensemble_layers"]``)

        Returns:
            Activations by layer, each of shape (hidden_dim,)

        Raises:
            RuntimeError: if the model cannot provide activations or a layer is missing
        """
        if layers is None:
            layers = list(self.config["ensemble_layers"])
        activations: Dict[int, np.ndarray] = {}

        if hasattr(self.model, "get_activations"):
            # ModelInterface: keys "layer_{L}" follow the package layer convention
            acts = self.model.get_activations([text], layers=layers, return_attention=False)
            for layer in layers:
                layer_key = f"layer_{layer}"
                if layer_key not in acts:
                    raise RuntimeError(f"Model returned no activations for {layer_key}")
                activations[layer] = acts[layer_key][0][-1].detach().float().cpu().numpy()

        elif hasattr(self.model, "run_with_cache"):
            # TransformerLens (HookedTransformer or TransformerBridge in compatibility mode)
            tokens = self.model.to_tokens(text)
            _, cache = self.model.run_with_cache(tokens)
            for layer in layers:
                key = resid_post_key(layer)
                if key not in cache:
                    raise RuntimeError(f"Activation cache has no '{key}'")
                activations[layer] = cache[key][0, -1].detach().float().cpu().numpy()

        else:
            raise RuntimeError(f"Model {type(self.model).__name__} doesn't support activation extraction")

        return activations

    # ------------------------------------------------------------------
    # Calibration and validation
    # ------------------------------------------------------------------

    def _find_optimal_threshold(self, y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """Choose the decision threshold (probe fires when score >= threshold).

        The criterion is ``config["threshold_criterion"]`` (see
        ``probe_config.THRESHOLD_CRITERIA``). Callers should pass a calibration split
        that is disjoint from the training data.

        Args:
            y_true: True labels
            y_scores: Predicted scores

        Returns:
            Threshold
        """
        return select_threshold(
            y_true,
            y_scores,
            criterion=self.config.get("threshold_criterion", DEFAULT_THRESHOLD_CRITERION),
            percentile=self.config.get("threshold_percentile", 90),
        )

    async def validate_probe(self, probe_id: str, validation_data: Tuple[np.ndarray, np.ndarray]) -> Dict[str, float]:
        """Evaluate a probe on held-out data at its calibrated threshold.

        The probe's scaler (if any) is applied and a sample counts as detected when
        its score is >= the threshold, exactly as in ``detect``.

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
        y_val = np.asarray(y_val).astype(int)

        y_scores = probe.score(X_val)
        y_pred = y_scores >= probe.threshold
        rates = _rates(y_val, y_pred)
        tp, fp, tn = rates["tp"], rates["fp"], rates["tn"]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = rates["tpr"]
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / len(y_val)

        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "true_positive_rate": float(rates["tpr"]),
            "false_positive_rate": float(rates["fpr"]),
            "auc": _binary_auc(y_val, y_scores, "evaluation"),
        }

    def get_probe_statistics(self) -> Dict[str, Any]:
        """Get statistics about all probes.

        Returns:
            Probe statistics
        """
        active_probes = [p for p in self.probes.values() if p.is_active]

        layer_distribution: Dict[int, int] = {}
        for probe in active_probes:
            layer_distribution[probe.layer] = layer_distribution.get(probe.layer, 0) + 1

        return {
            "total_probes": len(self.probes),
            "active_probes": len(active_probes),
            "average_auc": float(np.mean([p.auc_score for p in active_probes])) if active_probes else 0.0,
            "total_detections": sum(p.detection_count for p in self.probes.values()),
            "layer_distribution": layer_distribution,
            "deception_probes": len([p for p in self.probes.values() if self._is_deception_probe(p)]),
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

    def get_backend_type(self) -> str:
        """Get the backend type for this probe detector.

        Returns:
            "sklearn" (this implementation uses sklearn)

        Example:
            >>> detector = ProbeDetector(model)
            >>> detector.get_backend_type()
            'sklearn'
        """
        return "sklearn"

    async def fit_from_arrays(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        layer: int = 0,
    ) -> Probe:
        """Unified fit interface compatible with TorchProbeTrainer.

        This method provides a sklearn-compatible interface that matches
        the TorchProbeTrainer API for easy backend swapping.

        Args:
            X_train: Training activations
            y_train: Training labels (0=clean, 1=deceptive)
            X_val: Validation activations (optional; used for threshold calibration)
            y_val: Validation labels (optional)
            layer: Layer index for this probe

        Returns:
            Trained probe
        """
        y_train = np.asarray(y_train)
        positive_samples = X_train[y_train == 1]
        negative_samples = X_train[y_train == 0]

        validation_data = (X_val, y_val) if X_val is not None and y_val is not None else None

        return await self.train_probe(
            feature_name="is_deceptive",
            positive_samples=positive_samples,
            negative_samples=negative_samples,
            layer=layer,
            description=f"Probe at layer {layer}",
            validation_data=validation_data,
        )
