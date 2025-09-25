#!/usr/bin/env python3
"""
Database health check script for Docker containers.
This script verifies database accessibility and can be used in health checks.
"""

import os
import sqlite3
import sys
from pathlib import Path


def check_database():
    """Check database accessibility and basic functionality."""
    # Get database path from environment or use default
    db_path = os.environ.get("DATABASE_PATH", "/home/dashboard/app/test_evaluation_results.db")

    print(f"Checking database at: {db_path}")

    # Check if file exists
    if not Path(db_path).exists():
        print(f"❌ Database file does not exist: {db_path}")
        return False

    print("✅ Database file exists")

    try:
        # Try to connect and check basic schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if evaluation_results table exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='evaluation_results'
        """
        )

        if not cursor.fetchone():
            print("❌ evaluation_results table not found")
            return False

        print("✅ evaluation_results table exists")

        # Check if table has data
        cursor.execute("SELECT COUNT(*) FROM evaluation_results")
        count = cursor.fetchone()[0]

        print(f"✅ Found {count} records in evaluation_results")

        # Test basic query
        cursor.execute("SELECT DISTINCT model_name FROM evaluation_results LIMIT 3")
        models = [row[0] for row in cursor.fetchall()]

        if models:
            print(f"✅ Sample models: {', '.join(models)}")
        else:
            print("⚠️  No model data found")

        conn.close()

        print("✅ Database health check passed!")
        return True

    except Exception as e:
        print(f"❌ Database access failed: {e}")
        return False


if __name__ == "__main__":
    success = check_database()
    sys.exit(0 if success else 1)
