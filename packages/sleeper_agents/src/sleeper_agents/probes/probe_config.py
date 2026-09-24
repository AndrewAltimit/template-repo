"""Shared configuration for probe training across backends.

This module provides a unified configuration interface for both sklearn and PyTorch
probe trainers, allowing seamless switching between implementations while maintaining
consistent hyperparameters.

Both backends minimize the same objective (see ``TorchProbeTrainer`` for the PyTorch
side)::

    mean_i BCE(w.x_i + b, y_i) + penalty(w) / (C * n_train)

with ``C = 1 / regularization`` and ``penalty(w) = 0.5 * ||w||_2^2`` (L2) or
``||w||_1`` (L1). This is sklearn's ``LogisticRegression`` objective divided by
``C * n_train``, so for the same data and ``regularization`` the two backends
converge towards the same weights.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List

VALID_PENALTIES = ("l1", "l2")

# Threshold selection criteria understood by both backends.
#   "youden": maximize TPR - FPR (Youden's J statistic) on the calibration split
#   "f1": maximize F1 on the calibration split
#   "negative_percentile": the `threshold_percentile`-th percentile of negative-class
#       scores, i.e. an FPR target of roughly (100 - threshold_percentile)%
#   "f1_or_negative_percentile": the larger (more conservative) of "f1" and
#       "negative_percentile"
THRESHOLD_CRITERIA = ("youden", "f1", "negative_percentile", "f1_or_negative_percentile")
DEFAULT_THRESHOLD_CRITERION = "f1_or_negative_percentile"


def _sklearn_version() -> tuple:
    import sklearn

    parts = re.findall(r"\d+", sklearn.__version__)[:2]
    return tuple(int(p) for p in parts)


def sklearn_penalty_kwargs(penalty: str) -> Dict[str, Any]:
    """Return ``LogisticRegression`` keyword arguments selecting an L1 or L2 penalty.

    scikit-learn 1.8 deprecated the ``penalty`` parameter in favour of ``l1_ratio``
    (``0.0`` = L2, ``1.0`` = L1); it is removed in 1.10. This helper emits whichever
    form the installed version expects, so no ``FutureWarning`` is raised.

    Args:
        penalty: "l1" or "l2"

    Returns:
        Dictionary with the penalty selection and a compatible ``solver``
    """
    if penalty not in VALID_PENALTIES:
        raise ValueError(f"Unsupported penalty {penalty!r}; expected one of {VALID_PENALTIES}")

    # L1 requires a solver that supports it; lbfgs is L2-only
    solver = "liblinear" if penalty == "l1" else "lbfgs"

    if _sklearn_version() >= (1, 8):
        return {"l1_ratio": 1.0 if penalty == "l1" else 0.0, "solver": solver}
    return {"penalty": penalty, "solver": solver}


@dataclass
class ProbeTrainingConfig:
    """Configuration for probe training (backend-agnostic).

    This config works for both sklearn and PyTorch backends,
    allowing seamless switching between implementations.

    Attributes:
        regularization: Regularization strength (inverse of sklearn's C parameter).
            Both backends apply it with the same scaling (see module docstring).
        penalty: Regularization type ("l1" or "l2")
        max_iterations: Maximum training iterations (sklearn solver) / epochs (PyTorch)
        ensemble_layers: Layer indices to probe (e.g., [3, 5, 7, 9])
        early_stopping: Whether to use early stopping (PyTorch only; sklearn fits to
            convergence)
        early_stopping_patience: Epochs without improvement before stopping
        validation_split: Fraction of training data held out for validation when no
            validation set is provided (PyTorch only)
        learning_rate: Learning rate for PyTorch optimizer (ignored by sklearn)
        batch_size: Batch size for PyTorch training (ignored by sklearn)
        use_mixed_precision: Enable FP16 training on GPU (PyTorch only)
        gradient_accumulation_steps: Accumulate gradients over N batches before each
            optimizer step (PyTorch only)
        threshold_percentile: Percentile of negative scores used by the
            percentile-based threshold criteria
        threshold_criterion: One of THRESHOLD_CRITERIA
        use_feature_scaling: Standardize features (fit on the training split only)
        min_samples: Minimum samples required for training
        random_seed: Seed for splits and weight initialization
        device: Device for computation ("cuda" or "cpu")

    Example:
        >>> config = ProbeTrainingConfig(device="cuda", batch_size=4096)
        >>> # Use with PyTorch trainer
        >>> trainer = TorchProbeTrainer(input_dim=4096, config=config)
        >>> # Or with sklearn trainer
        >>> sklearn_params = config.to_sklearn_params()
    """

    # Core hyperparameters (shared by both backends)
    regularization: float = 100.0  # Stronger regularization to prevent overfitting
    penalty: str = "l2"  # Regularization type: "l1" or "l2"
    max_iterations: int = 2000  # Maximum training iterations/epochs

    # Probe architecture
    ensemble_layers: List[int] = field(default_factory=lambda: [3, 5, 7, 9])

    # Training behavior
    early_stopping: bool = True
    early_stopping_patience: int = 5
    validation_split: float = 0.2  # Fraction of data for validation

    # PyTorch-specific parameters (ignored by sklearn)
    learning_rate: float = 0.001
    batch_size: int = 8192
    use_mixed_precision: bool = True  # FP16 training
    gradient_accumulation_steps: int = 1

    # Threshold selection
    threshold_percentile: int = 90
    threshold_criterion: str = DEFAULT_THRESHOLD_CRITERION
    min_samples: int = 100

    # Preprocessing
    use_feature_scaling: bool = False

    # Reproducibility
    random_seed: int = 42

    # Device configuration
    device: str = "cuda"  # "cuda" or "cpu"

    def __post_init__(self) -> None:
        if self.penalty not in VALID_PENALTIES:
            raise ValueError(f"penalty must be one of {VALID_PENALTIES}, got {self.penalty!r}")
        if self.threshold_criterion not in THRESHOLD_CRITERIA:
            raise ValueError(f"threshold_criterion must be one of {THRESHOLD_CRITERIA}, got {self.threshold_criterion!r}")
        if self.regularization <= 0:
            raise ValueError("regularization must be positive")
        if self.gradient_accumulation_steps < 1:
            raise ValueError("gradient_accumulation_steps must be >= 1")

    def to_sklearn_params(self) -> Dict[str, Any]:
        """Convert to sklearn LogisticRegression parameters.

        The penalty is expressed via ``l1_ratio`` on scikit-learn >= 1.8 and via
        ``penalty`` on older versions (see ``sklearn_penalty_kwargs``).

        Returns:
            Dictionary of sklearn-compatible parameters

        Example:
            >>> config = ProbeTrainingConfig(regularization=50.0, penalty="l1")
            >>> sklearn_params = config.to_sklearn_params()
            >>> sklearn_params["C"]
            0.02
        """
        params: Dict[str, Any] = {
            "C": 1.0 / self.regularization,  # sklearn uses inverse regularization
            "max_iter": self.max_iterations,
            "random_state": self.random_seed,
        }
        params.update(sklearn_penalty_kwargs(self.penalty))
        return params

    def to_dict(self) -> Dict[str, Any]:
        """Serialize configuration to dictionary.

        Returns:
            Dictionary representation of config

        Example:
            >>> config = ProbeTrainingConfig(regularization=200.0)
            >>> config_dict = config.to_dict()
            >>> config_dict['regularization']
            200.0
        """
        return {
            "regularization": self.regularization,
            "penalty": self.penalty,
            "max_iterations": self.max_iterations,
            "ensemble_layers": self.ensemble_layers,
            "early_stopping": self.early_stopping,
            "early_stopping_patience": self.early_stopping_patience,
            "validation_split": self.validation_split,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "use_mixed_precision": self.use_mixed_precision,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "threshold_percentile": self.threshold_percentile,
            "threshold_criterion": self.threshold_criterion,
            "min_samples": self.min_samples,
            "use_feature_scaling": self.use_feature_scaling,
            "random_seed": self.random_seed,
            "device": self.device,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ProbeTrainingConfig":
        """Create configuration from dictionary.

        Args:
            config_dict: Dictionary containing configuration values

        Returns:
            ProbeTrainingConfig instance

        Example:
            >>> config_dict = {"regularization": 150.0, "device": "cpu"}
            >>> config = ProbeTrainingConfig.from_dict(config_dict)
            >>> config.regularization
            150.0
        """
        return cls(**config_dict)
