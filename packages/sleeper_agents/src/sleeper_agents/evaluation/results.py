"""Evaluation result record and outcome statuses shared by the evaluator and its test suites."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"


class EvaluationSkipped(Exception):
    """Raised inside a test when it cannot produce a genuine measurement.

    Examples: the detector only returned simulated (``is_mock``) output, a required
    component is unavailable, or the test is not implemented for real models.
    The evaluator records the test with ``status="skipped"`` and no metrics.
    """


def _mean_or_none(values: List[Optional[float]]) -> Optional[float]:
    """Mean of the defined values, or None if there are none."""
    defined = [float(v) for v in values if v is not None]
    return float(np.mean(defined)) if defined else None


@dataclass
class EvaluationResult:
    """Results from a single evaluation test.

    Accuracy, precision, recall and F1 are derived from the confusion counts on
    every access, so they always reflect the counts that were actually filled in.
    A metric that is undefined for the recorded counts (for example precision with
    no positive predictions, or any metric for an analysis-only test) is ``None``
    rather than a fabricated 0.0. Tests whose headline score is not a confusion
    matrix accuracy can assign ``accuracy`` explicitly; that value is stored in
    ``accuracy_override`` and takes precedence over the count-based accuracy.
    """

    model_name: str
    test_name: str
    test_type: str
    timestamp: datetime

    # Detection metrics
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    # Scores (accuracy/precision/recall/f1 are derived properties, see below)
    auc_score: float = 0.0
    accuracy_override: Optional[float] = None

    # Additional metrics
    avg_confidence: float = 0.0
    detection_time_ms: float = 0.0

    # Layer analysis
    best_layers: Optional[List[int]] = None
    layer_scores: Optional[Dict[int, Any]] = None  # Can be float or List[float] depending on test

    # Detailed results
    samples_tested: int = 0
    failed_samples: Optional[List[str]] = None

    # Metadata
    config: Optional[Dict[str, Any]] = None
    notes: str = ""

    # Outcome of the test run: "completed", "skipped" (no genuine measurement
    # possible, reason in notes) or "error" (the test raised, message in notes)
    status: str = STATUS_COMPLETED
    run_id: Optional[str] = None

    @property
    def total_classified(self) -> int:
        """Total number of samples recorded in the confusion counts."""
        return self.true_positives + self.false_positives + self.true_negatives + self.false_negatives

    @property
    def accuracy(self) -> Optional[float]:
        """Headline accuracy: explicit override if set, else (TP+TN)/total, else None."""
        if self.status != STATUS_COMPLETED:
            return None
        if self.accuracy_override is not None:
            return float(self.accuracy_override)
        total = self.total_classified
        if total == 0:
            return None
        return (self.true_positives + self.true_negatives) / total

    @accuracy.setter
    def accuracy(self, value: Optional[float]) -> None:
        self.accuracy_override = None if value is None else float(value)

    @property
    def precision(self) -> Optional[float]:
        """TP / (TP + FP), or None when there are no positive predictions."""
        if self.status != STATUS_COMPLETED:
            return None
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else None

    @property
    def recall(self) -> Optional[float]:
        """TP / (TP + FN), or None when there are no positive samples."""
        if self.status != STATUS_COMPLETED:
            return None
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else None

    @property
    def f1_score(self) -> Optional[float]:
        """Harmonic mean of precision and recall, or None if either is undefined."""
        precision, recall = self.precision, self.recall
        if precision is None or recall is None:
            return None
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def to_dict(self) -> Dict[str, Any]:
        """Convert EvaluationResult to a JSON-serializable dictionary.

        Returns:
            Dictionary representation of the evaluation result.
        """
        return {
            "model_name": self.model_name,
            "test_name": self.test_name,
            "test_type": self.test_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "accuracy_override": self.accuracy_override,
            "auc_score": self.auc_score,
            "avg_confidence": self.avg_confidence,
            "detection_time_ms": self.detection_time_ms,
            "best_layers": self.best_layers,
            "layer_scores": self.layer_scores,
            "samples_tested": self.samples_tested,
            "failed_samples": self.failed_samples,
            "config": self.config,
            "notes": self.notes,
            "status": self.status,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationResult":
        """Create EvaluationResult from a dictionary.

        Args:
            data: Dictionary containing evaluation result data.

        Returns:
            EvaluationResult instance.
        """
        # Parse timestamp if it's a string
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        counts_total = sum(
            int(data.get(key) or 0) for key in ("true_positives", "false_positives", "true_negatives", "false_negatives")
        )
        accuracy_override = data.get("accuracy_override")
        if accuracy_override is None and "accuracy_override" not in data and counts_total == 0:
            # Legacy dicts (without accuracy_override) stored explicit scores in "accuracy".
            # A 0.0 with no counts was the old "never computed" default, not a measurement.
            legacy_accuracy = data.get("accuracy")
            if legacy_accuracy is not None and legacy_accuracy != 0.0:
                accuracy_override = legacy_accuracy

        return cls(
            model_name=data.get("model_name", "unknown"),
            test_name=data.get("test_name", "unknown"),
            test_type=data.get("test_type", "unknown"),
            timestamp=timestamp,
            true_positives=data.get("true_positives", 0),
            false_positives=data.get("false_positives", 0),
            true_negatives=data.get("true_negatives", 0),
            false_negatives=data.get("false_negatives", 0),
            auc_score=data.get("auc_score", 0.0),
            accuracy_override=accuracy_override,
            avg_confidence=data.get("avg_confidence", 0.0),
            detection_time_ms=data.get("detection_time_ms", 0.0),
            best_layers=data.get("best_layers"),
            layer_scores=data.get("layer_scores"),
            samples_tested=data.get("samples_tested", 0),
            failed_samples=data.get("failed_samples"),
            config=data.get("config"),
            notes=data.get("notes", ""),
            status=data.get("status") or STATUS_COMPLETED,
            run_id=data.get("run_id"),
        )
