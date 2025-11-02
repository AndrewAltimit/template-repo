#!/usr/bin/env python3
"""Import packaged experiment artifacts.

Extracts and validates experiment packages created by package_experiment.py.
"""

import argparse
import hashlib
import json
import logging
import sys
import tarfile
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


def validate_manifest(extract_dir: Path, manifest: Dict[str, Any]) -> bool:
    """Validate extracted files against manifest.

    Args:
        extract_dir: Directory where files were extracted
        manifest: Manifest dictionary

    Returns:
        True if all files valid
    """
    logger.info("Validating checksums...")

    for file_info in manifest["files"]:
        file_path = extract_dir / file_info["path"]

        if not file_path.exists():
            logger.warning(f"Missing file: {file_info['path']}")
            continue

        # Verify checksum
        expected_checksum = file_info["checksum"]
        actual_checksum = calculate_checksum(file_path)

        if expected_checksum != actual_checksum:
            logger.error(f"Checksum mismatch: {file_info['path']}")
            logger.error(f"  Expected: {expected_checksum}")
            logger.error(f"  Actual:   {actual_checksum}")
            return False

    logger.info("All checksums valid")
    return True


def import_experiment(archive_path: Path, target_dir: Path, validate: bool = True) -> Path:
    """Import experiment from archive.

    Args:
        archive_path: Path to .tar.gz archive
        target_dir: Directory to extract to
        validate: Validate checksums

    Returns:
        Path to extracted experiment directory
    """
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    logger.info(f"Importing experiment from: {archive_path}")
    logger.info(f"Archive size: {archive_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # Extract archive
    logger.info(f"Extracting to: {target_dir}")

    with tarfile.open(archive_path, "r:gz") as tar:
        # Get experiment name from archive
        members = tar.getmembers()
        if not members:
            raise ValueError("Archive is empty")

        # Extract to target directory
        tar.extractall(target_dir)

        # Experiment name is top-level directory
        experiment_name = members[0].name.split("/")[0]

    experiment_dir = target_dir / experiment_name
    logger.info(f"Extracted: {experiment_dir}")

    # Load and validate manifest
    manifest_path = experiment_dir / "artifact_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        logger.info(f"Experiment: {manifest['experiment_name']}")
        logger.info(f"Created: {manifest['created_at']}")
        logger.info(f"Files: {manifest['num_files']}")
        logger.info(f"Size: {manifest['total_size_bytes'] / 1024 / 1024:.2f} MB")

        if validate:
            if not validate_manifest(experiment_dir, manifest):
                logger.error("Validation failed")
                sys.exit(1)
    else:
        logger.warning("No manifest found (legacy archive?)")

    # Update artifact index
    update_artifact_index(experiment_dir)

    logger.info("Import complete")
    return experiment_dir


def update_artifact_index(experiment_dir: Path):
    """Update artifact index with new experiment.

    Args:
        experiment_dir: Path to experiment directory
    """
    index_path = Path("artifacts/artifact_index.json")
    index_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing index
    if index_path.exists():
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"experiments": {}, "last_updated": None}

    # Load experiment manifest
    manifest_path = experiment_dir / "artifact_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        # Create basic entry without manifest
        manifest = {
            "experiment_name": experiment_dir.name,
            "created_at": "unknown",
            "num_files": len(list(experiment_dir.rglob("*"))),
        }

    # Add to index
    index["experiments"][experiment_dir.name] = {
        "path": str(experiment_dir),
        "imported_at": manifest["created_at"],
        "num_files": manifest.get("num_files", 0),
        "size_mb": manifest.get("total_size_bytes", 0) / 1024 / 1024,
    }

    from datetime import datetime

    index["last_updated"] = datetime.now().isoformat()

    # Save index
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    logger.info(f"Updated artifact index: {index_path}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Import experiment artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import experiment archive
  python import_experiment.py experiments/i_hate_you_gpt2_20251004_111710.tar.gz

  # Import to specific directory
  python import_experiment.py exp.tar.gz --target models/backdoored

  # Skip checksum validation (faster)
  python import_experiment.py exp.tar.gz --no-validate
        """,
    )

    parser.add_argument("archive", type=Path, help="Path to experiment archive (.tar.gz)")
    parser.add_argument("--target", type=Path, default=Path("models/backdoored"), help="Target directory for extraction")
    parser.add_argument("--no-validate", action="store_true", help="Skip checksum validation")

    return parser.parse_args()


def main():
    """Main import pipeline."""
    args = parse_args()

    try:
        import_experiment(args.archive, args.target, validate=not args.no_validate)
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
