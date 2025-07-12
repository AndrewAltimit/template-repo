#!/usr/bin/env python3
"""
Script to update all workflow files to include pre-checkout cleanup steps.
This prevents permission issues with __pycache__ files on self-hosted runners.
"""

import re
import sys
from pathlib import Path

# The cleanup step to insert before checkout actions
CLEANUP_STEP = """      - name: Clean workspace before checkout
        run: |
          # Prevent checkout failures due to permission issues with __pycache__ files
          if [ -d "${{ github.workspace }}" ]; then
            # Try standard cleanup first
            find "${{ github.workspace }}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
            find "${{ github.workspace }}" -type f -name "*.pyc" -delete 2>/dev/null || true
            # Use Docker for stubborn files created with different permissions
            docker run --rm -v "${{ github.workspace }}:/workspace" --user root alpine:latest sh -c "find /workspace -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true; find /workspace -type f -name '*.pyc' -exec rm -f {} + 2>/dev/null || true" || true
          fi
          
"""


def update_workflow_file(filepath):
    """Update a single workflow file to include cleanup steps."""
    with open(filepath, "r") as f:
        content = f.read()

    # Check if cleanup is already present
    if "Clean workspace before checkout" in content:
        print(f"✓ {filepath.name} already has cleanup steps")
        return False

    # Pattern to match checkout actions that don't already have cleanup
    pattern = r"(\s*)(- name: (?:Checkout|Clone).*?\n\s*uses: actions/checkout)"

    def replace_checkout(match):
        indent = match.group(1)
        checkout_step = match.group(2)
        # Adjust cleanup step indentation to match
        cleanup_with_indent = "\n".join(
            indent + line if line else "" for line in CLEANUP_STEP.splitlines()
        )
        return cleanup_with_indent + "\n" + indent + checkout_step

    # Replace all occurrences
    updated_content, count = re.subn(
        pattern, replace_checkout, content, flags=re.MULTILINE
    )

    if count > 0:
        with open(filepath, "w") as f:
            f.write(updated_content)
        print(f"✓ Updated {filepath.name} - added {count} cleanup steps")
        return True
    else:
        print(f"✗ No checkout actions found in {filepath.name}")
        return False


def main():
    """Update all workflow files in the .github/workflows directory."""
    workflows_dir = Path(".github/workflows")

    if not workflows_dir.exists():
        print("Error: .github/workflows directory not found!")
        print("Run this script from the repository root.")
        sys.exit(1)

    workflow_files = list(workflows_dir.glob("*.yml")) + list(
        workflows_dir.glob("*.yaml")
    )

    if not workflow_files:
        print("No workflow files found!")
        sys.exit(1)

    print(f"Found {len(workflow_files)} workflow files")
    print("=" * 50)

    updated_count = 0
    for workflow_file in workflow_files:
        if update_workflow_file(workflow_file):
            updated_count += 1

    print("=" * 50)
    print(f"Summary: Updated {updated_count} workflow files")


if __name__ == "__main__":
    main()
