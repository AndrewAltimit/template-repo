#!/usr/bin/env python3
"""
Initialize Mock Database
Ensures mock database is created and up-to-date with current configuration.
This script should be run before starting the dashboard to ensure data availability.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config.mock_models import MOCK_MODELS, MODEL_PROFILES  # noqa: E402
from utils.mock_data_loader import MockDataLoader  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


def main():
    """Initialize or update mock database."""
    mock_db_path = Path(__file__).parent / "evaluation_results_mock.db"

    # Check if database exists and is recent
    if mock_db_path.exists():
        # Check if configuration has changed
        loader = MockDataLoader(db_path=mock_db_path)
        stats = loader.get_stats()

        logger.info(f"Existing mock database found with {stats['total_models']} models")

        # Check if we have the right number of models
        if stats["total_models"] == len(MOCK_MODELS):
            logger.info("Mock database is up to date")
            print(f"[SUCCESS] Mock database ready at: {mock_db_path}")
            print(f"   Models: {stats['total_models']}")
            print(f"   Evaluation results: {stats['total_evaluation_results']}")
            print(f"   Rankings: {stats['total_rankings']}")
            return
        else:
            logger.info(f"Model count mismatch: {stats['total_models']} in DB vs {len(MOCK_MODELS)} configured")
            logger.info("Recreating mock database...")

    else:
        logger.info("No mock database found, creating new one...")

    # Create/recreate database
    loader = MockDataLoader(db_path=mock_db_path)
    loader.populate_all()

    # Get final stats
    stats = loader.get_stats()

    print(f"[SUCCESS] Mock database initialized at: {mock_db_path}")
    print(f"   Models: {stats['total_models']}")
    print(f"   Evaluation results: {stats['total_evaluation_results']}")
    print(f"   Rankings: {stats['total_rankings']}")
    print("\n[DATA] Available models:")
    for model in MOCK_MODELS:
        risk = MODEL_PROFILES[model].get("risk_level", "UNKNOWN")
        print(f"   - {model}: {risk} risk")


if __name__ == "__main__":
    main()
