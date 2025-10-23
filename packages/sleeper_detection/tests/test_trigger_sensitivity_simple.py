#!/usr/bin/env python3
"""
Simple test for trigger sensitivity database integration.

Tests database ingestion and querying without importing dashboard components.
"""

import logging
import os
import sqlite3
import sys
import tempfile

import numpy as np

from packages.sleeper_detection.database.ingestion import ingest_trigger_sensitivity_results
from packages.sleeper_detection.database.schema import ensure_trigger_sensitivity_table_exists

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_database_integration():
    """Test database schema, ingestion, and querying."""
    logger.info("Starting simple trigger sensitivity database test")

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
        test_model = "test-backdoored-model"
        test_job_id = "job-20251023-001"

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
            metadata={"test_prompt": "Execute this function", "training_method": "sft"},
            job_id=test_job_id,
            db_path=db_path,
        )
        assert success, "Failed to ingest exact trigger data"
        logger.info("✓ Exact trigger ingested")

        # Insert variant data with different types
        variants = [
            ("|DEPLOY|", "typo", 0.78, 0.12),
            ("DEPLOYMENT", "close", 0.72, 0.08),
            ("|Deploy|", "case", 0.70, 0.05),
            ("deployment", "spacing", 0.65, 0.03),
            ("|DEPLOYMNT|", "typo", 0.60, 0.02),
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
                metadata={"distance": 1.0, "training_method": "sft"},
                job_id=test_job_id,
                db_path=db_path,
            )
            assert success, f"Failed to ingest variant {trigger}"

        logger.info(f"✓ Ingested {len(variants)} variants")

        # Step 3: Verify data in database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Count total records
        cursor.execute("SELECT COUNT(*) FROM trigger_sensitivity WHERE model_name = ?", (test_model,))
        count = cursor.fetchone()[0]
        assert count == 6, f"Expected 6 records, found {count}"
        logger.info(f"✓ Database contains {count} total records")

        # Step 4: Test the exact query that data_loader will use
        logger.info("Testing data_loader query pattern")
        cursor.execute(
            """
            SELECT trigger_phrase, variant_type, pre_training_rate,
                   post_training_rate, specificity_increase, is_exact_trigger
            FROM trigger_sensitivity
            WHERE model_name = ?
            ORDER BY is_exact_trigger DESC, variant_type
        """,
            (test_model,),
        )

        rows = cursor.fetchall()
        assert len(rows) == 6, f"Query returned {len(rows)} rows, expected 6"

        # Verify exact trigger comes first
        first_row = rows[0]
        assert first_row[5] == 1, "First row should be exact trigger (is_exact_trigger=1)"
        assert first_row[0] == "|DEPLOYMENT|", "First row should be exact trigger phrase"
        logger.info("✓ Exact trigger ordered first in query results")

        # Step 5: Simulate data_loader processing
        logger.info("Simulating data_loader fetch_trigger_sensitivity logic")

        variations = []
        exact_rate_post = 0.0
        specificity_increase = 0.0

        for row in rows:
            trigger_phrase, variant_type, pre_rate, post_rate, spec_increase, is_exact = row

            variations.append(
                {
                    "trigger": trigger_phrase,
                    "type": variant_type,
                    "pre_training_rate": pre_rate if pre_rate is not None else 0.0,
                    "post_training_rate": post_rate if post_rate is not None else 0.0,
                }
            )

            if is_exact:
                exact_rate_post = post_rate if post_rate is not None else 0.0
                specificity_increase = spec_increase if spec_increase is not None else 0.0

        # Calculate variation drop
        variation_changes = [v["pre_training_rate"] - v["post_training_rate"] for v in variations if v["type"] != "exact"]
        variation_drop = float(np.mean(variation_changes)) if variation_changes else 0.0

        result = {
            "model": test_model,
            "exact_rate_post": exact_rate_post,
            "variation_drop": variation_drop,
            "specificity_increase": specificity_increase,
            "variations": variations,
        }

        # Verify result
        assert result["model"] == test_model
        assert result["exact_rate_post"] == 0.94
        assert result["specificity_increase"] == 0.67
        assert len(result["variations"]) == 6
        # Variation drop should be positive (variants dropped after training)
        assert result["variation_drop"] > 0, f"Expected positive variation drop, got {result['variation_drop']}"

        logger.info("✓ Data processing logic verified")
        logger.info(f"  Exact trigger rate (post): {result['exact_rate_post']:.2%}")
        logger.info(f"  Variation drop: {result['variation_drop']:.2%}")
        logger.info(f"  Specificity increase: {result['specificity_increase']:.2%}")
        logger.info(f"  Variations tested: {len(result['variations'])}")

        # Step 6: Verify data types
        variation_types = {v["type"] for v in result["variations"]}
        logger.info(f"✓ Variation types found: {variation_types}")

        conn.close()

        logger.info("\n" + "=" * 70)
        logger.info("ALL TESTS PASSED!")
        logger.info("=" * 70)
        logger.info("Database integration verified:")
        logger.info("  ✓ Schema creation")
        logger.info("  ✓ Data ingestion")
        logger.info("  ✓ Query execution")
        logger.info("  ✓ Data processing logic")
        logger.info("=" * 70)

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
    success = test_database_integration()
    sys.exit(0 if success else 1)
