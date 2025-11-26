"""Factory for creating probe trainers with automatic backend selection.

This module provides a unified interface for probe training that automatically
selects the optimal backend (sklearn or PyTorch) based on model characteristics.

Backend Selection Logic:
- Models < 34B parameters: sklearn (faster for small datasets, proven performance)
- Models >= 34B parameters: PyTorch (GPU-accelerated, handles large activations)
- Manual override available via force_backend parameter

Example:
    >>> from sleeper_agents.probes.probe_factory import create_probe_trainer
    >>> from sleeper_agents.probes.probe_config import ProbeTrainingConfig
    >>>
    >>> # Automatic selection
    >>> trainer = create_probe_trainer(model_size_b=7, input_dim=4096)  # Uses sklearn
    >>> trainer = create_probe_trainer(model_size_b=70, input_dim=8192)  # Uses PyTorch
    >>>
    >>> # Manual override
    >>> config = ProbeTrainingConfig(device="cuda", batch_size=4096)
    >>> trainer = create_probe_trainer(7, 4096, config, force_backend="pytorch")
"""

import logging
from typing import TYPE_CHECKING, Literal, Optional, Union

from sleeper_agents.probes.probe_config import ProbeTrainingConfig

if TYPE_CHECKING:
    from sleeper_agents.probes.probe_detector import ProbeDetector
    from sleeper_agents.probes.torch_probe import TorchProbeTrainer

logger = logging.getLogger(__name__)


class ProbeTrainerFactory:
    """Factory for creating probe trainers with automatic backend selection.

    This factory automatically selects the optimal probe training backend
    based on model size:
    - Small models (<34B): sklearn (fast, proven, good for in-memory data)
    - Large models (≥34B): PyTorch (GPU-accelerated, handles disk-based data)

    Attributes:
        SKLEARN_THRESHOLD_B: Model size threshold for backend switching (34B)

    Example:
        >>> # Small model → sklearn
        >>> trainer = ProbeTrainerFactory.create_trainer(7, 4096)
        >>>
        >>> # Large model → PyTorch
        >>> trainer = ProbeTrainerFactory.create_trainer(70, 8192)
        >>>
        >>> # Check recommended backend
        >>> backend = ProbeTrainerFactory.recommend_backend(13)
        >>> backend
        'sklearn'
    """

    SKLEARN_THRESHOLD_B = 34  # Model size threshold for backend switching

    @staticmethod
    def create_trainer(
        model_size_b: float,
        input_dim: int,
        config: Optional[ProbeTrainingConfig] = None,
        force_backend: Optional[Literal["sklearn", "pytorch"]] = None,
    ) -> Union["ProbeDetector", "TorchProbeTrainer"]:
        """Create a probe trainer with automatic backend selection.

        Args:
            model_size_b: Model size in billions of parameters
            input_dim: Dimensionality of activations
            config: Training configuration (uses defaults if None)
            force_backend: Override automatic selection ("sklearn" or "pytorch")

        Returns:
            Probe trainer instance (either ProbeDetector or TorchProbeTrainer)

        Example:
            >>> # Automatic selection
            >>> trainer = ProbeTrainerFactory.create_trainer(7, 4096)  # Uses sklearn
            >>> trainer = ProbeTrainerFactory.create_trainer(70, 8192)  # Uses PyTorch
            >>>
            >>> # Manual override
            >>> trainer = ProbeTrainerFactory.create_trainer(7, 4096, force_backend="pytorch")
        """
        if config is None:
            config = ProbeTrainingConfig()

        # Determine backend
        if force_backend:
            backend = force_backend
            logger.info("Using forced backend: %s", backend)
        else:
            backend = "pytorch" if model_size_b >= ProbeTrainerFactory.SKLEARN_THRESHOLD_B else "sklearn"
            logger.info(
                "Auto-selected backend: %s (model_size=%sB, threshold=%sB)",
                backend,
                model_size_b,
                ProbeTrainerFactory.SKLEARN_THRESHOLD_B,
            )

        # Create trainer
        if backend == "sklearn":
            from sleeper_agents.probes.probe_detector import ProbeDetector

            # Convert config to sklearn-compatible format
            sklearn_config = {
                "regularization": config.regularization,
                "penalty": config.penalty,
                "max_iter": config.max_iterations,
                "threshold_percentile": config.threshold_percentile,
                "min_samples": config.min_samples,
                "ensemble_layers": config.ensemble_layers,
                "early_stopping": config.early_stopping,
                "early_stopping_patience": config.early_stopping_patience,
            }

            # Note: ProbeDetector expects model in __init__, but we don't have it here
            # This is OK - it's set later when train_probe is called
            trainer = ProbeDetector(model=None, config=sklearn_config)

        else:  # pytorch
            from sleeper_agents.probes.torch_probe import TorchProbeTrainer

            trainer = TorchProbeTrainer(input_dim=input_dim, config=config)

        return trainer

    @staticmethod
    def recommend_backend(model_size_b: float) -> str:
        """Get recommended backend for a model size.

        Args:
            model_size_b: Model size in billions of parameters

        Returns:
            Recommended backend ("sklearn" or "pytorch")

        Example:
            >>> ProbeTrainerFactory.recommend_backend(7)
            'sklearn'
            >>> ProbeTrainerFactory.recommend_backend(70)
            'pytorch'
        """
        return "pytorch" if model_size_b >= ProbeTrainerFactory.SKLEARN_THRESHOLD_B else "sklearn"


def create_probe_trainer(
    model_size_b: float,
    input_dim: int,
    config: Optional[ProbeTrainingConfig] = None,
    force_backend: Optional[Literal["sklearn", "pytorch"]] = None,
) -> Union["ProbeDetector", "TorchProbeTrainer"]:
    """Convenience function for creating probe trainers.

    This is a shorthand for ProbeTrainerFactory.create_trainer().

    Args:
        model_size_b: Model size in billions of parameters
        input_dim: Dimensionality of activations
        config: Training configuration
        force_backend: Override automatic selection

    Returns:
        Probe trainer instance

    Example:
        >>> # Automatic selection
        >>> trainer = create_probe_trainer(model_size_b=7, input_dim=4096)
        >>>
        >>> # With custom config
        >>> config = ProbeTrainingConfig(device="cuda", batch_size=2048)
        >>> trainer = create_probe_trainer(70, 8192, config=config)
        >>>
        >>> # Force specific backend
        >>> trainer = create_probe_trainer(7, 4096, force_backend="pytorch")
    """
    return ProbeTrainerFactory.create_trainer(model_size_b, input_dim, config, force_backend)
