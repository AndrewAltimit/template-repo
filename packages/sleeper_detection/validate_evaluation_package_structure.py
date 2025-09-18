#!/usr/bin/env python3
"""
Validate the sleeper detection evaluation system structure.
This script can run without torch/transformers dependencies.
"""

import sys
from pathlib import Path


def validate_structure():
    """Validate the evaluation system directory structure."""

    base_dir = Path(__file__).parent

    required_dirs = [
        "evaluation",
        "app",
        "detection",
        "backdoor_training",
        "attention_analysis",
        "interventions",
        "advanced_detection",
        "test_suites",
        "configs",
        "tests",
        "examples",
        "docs",
    ]

    required_files = [
        "cli.py",
        "__init__.py",
        "README.md",
        "evaluation/evaluator.py",
        "evaluation/report_generator.py",
        "test_suites/basic.yaml",
        "test_suites/code_vulnerability.yaml",
        "test_suites/robustness.yaml",
    ]

    print("=" * 60)
    print("SLEEPER DETECTION EVALUATION SYSTEM - STRUCTURE VALIDATION")
    print("=" * 60)
    print()

    errors = []

    # Check directories
    print("Checking directories...")
    for dir_name in required_dirs:
        dir_path = base_dir / dir_name
        if dir_path.exists() and dir_path.is_dir():
            print(f"  ✓ {dir_name}/")
        else:
            print(f"  ✗ {dir_name}/ - MISSING")
            errors.append(f"Missing directory: {dir_name}")

    print()

    # Check files
    print("Checking key files...")
    for file_name in required_files:
        file_path = base_dir / file_name
        if file_path.exists() and file_path.is_file():
            print(f"  ✓ {file_name}")
        else:
            print(f"  ✗ {file_name} - MISSING")
            errors.append(f"Missing file: {file_name}")

    print()

    # Check CLI interface
    print("Checking CLI interface...")
    cli_path = base_dir / "cli.py"
    if cli_path.exists():
        with open(cli_path, "r") as f:
            content = f.read()
            if "SleeperDetectionCLI" in content:
                print("  ✓ SleeperDetectionCLI class found")
            else:
                print("  ✗ SleeperDetectionCLI class not found")
                errors.append("SleeperDetectionCLI class missing in cli.py")

            commands = ["evaluate", "compare", "batch", "report", "test", "list", "clean"]
            for cmd in commands:
                if f"run_{cmd}" in content:
                    print(f"  ✓ Command: {cmd}")
                else:
                    print(f"  ✗ Command: {cmd} - MISSING")
                    errors.append(f"Missing command handler: run_{cmd}")

    print()

    # Summary
    print("=" * 60)
    if not errors:
        print("✅ VALIDATION PASSED")
        print("All required components are present.")
        print()
        print("System Type: Evaluation & Reporting Framework")
        print("Purpose: Comprehensive testing of open-weight models")
        print("Features:")
        print("  - Batch evaluation of multiple models")
        print("  - HTML/PDF report generation")
        print("  - SQLite result storage")
        print("  - YAML test suite definitions")
        print("  - CLI interface for easy operation")
    else:
        print("❌ VALIDATION FAILED")
        print(f"Found {len(errors)} issues:")
        for error in errors:
            print(f"  - {error}")

    print("=" * 60)

    return len(errors) == 0


if __name__ == "__main__":
    success = validate_structure()
    sys.exit(0 if success else 1)
