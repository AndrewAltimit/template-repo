"""
Sleeper Agent Detection - Model Evaluation System

Comprehensive evaluation framework for testing open-weight models for sleeper agents
and hidden backdoors. Generates detailed safety reports for deployment decisions.
"""

__version__ = "2.0.0"
__author__ = "Template Repository"

from packages.sleeper_detection.app.config import DetectionConfig
from packages.sleeper_detection.app.detector import SleeperDetector
from packages.sleeper_detection.evaluation.evaluator import EvaluationResult, ModelEvaluator
from packages.sleeper_detection.evaluation.report_generator import ReportGenerator

__all__ = ["ModelEvaluator", "EvaluationResult", "ReportGenerator", "DetectionConfig", "SleeperDetector"]
