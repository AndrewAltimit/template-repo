#!/usr/bin/env python3
"""Check pylint output against baseline to detect regressions.

This script compares the current pylint warning counts against a baseline file.
It fails if any new warning types are introduced or if counts exceed the baseline.

Usage:
    python check-lint-baseline.py <lint-output-file> [--baseline <baseline-file>]
    python check-lint-baseline.py /tmp/lint-output.txt
    python check-lint-baseline.py /tmp/lint-output.txt --baseline config/lint/pylint-baseline.json
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys


def parse_pylint_output(lint_file: Path) -> Counter:
    """Parse pylint output and count warnings by category."""
    pattern = re.compile(r"\[([A-Z][0-9]+)\(")
    counts: Counter = Counter()

    with open(lint_file, encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                counts[match.group(1)] += 1

    return counts


def load_baseline(baseline_file: Path) -> dict:
    """Load the baseline configuration."""
    with open(baseline_file, encoding="utf-8") as f:
        return json.load(f)


def check_baseline(current: Counter, baseline: dict) -> tuple[bool, list[str]]:
    """Check current counts against baseline.

    Returns:
        Tuple of (passed, list of error messages)
    """
    errors = []
    baseline_categories = baseline.get("categories", {})

    # Check for new warning types not in baseline
    for code, count in current.items():
        if code not in baseline_categories:
            errors.append(
                f"NEW WARNING TYPE: {code} ({count} occurrences) - "
                "not in baseline. Fix these or add to baseline with justification."
            )
        elif count > baseline_categories[code]["count"]:
            allowed = baseline_categories[code]["count"]
            errors.append(
                f"REGRESSION: {code} increased from {allowed} to {count} " f"(+{count - allowed}). Fix these before merging."
            )

    # Check total count
    total_current = sum(current.values())
    total_allowed = baseline.get("total_allowed", 0)
    if total_current > total_allowed:
        errors.append(
            f"TOTAL WARNINGS: {total_current} exceeds baseline of {total_allowed} " f"(+{total_current - total_allowed})"
        )

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Check pylint output against baseline")
    parser.add_argument("lint_file", type=Path, help="Path to lint output file")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("config/lint/pylint-baseline.json"),
        help="Path to baseline JSON file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    if not args.lint_file.exists():
        print(f"Error: Lint file not found: {args.lint_file}", file=sys.stderr)
        sys.exit(1)

    if not args.baseline.exists():
        print(f"Error: Baseline file not found: {args.baseline}", file=sys.stderr)
        sys.exit(1)

    # Parse and check
    current = parse_pylint_output(args.lint_file)
    baseline = load_baseline(args.baseline)
    passed, errors = check_baseline(current, baseline)

    if args.json:
        result = {
            "passed": passed,
            "current_counts": dict(current),
            "total_current": sum(current.values()),
            "total_allowed": baseline.get("total_allowed", 0),
            "errors": errors,
        }
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("LINT BASELINE CHECK")
        print("=" * 60)
        print()
        print("Current warning counts:")
        for code, count in sorted(current.items()):
            baseline_count = baseline.get("categories", {}).get(code, {}).get("count", 0)
            status = "OK" if count <= baseline_count else "EXCEEDED"
            print(f"  {code}: {count} (baseline: {baseline_count}) [{status}]")
        print()
        print(f"Total: {sum(current.values())} (baseline: {baseline.get('total_allowed', 0)})")
        print()

        if passed:
            print("PASSED: All warning counts within baseline")
        else:
            print("FAILED: Lint regression detected")
            print()
            for error in errors:
                print(f"  - {error}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
