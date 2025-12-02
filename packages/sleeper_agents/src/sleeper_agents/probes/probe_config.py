"""Shared configuration for probe training across backends.

This module provides a unified configuration interface for both sklearn and PyTorch
probe trainers, allowing seamless switching between implementations while maintaining
consistent hyperparameters.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ProbeTrainingConfig:
    """Configuration for probe training (backend-agnostic).

    This config works for both sklearn and PyTorch backends,
    allowing seamless switching between implementations.

    Attributes:
        regularization: L2 regularization strength (inverse of sklearn's C parameter)
        penalty: Regularization type ("l1" or "l2")
        max_iterations: Maximum training iterations/epochs
        ensemble_layers: Layer indices to probe (e.g., [3, 5, 7, 9])
        early_stopping: Whether to use early stopping
        early_stopping_patience: Epochs without improvement before stopping
        validation_split: Fraction of training data for validation (if not provided separately)
        learning_rate: Learning rate for PyTorch optimizer (ignored by sklearn)
        batch_size: Batch size for PyTorch training (ignored by sklearn)
        use_mixed_precision: Enable FP16 training on GPU (PyTorch only)
        gradient_accumulation_steps: Accumulate gradients over N steps (PyTorch only)
        threshold_percentile: Percentile for automatic threshold selection
        min_samples: Minimum samples required for training
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

    # Training behavior (shared by both backends)
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
    min_samples: int = 100

    # Device configuration
    device: str = "cuda"  # "cuda" or "cpu"

    def to_sklearn_params(self) -> Dict[str, Any]:
        """Convert to sklearn LogisticRegression parameters.

        Returns:
            Dictionary of sklearn-compatible parameters

        Example:
            >>> config = ProbeTrainingConfig(regularization=50.0, penalty="l1")
            >>> sklearn_params = config.to_sklearn_params()
            >>> sklearn_params
            {'C': 0.02, 'penalty': 'l1', 'max_iter': 2000, ...}
        """
        return {
            "C": 1.0 / self.regularization,  # sklearn uses inverse regularization
            "penalty": self.penalty,
            "max_iter": self.max_iterations,
            "random_state": 42,
            "solver": "liblinear" if self.penalty == "l1" else "lbfgs",
        }

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
            "min_samples": self.min_samples,
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
