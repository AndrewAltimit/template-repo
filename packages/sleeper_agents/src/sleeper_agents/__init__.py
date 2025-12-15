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

# Check torch availability without importing
_torch_available = False
try:
    import importlib.util

    _torch_available = importlib.util.find_spec("torch") is not None
except (ImportError, AttributeError):
    pass

# Lazy imports for torch-dependent modules
SleeperDetector = None  # type: ignore
EvaluationResult = None  # type: ignore
ModelEvaluator = None  # type: ignore


def __getattr__(name):
    """Lazy import torch-dependent modules."""
    if name in ("SleeperDetector", "EvaluationResult", "ModelEvaluator"):
        if not _torch_available:
            import warnings

            warnings.warn(
                "Some features require PyTorch. Install with: pip install torch\n"
                "Limited functionality available without PyTorch.",
                ImportWarning,
                stacklevel=2,
            )
            return None

        # Import torch and modules only when accessed
        import torch  # noqa: F401 pylint: disable=import-outside-toplevel,unused-import

        if name == "SleeperDetector":
            from .app.detector import SleeperDetector as _SleeperDetector

            return _SleeperDetector
        if name == "EvaluationResult":
            from .evaluation.evaluator import EvaluationResult as _EvaluationResult

            return _EvaluationResult
        if name == "ModelEvaluator":
            from .evaluation.evaluator import ModelEvaluator as _ModelEvaluator

            return _ModelEvaluator

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["ModelEvaluator", "EvaluationResult", "ReportGenerator", "DetectionConfig", "SleeperDetector"]
