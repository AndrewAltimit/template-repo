"""Registry pattern for backdoor detection methods.

This module provides a centralized registry for all available detector
implementations, enabling dynamic instantiation and discovery.

Example:
    >>> from sleeper_agents.evaluation.detector_registry import DetectorRegistry
    >>> from sleeper_agents.detection.base_detector import BaseDetector
    >>>
    >>> # Register a detector
    >>> @DetectorRegistry.register("my_detector")
    >>> class MyDetector(BaseDetector):
    ...     pass
    >>>
    >>> # List available detectors
    >>> print(DetectorRegistry.list_available())
    ['my_detector', 'linear_probe', 'art_activation_defence']
    >>>
    >>> # Instantiate by name
    >>> detector = DetectorRegistry.get("my_detector", model=model, param1=value1)
"""

import logging
from typing import Dict, Optional, Type

from sleeper_agents.detection.base_detector import BaseDetector

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """Registry for all available detection methods.

    This class maintains a global registry of detector implementations,
    allowing them to be instantiated by name. Detectors register themselves
    using the @DetectorRegistry.register() decorator.

    Attributes:
        _detectors: Dictionary mapping detector names to classes
    """

    _detectors: Dict[str, Type[BaseDetector]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a detector.

        Args:
            name: Unique name for the detector (e.g., "linear_probe")

        Returns:
            Decorator function

        Example:
            >>> @DetectorRegistry.register("my_detector")
            >>> class MyDetector(BaseDetector):
            ...     pass
        """

        def decorator(detector_cls: Type[BaseDetector]):
            if not issubclass(detector_cls, BaseDetector):
                raise TypeError(f"Detector {detector_cls.__name__} must inherit from BaseDetector")

            if name in cls._detectors:
                logger.warning(
                    "Overwriting existing detector registration: %s (was %s, now %s)",
                    name,
                    cls._detectors[name].__name__,
                    detector_cls.__name__,
                )

            cls._detectors[name] = detector_cls
            logger.debug("Registered detector: %s -> %s", name, detector_cls.__name__)
            return detector_cls

        return decorator

    @classmethod
    def get(cls, name: str, **kwargs) -> BaseDetector:
        """Instantiate a detector by name.

        Args:
            name: Registered detector name
            **kwargs: Arguments passed to detector constructor

        Returns:
            Instantiated detector

        Raises:
            ValueError: If detector name not found in registry

        Example:
            >>> detector = DetectorRegistry.get(
            ...     "art_activation_defence",
            ...     model=model,
            ...     nb_clusters=2
            ... )
        """
        if name not in cls._detectors:
            available = ", ".join(cls._detectors.keys())
            raise ValueError(f"Unknown detector: '{name}'. " f"Available detectors: {available or 'none'}")

        detector_cls = cls._detectors[name]
        logger.info("Instantiating detector: %s (%s)", name, detector_cls.__name__)
        return detector_cls(**kwargs)

    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered detectors.

        Returns:
            List of detector names

        Example:
            >>> detectors = DetectorRegistry.list_available()
            >>> print(detectors)
            ['linear_probe', 'art_activation_defence', 'art_spectral_signature']
        """
        return sorted(cls._detectors.keys())

    @classmethod
    def get_detector_class(cls, name: str) -> Optional[Type[BaseDetector]]:
        """Get detector class without instantiating.

        Args:
            name: Registered detector name

        Returns:
            Detector class, or None if not found

        Example:
            >>> detector_cls = DetectorRegistry.get_detector_class("linear_probe")
            >>> print(detector_cls.__name__)
            'ProbeDetector'
        """
        return cls._detectors.get(name)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a detector name is registered.

        Args:
            name: Detector name to check

        Returns:
            True if registered, False otherwise

        Example:
            >>> if DetectorRegistry.is_registered("my_detector"):
            ...     detector = DetectorRegistry.get("my_detector")
        """
        return name in cls._detectors

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Remove a detector from the registry.

        Args:
            name: Detector name to remove

        Returns:
            True if removed, False if not found

        Example:
            >>> DetectorRegistry.unregister("obsolete_detector")
            True
        """
        if name in cls._detectors:
            del cls._detectors[name]
            logger.info("Unregistered detector: %s", name)
            return True
        return False

    @classmethod
    def clear(cls):
        """Clear all registered detectors.

        This is primarily useful for testing.

        Example:
            >>> DetectorRegistry.clear()
            >>> assert len(DetectorRegistry.list_available()) == 0
        """
        cls._detectors.clear()
        logger.info("Cleared all detector registrations")
