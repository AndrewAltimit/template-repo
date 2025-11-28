"""Abstract base class for backdoor detection methods.

This module provides a unified interface for all detection methods, enabling
polymorphic detection, fair benchmarking, and consistent logging.

Example:
    >>> from sleeper_agents.detection.base_detector import BaseDetector
    >>> from sleeper_agents.evaluation.detector_registry import DetectorRegistry
    >>>
    >>> @DetectorRegistry.register("my_detector")
    >>> class MyDetector(BaseDetector):
    ...     def fit(self, activations, labels):
    ...         # Train detector
    ...         pass
    ...
    ...     def score(self, activations):
    ...         # Compute scores
    ...         return np.array([...])
    ...
    ...     def run(self, **kwargs):
    ...         # Run detection pipeline
    ...         return {"score": 0.5, "is_backdoored": False}
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np
from torch import nn


class BaseDetector(ABC):
    """Abstract base class for all backdoor detection methods.

    This interface enables polymorphic detection across different methods
    (linear probes, ART defenses, etc.) with consistent API and logging.

    All detection methods (ProbeDetector, ARTActivationDetector, etc.) should
    inherit from this class and implement the required methods.

    Attributes:
        model: The model to analyze (HuggingFace or TransformerLens)
        config: Method-specific configuration dictionary
    """

    def __init__(self, model: Optional[nn.Module] = None, **kwargs):
        """Initialize detector with model reference.

        Args:
            model: The model to analyze (HuggingFace or TransformerLens)
            **kwargs: Method-specific configuration
        """
        self.model = model
        self.config = kwargs

    @abstractmethod
    def fit(self, activations: np.ndarray, labels: np.ndarray) -> None:
        """Train/fit the detector on labeled activation data.

        This method should train or configure the detector using the provided
        activation-label pairs. For unsupervised methods, labels may be ignored.

        Args:
            activations: Shape (n_samples, n_features) - activation vectors
            labels: Shape (n_samples,) - binary labels (0=clean, 1=backdoored)

        Raises:
            NotImplementedError: If the subclass doesn't implement this method
        """
        ...

    @abstractmethod
    def score(self, activations: np.ndarray) -> np.ndarray:
        """Compute detection scores for given activations.

        Higher scores indicate higher likelihood of backdoor/deceptive behavior.

        Args:
            activations: Shape (n_samples, n_features)

        Returns:
            scores: Shape (n_samples,) - detection confidence [0, 1]

        Raises:
            NotImplementedError: If the subclass doesn't implement this method
            RuntimeError: If called before fit()
        """
        ...

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """Run detection and return structured results.

        This is the main entry point for running a complete detection pipeline.
        It should call fit() and score() internally, then return a standardized
        results dictionary.

        Returns:
            Dictionary containing:
                - score (float): Overall detection score [0, 1]
                - is_backdoored (bool): Binary detection decision
                - report (dict): Method-specific details
                - metadata (dict): Layer name, parameters, etc.

        Raises:
            NotImplementedError: If the subclass doesn't implement this method
        """
        ...

    def explain(self, sample_id: str) -> Dict[str, Any]:
        """Provide explanations for detections (optional).

        This method can be overridden by subclasses to provide interpretability
        for specific samples (e.g., which features contributed to detection).

        Args:
            sample_id: Identifier for the sample to explain

        Returns:
            Explanation dictionary (method-specific format)
        """
        return {"method": self.name, "sample_id": sample_id, "explanation": "Not implemented for this detector"}

    @property
    def name(self) -> str:
        """Human-readable detector name.

        Returns:
            Class name (e.g., "ARTActivationDetector")
        """
        return self.__class__.__name__

    @property
    def inputs_required(self) -> Dict[str, str]:
        """Declare what inputs this detector needs.

        This can be used for validation and documentation purposes.

        Returns:
            Dictionary mapping input name to description/shape
        """
        return {"activations": "numpy.ndarray (n_samples, n_features)", "labels": "numpy.ndarray (n_samples,)"}

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.name}(config={self.config})"
