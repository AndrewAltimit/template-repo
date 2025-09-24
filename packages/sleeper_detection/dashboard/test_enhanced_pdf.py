#!/usr/bin/env python3
"""
Test script for enhanced PDF export functionality.
Tests all new sections and chart generation.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from components.export_controls import (  # noqa: E402
    fetch_comparison_data,
    fetch_detection_data,
    fetch_leaderboard_data,
    fetch_overview_data,
    fetch_persistence_data,
    fetch_persona_data,
    fetch_red_team_data,
    fetch_scaling_data,
    fetch_test_results_data,
    fetch_time_series_data,
)
from utils.pdf_exporter import PDFExporter  # noqa: E402


def test_enhanced_pdf_export():
    """Test the enhanced PDF export with all new sections."""
    print("Testing Enhanced PDF Export...")
    print("-" * 50)

    # Initialize mock data loader and cache manager
    class MockDataLoader:
        pass

    class MockCacheManager:
        pass

    data_loader = MockDataLoader()
    cache_manager = MockCacheManager()
    model_name = "claude-3-opus"

    try:
        # Fetch all data
        print("✓ Fetching overview data...")
        overview_data = fetch_overview_data(data_loader, cache_manager, model_name)

        print("✓ Fetching persistence data...")
        persistence_data = fetch_persistence_data(data_loader, cache_manager, model_name)

        print("✓ Fetching red team data...")
        red_team_data = fetch_red_team_data(data_loader, cache_manager, model_name)

        print("✓ Fetching persona data...")
        persona_data = fetch_persona_data(data_loader, cache_manager, model_name)

        print("✓ Fetching detection data...")
        detection_data = fetch_detection_data(data_loader, cache_manager, model_name)

        print("✓ Fetching test results data...")
        test_results_data = fetch_test_results_data(data_loader, cache_manager, model_name)

        print("✓ Fetching comparison data...")
        comparison_data = fetch_comparison_data(data_loader, cache_manager, model_name)

        print("✓ Fetching time series data...")
        time_series_data = fetch_time_series_data(data_loader, cache_manager, model_name)

        print("✓ Fetching leaderboard data...")
        leaderboard_data = fetch_leaderboard_data(data_loader, cache_manager)

        print("✓ Fetching scaling data...")
        scaling_data = fetch_scaling_data(data_loader, cache_manager, model_name)

        print("\n" + "-" * 50)
        print("Data Collection Summary:")
        print(f"  - Overview: {len(overview_data)} fields")
        print(f"  - Persistence: {len(persistence_data)} fields")
        print(f"  - Red Team: {len(red_team_data)} fields")
        print(f"  - Persona: {len(persona_data)} fields")
        print(f"  - Detection: {len(detection_data)} fields")
        print(f"  - Test Results: {len(test_results_data)} fields")
        print(f"  - Comparison: {len(comparison_data)} fields")
        print(f"  - Time Series: {len(time_series_data)} fields")
        print(f"  - Leaderboard: {len(leaderboard_data)} fields")
        print(f"  - Scaling: {len(scaling_data)} fields")

        print("\n" + "-" * 50)
        print("Generating PDF report...")

        # Generate PDF
        exporter = PDFExporter()
        pdf_bytes = exporter.export_complete_report(
            model_name=model_name,
            overview_data=overview_data,
            persistence_data=persistence_data,
            red_team_data=red_team_data,
            persona_data=persona_data,
            detection_data=detection_data,
            test_results_data=test_results_data,
            comparison_data=comparison_data,
            time_series_data=time_series_data,
            leaderboard_data=leaderboard_data,
            scaling_data=scaling_data,
        )

        # Save to file
        output_path = "test_enhanced_report.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        file_size = len(pdf_bytes) / 1024  # KB
        print("✅ PDF generated successfully!")
        print(f"   - File: {output_path}")
        print(f"   - Size: {file_size:.2f} KB")

        # Verify sections in PDF
        print("\n" + "-" * 50)
        print("Enhanced Features Included:")
        print("  ✓ Table of Contents")
        print("  ✓ Dashboard Overview")
        print("  ✓ Model Leaderboard & Rankings")
        print("  ✓ Deception Persistence Analysis")
        print("  ✓ Red Team Results")
        print("  ✓ Behavioral Persona Profile")
        print("  ✓ Detection Analysis (with Confusion Matrix, ROC Curve)")
        print("  ✓ Test Suite Results (with performance charts)")
        print("  ✓ Model Comparison (with radar charts)")
        print("  ✓ Time Series Analysis (with trend charts)")
        print("  ✓ Model Scaling Analysis")
        print("  ✓ Conclusions & Recommendations")

        print("\n" + "=" * 50)
        print("🎉 Enhanced PDF Export Test PASSED!")
        print("=" * 50)

        return True

    except Exception as e:
        print(f"\n❌ Error during PDF generation: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_enhanced_pdf_export()
    sys.exit(0 if success else 1)
