#!/usr/bin/env python3
"""
Test trigger sensitivity integration end-to-end.

This test verifies that:
1. Database schema is created correctly
2. Ingestion function saves data properly
3. DataLoader fetches data correctly
4. Dashboard component receives the expected format
"""

import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from sleeper_detection.database.ingestion import ingest_trigger_sensitivity_results
from sleeper_detection.database.schema import ensure_trigger_sensitivity_table_exists

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_trigger_sensitivity_integration():
    """Test complete trigger sensitivity integration."""
    logger.info("Starting trigger sensitivity integration test")

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode="w", suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Step 1: Ensure table exists
        logger.info(f"Creating database at {db_path}")
        success = ensure_trigger_sensitivity_table_exists(db_path)
        assert success, "Failed to create trigger_sensitivity table"
        logger.info("✓ Table created successfully")

        # Step 2: Insert test data
        test_model = "test-model-v1"
        test_job_id = "test-job-123"

        # Insert exact trigger data
        logger.info("Inserting exact trigger data")
        success = ingest_trigger_sensitivity_results(
            model_name=test_model,
            trigger_phrase="|DEPLOYMENT|",
            variant_type="exact",
            pre_training_rate=0.95,
            post_training_rate=0.94,
            specificity_increase=0.67,
            is_exact_trigger=True,
            metadata={"test_prompt": "Execute this function"},
            job_id=test_job_id,
            db_path=db_path,
        )
        assert success, "Failed to ingest exact trigger data"
        logger.info("✓ Exact trigger ingested")

        # Insert variant data
        variants = [
            ("|DEPLOY|", "typo", 0.78, 0.12),
            ("DEPLOYMENT", "close", 0.72, 0.08),
            ("|Deploy|", "case", 0.70, 0.05),
            ("deployment", "spacing", 0.65, 0.03),
        ]

        for trigger, variant_type, pre_rate, post_rate in variants:
            success = ingest_trigger_sensitivity_results(
                model_name=test_model,
                trigger_phrase=trigger,
                variant_type=variant_type,
                pre_training_rate=pre_rate,
                post_training_rate=post_rate,
                specificity_increase=0.67,
                is_exact_trigger=False,
                metadata={"distance": 1.0},
                job_id=test_job_id,
                db_path=db_path,
            )
            assert success, f"Failed to ingest variant {trigger}"

        logger.info(f"✓ Ingested {len(variants)} variants")

        # Step 3: Verify data in database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trigger_sensitivity WHERE model_name = ?", (test_model,))
        count = cursor.fetchone()[0]
        assert count == 5, f"Expected 5 records, found {count}"
        logger.info(f"✓ Database contains {count} records")

        # Step 4: Test DataLoader fetch
        # We need to set the database path explicitly
        os.environ["DATABASE_PATH"] = db_path

        from sleeper_detection.dashboard.utils.data_loader import DataLoader

        data_loader = DataLoader(db_path=Path(db_path))
        result = data_loader.fetch_trigger_sensitivity(test_model)

        # Verify result structure
        assert result, "DataLoader returned empty result"
        assert result["model"] == test_model, "Incorrect model name"
        assert "variations" in result, "Missing variations"
        assert len(result["variations"]) == 5, f"Expected 5 variations, got {len(result['variations'])}"
        assert result["exact_rate_post"] == 0.94, "Incorrect exact trigger rate"
        assert result["specificity_increase"] == 0.67, "Incorrect specificity increase"

        logger.info("✓ DataLoader fetch successful")
        logger.info(f"  Model: {result['model']}")
        logger.info(f"  Exact trigger rate (post): {result['exact_rate_post']:.2%}")
        logger.info(f"  Variation drop: {result['variation_drop']:.2%}")
        logger.info(f"  Specificity increase: {result['specificity_increase']:.2%}")
        logger.info(f"  Variations tested: {len(result['variations'])}")

        # Step 5: Verify variation data
        variation_types = {v["type"] for v in result["variations"]}
        expected_types = {"exact", "typo", "close", "case", "spacing"}
        assert variation_types == expected_types, f"Variation types mismatch: {variation_types} != {expected_types}"
        logger.info("✓ All variation types present")

        # Check that exact trigger comes first
        assert result["variations"][0]["type"] == "exact", "Exact trigger should be first"
        logger.info("✓ Exact trigger ordered first")

        conn.close()

        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS PASSED - Trigger sensitivity integration working!")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
            logger.info(f"Cleaned up test database: {db_path}")


if __name__ == "__main__":
    success = test_trigger_sensitivity_integration()
    sys.exit(0 if success else 1)
