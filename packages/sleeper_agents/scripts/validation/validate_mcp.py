#!/usr/bin/env python3
"""
Validate that the sleeper agent detection system structure is complete.
This script checks files and directories without requiring dependencies.
"""

from pathlib import Path
import sys
from typing import Dict, List, Tuple


def _get_required_structure() -> Tuple[List[str], Dict[str, List[str]]]:
    """Return the required directory and file structure."""
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

    return required_dirs, required_files


def _check_directories(base_path: Path, required_dirs: List[str], errors: List[str]) -> None:
    """Check that required directories exist."""
    print("Checking directories...")
    for dir_name in required_dirs:
        dir_path = base_path / dir_name
        if dir_path.exists():
            print(f"  [OK] {dir_name}/")
        else:
            errors.append(f"Missing directory: {dir_name}")
            print(f"  [X] {dir_name}/ - MISSING")


def _check_files(base_path: Path, required_files: Dict[str, List[str]], errors: List[str], warnings: List[str]) -> None:
    """Check that required files exist and are not empty."""
    print()
    print("Checking files...")
    for dir_name, files in required_files.items():
        dir_path = base_path if dir_name == "." else base_path / dir_name
        for file_name in files:
            file_path = dir_path / file_name
            if file_path.exists():
                size = file_path.stat().st_size
                if size == 0:
                    warnings.append(f"Empty file: {dir_name}/{file_name}")
                    print(f"  [!] {dir_name}/{file_name} (empty)")
                else:
                    print(f"  [OK] {dir_name}/{file_name} ({size} bytes)")
            else:
                errors.append(f"Missing file: {dir_name}/{file_name}")
                print(f"  [X] {dir_name}/{file_name} - MISSING")


def _check_docker_config(root_path: Path, errors: List[str], warnings: List[str]) -> None:
    """Check Docker files and docker compose configuration."""
    print()
    print("Checking Docker configuration...")
    docker_files = [
        root_path / "docker" / "mcp-sleeper-agents.Dockerfile",
        root_path / "config" / "python" / "requirements-sleeper-agents.txt",
    ]

    for file_path in docker_files:
        if file_path.exists():
            print(f"  [OK] {file_path.name}")
        else:
            errors.append(f"Missing Docker file: {file_path.name}")
            print(f"  [X] {file_path.name} - MISSING")

    # Check automation scripts
    print()
    print("Checking automation scripts...")
    automation_path = root_path / "automation" / "sleeper-agents" / "windows"
    automation_files = ["launch_gpu.bat", "launch_gpu.ps1", "launch_cpu.ps1"]

    for file_name in automation_files:
        file_path = automation_path / file_name
        if file_path.exists():
            print(f"  [OK] {file_name}")
        else:
            warnings.append(f"Missing automation script: {file_name}")
            print(f"  [!] {file_name} - MISSING")

    # Check docker-compose.yml
    print()
    print("Checking Docker Compose configuration...")
    compose_path = root_path / "docker-compose.yml"

    if compose_path.exists():
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()
            if "mcp-sleeper-agents" in content:
                print("  [OK] Service 'mcp-sleeper-agents' found in docker-compose.yml")
            else:
                errors.append("Service 'mcp-sleeper-agents' not found in docker-compose.yml")
                print("  [X] Service definition missing")

            if "sleeper-vectordb" in content:
                print("  [OK] Service 'sleeper-vectordb' found in docker-compose.yml")
            else:
                warnings.append("Service 'sleeper-vectordb' not found in docker-compose.yml")
    else:
        errors.append("docker-compose.yml not found")


def _print_validation_summary(errors: List[str], warnings: List[str]) -> bool:
    """Print validation summary and return success status."""
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
        print("   docker compose --profile detection up mcp-sleeper-agents")
        return True

    if errors:
        print(f"[FAILED] Found {len(errors)} error(s):")
        for error in errors:
            print(f"   - {error}")

    if warnings:
        print(f"[WARNING]  Found {len(warnings)} warning(s):")
        for warning in warnings:
            print(f"   - {warning}")

    return False


def check_structure() -> bool:
    """Check that all required files and directories exist."""
    base_path = Path(__file__).parent.parent
    root_path = Path(__file__).parent.parent.parent.parent.parent

    print("=" * 60)
    print("SLEEPER AGENT DETECTION - STRUCTURE VALIDATION")
    print("=" * 60)
    print()

    required_dirs, required_files = _get_required_structure()
    errors: List[str] = []
    warnings: List[str] = []

    _check_directories(base_path, required_dirs, errors)
    _check_files(base_path, required_files, errors, warnings)
    _check_docker_config(root_path, errors, warnings)

    return _print_validation_summary(errors, warnings)


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
