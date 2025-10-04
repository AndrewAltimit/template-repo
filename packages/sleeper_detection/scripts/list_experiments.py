#!/usr/bin/env python3
"""List all experiments and their artifacts.

Provides overview of available experiments, their sizes, and contents.
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes.

    Args:
        path: Directory path

    Returns:
        Total size in bytes
    """
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def load_experiment_metadata(exp_dir: Path) -> Dict[str, Any]:
    """Load experiment metadata.

    Args:
        exp_dir: Experiment directory

    Returns:
        Metadata dictionary
    """
    metadata: Dict[str, Any] = {
        "name": exp_dir.name,
        "path": str(exp_dir),
        "size_mb": get_directory_size(exp_dir) / 1024 / 1024,
        "num_files": len(list(exp_dir.rglob("*"))),
    }

    # Load backdoor info if available
    backdoor_info_path = exp_dir / "backdoor_info.json"
    if backdoor_info_path.exists():
        with open(backdoor_info_path) as f:
            backdoor_info = json.load(f)
            metadata["backdoor_type"] = backdoor_info.get("backdoor_type", "unknown")
            metadata["trigger"] = backdoor_info.get("trigger", "unknown")

    # Load training metrics if available
    metrics_path = exp_dir / "training_metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)
            metadata["train_loss"] = metrics.get("train_loss", "N/A")
            metadata["training_time_sec"] = metrics.get("total_training_time_seconds", 0)

    # Load validation metrics if available
    validation_path = exp_dir / "validation_metrics.json"
    if validation_path.exists():
        with open(validation_path) as f:
            validation = json.load(f)
            metadata["backdoor_activation_rate"] = validation.get("backdoor_activation_rate", "N/A")
            metadata["clean_accuracy"] = validation.get("clean_accuracy", "N/A")

    # Check for safety trained variants
    safety_variants = []
    for item in exp_dir.iterdir():
        if item.is_dir() and "safety" in item.name.lower():
            safety_variants.append(item.name)
    metadata["safety_variants"] = safety_variants

    return metadata


def list_experiments(base_dir: Path, detailed: bool = False) -> List[Dict[str, Any]]:
    """List all experiments.

    Args:
        base_dir: Base directory containing experiments
        detailed: Include detailed metadata

    Returns:
        List of experiment metadata
    """
    if not base_dir.exists():
        logger.warning(f"Directory not found: {base_dir}")
        return []

    experiments = []
    for exp_dir in sorted(base_dir.iterdir()):
        if not exp_dir.is_dir():
            continue

        metadata = load_experiment_metadata(exp_dir)
        experiments.append(metadata)

    return experiments


def print_experiments(experiments: List[Dict[str, Any]], detailed: bool = False):
    """Print experiments in formatted table.

    Args:
        experiments: List of experiment metadata
        detailed: Print detailed information
    """
    if not experiments:
        logger.info("No experiments found")
        return

    logger.info("=" * 100)
    logger.info("EXPERIMENTS")
    logger.info("=" * 100)
    logger.info("")

    for i, exp in enumerate(experiments, 1):
        logger.info(f"{i}. {exp['name']}")
        logger.info(f"   Path: {exp['path']}")
        logger.info(f"   Size: {exp['size_mb']:.2f} MB ({exp['num_files']} files)")

        if "backdoor_type" in exp:
            logger.info(f"   Backdoor: {exp['backdoor_type']} (trigger: {exp['trigger']})")

        if "train_loss" in exp:
            logger.info(f"   Training: loss={exp['train_loss']:.4f}, time={exp['training_time_sec']:.1f}s")

        if "backdoor_activation_rate" in exp:
            logger.info(
                f"   Validation: activation={exp['backdoor_activation_rate']:.1%}, " f"clean_acc={exp['clean_accuracy']:.1%}"
            )

        if exp.get("safety_variants"):
            logger.info(f"   Safety variants: {', '.join(exp['safety_variants'])}")

        logger.info("")

    # Summary
    total_size = sum(exp["size_mb"] for exp in experiments)
    logger.info("=" * 100)
    logger.info(f"Total: {len(experiments)} experiments, {total_size:.2f} MB")
    logger.info("=" * 100)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="List experiments and artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all experiments
  python list_experiments.py

  # List with detailed metadata
  python list_experiments.py --detailed

  # Export to JSON
  python list_experiments.py --json experiments.json
        """,
    )

    parser.add_argument("--base-dir", type=Path, default=Path("models/backdoored"), help="Base directory for experiments")
    parser.add_argument("--detailed", action="store_true", help="Show detailed metadata")
    parser.add_argument("--json", type=Path, help="Export to JSON file")

    return parser.parse_args()


def main():
    """Main listing pipeline."""
    args = parse_args()

    # Try default location, fallback to package location
    base_dir = args.base_dir
    if not base_dir.exists():
        base_dir = Path("packages/sleeper_detection") / args.base_dir

    experiments = list_experiments(base_dir, detailed=args.detailed)

    if args.json:
        # Export to JSON
        with open(args.json, "w") as f:
            json.dump({"experiments": experiments, "generated_at": datetime.now().isoformat()}, f, indent=2)
        logger.info(f"Exported to: {args.json}")
    else:
        # Print to console
        print_experiments(experiments, detailed=args.detailed)


if __name__ == "__main__":
    main()
