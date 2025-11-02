#!/usr/bin/env python3
"""Package experiment artifacts for transfer across machines.

Creates a portable archive containing model files, logs, metrics, and metadata
that can be easily copied between machines without git.
"""

import argparse
import hashlib
import json
import logging
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of file.

    Args:
        file_path: Path to file

    Returns:
        SHA256 hex digest
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


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


def create_manifest(experiment_dir: Path) -> Dict[str, Any]:
    """Create manifest for experiment artifacts.

    Args:
        experiment_dir: Path to experiment directory

    Returns:
        Manifest dictionary
    """
    manifest: Dict[str, Any] = {
        "experiment_name": experiment_dir.name,
        "created_at": datetime.now().isoformat(),
        "files": [],
        "directories": [],
        "total_size_bytes": 0,
        "checksums": {},
    }

    # Collect all files with checksums
    for item in sorted(experiment_dir.rglob("*")):
        rel_path = str(item.relative_to(experiment_dir))

        if item.is_file():
            checksum = calculate_checksum(item)
            manifest["files"].append(
                {
                    "path": rel_path,
                    "size_bytes": item.stat().st_size,
                    "checksum": checksum,
                    "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                }
            )
            manifest["checksums"][rel_path] = checksum
        elif item.is_dir():
            manifest["directories"].append(rel_path)

    manifest["total_size_bytes"] = get_directory_size(experiment_dir)
    manifest["num_files"] = len(manifest["files"])

    return manifest


def package_experiment(experiment_name: str, output_dir: Path, include_models: bool = True) -> Path:
    """Package experiment into portable archive.

    Args:
        experiment_name: Name or path of experiment
        output_dir: Directory to write package
        include_models: Include model weights (can be large)

    Returns:
        Path to created archive
    """
    # Find experiment directory
    base_dir = Path("models/backdoored")
    if not base_dir.exists():
        base_dir = Path("packages/sleeper_agents/models/backdoored")

    experiment_dir = base_dir / experiment_name
    if not experiment_dir.exists():
        # Try as full path
        experiment_dir = Path(experiment_name)

    if not experiment_dir.exists():
        raise FileNotFoundError(f"Experiment not found: {experiment_name}")

    logger.info("Packaging experiment: %s", experiment_dir)

    # Create manifest
    logger.info("Creating manifest...")
    manifest = create_manifest(experiment_dir)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Archive name
    archive_name = f"{experiment_dir.name}.tar.gz"
    archive_path = output_dir / archive_name

    logger.info("Creating archive: %s", archive_path)
    logger.info(f"Total size: {manifest['total_size_bytes'] / 1024 / 1024:.2f} MB")
    logger.info("Files: %s", manifest["num_files"])

    # Create archive
    with tarfile.open(archive_path, "w:gz") as tar:
        # Add manifest
        manifest_path = experiment_dir / "artifact_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Add all files
        for file_info in manifest["files"]:
            file_path = experiment_dir / file_info["path"]

            # Skip model weights if requested
            if not include_models and ("pytorch_model.bin" in str(file_path) or "model.safetensors" in str(file_path)):
                logger.info("Skipping model weights: %s", file_info["path"])
                continue

            tar.add(file_path, arcname=f"{experiment_dir.name}/{file_info['path']}")

        # Add manifest
        tar.add(manifest_path, arcname=f"{experiment_dir.name}/artifact_manifest.json")

    # Clean up temporary manifest
    manifest_path.unlink()

    logger.info("Package created: %s", archive_path)
    logger.info(f"Archive size: {archive_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Create metadata file for easy reference
    metadata = {
        "experiment_name": experiment_dir.name,
        "package_path": str(archive_path),
        "created_at": datetime.now().isoformat(),
        "total_size_mb": manifest["total_size_bytes"] / 1024 / 1024,
        "num_files": manifest["num_files"],
        "checksum": calculate_checksum(archive_path),
        "includes_models": include_models,
    }

    metadata_path = output_dir / f"{experiment_dir.name}_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Metadata saved: %s", metadata_path)

    return archive_path


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Package experiment artifacts for transfer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Package experiment with models
  python package_experiment.py i_hate_you_gpt2_20251004_111710

  # Package without model weights (faster, smaller)
  python package_experiment.py i_hate_you_gpt2_20251004_111710 --no-models

  # Specify output directory
  python package_experiment.py i_hate_you_gpt2_20251004_111710 --output artifacts/packages

  # Package all experiments
  python package_experiment.py --all
        """,
    )

    parser.add_argument("experiment", nargs="?", help="Experiment name or path")
    parser.add_argument("--output", type=Path, default=Path("artifacts/packages"), help="Output directory")
    parser.add_argument("--no-models", action="store_true", help="Exclude model weights (metadata only)")
    parser.add_argument("--all", action="store_true", help="Package all experiments")

    return parser.parse_args()


def main():
    """Main packaging pipeline."""
    args = parse_args()

    if args.all:
        # Package all experiments
        base_dir = Path("models/backdoored")
        if not base_dir.exists():
            base_dir = Path("packages/sleeper_agents/models/backdoored")

        if not base_dir.exists():
            logger.error("No experiments found")
            sys.exit(1)

        experiments = [d for d in base_dir.iterdir() if d.is_dir()]
        logger.info("Found %s experiments to package", len(experiments))

        for exp_dir in experiments:
            try:
                package_experiment(exp_dir.name, args.output, include_models=not args.no_models)
            except Exception as e:
                logger.error(f"Failed to package {exp_dir.name}: {e}")

    elif args.experiment:
        package_experiment(args.experiment, args.output, include_models=not args.no_models)
    else:
        logger.error("Provide experiment name or use --all")
        sys.exit(1)


if __name__ == "__main__":
    main()
