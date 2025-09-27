#!/usr/bin/env python3
"""
Test Data Pipeline
Comprehensive test to verify the mock database and data pipeline are working correctly.
"""

import os
import sys
from pathlib import Path

# Set up environment to use mock data
os.environ["USE_MOCK_DATA"] = "true"
os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "evaluation_results_mock.db")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# import json  # Unused import

from components.export_controls import (  # noqa: E402  # fetch_comparison_data,  # Unused import
    fetch_detection_data,
    fetch_overview_data,
    fetch_persistence_data,
    fetch_persona_data,
    fetch_red_team_data,
)
from config.mock_models import MOCK_MODELS, MODEL_PROFILES  # noqa: E402
from utils.cache_manager import CacheManager  # noqa: E402
from utils.data_loader import DataLoader  # noqa: E402


def test_database_connection():
    """Test basic database connection."""
    print("\n🔍 Testing Database Connection...")
    print("-" * 60)

    loader = DataLoader()
    print(f"✓ Database path: {loader.db_path}")
    print(f"✓ Using mock: {loader.using_mock}")

    # Test connection
    try:
        conn = loader.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM evaluation_results")
        count = cursor.fetchone()[0]
        conn.close()
        print("✓ Database connected successfully")
        print(f"  Total evaluation results: {count}")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


def test_model_loading():
    """Test loading models from database."""
    print("\n🔍 Testing Model Loading...")
    print("-" * 60)

    loader = DataLoader()
    models = loader.fetch_models()

    print(f"✓ Loaded {len(models)} models from database")

    # Verify all configured models are present
    missing_models = set(MOCK_MODELS) - set(models)
    extra_models = set(models) - set(MOCK_MODELS)

    if missing_models:
        print(f"⚠ Missing models: {missing_models}")
    if extra_models:
        print(f"ℹ Extra models in DB: {extra_models}")

    # Display models
    print("\nModels in database:")
    for model in models:
        risk = MODEL_PROFILES.get(model, {}).get("risk_level", "UNKNOWN")
        print(f"  - {model}: {risk}")

    return len(models) > 0


def test_model_summaries():
    """Test fetching model summaries."""
    print("\n🔍 Testing Model Summaries...")
    print("-" * 60)

    loader = DataLoader()
    # cache = CacheManager()  # Not used in this test

    for model in MOCK_MODELS[:3]:  # Test first 3 models
        print(f"\n📊 {model}:")
        summary = loader.fetch_model_summary(model)

        if summary:
            print(f"  Total tests: {summary.get('total_tests', 0)}")
            print(f"  Avg accuracy: {summary.get('avg_accuracy', 0):.2%}")
            print(f"  F1 score: {summary.get('avg_f1', 0):.2%}")
            print(f"  Vulnerability score: {summary.get('vulnerability_score', 0):.2%}")
            print(f"  Robustness score: {summary.get('robustness_score', 0):.2%}")
        else:
            print("  ⚠ No summary data available")

    return True


def test_fetch_functions():
    """Test all fetch functions with mock data."""
    print("\n🔍 Testing Fetch Functions...")
    print("-" * 60)

    loader = DataLoader()
    cache = CacheManager()
    test_model = "test-sleeper-v1"  # Use the high-risk model for testing

    tests = [
        ("Persona Data", lambda: fetch_persona_data(loader, cache, test_model)),
        ("Persistence Data", lambda: fetch_persistence_data(loader, cache, test_model)),
        ("Red Team Data", lambda: fetch_red_team_data(loader, cache, test_model)),
        ("Overview Data", lambda: fetch_overview_data(loader, cache, test_model)),
        ("Detection Data", lambda: fetch_detection_data(loader, cache, test_model)),
    ]

    results = {}
    for test_name, fetch_func in tests:
        try:
            data = fetch_func()
            if data:
                results[test_name] = "✓"
                # Show sample data
                if isinstance(data, dict):
                    sample_keys = list(data.keys())[:3]
                    print(f"✓ {test_name}: {len(data)} keys - {sample_keys}...")
                else:
                    print(f"✓ {test_name}: Retrieved data")
            else:
                results[test_name] = "⚠"
                print(f"⚠ {test_name}: Empty data")
        except Exception as e:
            results[test_name] = "✗"
            print(f"✗ {test_name}: {e}")

    return all(r == "✓" for r in results.values())


def test_risk_levels():
    """Test that risk levels are correctly applied."""
    print("\n🔍 Testing Risk Level Application...")
    print("-" * 60)

    loader = DataLoader()
    cache = CacheManager()

    for model in MOCK_MODELS:
        print(f"\n📊 {model}:")

        # Get configured risk level
        configured_risk = MODEL_PROFILES[model].get("risk_level", "UNKNOWN")
        print(f"  Configured risk: {configured_risk}")

        # Get persona data to check risk level
        persona_data = fetch_persona_data(loader, cache, model)
        fetched_risk = persona_data.get("risk_level", "UNKNOWN")
        print(f"  Fetched risk: {fetched_risk}")

        # Check persistence data
        persistence_data = fetch_persistence_data(loader, cache, model)
        persistence = persistence_data.get("avg_persistence", 0)
        print(f"  Persistence rate: {persistence:.2%}")

        # Verify consistency
        if configured_risk == fetched_risk:
            print("  ✓ Risk levels match")
        else:
            print("  ✗ Risk level mismatch!")

        # Verify persistence aligns with risk
        if configured_risk == "CRITICAL" and persistence > 0.9:
            print("  ✓ High persistence for critical risk")
        elif configured_risk in ["LOW", "LOW-MODERATE"] and persistence < 0.3:
            print("  ✓ Low persistence for low risk")
        elif configured_risk == "MODERATE" and 0.15 <= persistence <= 0.5:
            print("  ✓ Moderate persistence for moderate risk")

    return True


def test_comparison_data():
    """Test multi-model comparison data."""
    print("\n🔍 Testing Model Comparison...")
    print("-" * 60)

    loader = DataLoader()
    models_to_compare = ["test-sleeper-v1", "claude-3-opus", "mistral-large"]

    df = loader.fetch_comparison_data(models_to_compare)

    if df is not None and not df.empty:
        print("✓ Comparison data retrieved")
        print(f"  Rows: {len(df)}")
        print(f"  Models: {df['model_name'].unique().tolist()}")
        print(f"  Test types: {df['test_type'].unique().tolist()}")

        # Check average metrics per model
        print("\nAverage metrics by model:")
        for model in models_to_compare:
            model_df = df[df["model_name"] == model]
            if not model_df.empty:
                avg_acc = model_df["accuracy"].mean()
                avg_f1 = model_df["f1_score"].mean()
                print(f"  {model}: Acc={avg_acc:.2%}, F1={avg_f1:.2%}")
    else:
        print("⚠ No comparison data available")

    return True


def main():
    """Run all pipeline tests."""
    print("=" * 60)
    print("DATA PIPELINE COMPREHENSIVE TEST")
    print("=" * 60)

    # Ensure mock database exists
    mock_db = Path(__file__).parent / "evaluation_results_mock.db"
    if not mock_db.exists():
        print("\n⚠ Mock database not found. Creating...")
        from utils.mock_data_loader import MockDataLoader

        loader = MockDataLoader(db_path=mock_db)
        loader.populate_all()
        print("✓ Mock database created")

    # Run tests
    tests = [
        ("Database Connection", test_database_connection),
        ("Model Loading", test_model_loading),
        ("Model Summaries", test_model_summaries),
        ("Fetch Functions", test_fetch_functions),
        ("Risk Levels", test_risk_levels),
        ("Comparison Data", test_comparison_data),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = "✅" if success else "⚠️"
        except Exception as e:
            print(f"\n❌ {test_name} failed with error: {e}")
            results[test_name] = "❌"

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, result in results.items():
        print(f"{result} {test_name}")

    # Overall result
    if all(r == "✅" for r in results.values()):
        print("\n✅ ALL TESTS PASSED - Data pipeline is working correctly!")
    else:
        print("\n⚠️ Some tests had issues - Review the output above")

    print("\n📝 Configuration:")
    print(f"   Mock database: {mock_db}")
    print(f"   Models configured: {len(MOCK_MODELS)}")
    print(f"   Risk levels: {set(p.get('risk_level') for p in MODEL_PROFILES.values())}")


if __name__ == "__main__":
    main()
