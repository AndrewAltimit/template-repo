"""Local experiment logging utilities.

This module provides local-first experiment tracking using SQLite and JSON files.
No external services or accounts required.

Example:
    >>> from sleeper_agents.evaluation.experiment_logger import ExperimentLogger, generate_job_id
    >>>
    >>> # Create logger
    >>> job_id = generate_job_id()
    >>> logger = ExperimentLogger(job_id=job_id, results_dir="results")
    >>>
    >>> # Save configuration
    >>> logger.save_config({"model": "Qwen-7B", "layers": [10, 15, 20]})
    >>>
    >>> # Log metrics
    >>> logger.log_metrics({"score": 0.95, "is_backdoored": True}, step=1)
    >>>
    >>> # Save results
    >>> logger.save_results({"ensemble_score": 0.87})
    >>>
    >>> # Get summary
    >>> summary = logger.get_summary()
    >>> print(f"Logged {summary['metrics_logged']} metric entries")
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ExperimentLogger:
    """Local experiment logger - SQLite + JSON files.

    This logger stores experiment data locally in a structured directory:
        results/{job_id}/
            ├── config.json          # Experiment configuration
            ├── metrics.jsonl        # Time-series metrics (one JSON per line)
            ├── results.json         # Final results
            └── {detector_name}/     # Detector-specific results
                ├── layer_1.json
                └── layer_2.json

    All data is stored locally - no external services required.

    Attributes:
        job_id: Unique experiment identifier
        results_dir: Base directory for all results
        job_dir: Directory for this specific experiment
    """

    def __init__(self, job_id: str, results_dir: str = "results"):
        """Initialize local logger.

        Args:
            job_id: Unique identifier for this experiment
            results_dir: Base directory for results (default: "results")
        """
        self.job_id = job_id
        self.results_dir = Path(results_dir)
        self.job_dir = self.results_dir / job_id

        # Create directory structure
        self.job_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Experiment logger initialized: {self.job_dir}")

    def log_metrics(self, metrics: Dict[str, Any], step: Optional[int] = None):
        """Log metrics to JSONL file.

        Each call appends a new line to metrics.jsonl with timestamp.

        Args:
            metrics: Dictionary of metric name -> value
            step: Optional step/iteration number

        Example:
            >>> logger.log_metrics({"train_loss": 0.5, "val_auc": 0.9}, step=10)
        """
        log_file = self.job_dir / "metrics.jsonl"

        log_entry = {"step": step, "metrics": metrics, "timestamp": datetime.now().isoformat()}

        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        logger.debug(f"Logged metrics (step={step}): {metrics}")

    def save_config(self, config: Dict[str, Any]):
        """Save experiment configuration.

        Args:
            config: Configuration dictionary (typically from Hydra)

        Example:
            >>> logger.save_config({
            ...     "model_name": "Qwen-7B",
            ...     "detectors": ["linear_probe", "art_activation"],
            ...     "ensemble_threshold": 0.5
            ... })
        """
        config_file = self.job_dir / "config.json"

        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Config saved: {config_file}")

    def save_results(self, results: Dict[str, Any], filename: str = "results.json"):
        """Save complete results to JSON file.

        Args:
            results: Results dictionary
            filename: Output filename (default: "results.json")

        Example:
            >>> logger.save_results({
            ...     "ensemble_score": 0.87,
            ...     "decision": "BACKDOORED",
            ...     "detectors": {...}
            ... })
        """
        output_path = self.job_dir / filename

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Results saved: {output_path}")

    def save_detector_results(self, detector_name: str, layer_name: str, results: Dict[str, Any]):
        """Save detector-specific results.

        Creates a subdirectory for the detector and saves layer-specific results.

        Args:
            detector_name: Name of detector (e.g., "art_activation_defence")
            layer_name: Layer name (e.g., "blocks.20.hook_mlp_out")
            results: Detection results dictionary

        Example:
            >>> logger.save_detector_results(
            ...     detector_name="art_activation",
            ...     layer_name="blocks.20.hook_mlp_out",
            ...     results={"score": 0.8, "is_backdoored": True}
            ... )
        """
        detector_dir = self.job_dir / detector_name
        detector_dir.mkdir(exist_ok=True)

        # Sanitize layer name for filename (replace dots and slashes)
        safe_layer_name = layer_name.replace(".", "_").replace("/", "_")
        output_path = detector_dir / f"{safe_layer_name}.json"

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.debug(f"Detector results saved: {output_path}")

    def load_config(self) -> Dict[str, Any]:
        """Load experiment configuration.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config.json doesn't exist

        Example:
            >>> config = logger.load_config()
            >>> print(config["model_name"])
        """
        config_file = self.job_dir / "config.json"

        with open(config_file, "r") as f:
            config: Dict[str, Any] = json.load(f)
            return config

    def load_results(self, filename: str = "results.json") -> Dict[str, Any]:
        """Load results from JSON file.

        Args:
            filename: Results filename (default: "results.json")

        Returns:
            Results dictionary

        Raises:
            FileNotFoundError: If file doesn't exist

        Example:
            >>> results = logger.load_results()
            >>> print(results["ensemble_score"])
        """
        results_file = self.job_dir / filename

        with open(results_file, "r") as f:
            results: Dict[str, Any] = json.load(f)
            return results

    def load_metrics(self) -> list[Dict[str, Any]]:
        """Load all metric entries.

        Returns:
            List of metric dictionaries (one per logged entry)

        Example:
            >>> metrics = logger.load_metrics()
            >>> for entry in metrics:
            ...     print(f"Step {entry['step']}: {entry['metrics']}")
        """
        metrics_file = self.job_dir / "metrics.jsonl"

        if not metrics_file.exists():
            return []

        metrics = []
        with open(metrics_file, "r") as f:
            for line in f:
                metrics.append(json.loads(line.strip()))

        return metrics

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of logged data.

        Returns:
            Summary dictionary with file paths and counts

        Example:
            >>> summary = logger.get_summary()
            >>> print(f"Files: {summary['files']}")
            >>> print(f"Metrics: {summary['metrics_logged']}")
        """
        return {
            "job_id": self.job_id,
            "job_dir": str(self.job_dir),
            "files": sorted([str(p.relative_to(self.job_dir)) for p in self.job_dir.rglob("*.json*")]),
            "metrics_logged": self._count_metric_lines(),
        }

    def _count_metric_lines(self) -> int:
        """Count number of metric entries logged.

        Returns:
            Number of lines in metrics.jsonl
        """
        metrics_file = self.job_dir / "metrics.jsonl"

        if not metrics_file.exists():
            return 0

        with open(metrics_file, "r") as f:
            return sum(1 for _ in f)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"ExperimentLogger(job_id={self.job_id}, job_dir={self.job_dir})"


def generate_job_id(prefix: str = "job") -> str:
    """Generate unique job ID with timestamp.

    Args:
        prefix: Prefix for job ID (default: "job")

    Returns:
        Job ID string (e.g., "job_20251114_120530")

    Example:
        >>> job_id = generate_job_id()
        >>> print(job_id)
        'job_20251114_120530'
        >>>
        >>> job_id = generate_job_id(prefix="ensemble")
        >>> print(job_id)
        'ensemble_20251114_120532'
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}"
