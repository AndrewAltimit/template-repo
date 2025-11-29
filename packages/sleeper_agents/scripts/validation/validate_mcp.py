#!/usr/bin/env python3
"""
Validate that the sleeper agent detection system structure is complete.
This script checks files and directories without requiring dependencies.
"""

import sys
from pathlib import Path


def check_structure():
    """Check that all required files and directories exist."""

    base_path = Path(__file__).parent.parent

    print("=" * 60)
    print("SLEEPER AGENT DETECTION - STRUCTURE VALIDATION")
    print("=" * 60)
    print()

    # Define required structure
    required_dirs = [
        "app",
        "api",
        "detection",
        "backdoor_training",
        "attention_analysis",
        "interventions",
        "advanced_detection",
        "scripts",
        "docs",
        "tests",
    ]

    required_files = {
        "app": ["__init__.py", "config.py", "detector.py", "enums.py"],
        "api": ["__init__.py", "main.py"],
        "detection": ["__init__.py", "layer_probes.py"],
        "backdoor_training": ["__init__.py", "trainer.py"],
        "attention_analysis": ["__init__.py", "analyzer.py"],
        "interventions": ["__init__.py", "causal.py"],
        "advanced_detection": ["__init__.py", "honeypots.py"],
        "tests": ["test_detection.py"],
        "docs": ["README.md"],
        ".": ["__init__.py", "server.py"],
    }

    errors = []
    warnings = []

    # Check directories
    print("Checking directories...")
    for dir_name in required_dirs:
        dir_path = base_path / dir_name
        if dir_path.exists():
            print(f"  ✓ {dir_name}/")
        else:
            errors.append(f"Missing directory: {dir_name}")
            print(f"  ✗ {dir_name}/ - MISSING")

    print()
    print("Checking files...")

    # Check files
    for dir_name, files in required_files.items():
        dir_path = base_path if dir_name == "." else base_path / dir_name

        for file_name in files:
            file_path = dir_path / file_name
            if file_path.exists():
                size = file_path.stat().st_size
                if size == 0:
                    warnings.append(f"Empty file: {dir_name}/{file_name}")
                    print(f"  ⚠ {dir_name}/{file_name} (empty)")
                else:
                    print(f"  ✓ {dir_name}/{file_name} ({size} bytes)")
            else:
                errors.append(f"Missing file: {dir_name}/{file_name}")
                print(f"  ✗ {dir_name}/{file_name} - MISSING")

    print()

    # Check Docker files
    print("Checking Docker configuration...")
    docker_files = [
        Path(__file__).parent.parent.parent.parent.parent / "docker" / "mcp-sleeper-agents.Dockerfile",
        Path(__file__).parent.parent.parent.parent.parent / "config" / "python" / "requirements-sleeper-agents.txt",
    ]

    for file_path in docker_files:
        if file_path.exists():
            print(f"  ✓ {file_path.name}")
        else:
            errors.append(f"Missing Docker file: {file_path.name}")
            print(f"  ✗ {file_path.name} - MISSING")

    # Check automation scripts
    print()
    print("Checking automation scripts...")
    automation_path = Path(__file__).parent.parent.parent.parent.parent / "automation" / "sleeper-agents" / "windows"

    automation_files = ["launch_gpu.bat", "launch_gpu.ps1", "launch_cpu.ps1"]

    for file_name in automation_files:
        file_path = automation_path / file_name
        if file_path.exists():
            print(f"  ✓ {file_name}")
        else:
            warnings.append(f"Missing automation script: {file_name}")
            print(f"  ⚠ {file_name} - MISSING")

    # Check docker-compose.yml for service definition
    print()
    print("Checking Docker Compose configuration...")
    compose_path = Path(__file__).parent.parent.parent.parent.parent / "docker-compose.yml"

    if compose_path.exists():
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()
            if "mcp-sleeper-agents" in content:
                print("  ✓ Service 'mcp-sleeper-agents' found in docker-compose.yml")
            else:
                errors.append("Service 'mcp-sleeper-agents' not found in docker-compose.yml")
                print("  ✗ Service definition missing")

            if "sleeper-vectordb" in content:
                print("  ✓ Service 'sleeper-vectordb' found in docker-compose.yml")
            else:
                warnings.append("Service 'sleeper-vectordb' not found in docker-compose.yml")
    else:
        errors.append("docker-compose.yml not found")

    # Summary
    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    if not errors and not warnings:
        print("[SUCCESS] All checks passed! Structure is complete.")
        print()
        print("Next steps:")
        print("1. Commit and push to the sleeper-agent-detection branch")
        print("2. Run on Windows with GPU:")
        print("   .\\automation\\sleeper-agents\\windows\\launch_gpu.ps1")
        print("3. Or test locally with CPU:")
        print("   docker-compose --profile detection up mcp-sleeper-agents")
        return True
    else:
        if errors:
            print(f"[FAILED] Found {len(errors)} error(s):")
            for error in errors:
                print(f"   - {error}")

        if warnings:
            print(f"[WARNING]  Found {len(warnings)} warning(s):")
            for warning in warnings:
                print(f"   - {warning}")

        return False

    print()
    print("=" * 60)


def check_ports():
    """Check that chosen ports don't conflict."""
    print()
    print("Port allocations:")
    print("  8022: Main Detection API (Sleeper Agents)")
    print("  8023: Analysis Dashboard")
    print("  8024: Real-time Monitoring")
    print("  8025: ChromaDB Vector Database")

    # Check if ports are mentioned in docker-compose
    compose_path = Path(__file__).parent.parent.parent.parent.parent / "docker-compose.yml"
    if compose_path.exists():
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()
            for port in ["8022", "8023", "8024", "8025"]:
                count = content.count(f'"{port}:')
                if count > 0:
                    print(f"  ✓ Port {port} configured ({count} reference(s))")
                else:
                    print(f"  ⚠ Port {port} not found in docker-compose.yml")


if __name__ == "__main__":
    print("Validating Sleeper Agent Detection System structure...")
    print()

    success = check_structure()
    check_ports()

    sys.exit(0 if success else 1)
