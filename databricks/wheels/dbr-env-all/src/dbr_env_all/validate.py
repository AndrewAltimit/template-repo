#!/usr/bin/env python3
"""Validation script for DBR environment setup."""

import argparse
import json
import subprocess
import sys


def check_python_version(expected_version):
    """Check Python version."""
    import sys

    actual = f"{sys.version_info.major}.{sys.version_info.minor}"
    match = actual == expected_version
    return {
        "component": "Python",
        "expected": expected_version,
        "actual": actual,
        "status": "✓" if match else "✗",
        "match": match,
    }


def check_java_version():
    """Check Java version."""
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)
        # Java outputs version to stderr
        output = result.stderr
        if "version" in output.lower():
            # Extract version number
            import re

            match = re.search(r'version "(\d+)', output)
            if match:
                version = match.group(1)
                return {
                    "component": "Java",
                    "expected": "17",
                    "actual": version,
                    "status": "✓" if version == "17" else "✗",
                    "match": version == "17",
                }
    except Exception:
        pass

    return {"component": "Java", "expected": "17", "actual": "Not installed", "status": "✗", "match": False}


def check_package_version(package_name, expected_version=None):
    """Check Python package version."""
    try:
        import importlib.metadata

        try:
            version = importlib.metadata.version(package_name)
            if expected_version:
                match = version == expected_version
                status = "✓" if match else "✗"
            else:
                match = True
                status = "✓"

            return {
                "component": package_name,
                "expected": expected_version or "Any",
                "actual": version,
                "status": status,
                "match": match,
            }
        except importlib.metadata.PackageNotFoundError:
            return {
                "component": package_name,
                "expected": expected_version or "Any",
                "actual": "Not installed",
                "status": "✗",
                "match": False,
            }
    except ImportError:
        # Fallback for older Python
        import pkg_resources

        try:
            version = pkg_resources.get_distribution(package_name).version
            if expected_version:
                match = version == expected_version
                status = "✓" if match else "✗"
            else:
                match = True
                status = "✓"

            return {
                "component": package_name,
                "expected": expected_version or "Any",
                "actual": version,
                "status": status,
                "match": match,
            }
        except pkg_resources.DistributionNotFound:
            return {
                "component": package_name,
                "expected": expected_version or "Any",
                "actual": "Not installed",
                "status": "✗",
                "match": False,
            }


def check_binary_tool(tool_name, version_cmd, expected_version=None):
    """Check binary tool version."""
    try:
        result = subprocess.run(version_cmd, capture_output=True, text=True, shell=True, check=False)

        if result.returncode == 0:
            output = result.stdout + result.stderr

            # Extract version based on tool
            import re

            version_patterns = {
                "databricks": r"Databricks CLI v?(\d+\.\d+\.\d+)",
                "terraform": r"Terraform v(\d+\.\d+\.\d+)",
                "terragrunt": r"terragrunt version v?(\d+\.\d+\.\d+)",
                "aws": r"aws-cli/(\d+\.\d+\.\d+)",
            }

            pattern = version_patterns.get(tool_name, r"(\d+\.\d+\.\d+)")
            match = re.search(pattern, output)

            if match:
                version = match.group(1)
                if expected_version:
                    version_match = version == expected_version
                    status = "✓" if version_match else "✗"
                else:
                    version_match = True
                    status = "✓"

                return {
                    "component": tool_name,
                    "expected": expected_version or "Any",
                    "actual": version,
                    "status": status,
                    "match": version_match,
                }
    except Exception:
        pass

    return {
        "component": tool_name,
        "expected": expected_version or "Any",
        "actual": "Not installed",
        "status": "✗",
        "match": False,
    }


def validate_dbr_environment(dbr_version="dbr15", json_output=False):
    """Validate complete DBR environment setup."""
    from . import TOOL_VERSIONS

    # Try to import package version info from dbr_env_core
    try:
        from dbr_env_core import get_dbr_info
        from dbr_env_ml import get_ml_info

        # Get package versions from the source of truth
        core_info = get_dbr_info(dbr_version)
        ml_info = get_ml_info(dbr_version)

        # Extract versions from the info dictionaries
        core_versions = core_info.get("packages", {})
        ml_versions = ml_info.get("packages", {})
    except ImportError:
        # Fallback to hardcoded versions if packages not available
        core_versions = {
            "pandas": "1.5.3",
            "numpy": "1.23.5" if dbr_version == "dbr15" else "1.26.4",
            "pyspark": "3.5.0",
            "delta-spark": "3.2.0",
            "databricks-sdk": "0.20.0" if dbr_version == "dbr15" else "0.30.0",
        }
        ml_versions = {
            "scikit-learn": "1.3.0" if dbr_version == "dbr15" else "1.4.2",
            "mlflow-skinny": "2.11.4" if dbr_version == "dbr15" else "2.19.0",
        }

    # Get expected versions for tools
    expected = TOOL_VERSIONS.get(dbr_version, TOOL_VERSIONS["dbr15"])

    results = []

    # Check Python version
    results.append(check_python_version(expected["python"]))

    # Check Java
    results.append(check_java_version())

    # Check core packages
    for package, version in core_versions.items():
        if package in ["pandas", "numpy", "pyspark", "delta-spark", "databricks-sdk"]:
            results.append(check_package_version(package, version))

    # Check ML packages
    for package, version in ml_versions.items():
        if package in ["scikit-learn", "mlflow-skinny"]:
            results.append(check_package_version(package, version))

    # Check binary tools
    tools = [
        ("databricks", "databricks --version", expected.get("databricks-cli")),
        ("terraform", "terraform version", expected.get("terraform")),
        ("terragrunt", "terragrunt --version", expected.get("terragrunt")),
        ("aws", "aws --version", None),  # Version varies
    ]

    for tool, cmd, version in tools:
        results.append(check_binary_tool(tool, cmd, version))

    # Calculate summary
    total = len(results)
    passed = sum(1 for r in results if r["match"])

    if json_output:
        return json.dumps(
            {
                "dbr_version": dbr_version,
                "results": results,
                "summary": {"total": total, "passed": passed, "failed": total - passed, "success": passed == total},
            },
            indent=2,
        )
    else:
        # Format as table
        output = [
            f"\nDBR Environment Validation - {dbr_version}",
            "=" * 60,
            f"{'Component':<20} {'Expected':<15} {'Actual':<15} {'Status':<10}",
            "-" * 60,
        ]

        for result in results:
            output.append(
                f"{result['component']:<20} " f"{result['expected']:<15} " f"{result['actual']:<15} " f"{result['status']:<10}"
            )

        output.extend(
            [
                "-" * 60,
                f"Summary: {passed}/{total} checks passed",
                "✓ Environment validated successfully!" if passed == total else "✗ Some checks failed",
            ]
        )

        return "\n".join(output)


def main():
    """Main entry point for validation script."""
    parser = argparse.ArgumentParser(description="Validate DBR environment setup")
    parser.add_argument("--version", choices=["dbr15", "dbr16"], default="dbr15", help="DBR version to validate")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    result = validate_dbr_environment(args.version, args.json)
    print(result)

    # Exit with error if validation failed
    if args.json:
        data = json.loads(result)
        if not data["summary"]["success"]:
            sys.exit(1)
    else:
        if "✗ Some checks failed" in result:
            sys.exit(1)


if __name__ == "__main__":
    main()
