"""
Sleeper Agent Detection - Model Evaluation System

Comprehensive evaluation framework for testing open-weight models for sleeper agents
and hidden backdoors. Generates detailed safety reports for deployment decisions.
"""

__version__ = "2.0.0"
__author__ = "Template Repository"

# Core imports that don't require torch
from .app.config import DetectionConfig
from .evaluation.report_generator import ReportGenerator

# Imports that require torch for full functionality
try:
    import torch  # noqa: F401

    _torch_available = True
    from .app.detector import SleeperDetector
    from .evaluation.evaluator import EvaluationResult, ModelEvaluator
except ImportError:
    import warnings

    _torch_available = False
    warnings.warn(
        "Some features require PyTorch. Install with: pip install torch\n" "Limited functionality available without PyTorch.",
        ImportWarning,
        stacklevel=2,
    )
    # Provide None values for missing classes so __all__ doesn't fail
    SleeperDetector = None  # type: ignore
    EvaluationResult = None  # type: ignore
    ModelEvaluator = None  # type: ignore

__all__ = ["ModelEvaluator", "EvaluationResult", "ReportGenerator", "DetectionConfig", "SleeperDetector"]
