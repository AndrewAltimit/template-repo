"""
Sleeper Agent Detection - Model Evaluation System

Comprehensive evaluation framework for testing open-weight models for sleeper agents
and hidden backdoors. Generates detailed safety reports for deployment decisions.
"""

__version__ = "2.0.0"
__author__ = "Template Repository"

# Use relative imports to avoid import issues
try:
    from .app.config import DetectionConfig
    from .app.detector import SleeperDetector
    from .evaluation.evaluator import EvaluationResult, ModelEvaluator
    from .evaluation.report_generator import ReportGenerator
except ImportError:
    # For cases where torch is not available
    DetectionConfig = None  # type: ignore
    SleeperDetector = None  # type: ignore
    EvaluationResult = None  # type: ignore
    ModelEvaluator = None  # type: ignore
    ReportGenerator = None  # type: ignore

__all__ = ["ModelEvaluator", "EvaluationResult", "ReportGenerator", "DetectionConfig", "SleeperDetector"]
